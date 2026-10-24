#!/usr/bin/env python3
"""Rebuild a released source ZIP in a fresh directory and Python environment.

This exercises the documented Linux toolchain; it does not install system
packages or claim a new operating-system/container installation. Proxy and CA
settings are inherited. No existing checkout, build tree or font cache is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import time
import zipfile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_sources(archive_path: Path, destination: Path) -> dict[str, str]:
    """Extract only ordinary source members, rejecting traversal and duplicates."""
    members: dict[str, str] = {}
    with zipfile.ZipFile(archive_path) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC check failed: {bad}")
        sources = [item for item in archive.infolist()
                   if item.filename.startswith("source/") and not item.is_dir()]
        if not sources:
            raise RuntimeError("ZIP contains no source/ files")
        if len(sources) > 10000 or sum(item.file_size for item in sources) > 256 * 1024 * 1024:
            raise RuntimeError("Source archive exceeds the verification extraction limit")
        for item in sources:
            relative = PurePosixPath(item.filename).relative_to("source")
            if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
                raise RuntimeError(f"Unsafe source path: {item.filename}")
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Source ZIP contains a symbolic link: {item.filename}")
            name = relative.as_posix()
            if not name or name in members:
                raise RuntimeError(f"Duplicate/empty source path: {item.filename}")
            data = archive.read(item)
            output = destination.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            members[name] = hashlib.sha256(data).hexdigest()
    required = {"Makefile", "requirements-dev.txt", "scripts/setup_environment.py",
                "scripts/build.py", "scripts/release.py", "scripts/check_clean_install.py",
                "scripts/check_stress.py"}
    missing = required - members.keys()
    if missing:
        raise RuntimeError("Source archive is missing: " + ", ".join(sorted(missing)))
    return members


def clean_environment() -> dict[str, str]:
    env = os.environ.copy()
    # Clear only checkout-specific build selectors. Keep HOME, proxies, CA trust
    # and the managed runtime's authentication/guard variables unchanged.
    for name in ("FONTCONFIG_FILE", "OSFONTDIR", "TEXMFHOME", "TEXMFVAR",
                 "TEXMFCONFIG", "XDG_CACHE_HOME", "VIRTUAL_ENV", "PYTHONPATH"):
        env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def run_step(name: str, command: list[str], cwd: Path, logs: Path,
             env: dict[str, str], report: dict, timeout: int = 900) -> None:
    number = len(report["commands"]) + 1
    log = logs / f"{number:02d}-{name}.log"
    entry = {"name": name, "argv": command, "log": str(log), "status": "running"}
    report["commands"].append(entry)
    print(f"[clean-install] {name}", flush=True)
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            entry.update(status="timed_out", elapsed_seconds=round(time.monotonic() - start, 3),
                         log_sha256=sha(log))
            raise RuntimeError(f"{name} timed out; inspect {log}") from None
    entry.update(exit_code=code, elapsed_seconds=round(time.monotonic() - start, 3),
                 log_sha256=sha(log), status="passed" if code == 0 else "failed")
    if code:
        raise RuntimeError(f"{name} exited with {code}; inspect {log}")


def inspect_outputs(root: Path, reference: Path | None) -> dict:
    """Runs under the newly installed venv, so helpers use its locked packages."""
    import fitz

    sys.path.insert(0, str(root / "scripts"))
    from build import TARGETS
    from release import source_fingerprint

    result = {"source_fingerprint": source_fingerprint(root), "outputs": {},
              "layout_comparison": {"status": "not_requested"}}
    if reference:
        result["reference_source_fingerprint"] = source_fingerprint(reference)
        if result["source_fingerprint"] != result["reference_source_fingerprint"]:
            raise RuntimeError("Extracted source fingerprint differs from reference checkout")
    comparison = []
    for target, (_, jobname, folder) in TARGETS.items():
        pdf_path = root / "build" / folder / (jobname + ".pdf")
        log_path = root / "build" / folder / (jobname + ".log")
        if not pdf_path.is_file() or not log_path.is_file():
            raise RuntimeError(f"Missing build output for {target}")
        log = log_path.read_text(encoding="utf-8", errors="replace")
        unresolved = re.findall(r"(?:LaTeX Warning: (?:Reference|Hyper reference)[^\n]*undefined|"
                                r"There were undefined references|Missing character:)", log)
        overfull = len(re.findall(r"Overfull \\[hv]box", log))
        if overfull or unresolved:
            raise RuntimeError(f"{target}: {overfull} overfull boxes; {len(unresolved)} unresolved/missing text warnings")
        with fitz.open(pdf_path) as document:
            fonts: set[str] = set()
            for page in document:
                for font in page.get_fonts(full=True):
                    xref, extension, kind, name = font[:4]
                    fonts.add(name)
                    if not xref or not document.extract_font(xref)[3]:
                        raise RuntimeError(f"{target}: font {name} is not embedded")
            row = {"path": str(pdf_path.relative_to(root)), "sha256": sha(pdf_path),
                   "pages": len(document), "fonts": sorted(fonts), "fonts_embedded": True,
                   "overfull_boxes": overfull,
                   "underfull_boxes": len(re.findall(r"Underfull \\[hv]box", log))}
            if reference:
                other_path = reference / "build" / folder / (jobname + ".pdf")
                if not other_path.is_file():
                    raise RuntimeError(f"Reference PDF is missing: {other_path}")
                with fitz.open(other_path) as other:
                    if len(document) != len(other):
                        raise RuntimeError(f"{target}: page count differs from reference")
                    word_count = 0
                    for page_index, (page, baseline) in enumerate(zip(document, other), 1):
                        if abs(page.rect.width - baseline.rect.width) > .01 or abs(page.rect.height - baseline.rect.height) > .01:
                            raise RuntimeError(f"{target} page {page_index}: page size differs")
                        words, expected = page.get_text("words"), baseline.get_text("words")
                        if len(words) != len(expected):
                            raise RuntimeError(f"{target} page {page_index}: word count differs")
                        for actual, wanted in zip(words, expected):
                            if actual[4] != wanted[4] or any(abs(a - b) > .02 for a, b in zip(actual[:4], wanted[:4])):
                                raise RuntimeError(f"{target} page {page_index}: text/layout differs at {actual[4]!r}")
                        word_count += len(words)
                    comparison.append({"target": target, "pages": len(document),
                                       "words": word_count, "text_and_positions_match": True})
            result["outputs"][target] = row
    if reference:
        result["layout_comparison"] = {"status": "passed", "position_tolerance_pdf_bp": .02,
                                       "targets": comparison}
    result["total_output_pages"] = sum(row["pages"] for row in result["outputs"].values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", dest="archive", type=Path, help="Released ZIP with source/ members")
    parser.add_argument("--workdir", type=Path, help="New or empty directory; never reused or deleted")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--python", default=sys.executable, help="Python used to create the fresh venv")
    parser.add_argument("--inspect-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inspect_root:
        try:
            result = inspect_outputs(args.inspect_root.resolve(),
                                     args.reference_root.resolve() if args.reference_root else None)
            write_report(args.report, result)
            return 0
        except Exception as error:
            print(f"Output inspection failed: {error}", file=sys.stderr)
            return 1
    if not args.archive or not args.workdir:
        parser.error("--zip and --workdir are required")
    archive = args.archive.resolve()
    work = args.workdir.resolve()
    report_path = args.report.resolve()
    if not archive.is_file():
        parser.error("--zip must be an existing file")
    if work.exists() and (not work.is_dir() or any(work.iterdir())):
        parser.error("--workdir must be an empty directory; previous verification directories are never reused")
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source"
    logs = work / "logs"
    logs.mkdir()
    report = {"status": "running", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "input_zip": str(archive), "input_zip_sha256": sha(archive),
              "workdir": str(work), "commands": [],
              "fresh_source_tree": True, "fresh_python_venv": True,
              "fresh_font_downloads": True,
              "system_toolchain_scope": "Existing documented Linux tools; no new OS/container installation",
              "host": {"system": platform.system(), "release": platform.release(),
                       "python_launcher": platform.python_version()}}
    env = clean_environment()
    try:
        members = extract_sources(archive, source)
        report["source_archive_files"] = len(members)
        report["source_archive_manifest_sha256"] = hashlib.sha256(
            json.dumps(members, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (source / ".local").exists() or (source / ".venv").exists() or (source / "build").exists():
            raise RuntimeError("Archive improperly contains a prior toolchain or build")
        if args.reference_root:
            reference = args.reference_root.resolve()
            for relative, expected in members.items():
                path = reference / relative
                if not path.is_file() or sha(path) != expected:
                    raise RuntimeError(f"ZIP source differs from checkout: {relative}")
            report["zip_members_match_reference"] = True
        else:
            reference = None
        venv = source / ".venv"
        python = venv / "bin" / "python"
        run_step("create-venv", [args.python, "-m", "venv", str(venv)], source, logs, env, report)
        run_step("install-locked-dependencies", [str(python), "-m", "pip", "install", "--quiet",
                 "--disable-pip-version-check", "--no-cache-dir", "--timeout", "60", "--retries", "2",
                 "-r", "requirements-dev.txt"], source, logs, env, report, timeout=600)
        make = ["make", "PYTHON=" + str(python)]
        run_step("setup", make + ["setup"], source, logs, env, report, timeout=900)
        run_step("build-all", make + ["-j2", "all"], source, logs, env, report, timeout=1800)
        run_step("unit-and-pdf-tests", make + ["test"], source, logs, env, report, timeout=900)
        test_log = Path(report["commands"][-1]["log"]).read_text(encoding="utf-8", errors="replace")
        if re.search(r"^OK\s*\([^\n]*skipped=|\.\.\. skipped ", test_log, re.M):
            raise RuntimeError("Fresh test suite skipped checks; full clean verification requires all tests")
        test_counts = re.findall(r"^Ran (\d+) tests? in ", test_log, re.M)
        if not test_counts or int(test_counts[-1]) == 0:
            raise RuntimeError("Fresh test suite did not report a positive test count")
        report["tests_run"] = int(test_counts[-1])
        report["test_skips"] = 0
        run_step("preflight-all", make + ["preflight-all"], source, logs, env, report, timeout=900)
        stress_report = source / "build" / "validation" / "stress-layout.json"
        run_step("stress-layout", [str(python), "scripts/check_stress.py",
                 "--print", "build/stress-print2/Stress_Print.pdf",
                 "--screen", "build/stress-screen/Stress_Screen.pdf",
                 "--report", str(stress_report)], source, logs, env, report, timeout=180)
        inspection = work / "output-inspection.json"
        command = [str(python), str(source / "scripts/check_clean_install.py"),
                   "--inspect-root", str(source), "--report", str(inspection)]
        if reference:
            command += ["--reference-root", str(reference)]
        run_step("inspect-and-compare-outputs", command, source, logs, env, report, timeout=300)
        report.update(json.loads(inspection.read_text(encoding="utf-8")))
        suite = json.loads((source / "build/validation/suite.json").read_text())
        if not suite or any(row["exit_code"] for row in suite):
            raise RuntimeError("Fresh PDF pair suite is missing or failed")
        report["pdf_pairs_passed"] = len(suite)
        stress = json.loads(stress_report.read_text())
        if stress.get("status") != "passed":
            raise RuntimeError("Fresh stress layout report did not pass")
        report["stress_layout"] = stress
        downloads = source / ".local/downloads"
        manifest = json.loads((source / "scripts/dependency-manifest.json").read_text())
        verified = []
        for entry in manifest["artifacts"]:
            path = downloads / entry["name"]
            if not path.is_file() or sha(path) != entry["sha256"]:
                raise RuntimeError(f"Fresh setup artifact mismatch: {entry['name']}")
            verified.append(entry["name"])
        report["fresh_setup_artifacts_verified"] = verified
        tools = {}
        for name, command in [("python", [str(python), "--version"]),
                              ("xelatex", ["xelatex", "--version"]),
                              ("latexmk", ["latexmk", "-v"]),
                              ("ghostscript", ["gs", "--version"])]:
            output = subprocess.run(command, cwd=source, env=env, check=True,
                                    capture_output=True, text=True).stdout.strip().splitlines()
            tools[name] = output[:3]
        report["tools"] = tools
        frozen = subprocess.run([str(python), "-m", "pip", "freeze"], cwd=source, env=env,
                                check=True, capture_output=True, text=True).stdout.splitlines()
        report["installed_python_packages"] = frozen
        report["status"] = "passed"
        print(f"PASSED: clean ZIP installation, {len(report['outputs'])} PDFs, "
              f"{report['total_output_pages']} pages, {report['pdf_pairs_passed']} pairs", flush=True)
        return 0
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        print(f"FAILED: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_report(report_path, report)


if __name__ == "__main__":
    raise SystemExit(main())

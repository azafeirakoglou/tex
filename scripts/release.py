#!/usr/bin/env python3
"""Build and verify a complete release before creating its source/PDF archive.

The manifest binds source files, test results, every PDF pair and the stress
check to their SHA-256 values. It is intentionally separate from press approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import fitz

from build import TARGETS
from setup_environment import ROOT
from validate_suite import PAIRS

EXCLUDED_PARTS = {'.git', '.local', '.venv', 'build', 'dist', 'releases',
                  '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
EXCLUDED_SUFFIXES = {'.aux', '.log', '.out', '.toc', '.xdv', '.pyc', '.fls', '.fdb_latexmk'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root: Path):
    """The exact authoring source set shared by fingerprinting and export."""
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if any(part.startswith('.') and part != '.gitignore' for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES or path.name.endswith('.synctex.gz'):
            continue
        if path.is_symlink():
            raise ValueError('Source archives require regular files: ' + str(relative))
        if path.is_file():
            yield path


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in source_files(root):
        relative = path.relative_to(root).as_posix().encode('utf-8')
        digest.update(len(relative).to_bytes(8, 'big'))
        digest.update(relative)
        digest.update(bytes.fromhex(sha(path)))
    return digest.hexdigest()


def palette_hash(root: Path) -> str:
    palette = json.loads((root / 'config/color-map.json').read_text(encoding='utf-8'))
    return hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest()


def pdf_path(root: Path, target: str, targets=TARGETS) -> Path:
    _, job, folder = targets[target]
    return root / 'build' / folder / (job + '.pdf')


def relative_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Release evidence must use repository-relative paths')
    result = root / path
    if not result.is_file() or result.is_symlink():
        raise ValueError('Missing release evidence: ' + value)
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_release_manifest(root: Path, manifest_path: Path, *, targets=None, pairs=None) -> dict:
    """Reject incomplete, failed or stale evidence before copying any artifact."""
    targets = TARGETS if targets is None else targets
    pairs = PAIRS if pairs is None else pairs
    manifest = load_json(manifest_path)
    if manifest.get('schema_version') != 1 or manifest.get('status') != 'passed':
        raise ValueError('The complete release gate has not passed')
    if manifest.get('source_sha256') != source_fingerprint(root):
        raise ValueError('Source changed after release checks; run make release again')
    if manifest.get('palette_sha256') != palette_hash(root):
        raise ValueError('Palette changed after release checks')
    palette = load_json(root / 'config/color-map.json')
    if manifest.get('version') != palette.get('version'):
        raise ValueError('Release version does not match the palette')
    current_targets = manifest.get('targets', {})
    if set(current_targets) != set(targets):
        raise ValueError('Release evidence does not cover every build target')
    for target in targets:
        path = pdf_path(root, target, targets)
        record = current_targets[target]
        if record.get('pdf') != path.relative_to(root).as_posix() or not path.is_file():
            raise ValueError('Missing release PDF: ' + target)
        if record.get('sha256') != sha(path):
            raise ValueError('PDF changed after release checks: ' + target)
    reports = manifest.get('reports', {})
    if not reports:
        raise ValueError('Release reports are missing')
    for name, expected in reports.items():
        path = relative_path(root, name)
        if sha(path) != expected:
            raise ValueError('Release report changed: ' + name)
    pair_records = manifest.get('pairs', [])
    if len(pair_records) != len(pairs) or {(r.get('print_target'), r.get('screen_target'))
                                        for r in pair_records} != set(pairs):
        raise ValueError('Release evidence does not cover every PDF pair')
    for record in pair_records:
        report_name = record.get('report')
        if report_name not in reports:
            raise ValueError('PDF pair report is not in the verified report set')
        report = load_json(relative_path(root, report_name))
        expected = {'print': current_targets[record['print_target']]['sha256'],
                    'screen': current_targets[record['screen_target']]['sha256'],
                    'palette': manifest['palette_sha256']}
        if record.get('exit_code') != 0 or report.get('status') != 'passed' or report.get('input_sha256') != expected:
            raise ValueError('PDF pair preflight is failed or stale: ' + record['print_target'])
    test_name = manifest.get('test_report')
    if test_name not in reports:
        raise ValueError('Full test-suite evidence is missing')
    tests = load_json(relative_path(root, test_name))
    if (tests.get('status') != 'passed' or tests.get('source_sha256') != manifest['source_sha256']
            or tests.get('tests', 0) < 1 or tests.get('failures') != 0 or tests.get('errors') != 0
            or tests.get('skipped') != 0):
        raise ValueError('The full test suite did not pass without skips')
    driver_name = manifest.get('driver_report')
    if driver_name not in reports:
        raise ValueError('Fresh PDF-driver evidence is missing')
    driver = load_json(relative_path(root, driver_name))
    if driver.get('status') != 'passed' or driver.get('unexpected_warnings'):
        raise ValueError('The PDF driver reported duplicate destinations or other warnings')
    if 'stress-print2' in targets:
        stress_name = manifest.get('stress_report')
        if stress_name not in reports:
            raise ValueError('Stress-book evidence is missing')
        stress = load_json(relative_path(root, stress_name))
        expected = {'print': current_targets['stress-print2']['sha256'],
                    'screen': current_targets['stress-screen']['sha256']}
        if stress.get('status') != 'passed' or stress.get('input_sha256') != expected:
            raise ValueError('Stress-book check is failed or stale')
    summary_name = manifest.get('build_summary')
    if summary_name not in reports:
        raise ValueError('Build-summary evidence is missing')
    summary = load_json(relative_path(root, summary_name))
    if len(summary) != len(targets) or {row.get('target') for row in summary} != set(targets):
        raise ValueError('Build summary does not cover every target')
    for row in summary:
        if row.get('overfull') != 0 or row.get('unresolved') or row.get('missing_characters'):
            raise ValueError('Unresolved layout/build error: ' + row['target'])
        record = current_targets[row['target']]
        if row.get('pages', 0) < 1 or record.get('pages') != row['pages']:
            raise ValueError('Invalid page-count evidence: ' + row['target'])
    return manifest


def collect_build_summary(root: Path) -> list[dict]:
    summary = []
    for target, (_, job, folder) in TARGETS.items():
        path = root / 'build' / folder / (job + '.log')
        if not path.is_file():
            raise ValueError('Build log is missing: ' + target)
        text = path.read_text(encoding='utf-8', errors='replace')
        unresolved = re.findall(r'^.*(?:undefined references|Reference .* undefined|Citation .* undefined|'
                                r'Rerun to get cross-references right|Label\(s\) may have changed|'
                                r'Table widths have changed).*$','\n'.join(text.splitlines()), re.M | re.I)
        with fitz.open(pdf_path(root, target)) as pdf:
            pages = len(pdf)
        row = {'target': target, 'pages': pages,
               'overfull': len(re.findall(r'Overfull \\[hv]box', text)),
               'underfull': len(re.findall(r'Underfull \\[hv]box', text)),
               'unresolved': unresolved,
               'missing_characters': re.findall(r'^Missing character:.*$', text, re.M),
               'warnings': re.findall(r'^.*Warning:.*$', text, re.M)}
        if row['overfull'] or unresolved or row['missing_characters']:
            raise ValueError('Build has overflow, missing glyphs or unresolved references: ' + target)
        summary.append(row)
    return summary


def versions() -> dict:
    result = {'python': sys.version.splitlines()[0]}
    for tool, args in [('xelatex', ['--version']), ('latexmk', ['-version']), ('gs', ['--version'])]:
        value = subprocess.run([tool, *args], check=True, capture_output=True, text=True)
        result[tool] = next((line.strip() for line in value.stdout.splitlines() if line.strip()), '')
    result['python_packages'] = {name: importlib.metadata.version(name)
                                 for name in ['Pillow', 'pypdf', 'PyMuPDF']}
    return result


def inspect_driver_output(text: str) -> dict:
    """Only the documented repeated spot-resource warning is benign."""
    warnings = [line.strip() for line in text.splitlines()
                if 'xdvipdfmx:warning:' in line.lower()]
    allowed = re.compile(r'Object "Second" already defined in dict! \(ignored\)')
    unexpected = [line for line in warnings if not allowed.search(line)]
    duplicate_destinations = [line.strip() for line in text.splitlines()
                              if re.search(r'duplicate[^\n]{0,100}dest(?:ination)?|'
                                           r'dest(?:ination)?[^\n]{0,100}duplicate', line, re.I)]
    unexpected = list(dict.fromkeys(unexpected + duplicate_destinations))
    return {'status': 'failed' if unexpected else 'passed',
            'allowed_spot_resource_warnings': len(warnings) - len([line for line in warnings if not allowed.search(line)]),
            'unexpected_warnings': unexpected}


def run_test_suite(report: Path) -> int:
    fingerprint = source_fingerprint(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.wasSuccessful() and not result.skipped
    write_json(report, {'status': 'passed' if passed else 'failed',
                        'source_sha256': fingerprint, 'tests': result.testsRun,
                        'failures': len(result.failures), 'errors': len(result.errors),
                        'skipped': len(result.skipped)})
    return 0 if passed else 1


def checked_command(command: list[str], *, log: Path | None = None, env=None) -> None:
    print('Running: ' + ' '.join(command), flush=True)
    if log is None:
        subprocess.run(command, cwd=ROOT, check=True, env=env)
    else:
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=env)
        if result.returncode:
            raise RuntimeError(f'Check failed ({result.returncode}); see {log}')


def create_release(out: Path, jobs: int) -> Path:
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    checks_root = build / 'release-checks'
    checks_root.mkdir(exist_ok=True)
    check_dir = Path(tempfile.mkdtemp(prefix='run-', dir=checks_root))
    manifest_path = build / 'release-manifest.json'
    source_hash = source_fingerprint(ROOT)
    palette = load_json(ROOT / 'config/color-map.json')
    manifest = {'schema_version': 1, 'status': 'running', 'version': palette['version'],
                'created_utc': datetime.now(timezone.utc).isoformat(), 'source_sha256': source_hash}
    write_json(manifest_path, manifest)
    try:
        checked_command([sys.executable, 'scripts/setup_environment.py'], log=check_dir / 'setup.log')
        build_env = os.environ.copy()
        build_env['BOOK_FORCE_REBUILD'] = '1'
        checked_command(['make', f'-j{jobs}', f'PYTHON={sys.executable}', 'all'],
                        log=check_dir / 'build.log', env=build_env)
        driver_report = check_dir / 'pdf-driver.json'
        driver = inspect_driver_output((check_dir / 'build.log').read_text(encoding='utf-8', errors='replace'))
        write_json(driver_report, driver)
        if driver['status'] != 'passed':
            raise ValueError('PDF driver warnings; see ' + str(driver_report))
        test_report = check_dir / 'tests.json'
        checked_command([sys.executable, 'scripts/release.py', '--tests-only-report', str(test_report)],
                        log=check_dir / 'tests.log')
        checked_command([sys.executable, 'scripts/validate_suite.py', '--out', str(check_dir / 'pdf')],
                        log=check_dir / 'preflight.log')
        stress_report = check_dir / 'stress.json'
        if 'stress-print2' in TARGETS:
            checked_command([sys.executable, 'scripts/check_stress.py',
                             '--print', str(pdf_path(ROOT, 'stress-print2')),
                             '--screen', str(pdf_path(ROOT, 'stress-screen')),
                             '--report', str(stress_report)], log=check_dir / 'stress.log')
        summary = collect_build_summary(ROOT)
        summary_path = check_dir / 'build-summary.json'
        write_json(summary_path, summary)
        write_json(build / 'build-summary.json', summary)
        tool_path = check_dir / 'tool-versions.json'
        write_json(tool_path, versions())
        if source_fingerprint(ROOT) != source_hash:
            raise ValueError('Source changed during release checks; restart make release')
        suite = load_json(check_dir / 'pdf/suite.json')
        records = {row['target']: row for row in summary}
        target_records = {target: {'pdf': pdf_path(ROOT, target).relative_to(ROOT).as_posix(),
                                   'sha256': sha(pdf_path(ROOT, target)),
                                   'pages': records[target]['pages']}
                          for target in TARGETS}
        report_paths = [test_report, driver_report, summary_path, tool_path, check_dir / 'pdf/suite.json']
        report_paths.extend(ROOT / row['report'] for row in suite)
        if stress_report.exists():
            report_paths.append(stress_report)
        report_paths.extend(sorted(check_dir.glob('*.log')))
        manifest.update({'status': 'passed', 'palette_sha256': palette_hash(ROOT),
                         'targets': target_records, 'pairs': suite,
                         'test_report': test_report.relative_to(ROOT).as_posix(),
                         'driver_report': driver_report.relative_to(ROOT).as_posix(),
                         'build_summary': summary_path.relative_to(ROOT).as_posix(),
                         'tool_versions': tool_path.relative_to(ROOT).as_posix(),
                         'main_report': next(row['report'] for row in suite if row['print_target'] == 'print2'),
                         'reports': {p.relative_to(ROOT).as_posix(): sha(p) for p in report_paths}})
        if stress_report.exists():
            manifest['stress_report'] = stress_report.relative_to(ROOT).as_posix()
        write_json(manifest_path, manifest)
        validate_release_manifest(ROOT, manifest_path)
        checked_command([sys.executable, 'scripts/export_review.py', '--out', str(out),
                         '--release-manifest', str(manifest_path)])
        print('Release gate passed: ' + str(manifest_path), flush=True)
        return manifest_path
    except Exception as exc:
        manifest.update({'status': 'failed', 'error': str(exc)})
        write_json(manifest_path, manifest)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--tests-only-report', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.tests_only_report:
        return run_test_suite(args.tests_only_report)
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    try:
        create_release(args.out.resolve(), args.jobs)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print('Release failed: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

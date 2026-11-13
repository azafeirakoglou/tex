#!/usr/bin/env python3
"""Export current proof PDFs, or a release bound to complete verified evidence."""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile

import fitz
from PIL import Image, ImageDraw, ImageFont

from release import (ROOT, pdf_path, sha, source_files, source_fingerprint,
                     validate_release_manifest)


def check_output_location(root: Path, out: Path) -> None:
    # Generated output must never become a member of its own source archive.
    if out.is_relative_to(root):
        relative = out.relative_to(root)
        if not relative.parts or relative.parts[0] not in {'dist', 'releases', 'build'}:
            raise ValueError('Use dist/, releases/, build/, or an output directory outside the checkout')


def verify_main_report(root: Path, report_path: Path) -> dict:
    if not report_path.is_file():
        raise ValueError('Run make preflight before proof export')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    palette = json.loads((root / 'config/color-map.json').read_text(encoding='utf-8'))
    actual = {'print': sha(pdf_path(root, 'print2')),
              'screen': sha(pdf_path(root, 'screen')),
              'palette': hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest()}
    if report.get('status') != 'passed' or report.get('input_sha256') != actual:
        raise ValueError('Main preflight is failed or stale; run make preflight again')
    return palette


def write_source_archive(bundle: zipfile.ZipFile, root: Path) -> list[str]:
    names = []
    for path in source_files(root):
        name = (Path('source') / path.relative_to(root)).as_posix()
        bundle.write(path, name)
        names.append(name)
    return names


def export_bundle(root: Path, out: Path, release_manifest: Path | None = None) -> list[Path]:
    root, out = root.resolve(), out.resolve()
    check_output_location(root, out)
    manifest = validate_release_manifest(root, release_manifest) if release_manifest else None
    report_path = root / manifest['main_report'] if manifest else root / 'build/validation/report.json'
    palette = verify_main_report(root, report_path)
    version = palette.get('version')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', version):
        raise ValueError('Palette version must be a dotted numeric version')
    fingerprint = source_fingerprint(root)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    sources = {'PRINT': pdf_path(root, 'print2'), 'SCREEN': pdf_path(root, 'screen')}
    for edition, source in sources.items():
        dest = out / f'Book_v{version}_{edition}.pdf'
        shutil.copyfile(source, dest)
        files.append(dest)
    if manifest:
        for category, prefix in [('figures', 'Figures'), ('starter', 'Starter'), ('stress', 'Stress')]:
            for target_suffix, edition in [('print2', 'PRINT'), ('screen', 'SCREEN')]:
                target = f'{category}-{target_suffix}'
                if target in manifest['targets']:
                    dest = out / f'{prefix}_v{version}_{edition}.pdf'
                    shutil.copyfile(root / manifest['targets'][target]['pdf'], dest)
                    files.append(dest)
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font = ImageFont.truetype(str(font_path), 30) if font_path.is_file() else ImageFont.load_default()
    pages = []
    for edition, source in sources.items():
        with fitz.open(source) as doc:
            page_index = next((i for i, page in enumerate(doc)
                               if 'Πώς σκέφτομαι' in page.get_text()), min(5, len(doc) - 1))
            pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
            page = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            single = out / f'Book_v{version}_{edition}_preview.png'
            page.save(single)
            files.append(single)
            pages.append((edition, page))
    width = sum(page.width for _, page in pages) + 60
    height = max(page.height for _, page in pages) + 90
    comparison = Image.new('RGB', (width, height), '#eeeeee')
    draw = ImageDraw.Draw(comparison)
    left = 20
    for label, page in pages:
        draw.text((left, 15), label + ' — PROOF', font=font, fill='#222222')
        comparison.paste(page, (left, 65))
        left += page.width + 20
    preview = out / f'Book_v{version}_comparison.png'
    comparison.save(preview)
    files.append(preview)
    validation = out / 'validation.json'
    shutil.copyfile(report_path, validation)
    files.append(validation)
    if manifest:
        evidence = out / 'release-manifest.json'
        shutil.copyfile(release_manifest, evidence)
        files.append(evidence)
        summary = out / 'build-summary.json'
        shutil.copyfile(root / manifest['build_summary'], summary)
        files.append(summary)
    guide = out / 'START_HERE.txt'
    guide.write_text(
        f'Universal Book Template v{version}\n\n'
        + ('Complete release checks passed; see release-manifest.json and reports/.\n'
           'Starter_*.pdf shows the clean authoring example; source/starter.tex and source/starter-content.tex are the starting point.\n'
           'Figures_*.pdf documents the diagram conventions; Stress_*.pdf exercises page breaks.\n'
           if manifest else 'PROOF EXPORT: only the main PDF pair is covered by this export.\n'
           'Use make release for the complete tests, samples and stress-book checks.\n')
        + 'PRINT: black + provisional red spot; SCREEN: black + blue. Both are print proofs.\n'
        'If the chat PDF viewer fails, extract this ZIP and open the PDFs locally.\n'
        'The PNG comparison is a preview, not a print master.\n'
        'For setup and commands see source/README.md, source/SETUP.md and source/docs/.\n'
        'Printer ink, tint approval, bleed and PDF/X remain pending.\n', encoding='utf-8')
    files.append(guide)
    archive = out / f'Universal_Book_Template_v{version}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        source_names = write_source_archive(bundle, root)
        for path in files:
            bundle.write(path, path.name)
        for path in sorted((root / '.local/licenses').glob('*')):
            if path.is_file():
                bundle.write(path, Path('font-licenses') / path.name)
        if manifest:
            # Explicit records replace the former wildcard of old JSON reports.
            for name in manifest['reports']:
                bundle.write(root / name, (Path('reports') / name).as_posix())
            selected = {'print2', 'screen', 'figures-print2', 'figures-screen',
                        'starter-print2', 'starter-screen', 'stress-print2', 'stress-screen'}
            for target, data in manifest['targets'].items():
                if target not in selected:
                    bundle.write(root / data['pdf'], Path('pdf-samples') / (target + '.pdf'))
    if source_fingerprint(root) != fingerprint:
        archive.unlink(missing_ok=True)
        raise ValueError('Source changed during export; source/PDF archive was not released')
    if manifest:
        validate_release_manifest(root, release_manifest)
    with zipfile.ZipFile(archive) as bundle:
        bad = bundle.testzip()
        if bad:
            raise ValueError('Archive CRC verification failed: ' + bad)
        for name in source_names:
            original = root / Path(name).relative_to('source')
            if bundle.read(name) != original.read_bytes():
                raise ValueError('Archived source changed: ' + name)
    files.append(archive)
    sums = out / 'SHA256SUMS.txt'
    sums.write_text(''.join(sha(path) + '  ' + path.name + '\n' for path in files), encoding='utf-8')
    files.append(sums)
    out.chmod(0o755)
    for path in files:
        path.chmod(0o644)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--release-manifest', type=Path,
                        help='Require complete current release evidence')
    args = parser.parse_args()
    try:
        files = export_bundle(ROOT, args.out, args.release_manifest)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    for path in files:
        print(path.name, path.stat().st_size, 'bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

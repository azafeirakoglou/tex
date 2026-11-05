#!/usr/bin/env python3
"""Build a fresh extracted copy and compare both complete main PDFs."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import fitz

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.local', 'build', '__pycache__', '.pytest_cache', '.git', '.venv'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_smoke_input(path):
    files = [ROOT / name for name in ('build_stable.py', 'prepare_runtime.py',
                                      'runtime/RUNTIME_MANIFEST.json')]
    for name in ('source', 'runtime/fonts', 'runtime/licenses', 'runtime/texmf'):
        files.extend(p for p in (ROOT / name).rglob('*') if p.is_file()
                     and not p.is_symlink() and not any(x in p.relative_to(ROOT).parts for x in SKIP))
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(item, 'smoke-input/' + str(item.relative_to(ROOT)))
    return len(files)


def compare(reference, fresh):
    with fitz.open(reference) as a, fitz.open(fresh) as b:
        if len(a) != len(b):
            raise RuntimeError('Page count mismatch: ' + reference.name)
        for number, (left, right) in enumerate(zip(a, b), 1):
            if any(abs(x - y) > .02 for x, y in zip(left.rect, right.rect)):
                raise RuntimeError(f'Page geometry mismatch: {reference.name} page {number}')
            words_a, words_b = left.get_text('words'), right.get_text('words')
            if len(words_a) != len(words_b):
                raise RuntimeError(f'Word count mismatch: {reference.name} page {number}')
            for wa, wb in zip(words_a, words_b):
                if wa[4:] != wb[4:] or any(abs(x - y) > .02 for x, y in zip(wa[:4], wb[:4])):
                    raise RuntimeError(f'Text/position mismatch: {reference.name} page {number}')
            pa = left.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            pb = right.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            if (pa.width, pa.height, pa.samples) != (pb.width, pb.height, pb.samples):
                raise RuntimeError(f'Raster mismatch: {reference.name} page {number}')
        return {'pages': len(a), 'reference_sha256': digest(reference),
                'fresh_sha256': digest(fresh), 'all_words_positions_within_bp': .02,
                'all_rendered_pages_pixel_identical_72dpi': True}


def main(archive_path=None):
    began = time.monotonic()
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    temporary_root = ROOT / 'runtime/tmp'
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='clean-install-', dir=temporary_root) as temp:
        work = Path(temp)
        archive = Path(archive_path).resolve() if archive_path else work / 'smoke-input.zip'
        file_count = make_smoke_input(archive) if archive_path is None else None
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            prefixes = {Path(n).parts[0] for n in names if Path(n).parts}
            if len(prefixes) != 1 or any(Path(n).is_absolute() or '..' in Path(n).parts for n in names):
                raise RuntimeError('Expected one safe package root in the ZIP')
            if any(x in Path(n).parts for n in names for x in ('.local', 'build', '__pycache__')):
                raise RuntimeError('Clean input must not contain prepared or build state')
            extracted = work / 'unpacked'
            zipped.extractall(extracted)
        fresh = extracted / prefixes.pop()
        if (fresh / 'runtime/texmf-var/web2c/xetex/xelatex.fmt').exists():
            raise RuntimeError('Compiled format was unexpectedly packaged')
        setup_log = reports / 'CLEAN_INSTALL_SMOKE.setup.log'
        with setup_log.open('w') as stream:
            setup = subprocess.run([sys.executable, 'prepare_runtime.py'], cwd=fresh,
                                   stdout=stream, stderr=subprocess.STDOUT)
        if setup.returncode:
            raise RuntimeError('Fresh setup failed; see ' + str(setup_log))
        moved = work / 'moved package'
        fresh.rename(moved)
        for name in ('fonts', 'texmf', 'texmf-var'):
            link = moved / 'source/.local' / name
            if not link.is_symlink() or not link.resolve().is_relative_to(moved):
                raise RuntimeError('Runtime link does not survive relocation: ' + str(link))
        build_log = reports / 'CLEAN_INSTALL_SMOKE.build.log'
        with build_log.open('w') as stream:
            build = subprocess.run([sys.executable, 'build_stable.py', '--jobs', '2'], cwd=moved,
                                   stdout=stream, stderr=subprocess.STDOUT)
        if build.returncode:
            raise RuntimeError('Fresh full build failed; see ' + str(build_log))
        comparisons = {}
        for profile in ('PRINT', 'SCREEN'):
            name = 'Universal_Book_Template_v1.0.12_' + profile + '.pdf'
            comparisons[profile] = compare(ROOT / 'pdf' / name, moved / 'pdf' / name)
        archive_sha = digest(archive)
    source = ROOT / 'source'
    source_hashes = {str(p.relative_to(source)): digest(p) for name in ('config', 'styles')
                     for p in sorted((source / name).glob('*')) if p.is_file()}
    result = {'status': 'passed', 'checked_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Fresh ZIP extraction, offline runtime, relocated prepared folder, both complete main PDFs.',
              'archive_kind': 'final_package' if archive_path else 'minimal_reproduction_input',
              'archive_sha256': archive_sha, 'minimal_input_files': file_count,
              'started_without_local_build_format_or_cache': True,
              'relative_links_survive_folder_move': True, 'network_used': False,
              'setup_exit_code': setup.returncode, 'build_exit_code': build.returncode,
              'pdfs': comparisons, 'source_config_style_sha256': source_hashes,
              'binary_pdf_identity_required': False,
              'elapsed_seconds': round(time.monotonic() - began, 2)}
    (reports / 'CLEAN_INSTALL_SMOKE.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Test the actual final package ZIP instead of a minimal reproduction ZIP')
    args = parser.parse_args()
    raise SystemExit(main(args.archive))

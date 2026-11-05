#!/usr/bin/env python3
"""Package verified v1.0.12 locally; never publish, merge, tag or release."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Universal_Book_Template_v1.0.12_STABLE'
ROOT_FILES = ('README.md', 'CHANGELOG.md', 'REQUEST.md', 'VERSION.json',
              'BUILD_RESULTS.json', 'QA_REPORT.md', 'REPRODUCTION.md',
              'requirements-review.txt', 'build_stable.py', 'prepare_runtime.py')
SKIP_PARTS = {'.local', 'build', '__pycache__', '.pytest_cache', '.git', '.venv',
              'work', 'smoke-views'}
SKIP_SUFFIXES = {'.pyc', '.aux', '.out', '.toc', '.fls', '.fdb_latexmk', '.xdv', '.fmt'}
TABLE_DIAGNOSTICS = {'no-rule', 'zero-parskip', 'large-chunk', 'normal-rowheader',
                     'independent-not-canonical', 'no-rule.tex', 'diagnose_tail.py',
                     'page6.png'}


def included(path):
    relative = path.relative_to(ROOT)
    if (not path.is_file() or path.is_symlink() or
            any(x in relative.parts for x in SKIP_PARTS) or path.suffix in SKIP_SUFFIXES or
            path.name.startswith('PAIR_') or
            any(x in path.name.lower() for x in
                ('initial-', 'preliminary', 'pre-rule-', 'recheck', 'pre_category'))):
        return False
    if relative.parts[:2] == ('qa', 'tables'):
        # Only the final table fixture/runners/reports and its two profile
        # outputs belong in a stable package; diagnostic trials stay local.
        tail = relative.parts[2:]
        if any(part in TABLE_DIAGNOSTICS for part in tail):
            return False
        if len(tail) > 1 and tail[0] not in ('SCREEN', 'PRINT'):
            return False
    return True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def select():
    selected = {ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()}
    trees = ('source', 'runtime/fonts', 'runtime/licenses', 'runtime/texmf',
             'tools', 'pdf', 'qa', 'logs', 'visual-audit')
    for name in trees:
        for path in (ROOT / name).rglob('*'):
            if included(path):
                selected.add(path)
    selected.add(ROOT / 'runtime/RUNTIME_MANIFEST.json')
    for path in (ROOT / 'reports').glob('*'):
        if (path.is_file() and path.name != 'PACKAGE_INTEGRITY.json' and
                not any(x in path.name.lower() for x in ('draft', 'preliminary', 'package_selection'))):
            selected.add(path)
    return sorted(selected, key=lambda p: str(p.relative_to(ROOT)))


def verified_selection():
    selected = select()
    version = json.loads((ROOT / 'VERSION.json').read_text())
    if version.get('status') != 'stable':
        raise RuntimeError('VERSION.json must record stable after successful QA; packaging does not promote it')
    required = list(ROOT_FILES) + ['pdf/' + name for name in (
        'Universal_Book_Template_v1.0.12_PRINT.pdf',
        'Universal_Book_Template_v1.0.12_SCREEN.pdf', 'EXAMPLE_HEADER_COMPARISON.pdf')]
    missing = [name for name in required if ROOT / name not in selected]
    if missing:
        raise RuntimeError('Required package artifacts missing: ' + ', '.join(missing))
    for name in ('ORIGINAL_INTEGRITY.json', 'SOURCE_DIFF.json', 'CLEAN_INSTALL_SMOKE.json'):
        path = ROOT / 'reports' / name
        if not path.is_file() or json.loads(path.read_text()).get('status') != 'passed':
            raise RuntimeError('Final passing evidence required: reports/' + name)
    summary = ROOT / 'qa/QA_SUMMARY.json'
    if not summary.is_file() or json.loads(summary.read_text()).get('status') != 'passed':
        raise RuntimeError('Final passing evidence required: qa/QA_SUMMARY.json')
    difference = json.loads((ROOT / 'reports/SOURCE_DIFF.json').read_text())
    for name, expected in difference.get('all_source_sha256', {}).items():
        path = ROOT / 'source' / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('Source manifest predates source change: ' + name)
    smoke = json.loads((ROOT / 'reports/CLEAN_INSTALL_SMOKE.json').read_text())
    for name, expected in smoke.get('source_config_style_sha256', {}).items():
        path = ROOT / 'source' / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('Clean-install proof predates source change: ' + name)
    for profile, row in smoke.get('pdfs', {}).items():
        path = ROOT / 'pdf' / ('Universal_Book_Template_v1.0.12_' + profile + '.pdf')
        if sha(path.read_bytes()) != row.get('reference_sha256'):
            raise RuntimeError('Clean-install proof predates main PDF change: ' + profile)
    return selected


def content_manifest(hashes):
    return json.dumps({'version': '1.0.12', 'status': 'stable',
                       'scope': 'Local verified template; not a remote release or PDF/X certification.',
                       'files_sha256': hashes}, ensure_ascii=False, indent=2).encode() + b'\n'


def install(destination):
    if destination.exists():
        raise RuntimeError('Refusing to replace an existing version directory: ' + str(destination))
    selected = verified_selection()
    hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in selected}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    for name, expected in hashes.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
        if sha(target.read_bytes()) != expected:
            raise RuntimeError('Installed file hash mismatch: ' + name)
    (destination / 'PACKAGE_CONTENTS.json').write_bytes(content_manifest(hashes))
    print(json.dumps({'status': 'passed', 'installed_directory': str(destination),
                      'files': len(hashes) + 1, 'all_file_sha256_verified': True,
                      'previous_directory_replaced': False}, indent=2))


def make(output, listing=False):
    if listing:
        selected = select()
        print('\n'.join(str(p.relative_to(ROOT)) for p in selected))
        print(f'{len(selected)} files; {sum(p.stat().st_size for p in selected):,} uncompressed bytes')
        return
    selected = verified_selection()
    hashes = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in selected}
    contents = content_manifest(hashes)
    # Keep the installed directory's manifest identical to the manifest in
    # the ZIP, including when final provenance reports were refreshed there.
    (ROOT / 'PACKAGE_CONTENTS.json').write_bytes(contents)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        entries = [(name, (ROOT / name).read_bytes()) for name in hashes]
        entries.append(('PACKAGE_CONTENTS.json', contents))
        for name, data in entries:
            info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2026, 11, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('ZIP CRC failure')
        for name, expected in hashes.items():
            if sha(archive.read(NAME + '/' + name)) != expected:
                raise RuntimeError('Archived file hash mismatch: ' + name)
    result = {'status': 'passed', 'zip': str(output), 'sha256': sha(output.read_bytes()),
              'bytes': output.stat().st_size, 'archived_files': len(hashes) + 1,
              'crc_verified': True, 'all_archived_file_sha256_verified': True,
              'excluded': ['previous versions', '.local/build/caches/compiled formats',
                           'qa/work snapshots', 'table diagnostic trials',
                           'preliminary smoke views', 'duplicate paired PNGs'],
              'internal_hash_manifest': NAME + '/PACKAGE_CONTENTS.json'}
    (ROOT / 'reports/PACKAGE_INTEGRITY.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / (NAME + '.zip'))
    parser.add_argument('--list', action='store_true', help='Inspect file selection without creating a ZIP')
    parser.add_argument('--install', type=Path,
                        help='Copy verified files into a new version directory, refusing existing paths')
    args = parser.parse_args()
    if args.install:
        if args.list:
            parser.error('--install and --list are mutually exclusive')
        install(args.install.resolve())
    else:
        make(args.output.resolve(), args.list)

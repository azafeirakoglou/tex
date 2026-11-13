#!/usr/bin/env python3
"""Package verified v1.0.13 locally; never publish, merge, tag or release."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.13'
BASE = 'v1.0.12 STABLE'
NAME = 'Universal_Book_Template_v1.0.13_STABLE'
MODIFIED_AREA_PROOF = 'REFINEMENT_PROOF.pdf'
ROOT_FILES = ('README.md', 'CHANGELOG.md', 'REQUEST.md', 'VERSION.json',
              'BUILD_RESULTS.json', 'QA_REPORT.md', 'REPRODUCTION.md',
              'requirements-review.txt', 'build_stable.py', 'prepare_runtime.py')
SKIP_PARTS = {'.local', 'build', '__pycache__', '.pytest_cache', '.git', '.venv',
              'cache', '.cache', 'work', 'smoke-views', 'main-preview',
              'baseline-source', 'candidates', 'test-diagnostics', 'testdiagnostics'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.aux', '.out', '.toc', '.fls', '.fdb_latexmk', '.xdv', '.fmt'}
TABLE_DIAGNOSTICS = {'no-rule', 'zero-parskip', 'large-chunk', 'normal-rowheader',
                     'independent-not-canonical', 'no-rule.tex', 'diagnose_tail.py',
                     'page6.png'}


def included(path):
    relative = path.relative_to(ROOT)
    if (not path.is_file() or path.is_symlink() or
            any(x in relative.parts for x in SKIP_PARTS) or path.suffix in SKIP_SUFFIXES or
            path.name.endswith('.synctex.gz') or
            path.name.startswith('PAIR_') or
            any(x in path.name.lower() for x in
                ('initial-', 'preliminary', 'pre-rule-', 'recheck', 'pre_category', '.pending'))):
        return False
    if relative.parts[:3] == ('qa', 'refinement', 'pdf') and path.suffix == '.png':
        # Exploratory page crops are superseded by final component/visual proofs.
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
    if version.get('version') != VERSION or version.get('status') != 'stable':
        raise RuntimeError('VERSION.json must record stable after successful QA; packaging does not promote it')
    required = list(ROOT_FILES) + ['pdf/' + name for name in (
        'Universal_Book_Template_v1.0.13_PRINT.pdf',
        'Universal_Book_Template_v1.0.13_SCREEN.pdf')]
    missing = [name for name in required if ROOT / name not in selected]
    if missing:
        raise RuntimeError('Required package artifacts missing: ' + ', '.join(missing))
    if ROOT / 'pdf' / MODIFIED_AREA_PROOF not in selected:
        raise RuntimeError('Modified-area proof required: pdf/' + MODIFIED_AREA_PROOF)
    for name in ('ORIGINAL_INTEGRITY.json', 'SOURCE_DIFF.json', 'CLEAN_INSTALL_SMOKE.json'):
        path = ROOT / 'reports' / name
        if not path.is_file() or json.loads(path.read_text()).get('status') != 'passed':
            raise RuntimeError('Final passing evidence required: reports/' + name)
    summary = ROOT / 'qa/QA_SUMMARY.json'
    if not summary.is_file():
        raise RuntimeError('Final passing evidence required: qa/QA_SUMMARY.json')
    qa = json.loads(summary.read_text())
    if (qa.get('version') != VERSION or qa.get('status') != 'passed' or
            not qa.get('checks') or not all(qa['checks'].values())):
        raise RuntimeError('Current v1.0.13 passing evidence required: qa/QA_SUMMARY.json')
    qa_hashes = qa.get('canonical_source_config_style_sha256', {})
    if not qa_hashes:
        raise RuntimeError('QA report must bind the current configuration/styles to SHA-256')
    for name, expected in qa_hashes.items():
        path = ROOT / 'source' / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('QA report predates source change: ' + name)
    difference = json.loads((ROOT / 'reports/SOURCE_DIFF.json').read_text())
    source_hashes = difference.get('all_source_sha256', {})
    if difference.get('version') != VERSION or not source_hashes:
        raise RuntimeError('Current v1.0.13 full source manifest required')
    current_source_names = {
        str(path.relative_to(ROOT / 'source'))
        for path in (ROOT / 'source').rglob('*')
        if path.is_file() and not path.is_symlink() and
        not any(part in SKIP_PARTS for part in path.relative_to(ROOT / 'source').parts)
        and path.suffix not in SKIP_SUFFIXES and not path.name.endswith('.synctex.gz')
    }
    if set(source_hashes) != current_source_names:
        raise RuntimeError('Source manifest file inventory predates source changes')
    for name, expected in source_hashes.items():
        path = ROOT / 'source' / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('Source manifest predates source change: ' + name)
    smoke = json.loads((ROOT / 'reports/CLEAN_INSTALL_SMOKE.json').read_text())
    smoke_hashes = smoke.get('source_config_style_sha256', {})
    if (smoke.get('version') != VERSION or smoke.get('base') != BASE or
            not smoke_hashes or set(smoke.get('pdfs', {})) != {'PRINT', 'SCREEN'} or
            smoke.get('all_source_sha256') != source_hashes or
            smoke.get('all_source_files_match_before_and_after_build') is not True):
        raise RuntimeError('Clean-install proof must cover source hashes and both main PDFs')
    for name, expected in smoke_hashes.items():
        path = ROOT / 'source' / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError('Clean-install proof predates source change: ' + name)
    for profile, row in smoke.get('pdfs', {}).items():
        path = ROOT / 'pdf' / ('Universal_Book_Template_v1.0.13_' + profile + '.pdf')
        if sha(path.read_bytes()) != row.get('reference_sha256'):
            raise RuntimeError('Clean-install proof predates main PDF change: ' + profile)
    return selected


def content_manifest(hashes):
    return json.dumps({'version': VERSION, 'base': BASE, 'status': 'stable',
                       'scope': 'Verified template; Git publication is a separate step. No PDF/X certification claimed.',
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
                           'qa/work and icon baseline source snapshots', 'candidate and diagnostic trials',
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

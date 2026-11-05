#!/usr/bin/env python3
"""Build the independent v1.0.12 project; no Git or remote operations."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
sys.dont_write_bytecode = True


def environment(src=None):
    src = Path(src) if src is not None else SOURCE
    local = src / '.local'
    env = os.environ.copy()
    env.update({'TMPDIR': str(ROOT / 'runtime/tmp'), 'TMP': str(ROOT / 'runtime/tmp'),
                'TEMP': str(ROOT / 'runtime/tmp'), 'PYTHONDONTWRITEBYTECODE': '1',
                'FONTCONFIG_FILE': str(local / 'fontconfig.xml'),
                'OSFONTDIR': str(local / 'fonts'), 'TEXMFHOME': str(local / 'texmf'),
                'TEXMFVAR': str(local / 'texmf-var'),
                'TEXMFCONFIG': str(local / 'texmf-config'),
                'XDG_CACHE_HOME': str(local / 'cache'), 'TEXMFCACHE': str(local / 'cache/texmf')})
    return env


def prepare_source(src):
    src = Path(src)
    local = src / '.local'
    local.mkdir(exist_ok=True)
    for name in ('fonts', 'texmf', 'texmf-var'):
        link = local / name
        if link.is_symlink():
            link.unlink()
        if not link.exists():
            link.symlink_to(os.path.relpath(ROOT / 'runtime' / name, local), target_is_directory=True)
    for name in ('cache/fontconfig', 'texmf-config'):
        (local / name).mkdir(parents=True, exist_ok=True)
    directories = [local / 'fonts', Path('/usr/share/fonts/truetype/dejavu')]
    xml = '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>'
    xml += ''.join('<dir>' + escape(str(p)) + '</dir>' for p in directories if p.exists())
    xml += '<cachedir>' + escape(str(local / 'cache/fontconfig')) + '</cachedir></fontconfig>\n'
    (local / 'fontconfig.xml').write_text(xml)
    subprocess.run(['fc-cache', '--force'], env=environment(src), check=True, stdout=subprocess.DEVNULL)


def prepare():
    for name in ('pdf', 'logs', 'runtime/tmp', 'runtime/cache', 'runtime/texmf-config', 'runtime/texmf-var'):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    prepare_source(SOURCE)


def build(target, variant='A'):
    if variant != 'A':
        raise ValueError('The canonical source uses A; compile B in an isolated QA source or proof preamble.')
    log = ROOT / 'logs' / (target + '.log')
    with log.open('w') as stream:
        result = subprocess.run([sys.executable, 'scripts/build.py', target], cwd=SOURCE,
                                env=environment(), stdout=stream, stderr=subprocess.STDOUT)
    row = {'target': target, 'exit_code': result.returncode, 'log': str(log.relative_to(ROOT))}
    if result.returncode == 0 and target in ('screen', 'print2'):
        profile, folder, job = (('SCREEN', 'screen', 'Physics_A_Screen') if target == 'screen'
                                else ('PRINT', 'print', 'Physics_A_Print_Technical'))
        path = SOURCE / 'build' / folder / (job + '.pdf')
        dest = ROOT / 'pdf' / ('Universal_Book_Template_v1.0.12_' + profile + '.pdf')
        dest.write_bytes(path.read_bytes())
        row.update(pdf=str(dest.relative_to(ROOT)), sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    print(target, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--targets', nargs='+', default=['screen', 'print2'])
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    prepare()
    if args.prepare_only:
        return 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows = list(pool.map(build, args.targets))
    (ROOT / 'BUILD_RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n')
    return int(any(row['exit_code'] for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())

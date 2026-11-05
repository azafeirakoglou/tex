#!/usr/bin/env python3
"""Prepare the bundled v1.0.12 runtime; no downloads, Git or remote writes."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['TMPDIR'] = str(ROOT / 'runtime/tmp')


def main():
    needed = ['fc-cache', 'kpsewhich', 'fmtutil-user', 'xetex', 'xelatex', 'latexmk']
    missing = [name for name in needed if not shutil.which(name)]
    if missing:
        raise RuntimeError('Missing system tools: ' + ', '.join(missing) + '; see REPRODUCTION.md')
    if not (ROOT / 'source').is_dir():
        raise RuntimeError('Complete source/ directory is required')
    manifest = json.loads((ROOT / 'runtime/RUNTIME_MANIFEST.json').read_text())
    for name, expected in manifest['sha256'].items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Bundled dependency missing or altered: ' + name)
    from build_stable import prepare, environment
    prepare()
    log = ROOT / 'runtime/format-setup.log'
    with log.open('w') as stream:
        result = subprocess.run(['fmtutil-user', '--byfmt', 'xelatex', '--quiet'],
                                env=environment(), stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Local Greek XeLaTeX format failed; see ' + str(log))
    fmt = ROOT / 'runtime/texmf-var/web2c/xetex/xelatex.fmt'
    if not fmt.is_file():
        raise RuntimeError('fmtutil did not create the local XeLaTeX format')
    print('Verified bundled fonts, licenses and Greek hyphenation; local runtime ready.')
    print('Next: python3 build_stable.py --jobs 2')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('Setup failed: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)

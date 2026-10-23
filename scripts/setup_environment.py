#!/usr/bin/env python3
"""Prepare pinned fonts and Greek hyphenation in a checkout-local environment.

Downloads retain TLS validation and are verified against dependency-manifest.json.
No system files or TeX installations are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.sax.saxutils
import zipfile

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.local'
MANIFEST = Path(__file__).with_name('dependency-manifest.json')


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        'FONTCONFIG_FILE': str(LOCAL / 'fontconfig.xml'),
        'OSFONTDIR': str(LOCAL / 'fonts'),
        'TEXMFHOME': str(LOCAL / 'texmf'),
        'TEXMFVAR': str(LOCAL / 'texmf-var'),
        'TEXMFCONFIG': str(LOCAL / 'texmf-config'),
        'XDG_CACHE_HOME': str(LOCAL / 'cache'),
    })
    return env


def run(args: list[str], **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_if_changed(path: Path, data: bytes) -> None:
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def download(artifact: dict) -> Path:
    target = LOCAL / 'downloads' / artifact['name']
    if target.exists() and digest(target) == artifact['sha256']:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        pending = Path(tmp.name)
    try:
        run(['curl', '--fail', '--location', '--silent', '--show-error',
             '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '20',
             '--max-time', '180', artifact['url'], '--output', str(pending)])
        if digest(pending) != artifact['sha256']:
            raise RuntimeError(f"Checksum mismatch for {artifact['name']}; refusing artifact")
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target


def prepare_fonts(artifacts: dict[str, Path]) -> None:
    fonts = LOCAL / 'fonts'
    licenses = LOCAL / 'licenses'
    fonts.mkdir(parents=True, exist_ok=True)
    licenses.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifacts['Inter-4.1.zip']) as archive:
        for name in ['Regular', 'Italic', 'SemiBold', 'SemiBoldItalic', 'Medium']:
            filename = f'Inter-{name}.otf'
            write_if_changed(fonts / filename, archive.read('extras/otf/' + filename))
        write_if_changed(licenses / 'Inter-LICENSE.txt', archive.read('LICENSE.txt'))
    for name, path in artifacts.items():
        if name.endswith('.ttf'):
            shutil.copy2(path, fonts / name)
        elif name.endswith('-OFL.txt'):
            shutil.copy2(path, licenses / name)
    # All four Noto text faces are pinned; do not fall through to system versions.
    font_dirs = [str(fonts)]
    for location in ['/usr/share/fonts/truetype/dejavu',
                     '/usr/share/fonts/dejavu', '/usr/local/share/fonts']:
        if Path(location).is_dir():
            font_dirs.append(location)
    entries = ''.join('<dir>' + xml.sax.saxutils.escape(p) + '</dir>' for p in font_dirs)
    cache = xml.sax.saxutils.escape(str(LOCAL / 'cache' / 'fontconfig'))
    write_if_changed(LOCAL / 'fontconfig.xml', (
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
        '<fontconfig>' + entries + '<cachedir>' + cache + '</cachedir></fontconfig>\n'
        ).encode('utf-8'))
    run(['fc-cache', '--force'], env=runtime_env(), stdout=subprocess.DEVNULL)


def prepare_hyphenation(artifacts: dict[str, Path]) -> None:
    texmf = LOCAL / 'texmf'
    hyph = texmf / 'tex' / 'generic' / 'hyph-utf8'
    hyph.mkdir(parents=True, exist_ok=True)
    for name in ['loadhyph-el-monoton.tex', 'hyph-el-monoton.tex']:
        shutil.copy2(artifacts[name], hyph / name)
    # Preserve the base installation's languages, then add our language if absent.
    clean_env = os.environ.copy()
    for key in ['TEXMFHOME', 'TEXMFVAR', 'TEXMFCONFIG']:
        clean_env.pop(key, None)
    language_path = run(['kpsewhich', 'language.dat'], env=clean_env,
                        capture_output=True, text=True).stdout.strip()
    if not language_path:
        raise RuntimeError('TeX Live language.dat not found')
    text = Path(language_path).read_text()
    import re
    if not re.search(r'^\s*monogreek\s+', text, re.M):
        text += '\n% Template-local Unicode Greek patterns.\nmonogreek loadhyph-el-monoton.tex\n'
        if not re.search(r'^\s*(?:greek\s+|=greek\s*$)', text, re.M):
            text += '=greek\n'
    config = texmf / 'tex' / 'generic' / 'config'
    config.mkdir(parents=True, exist_ok=True)
    write_if_changed(config / 'language.dat', text.encode('utf-8'))
    for directory in ['texmf-var', 'texmf-config', 'cache']:
        (LOCAL / directory).mkdir(parents=True, exist_ok=True)
    # The local format is intentionally rebuilt when TeX versions/patterns change.
    stamp_payload = (text + run(['xetex', '--version'], capture_output=True,
                                text=True).stdout + digest(artifacts['hyph-el-monoton.tex']) +
                     digest(artifacts['loadhyph-el-monoton.tex']))
    stamp_value = hashlib.sha256(stamp_payload.encode()).hexdigest()
    stamp = LOCAL / 'xelatex-format.sha256'
    fmt = LOCAL / 'texmf-var' / 'web2c' / 'xetex' / 'xelatex.fmt'
    if not fmt.exists() or not stamp.exists() or stamp.read_text() != stamp_value:
        log = LOCAL / 'format-setup.log'
        with log.open('w') as output:
            try:
                run(['fmtutil-user', '--byfmt', 'xelatex', '--quiet'],
                    env=runtime_env(), stdout=output, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                raise RuntimeError(f'Local Greek XeLaTeX format failed; see {log}') from None
        if not fmt.exists():
            raise RuntimeError(f'fmtutil did not create {fmt}')
        stamp.write_text(stamp_value)


def setup() -> None:
    required = ['curl', 'fc-cache', 'kpsewhich', 'fmtutil-user', 'xetex', 'xelatex', 'latexmk']
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise RuntimeError('Missing system tools: ' + ', '.join(missing) + '; see SETUP.md')
    manifest = json.loads(MANIFEST.read_text())
    artifacts = {entry['name']: download(entry) for entry in manifest['artifacts']}
    prepare_fonts(artifacts)
    prepare_hyphenation(artifacts)
    print('Ready: pinned local fonts and Greek XeLaTeX format in .local/')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prepared files without downloading')
    args = parser.parse_args()
    try:
        if args.check:
            for p in [LOCAL / 'fontconfig.xml', LOCAL / 'fonts/STIXTwoMath-Regular.ttf',
                      LOCAL / 'texmf-var/web2c/xetex/xelatex.fmt']:
                if not p.exists():
                    raise RuntimeError(f'{p} missing; run make setup')
            print('Local build dependencies present')
        else:
            setup()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

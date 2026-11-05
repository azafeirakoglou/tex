#!/usr/bin/env python3
"""Bind final rebuilt callout PDFs to the previously viewed identical renders."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import fitz

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'qa/callouts'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = FOLDER / 'CALLOUT_VERIFICATION.json'
    report = json.loads(path.read_text())
    checked = []
    for profile, pages in report['actual_visual_views'].items():
        pdf = FOLDER / profile / ('callout-proof-' + profile.lower() + '.pdf')
        with fitz.open(pdf) as document:
            for number in pages:
                image = FOLDER / profile / f'p{number:02}.png'
                expected = fitz.Pixmap(str(image))
                actual = document[number - 1].get_pixmap(matrix=fitz.Matrix(report['matrix'], report['matrix']), alpha=False)
                assert (actual.width, actual.height, actual.n) == (expected.width, expected.height, expected.n)
                assert actual.samples == expected.samples, (profile, number)
                assert digest(image) == report['png_sha256'][str(image.relative_to(ROOT))]
                checked.append({'profile': profile, 'page': number})
        report['pdf_sha256'][profile] = digest(pdf)
    report['source_sha256'] = {name: digest(ROOT / name) for name in report['source_sha256']}
    report['canonical_config_style_sha256'] = {
        str(file.relative_to(ROOT / 'source')): digest(file)
        for folder in ('config', 'styles') for file in sorted((ROOT / 'source' / folder).glob('*'))
        if file.is_file()}
    report['final_rebuild_pixel_identity'] = {'status': 'passed',
        'checked_utc': datetime.now(timezone.utc).isoformat(), 'pages': checked,
        'meaning': 'Previously actually viewed PNGs are pixel-identical to the rebuilt final PDFs.'}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('PASS:', len(checked), 'reviewed callout pages are pixel-identical after final rebuild')


if __name__ == '__main__':
    raise SystemExit(main())

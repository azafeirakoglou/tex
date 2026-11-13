#!/usr/bin/env python3
"""Preflight all pages of the three dedicated v1.0.13 component pairs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import build_stable as build


def run(kind):
    if kind == 'refinement':
        files = {p: ROOT / 'qa/refinement/pdf' / ('REFINEMENT_' + p + '.pdf')
                 for p in ('PRINT', 'SCREEN')}
    else:
        name = 'material-proof.pdf' if kind == 'material' else 'icon-context.pdf'
        files = {p: ROOT / 'qa' / kind / p / name for p in ('PRINT', 'SCREEN')}
    report = ROOT / 'qa/components' / (kind + '.preflight.json')
    log = report.with_suffix('.log')
    with log.open('w') as stream:
        result = subprocess.run([sys.executable, str(build.SOURCE / 'scripts/validate_pdf.py'),
            '--print', str(files['PRINT']), '--screen', str(files['SCREEN']),
            '--map', str(build.SOURCE / 'config/color-map.json'), '--report', str(report), '--dpi', '72'],
            cwd=build.SOURCE, env=build.environment(), stdout=stream, stderr=subprocess.STDOUT)
    return {'kind': kind, 'exit_code': result.returncode, 'report': str(report.relative_to(ROOT))}


def main():
    (ROOT / 'qa/components').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run, ('refinement', 'material', 'icons')))
    (ROOT / 'qa/components/PREFLIGHT_RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(rows, indent=2))
    return int(any(row['exit_code'] for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())

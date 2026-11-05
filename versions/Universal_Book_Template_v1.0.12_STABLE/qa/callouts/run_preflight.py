#!/usr/bin/env python3
"""Run the all-page, five-plate preflight for both callout proofs."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import build_stable as driver


def main():
    folder = ROOT / 'qa/callouts'
    with (folder / 'PREFLIGHT.log').open('w') as stream:
        result = subprocess.run([sys.executable, str(driver.SOURCE / 'scripts/validate_pdf.py'),
            '--print', str(folder / 'PRINT/callout-proof-print.pdf'),
            '--screen', str(folder / 'SCREEN/callout-proof-screen.pdf'),
            '--map', str(driver.SOURCE / 'config/color-map.json'),
            '--report', str(folder / 'PREFLIGHT.json'), '--dpi', '72'],
            cwd=driver.SOURCE, env=driver.environment(), stdout=stream, stderr=subprocess.STDOUT)
    print('Callout paired preflight:', 'PASS' if result.returncode == 0 else 'FAIL')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())

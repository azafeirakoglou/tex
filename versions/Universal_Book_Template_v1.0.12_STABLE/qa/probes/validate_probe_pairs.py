#!/usr/bin/env python3
"""Apply each copied candidate's five-plate preflight to the QA fixture pairs."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('candidate_driver', ROOT / 'qa/driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def check(item):
    design, kind = item
    src = driver.source(design)
    folder = ROOT / 'qa/probes/pdf'
    output = ROOT / 'qa/probes/results' / (design + '_' + kind + '_pair.json')
    command = [sys.executable, str(src / 'scripts/validate_pdf.py'), '--print',
               str(folder / (design + '_print_' + kind + '.pdf')),
               '--screen', str(folder / (design + '_screen_' + kind + '.pdf')),
               '--map', str(src / 'config/color-map.json'), '--dpi', '72', '--report', str(output)]
    # These raw XeLaTeX review fixtures use the 170 x 240 mm MediaBox verified
    # by check_editorial_pdf.py. Explicit press TrimBox metadata is a separate
    # optional validator mode and is not part of the approved source profile.
    result = subprocess.run(command, env=driver.environment(src), cwd=src,
                            capture_output=True, text=True)
    output.with_suffix('.stdout').write_text(result.stdout + result.stderr)
    row = {'design': design, 'kind': kind, 'status': 'passed' if result.returncode == 0 else 'failed',
           'report': str(output), 'command': command}
    print(json.dumps(row), flush=True)
    return row


def main():
    rows = list(ThreadPoolExecutor(max_workers=2).map(check,
                [(d, k) for d in driver.DESIGNS for k in ('metrics', 'edges')]))
    (ROOT / 'qa/probes/PREFLIGHT_RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n')
    return 0 if all(x['status'] == 'passed' for x in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the complete 66-method suite against the canonical stable source."""
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('stable_driver', ROOT / 'build_stable.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def main():
    destination = ROOT / 'qa/suites'
    destination.mkdir(parents=True, exist_ok=True)
    logfile = destination / 'A.unittest.log'
    start = time.monotonic()
    with logfile.open('w') as stream:
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=driver.SOURCE, env=driver.environment(),
                                stdout=stream, stderr=subprocess.STDOUT)
    text = logfile.read_text()
    match = re.search(r'Ran (\d+) tests', text)
    report = {'variant': 'A', 'exit_code': result.returncode,
              'elapsed_seconds': round(time.monotonic() - start, 2),
              'log': str(logfile.relative_to(ROOT)),
              'tests_run': int(match.group(1)) if match else None,
              'skipped': len(re.findall(r'\.\.\. skipped ', text))}
    (destination / 'A.RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return int(result.returncode != 0 or report['tests_run'] != 66 or report['skipped'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())

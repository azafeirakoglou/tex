#!/usr/bin/env python3
"""Validate the book and every shipped sample pair, preserving each result."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from build import TARGETS
from setup_environment import ROOT

PAIRS = [('print2', 'screen'), ('sample-print2', 'sample-screen'),
         ('figures-print2', 'figures-screen'), ('assessment-print2', 'assessment-screen'),
         ('tables-print2', 'tables-screen'), ('opening-goals-print2', 'opening-goals-screen'),
         ('history-statements-print2', 'history-statements-screen'),
         ('callouts-print2', 'callouts-screen'), ('palette-print2', 'palette-screen')]


def pdf(target):
    _, jobname, directory = TARGETS[target]
    return ROOT / 'build' / directory / (jobname + '.pdf')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dpi', type=int, default=72)
    args = parser.parse_args()
    output = ROOT / 'build' / 'validation'
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for print_target, screen_target in PAIRS:
        report = output / (print_target + '.json')
        print('\nChecking ' + print_target + ' / ' + screen_target, flush=True)
        result = subprocess.run([
            sys.executable, str(ROOT / 'scripts' / 'validate_pdf.py'),
            '--print', str(pdf(print_target)), '--screen', str(pdf(screen_target)),
            '--map', str(ROOT / 'config/color-map.json'), '--report', str(report),
            '--dpi', str(args.dpi)], cwd=ROOT)
        results.append({'print_target': print_target, 'screen_target': screen_target,
                        'exit_code': result.returncode,
                        'report': str(report.relative_to(ROOT))})
    (output / 'suite.json').write_text(json.dumps(results, indent=2) + '\n')
    failed = [result for result in results if result['exit_code']]
    print(f"\n{len(results) - len(failed)}/{len(results)} PDF pairs passed")
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compile and inspect isolated editorial fixture PDFs for both candidates."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('candidate_driver', ROOT / 'qa/driver.py')
driver = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(driver)


def run_one(item):
    design, edition, kind = item
    src = driver.source(design)
    out = ROOT / 'runtime/tmp/editorial-probes' / design / edition / kind
    out.mkdir(parents=True, exist_ok=True)
    env = driver.environment(src)
    env['TEXINPUTS'] = str(HERE) + ':' + str(src) + '//:'
    job = 'editorial-' + kind + '-' + edition
    fixture = 'typography-metrics.tex' if kind == 'metrics' else 'editorial-probe-' + edition + '.tex'
    command = ['latexmk', '-xelatex', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-e', '$max_repeat = 8;', '-outdir=' + str(out),
               '-jobname=' + job]
    if kind == 'metrics' and edition == 'print':
        # Keep the public fixture unchanged; the edition switch precedes input.
        wrapper = out / 'metrics-print.tex'
        wrapper.write_text('\\def\\MetricsPrint{1}\\input{typography-metrics.tex}\n')
        command.append(str(wrapper))
    else:
        command.append(str(HERE / fixture))
    log = ROOT / 'qa/probes/results' / (design + '_' + edition + '_' + kind + '_build.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=src, env=env, stdout=stream, stderr=subprocess.STDOUT)
    row = dict(design=design, edition=edition, kind=kind, status='failed', build_log=str(log),
               output=str(out), pdf=str(out / (job + '.pdf')))
    if result.returncode == 0:
        # Keep compact QA evidence in the review package; aux trees stay temporary.
        durable = HERE / 'pdf' / (design + '_' + edition + '_' + kind + '.pdf')
        durable.parent.mkdir(exist_ok=True)
        shutil.copy2(row['pdf'], durable)
        row['pdf'] = str(durable)
        xetex_log = log.with_name(log.name.replace('_build.log', '_xelatex.log'))
        shutil.copy2(out / (job + '.log'), xetex_log)
        log_text = xetex_log.read_text(errors='replace')
        row['xelatex_log'] = str(xetex_log)
        row['diagnostics'] = {name: len(re.findall(pattern, log_text)) for name, pattern in {
            'overfull': r'Overfull \\[hv]box', 'underfull': r'Underfull \\[hv]box',
            'missing_characters': r'Missing character:', 'warnings': r'Warning:'}.items()}
        report = log.with_name(log.name.replace('_build.log', '.json'))
        check = subprocess.run([sys.executable, str(HERE / 'check_editorial_pdf.py'),
                                '--pdf', row['pdf'], '--kind', kind, '--report', str(report),
                                '--edition', edition, '--palette', str(src / 'config/color-map.json')],
                               cwd=src, env=env, capture_output=True, text=True)
        row['report'] = str(report)
        row['status'] = 'passed' if check.returncode == 0 else 'measurement_failed'
        if check.returncode:
            row['error'] = check.stdout[-1500:] + check.stderr[-1500:]
    print(json.dumps(row), flush=True)
    return row


def main():
    rows = list(ThreadPoolExecutor(max_workers=4).map(run_one,
        [(d, e, k) for d in driver.DESIGNS for e in ('screen', 'print') for k in ('metrics', 'edges')]))
    (ROOT / 'qa/probes/BUILD_RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n')
    return 0 if all(row['status'] == 'passed' for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())

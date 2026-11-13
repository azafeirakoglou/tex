#!/usr/bin/env python3
"""Compile same-content example A/B proof in both ink profiles."""
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
sys.path.insert(0, str(ROOT))
import build_stable as driver


def one(item):
    variant, profile = item
    out = ROOT / 'runtime/tmp/example-proofs' / variant / profile
    out.mkdir(parents=True, exist_ok=True)
    for kind, count in [('problem', 24), ('solution', 18)]:
        (out / ('long-' + kind + '-rows.tex')).write_text(''.join(
            'LONG' + kind.upper() + f'ROW{i:03d}\\quad\\StableProofParagraph\n'
            for i in range(1, count + 1)))
    tex = out / 'examples.tex'
    tex.write_text(r'\documentclass[11pt,twoside,openright]{book}' + '\n' +
        r'\def\BookExampleHeaderVariant{' + variant + '}\n' +
        r'\input{config/book-config.tex}' + '\n' +
        r'\newif\ifBookTwoInkProof\BookTwoInkProof' + ('true' if profile == 'PRINT' else 'false') + '\n' +
        r'\newif\ifPrintThreeInk\PrintThreeInkfalse\usepackage{styles/universalbook}' + '\n' +
        r'\begin{document}\input{examples-content.tex}' + '\n')
    env = driver.environment()
    env['TEXINPUTS'] = str(out) + ':' + str(HERE) + ':' + str(driver.SOURCE) + '//:'
    command = ['latexmk', '-xelatex', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-e', '$max_repeat = 8;', '-outdir=' + str(out), str(tex)]
    results = HERE / 'examples-results'; results.mkdir(exist_ok=True)
    log = results / (variant + '_' + profile + '.build.log')
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=driver.SOURCE, env=env, stdout=stream, stderr=subprocess.STDOUT)
    row = dict(variant=variant, profile=profile, exit_code=result.returncode,
               log=str(log.relative_to(ROOT)))
    if result.returncode == 0:
        pdf = HERE / 'pdf' / ('EXAMPLES_' + variant + '_' + profile + '.pdf')
        pdf.parent.mkdir(exist_ok=True)
        shutil.copy2(out / 'examples.pdf', pdf)
        xlog = results / (variant + '_' + profile + '.xelatex.log')
        shutil.copy2(out / 'examples.log', xlog)
        text = xlog.read_text(errors='replace')
        row.update(pdf=str(pdf.relative_to(ROOT)), xelatex_log=str(xlog.relative_to(ROOT)),
                   diagnostics={n: len(re.findall(p, text)) for n, p in {
                       'overfull': r'Overfull \\[hv]box', 'underfull': r'Underfull \\[hv]box',
                       'missing_characters': r'Missing character:', 'warnings': r'Warning:'}.items()})
    print(json.dumps(row), flush=True)
    return row


if __name__ == '__main__':
    rows = list(ThreadPoolExecutor(max_workers=4).map(one,
        [(v, p) for v in ('A', 'B') for p in ('SCREEN', 'PRINT')]))
    (HERE / 'EXAMPLES_BUILD_RESULTS.json').write_text(json.dumps(rows, indent=2) + '\n')
    raise SystemExit(any(r['exit_code'] for r in rows))

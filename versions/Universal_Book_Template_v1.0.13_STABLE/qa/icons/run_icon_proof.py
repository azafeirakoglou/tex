#!/usr/bin/env python3
"""Compile the same teaching-icon context against v1.0.12 and v1.0.13."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile

import fitz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('icon_build_driver', ROOT / 'build_stable.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_one(name, source, profile):
    output = HERE / name
    output.mkdir(exist_ok=True)
    env = build.environment(source)
    env['TEXINPUTS'] = str(source) + '//:'
    code = r'\input{' + str(HERE / ('icon-context-' + profile.lower() + '.tex')) + '}'
    for number in (1, 2):
        with (output / f'pass{number}.stdout').open('w') as stream:
            result = subprocess.run(['xelatex', '-interaction=nonstopmode', '-halt-on-error',
                                     '-file-line-error', '-output-directory=' + str(output),
                                     '-jobname=icon-context', code], cwd=source,
                                    env=env, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Icon proof failed: ' + name)
    pdf = output / 'icon-context.pdf'
    log = pdf.with_suffix('.log').read_text(errors='replace')
    assert not re.search(r'Overfull \\[hv]box|Underfull \\[hv]box|Missing character:', log), name
    with fitz.open(pdf) as doc:
        # Inter's pre-existing embedded PDF mapping represents the hyphen as
        # U+EE55. Normalize this exact known glyph, retaining strict markers.
        text = '\n'.join(page.get_text() for page in doc).replace('\uee55', '-')
        for marker in ('THINK', 'ATTENTION', 'HISTORY'):
            numbers = re.findall(r'\b' + marker + r'-(\d{2})\b', text)
            assert numbers == [f'{n:02}' for n in range(1, 15)], (name, marker, numbers)
        assert all(not page.get_images() for page in doc)
        for number in (1, 2, 3, 4, 5, 6, len(doc)):
            if number <= len(doc):
                doc[number - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(output / f'p{number:02}.png')
        return {'name': name, 'profile': profile, 'pdf': str(pdf.relative_to(ROOT)),
                'sha256': sha(pdf), 'pages': len(doc),
                'diagnostics': {'overfull': 0, 'underfull': 0, 'missing_characters': 0,
                                'warnings': [line.strip() for line in log.splitlines() if 'Warning:' in line]},
                'all_42_marked_paragraphs_once_in_order': True, 'all_vector': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-source', type=Path,
                        help='Optional previous source to copy for visual comparison; never modified')
    args = parser.parse_args()
    jobs = [('SCREEN', build.SOURCE, 'SCREEN'), ('PRINT', build.SOURCE, 'PRINT')]
    if args.baseline_source is not None:
        # A comparison is optional. The current package reproduces both new
        # proofs without the old workspace; an explicit old source is copied
        # into private temporary runtime state before font preparation.
        baseline = Path(tempfile.mkdtemp(prefix='icon-baseline-', dir=ROOT / 'runtime/tmp')) / 'source'
        shutil.copytree(args.baseline_source, baseline,
                        ignore=shutil.ignore_patterns('.local', 'build', '__pycache__', '.pytest_cache'))
        build.prepare_source(baseline)
        jobs.insert(0, ('BASELINE_SCREEN', baseline, 'SCREEN'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda job: compile_one(*job), jobs))
    (HERE / 'BUILD_RESULTS.json').write_text(json.dumps([r for r in rows if r['name'] != 'BASELINE_SCREEN'], ensure_ascii=False, indent=2) + '\n')
    baseline_rows = [r for r in rows if r['name'] == 'BASELINE_SCREEN']
    if baseline_rows:
        (HERE / 'BASELINE_RESULTS.json').write_text(json.dumps(baseline_rows, ensure_ascii=False, indent=2) + '\n')
    print('PASS:', [(row['name'], row['pages']) for row in rows])


if __name__ == '__main__':
    main()

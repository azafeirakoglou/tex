#!/usr/bin/env python3
"""Retain exact final XeLaTeX diagnostics for every public candidate target."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re

import fitz

ROOT = Path(__file__).resolve().parents[2]


def main():
    for design in ('A', 'B'):
        source = ROOT / 'qa/work' / design / 'source'
        module = ast.parse((source / 'scripts/build.py').read_text())
        targets = next(ast.literal_eval(node.value) for node in module.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(name, ast.Name) and name.id == 'TARGETS'
                               for name in node.targets))
        rows = []
        for target, (_, job, folder) in sorted(targets.items()):
            if target in ('screen', 'print2'):
                continue  # The two delivered main books belong to the canonical source.
            stem = source / 'build' / folder / job
            log = stem.with_suffix('.log')
            pdf = stem.with_suffix('.pdf')
            content = log.read_text(errors='replace')
            with fitz.open(pdf) as document:
                pages = len(document)
            rows.append({
                'target': target,
                'log': str(log.relative_to(ROOT)),
                'pdf': str(pdf.relative_to(ROOT)),
                'pages': pages,
                'overfull': len(re.findall(r'Overfull \\[hv]box', content)),
                'underfull': len(re.findall(r'Underfull \\[hv]box', content)),
                'missing_characters': len(re.findall(r'Missing character:', content)),
                'warnings': [line.strip() for line in content.splitlines()
                             if 'Warning:' in line],
                'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
                'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
            })
        output = ROOT / 'qa/compat' / design / 'build_log_audit.json'
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        print(design, len(rows), 'targets;', sum(r['overfull'] for r in rows),
              'overfull;', sum(r['underfull'] for r in rows), 'underfull;',
              sum(r['missing_characters'] for r in rows), 'missing characters')
    main_rows = []
    source = ROOT / 'source'
    for target in ('screen', 'print2'):
        _, job, folder = targets[target]
        stem = source / 'build' / folder / job
        log, pdf = stem.with_suffix('.log'), stem.with_suffix('.pdf')
        content = log.read_text(errors='replace')
        with fitz.open(pdf) as document:
            pages = len(document)
        main_rows.append({
            'target': target, 'log': str(log.relative_to(ROOT)),
            'pdf': str(pdf.relative_to(ROOT)), 'pages': pages,
            'overfull': len(re.findall(r'Overfull \\[hv]box', content)),
            'underfull': len(re.findall(r'Underfull \\[hv]box', content)),
            'missing_characters': len(re.findall(r'Missing character:', content)),
            'warnings': [line.strip() for line in content.splitlines() if 'Warning:' in line],
            'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
            'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
        })
    (ROOT / 'qa/main/BUILD_LOG_AUDIT.json').write_text(json.dumps(main_rows, ensure_ascii=False, indent=2) + '\n')
    print('Canonical main', len(main_rows), 'targets;', sum(r['overfull'] for r in main_rows),
          'overfull;', sum(r['underfull'] for r in main_rows), 'underfull;',
          sum(r['missing_characters'] for r in main_rows), 'missing characters')


if __name__ == '__main__':
    main()

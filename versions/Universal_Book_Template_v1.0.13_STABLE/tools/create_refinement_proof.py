#!/usr/bin/env python3
"""Gather the changed regions and controlled probes at native PDF page size."""
from pathlib import Path
import hashlib
import json
import fitz

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = fitz.open()
    toc, labels, rows, inputs = [], [], [], {}
    for profile in ('SCREEN', 'PRINT'):
        toc.append([1, profile, len(result) + 1])
        sections = [
            ('Main changed regions', ROOT / 'pdf' / f'Universal_Book_Template_v1.0.13_{profile}.pdf',
             [5, 6, 7, 9, 10, 11, 12, 15, 18, 19]),
            ('Rules, goals, answers and choices', ROOT / 'qa/refinement/pdf' / f'REFINEMENT_{profile}.pdf', None),
            ('Short and long material headers', ROOT / 'qa/material' / profile / 'material-proof.pdf', None),
            ('Teaching icons and broken boxes', ROOT / 'qa/icons' / profile / 'icon-context.pdf', None),
        ]
        for title, path, selected in sections:
            inputs[str(path.relative_to(ROOT))] = sha(path)
            toc.append([2, title, len(result) + 1])
            with fitz.open(path) as document:
                pages = selected if selected is not None else list(range(1, len(document) + 1))
                for number in pages:
                    original = document[number - 1]
                    assert abs(original.rect.width * 25.4 / 72 - 170) < .01
                    assert abs(original.rect.height * 25.4 / 72 - 240) < .01
                    index = len(result)
                    result.insert_pdf(document, from_page=number - 1, to_page=number - 1, links=False, annots=False)
                    toc.append([3, 'Original page ' + str(number), index + 1])
                    labels.append({'startpage': index, 'prefix': f'{profile} — {title} — {number}', 'style': ''})
                    rows.append({'proof_page': index + 1, 'source': str(path.relative_to(ROOT)),
                                 'source_page': number, 'profile': profile, 'scale': 1, 'overlays': False})
    result.set_toc(toc)
    result.set_page_labels(labels)
    result.set_metadata({'title': 'v1.0.13 — Modified regions and controlled proofs',
                         'subject': 'Native 170 × 240 mm; SCREEN then PRINT; proof only',
                         'creator': 'Universal Book Template'})
    output = ROOT / 'pdf/REFINEMENT_PROOF.pdf'
    result.save(output, garbage=4, deflate=True)
    result.close()
    with fitz.open(output) as proof:
        for row in rows:
            with fitz.open(ROOT / row['source']) as source:
                a = proof[row['proof_page'] - 1].get_pixmap(alpha=False)
                b = source[row['source_page'] - 1].get_pixmap(alpha=False)
                assert a.width == b.width and a.height == b.height and a.samples == b.samples, row
    report = {'status': 'passed', 'pdf': str(output.relative_to(ROOT)), 'sha256': sha(output),
              'pages': len(rows), 'page_mm': [170, 240], 'scale': 1,
              'all_pages_pixel_identical_to_sources_at_72dpi': True,
              'source_sha256': inputs, 'page_map': rows,
              'purpose': 'Mixed SCREEN/PRINT viewing proof, not the two-ink production PDF.'}
    (ROOT / 'reports/REFINEMENT_PROOF.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('PASS:', len(rows), 'native-size proof pages')


if __name__ == '__main__':
    main()

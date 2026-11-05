#!/usr/bin/env python3
"""Compare the identical A/B example fixtures at original page size."""
from pathlib import Path
import hashlib
import json
import fitz

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / 'pdf/EXAMPLE_HEADER_COMPARISON.pdf'
    combined = fitz.open()
    toc, labels, rows, hashes = [], [], [], {}
    for profile in ('SCREEN', 'PRINT'):
        paths = {v: ROOT / 'qa/probes/pdf' / f'EXAMPLES_{v}_{profile}.pdf' for v in ('A', 'B')}
        documents = {v: fitz.open(p) for v, p in paths.items()}
        assert len(documents['A']) == len(documents['B'])
        toc.append([1, profile, len(combined) + 1])
        for number in range(len(documents['A'])):
            toc.append([2, 'Original page ' + str(number + 1), len(combined) + 1])
            for variant in ('A', 'B'):
                document = documents[variant]
                page = document[number]
                assert abs(page.rect.width * 25.4 / 72 - 170) < .01
                assert abs(page.rect.height * 25.4 / 72 - 240) < .01
                index = len(combined)
                combined.insert_pdf(document, from_page=number, to_page=number, links=False, annots=False)
                toc.append([3, variant + ' — ' + profile, index + 1])
                labels.append({'startpage': index, 'prefix': f'{profile} {variant} p{number+1:02}', 'style': ''})
                rows.append({'comparison_page': index + 1, 'profile': profile, 'variant': variant,
                             'source_page': number + 1, 'scale': 1, 'overlays': False})
        for variant, document in documents.items():
            hashes[str(paths[variant].relative_to(ROOT))] = sha(paths[variant])
            document.close()
    combined.set_toc(toc)
    combined.set_page_labels(labels)
    combined.set_metadata({'title': 'v1.0.12 — Worked-example headers A / B, actual size',
                           'subject': 'Same sample content, alternating A/B at 170 × 240 mm',
                           'creator': 'Universal Book Template comparison helper'})
    combined.save(output, garbage=4, deflate=True)
    combined.close()
    with fitz.open(output) as result:
        for row in rows:
            path = ROOT / 'qa/probes/pdf' / f"EXAMPLES_{row['variant']}_{row['profile']}.pdf"
            with fitz.open(path) as source:
                actual = result[row['comparison_page'] - 1].get_pixmap(alpha=False)
                expected = source[row['source_page'] - 1].get_pixmap(alpha=False)
                assert actual.width == expected.width and actual.height == expected.height
                assert actual.samples == expected.samples, row
    report = {'status': 'passed', 'output': str(output.relative_to(ROOT)), 'sha256': sha(output),
              'pages': len(rows), 'page_mm': [170, 240], 'scale': 1,
              'source_sha256': hashes, 'page_map': rows,
              'all_pages_pixel_identical_to_sources_at_72dpi': True,
              'method': 'Direct page insertion without overlays; bookmarks and page labels identify A/B.'}
    (ROOT / 'reports/EXAMPLE_COMPARISON.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('PASS:', len(rows), 'unscaled A/B comparison pages')


if __name__ == '__main__':
    main()

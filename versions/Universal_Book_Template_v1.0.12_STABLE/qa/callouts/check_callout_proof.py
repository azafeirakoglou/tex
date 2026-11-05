#!/usr/bin/env python3
"""Measure actual multi-page callout PDF content, fonts and vector rules."""
from pathlib import Path
import hashlib
import json
import re

import fitz

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'qa/callouts'


def accent_strokes(page, profile):
    values = []
    for drawing in page.get_drawings():
        colour = drawing.get('color')
        if not colour:
            continue
        if profile == 'PRINT':
            matches = colour[0] > .9 and colour[1] < .3
        else:
            matches = max(abs(colour[i] - [32/255, 59/255, 99/255][i])
                          for i in range(3)) < .02
        if matches:
            values.append(drawing)
    return values


def measure(profile):
    path = D / profile / ('callout-proof-' + profile.lower() + '.pdf')
    with fitz.open(path) as document:
        texts = [page.get_text().replace('\uee55', '-') for page in document]
        text = '\n'.join(texts)
        checks = {'pages_are_13': len(document) == 13}
        fragments = {}
        for marker, first, width in [('THINK', 2, .8), ('ATTENTION', 6, 1),
                                     ('HISTORY', 10, .8)]:
            found = re.findall(marker + r'-(\d\d)\b', text)
            checks[marker + '_36_markers_once_ordered'] = found == [f'{i:02}' for i in range(1, 37)]
            pages = [i+1 for i, content in enumerate(texts)
                     if re.search(marker + r'-\d\d\b', content)]
            checks[marker + '_four_fragments'] = pages == list(range(first, first+4))
            counts = []
            west = []
            for page in pages:
                drawings = accent_strokes(document[page-1], profile)
                counts.append(len(drawings))
                rules = [drawing for drawing in drawings
                         if drawing['rect'].width < .01
                         and drawing['rect'].height > 100
                         and abs(drawing['width'] - width*72/72.27) < .01]
                west.append(len(rules) == 1)
            checks[marker + '_one_west_rule_each_fragment'] = all(west)
            checks[marker + '_icon_only_first_fragment'] = (counts[0] > 1 and
                                                            counts[1:] == [1, 1, 1])
            fragments[marker] = {'pages': pages, 'accent_drawing_counts': counts}
        spans = [span for block in document[0].get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        metrics = {}
        for label in ['Πώς σκέφτομαι', 'ΠΡΟΣΟΧΗ', 'Ιστορίες από τη Φυσική']:
            values = [span for span in spans if span['text'].startswith(label)]
            checks[label + '_font'] = (len(values) == 1 and values[0]['font'] == 'Inter-Medium'
                                      and abs(values[0]['size']*72.27/72 - 9.5) < .012)
            if values:
                metrics[label] = {'font': values[0]['font'],
                                  'size_tex_pt': values[0]['size']*72.27/72}
    return {'profile': profile, 'pdf': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'status': 'passed' if all(checks.values()) else 'failed',
            'checks': checks, 'fragments': fragments, 'title_metrics': metrics}


if __name__ == '__main__':
    rows = [measure(profile) for profile in ['SCREEN', 'PRINT']]
    (D / 'MEASUREMENTS.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    for row in rows:
        print(row['profile'], row['status'].upper())
    raise SystemExit(any(row['status'] != 'passed' for row in rows))

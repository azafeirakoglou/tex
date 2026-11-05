#!/usr/bin/env python3
"""Measure editorial roles and pagination in independently compiled QA PDFs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import fitz

PT_TO_BP = 72 / 72.27
MM_TO_BP = 72 / 25.4


def page_spans(page):
    return [s for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for s in line['spans']]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def marker_span(pdf, marker, font=None, size=None):
    matches = [(i, s) for i, p in enumerate(pdf) for s in page_spans(p)
               if marker in s['text'] and (size is None or abs(s['size'] - size * PT_TO_BP) < .012)]
    require(len(matches) == 1, f'{marker}: expected one matching span, got {matches}')
    index, span = matches[0]
    if font:
        require(span['font'] == font, f'{marker}: expected {font}, got {span["font"]}')
    return index, span


def measure_metrics(pdf, expected_caption_color=None):
    roles = {}
    expected = {
        'BODYTITLEMETRIC': ('NotoSerif-Medium', 17.5),
        'ΚΕΦΑΛΑΙΟ 1': ('Inter-Medium', 9.5),
        'SECTIONMETRIC': ('NotoSerif-Medium', 13),
        'SUBSECTIONMETRIC': ('NotoSerif-Medium', 11),
        'THEMATICMETRIC': ('NotoSerif-Medium', 11.7),
        'BODYMETRIC': ('Inter-Regular', 10.95),
        'ATTENTIONBODYMETRIC': ('Inter-Regular', 10),
        'THINKBODYMETRIC': ('Inter-Regular', 10),
        'HISTORYBODYMETRIC': ('Inter-Regular', 10),
        'EXAMPLETITLEMETRIC': ('NotoSerif-Medium', 10.7),
        'CAPTIONMETRIC': ('Inter-Regular', 9.5),
        'TABLECAPMETRIC': ('Inter-Regular', 9.5),
        'DIAGRAMLABELMETRIC': ('Inter-Regular', 9.5),
        'TICKMETRIC': ('Inter-Regular', 8.5),
        'Quantity': ('Inter-SemiBold', 10),
        'Value': ('Inter-SemiBold', 10),
        'Position': ('Inter-Regular', 10),
        'ΠΡΟΣΟΧΗ': ('Inter-Medium', 9.5),
        'Πώς σκέφτομαι': ('Inter-Medium', 9.5),
        'HISTORYTITLEMETRIC': ('Inter-Medium', 9.5),
        'Λύση': ('Inter-Medium', 10.2),
    }
    for marker, (font, size) in expected.items():
        # BODYMETRIC is a suffix of the three callout body markers.
        matches = [(i, s) for i, p in enumerate(pdf) for s in page_spans(p)
                   if marker in s['text'] and (marker != 'BODYMETRIC'
                                             or s['text'].strip() == marker)]
        if marker == 'BODYMETRIC':
            require(len(matches) == 1, f'{marker}: expected one exact span')
            i, span = matches[0]
            require(span['font'] == font and abs(span['size'] - size * PT_TO_BP) < .012,
                    f'{marker}: incorrect body font/size: {span}')
        else:
            i, span = marker_span(pdf, marker, font, size)
        roles[marker] = {'page': i + 1, 'font': span['font'],
                         'size_tex_pt': round(span['size'] / PT_TO_BP, 4),
                         'rendered_rgb_hex': f'{span["color"]:06X}'}
        if marker in ('CAPTIONMETRIC', 'TABLECAPMETRIC') and expected_caption_color is not None:
            require(span['color'] == 0,
                    f'{marker}: v1.0.12 caption description must be neutral black')
    math = {}
    for marker, base in [('BODYMETRIC', 10.95), ('ATTENTIONBODYMETRIC', 10),
                         ('THINKBODYMETRIC', 10), ('HISTORYBODYMETRIC', 10),
                         ('DIAGRAMLABELMETRIC', 9.5), ('TICKMETRIC', 8.5)]:
        i = roles[marker]['page'] - 1
        marker = next(s for s in page_spans(pdf[i])
                      if marker in s['text'] and (marker != 'BODYMETRIC'
                                                 or s['text'].strip() == marker))
        stix = [s for s in page_spans(pdf[i]) if s['font'] == 'STIXTwoMath-Regular'
                and abs(s['origin'][1] - marker['origin'][1]) < .15
                and s['bbox'][0] >= marker['bbox'][2] - .2]
        require(stix, f'No math next to {marker["text"]}')
        actual = max(s['size'] for s in stix) / PT_TO_BP
        require(abs(actual - base * 1.05) < .012,
                f'{marker["text"]}: math {actual}pt differs from {base} × 1.05')
        math[marker['text'].strip()] = round(actual, 4)
    index, display_marker = marker_span(pdf, 'DISPLAYMETRIC')
    display = [s for s in page_spans(pdf[index]) if s['font'] == 'STIXTwoMath-Regular'
               and display_marker['bbox'][3] < s['bbox'][1] < display_marker['bbox'][3] + 85]
    require(display, 'Display formula is missing')
    normal_math = [s for s in display if any(c in 'xαβγ' for c in unicodedata.normalize('NFKC', s['text']))
                   and abs(s['origin'][1] - display[0]['origin'][1]) < .15]
    require(normal_math and all(abs(s['size'] / PT_TO_BP - 10.95 * 1.05) < .012
                               for s in normal_math),
            'Display base letters must use the same 105% math scale as inline body math')
    headers = [s for p in pdf for s in page_spans(p)
               if s['bbox'][1] < 40 and s['text'] == 'Μετρικά']
    footers = [s for p in pdf for s in page_spans(p)
               if s['bbox'][1] > 640 and s['text'].strip().isdigit()]
    require(headers and footers and all(s['font'] == 'Inter-Regular'
            and abs(s['size'] / PT_TO_BP - 8) < .012 for s in headers + footers),
            'Running header and footer must retain Inter Regular 8pt')
    # Only the numbered prefix keeps the second ink; descriptions are black.
    for key in ('CAPTIONMETRIC', 'TABLECAPMETRIC'):
        page = pdf[roles[key]['page'] - 1]
        marker = next(x for x in page_spans(page) if key in x['text'])
        prefix = [x for x in page_spans(page) if x['font'] == 'Inter-SemiBold'
                  and abs(x['origin'][1] - marker['origin'][1]) < .1
                  and x['bbox'][2] <= marker['bbox'][0] + .2]
        require(prefix, key + ': numbered SemiBold prefix is missing')
        if expected_caption_color is not None:
            require(all(x['color'] == expected_caption_color for x in prefix),
                    key + ': prefix must retain existing BookSecondary')
        require(marker['color'] == 0, key + ': description must be black')
    # Header cells use the existing neutral 10% black surface, never a solid spot fill.
    qpage = pdf[roles['Quantity']['page'] - 1]
    q = next(x for x in page_spans(qpage) if x['text'] == 'Quantity')
    point = fitz.Point((q['bbox'][0]+q['bbox'][2])/2, (q['bbox'][1]+q['bbox'][3])/2)
    cells = [x for x in qpage.get_drawings() if x.get('fill') is not None and x['rect'].contains(point)]
    require(cells and min(cells, key=lambda x:x['rect'].get_area())['fill'][0] > .89,
            'Table header must have light neutral background')
    require(q['color'] == 0 and roles['Value']['rendered_rgb_hex'] == '000000',
            'Table header text must remain black')
    rules = [x for x in qpage.get_drawings() if (x.get('fill') is not None or x.get('color') is not None)
             and x['rect'].width > 50 and x['rect'].height < 1
             and q['bbox'][1]-12 < x['rect'].y0 < q['bbox'][1]+2
             and any(c is not None and max(c)-min(c) > .05 for c in (x.get('fill'),x.get('color')))]
    require(rules, 'Table header must retain its thin second-ink rule')
    return {'font_roles': roles, 'math_base_sizes_tex_pt': math,
            'running_header_and_footer_tex_pt': 8,
            'display_uses_same_base_math_size': True}


def measure_edges(pdf, expected_caption_color=None):
    texts = [p.get_text() for p in pdf]
    joined = '\n'.join(texts)
    require('??' not in joined, 'An unresolved reference remains')
    result = {'callouts': {}, 'captions': {}}
    result['chapter_starts'] = {}
    for number, kind in enumerate(('PARAGRAPH', 'SECTION', 'CALLOUT'), 1):
        starts = [i for i, text in enumerate(texts) if kind + 'START' in text]
        nexts = [i for i, text in enumerate(texts) if kind + 'NEXT' in text]
        labels = [(i, s) for i, p in enumerate(pdf) for s in page_spans(p)
                  if s['text'].strip() == 'ΚΕΦΑΛΑΙΟ ' + str(number)]
        require(len(starts) == len(nexts) == len(labels) == 1
                and starts[0] == labels[0][0] and starts[0] < nexts[0],
                f'{kind}: body chapter label must occur only at the first body page')
        title_spans = [s for s in page_spans(pdf[starts[0]])
                       if s['font'] == 'NotoSerif-Medium'
                       and abs(s['size'] / PT_TO_BP - 17.5) < .012]
        require(title_spans and all('ΚΕΦΑΛΑΙΟ' not in texts[i] for i in nexts),
                f'{kind}: 17.5pt title missing or body heading repeated')
        require('ΕΝΟΤΗΤΑ ' + str(number) in texts[starts[0] - 1],
                f'{kind}: opening page must remain separate with its original label')
        result['chapter_starts'][kind.lower()] = {
            'opening_page': starts[0], 'body_page': starts[0] + 1,
            'following_page': nexts[0] + 1, 'title_tex_pt': 17.5,
            'body_label_count': 1, 'title_lines': len(title_spans)}
    for kind in ('THINK', 'ATTENTION', 'HISTORY'):
        begins = [i for i, text in enumerate(texts) if 'PROBE' + kind + 'BEGIN' in text]
        ends = [i for i, text in enumerate(texts) if 'PROBE' + kind + 'END' in text]
        require(len(begins) == len(ends) == 1 and begins[0] < ends[0],
                f'{kind}: missing or duplicated begin/end')
        rows = re.findall('PROBE' + kind + r'ROW(\d{3})', joined)
        require(rows == [f'{i:03d}' for i in range(1, 37)], f'{kind}: paragraph loss/repetition')
        occupied = list(range(begins[0], ends[0] + 1))
        require(len(occupied) >= 3, f'{kind}: probe must exercise at least three fragments')
        icon_counts = []
        for index in occupied:
            page = pdf[index]
            left = (20 if (index + 1) % 2 else 17) * MM_TO_BP
            gutter_right = left + 17.5 * MM_TO_BP
            icons = [d for d in page.get_drawings()
                     if (d.get('color') or d.get('fill')) and d['rect'].y0 > 45
                     and d['rect'].x0 > left + 2 and d['rect'].x1 < gutter_right - 2
                     and (d['rect'].width > .1 or d['rect'].height > .1)]
            icon_counts.append(len(icons))
        require(icon_counts[0] >= 3 and not any(icon_counts[1:]),
                f'{kind}: icon must occur only in the first fragment: {icon_counts}')
        west_counts = []
        for index in occupied:
            page = pdf[index]
            left = (20 if (index + 1) % 2 else 17) * MM_TO_BP
            right = left + 133 * MM_TO_BP
            side_paths = [d for d in page.get_drawings()
                          if d['rect'].y0 > 45 and d['rect'].height > 25
                          and d['rect'].width < 2
                          and any(c is not None and max(c)-min(c) > .05
                                  for c in (d.get('color'), d.get('fill'))) ]
            west = [d for d in side_paths if abs(d['rect'].x0-left) < 3]
            east = [d for d in side_paths if abs(d['rect'].x0-right) < 3]
            require(west and not east, f'{kind}: each fragment needs only a thin west rule')
            horizontal = [d for d in page.get_drawings()
                          if d['rect'].y0 > 45 and d['rect'].width > 200
                          and d['rect'].height < 2
                          and any(c is not None and max(c)-min(c) > .05
                                  for c in (d.get('color'), d.get('fill'))) ]
            require(not horizontal, f'{kind}: top/bottom accent border remains')
            west_counts.append(len(west))
        result['callouts'][kind.lower()] = {'west_rules_by_fragment': west_counts,
                                           'no_east_top_bottom_rule': True,
                                           'pages': [i + 1 for i in occupied],
                                           'paragraphs': len(rows),
                                           'icon_paths_by_fragment': icon_counts}
        if kind == 'THINK':
            math = [s for i in occupied for s in page_spans(pdf[i])
                    if s['font'] == 'STIXTwoMath-Regular']
            require(math and all(min(abs(s['size'] / PT_TO_BP - n) for n in (10.5, 7.35))
                    < .012 for s in math), 'Long Think math must use 10pt × 1.05 with 70% scripts')
            symbols = ''.join(s['text'] for s in math)
            require(all(c in symbols for c in ('√', '∑', '∫', '𝑥', '𝜎')),
                    'Long Think fixture must retain Greek/Latin, roots, sums and integrals')
            result['callouts']['think']['math_sizes_tex_pt'] = [10.5, 7.35]
    short_index, short = marker_span(pdf, 'THINKSHORTBEGIN')
    short_math = [s for s in page_spans(pdf[short_index]) if s['font'] == 'STIXTwoMath-Regular'
                  and abs(s['origin'][1] - short['origin'][1]) < .15]
    require(short_math and max(abs(s['size'] / PT_TO_BP - 10.5) for s in short_math) < .012,
            'Short Think inline math must use 10pt × 1.05')
    result['callouts']['short_think'] = {'page': short_index + 1, 'math_tex_pt': 10.5}
    rows = re.findall(r'PROBETABLEROW(\d{3})', joined)
    require(rows == [f'{i:03d}' for i in range(1, 121)], 'Long-table rows lost/repeated')
    table_pages = [i for i, text in enumerate(texts) if 'PROBETABLEROW' in text]
    require(len(table_pages) >= 3, 'Long table must occupy at least three pages')
    require(all('PROBETABLEHEAD' in texts[i] for i in table_pages), 'Long table loses repeated heads')
    result['long_table'] = {'pages': [i + 1 for i in table_pages], 'rows': 120,
                            'repeated_header': True}
    for prefix in ('FIGCAP', 'TABLECAP', 'LONGCAP'):
        begins = [i for i, text in enumerate(texts) if prefix + 'BEGIN' in text]
        ends = [i for i, text in enumerate(texts) if prefix + 'END' in text]
        require(len(begins) == len(ends) == 1 and begins == ends,
                f'{prefix}: caption must be intact on one page')
        page = pdf[begins[0]]
        first = next(s for s in page_spans(page) if prefix + 'BEGIN' in s['text'])
        last = next(s for s in page_spans(page) if prefix + 'END' in s['text'])
        caption_spans = [s for s in page_spans(page)
                         if first['bbox'][1] - .1 <= s['bbox'][1] <= last['bbox'][1] + .1]
        require(last['origin'][1] > first['origin'][1] + 5, f'{prefix}: caption must wrap')
        require(all(s['font'] == 'Inter-Regular' for s in caption_spans
                    if not s['text'].startswith(('Σχήμα', 'Πίνακας'))),
                f'{prefix}: descriptive caption text must use Inter Regular')
        require(all(abs(s['size'] / PT_TO_BP - 9.5) < .012 for s in caption_spans),
                f'{prefix}: every caption span must measure 9.5pt')
        if expected_caption_color is not None:
            require(all(s['color'] == (expected_caption_color if s['font'] == 'Inter-SemiBold' else 0) for s in caption_spans),
                    f'{prefix}: only the prefix/number may use BookSecondary; descriptions must remain black')
        continuation = [s for s in caption_spans if s['origin'][1] > first['origin'][1] + 2]
        first_word = next(w for w in page.get_text('words') if prefix + 'BEGIN' in w[4])
        # PDF spans retain the separator space; compare the actual first word.
        # Microtype margin protrusion can shift the outermost glyph by <0.5 bp.
        require(continuation and all(abs(s['bbox'][0] - first_word[0]) < .5 for s in continuation),
                f'{prefix}: wrapped text loses its hanging alignment')
        result['captions'][prefix] = {'page': begins[0] + 1,
                                      'lines': len(set(round(s['origin'][1], 2) for s in caption_spans)),
                                      'font': 'Inter-Regular', 'size_tex_pt': 9.5,
                                      'rendered_rgb_hex': f'{first["color"]:06X}',
                                      'hanging_alignment': True}
    mark = [(i, s) for i, p in enumerate(pdf) for s in page_spans(p)
            if 'AFTERLONGTABLEBLACK' in s['text']]
    require(len(mark) == 1 and mark[0][1]['color'] == 0, 'Table color leaks into following text')
    figure_index = next(i for i, text in enumerate(texts) if 'FIGCAPBEGIN' in text)
    figure_page = pdf[figure_index]
    caption_top = min(s['bbox'][1] for s in page_spans(figure_page)
                      if 'FIGCAPBEGIN' in s['text'])
    diagram_paths = [d for d in figure_page.get_drawings()
                     if 50 < d['rect'].y0 and d['rect'].y1 < caption_top
                     and d.get('color') is not None and d.get('fill') is None]
    horizontal = [d for d in diagram_paths if d['rect'].width > 50 and d['rect'].height < .2]
    vertical = [d for d in diagram_paths if d['rect'].height > 50 and d['rect'].width < .2]
    curves = [d for d in diagram_paths if d['rect'].width > 80 and d['rect'].height > 30]
    require(horizontal and vertical and curves,
            'Physics diagram must retain vector horizontal/vertical axes and data line')
    require(not figure_page.get_images(), 'Vector-only diagram page contains a raster image')
    result['vector_figure'] = {'page': figure_index + 1, 'horizontal_axes': len(horizontal),
                               'vertical_axes': len(vertical), 'data_paths': len(curves),
                               'raster_images': 0}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--kind', choices=['metrics', 'edges'], required=True)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--edition', choices=['screen', 'print'])
    parser.add_argument('--palette', type=Path)
    args = parser.parse_args()
    report = {'status': 'failed', 'pdf': str(args.pdf), 'kind': args.kind,
              'input_sha256': hashlib.sha256(args.pdf.read_bytes()).hexdigest()}
    try:
        expected_caption_color = None
        if args.edition == 'screen' and args.palette:
            palette = json.loads(args.palette.read_text())
            color = palette['colors'][palette['semantic']['BookSecondary']]
            base = palette['screen_base_hex'][color['print_ink']].lstrip('#')
            amount = color['tint'] / 100
            rgb = [round(int(base[i:i + 2], 16) * amount + 255 * (1 - amount))
                   for i in (0, 2, 4)]
            expected_caption_color = rgb[0] * 65536 + rgb[1] * 256 + rgb[2]
            report['expected_caption_role'] = 'BookSecondary'
            report['expected_caption_rgb_hex'] = f'{expected_caption_color:06X}'
        with fitz.open(args.pdf) as pdf:
            require(all(abs(p.rect.width / MM_TO_BP - 170) < .02
                        and abs(p.rect.height / MM_TO_BP - 240) < .02 for p in pdf),
                    'A page differs from the required 170 × 240mm trim size')
            report['pages'] = len(pdf)
            report['measurements'] = (measure_metrics(pdf, expected_caption_color) if args.kind == 'metrics'
                                      else measure_edges(pdf, expected_caption_color))
        report['status'] = 'passed'
    except (AssertionError, RuntimeError, ValueError, StopIteration) as exc:
        report['error'] = str(exc)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

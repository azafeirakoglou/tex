#!/usr/bin/env python3
"""Compile and measure controlled tables/captions against the final source."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

import fitz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('table_probe_build', ROOT / 'build_stable.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
PT = 72 / 72.27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_profile(profile):
    out = HERE / profile
    out.mkdir(exist_ok=True)
    environment = BUILD.environment()
    environment['TEXINPUTS'] = str(BUILD.SOURCE) + '//:'
    code = (r'\def\ProbePrint{1}' if profile == 'PRINT' else '')
    code += r'\input{' + str(HERE / 'table-caption-probe.tex') + '}'
    for number in (1, 2):
        with (out / f'pass{number}.stdout').open('w') as stream:
            result = subprocess.run([
                'xelatex', '-interaction=nonstopmode', '-halt-on-error',
                '-file-line-error', '-output-directory=' + str(out),
                '-jobname=table-caption-probe', code], cwd=BUILD.SOURCE,
                env=environment, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            return dict(profile=profile, status='failed', pass_number=number)
    return dict(profile=profile, status='passed',
                pdf=str((out / 'table-caption-probe.pdf').relative_to(ROOT)))


def spans(page):
    return [span for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for span in line['spans']]


def analyze(profile):
    path = HERE / profile / 'table-caption-probe.pdf'
    log = path.with_suffix('.log').read_text(errors='replace')
    checks = {}
    measurements = {'caption_blocks': [], 'table_pages': []}
    with fitz.open(path) as document:
        text = '\n'.join(page.get_text() for page in document)
        row_numbers = [int(number) for number in re.findall(r'\bROW(\d{3})\b', text)]
        checks['all_120_data_rows_once_in_order'] = row_numbers == list(range(1, 121))
        checks['caption_numbers_and_references_resolve'] = (
            'Figure 1.1' in text and 'table 1.1, long table 1.2' in text
            and '??' not in text)
        checks['native_170x240_page_geometry'] = all(
            abs(page.rect.width * 25.4 / 72 - 170) < .01 and
            abs(page.rect.height * 25.4 / 72 - 240) < .01 for page in document)
        checks['no_raster_images_in_controlled_vector_fixture'] = all(
            not page.get_images() for page in document)
        table_pages = [page for page in document if re.search(r'\bROW\d{3}\b', page.get_text())]
        checks['longtable_spans_at_least_three_pages'] = len(table_pages) >= 3
        checks['every_data_page_repeats_its_header'] = all(
            len(page.search_for('LONGHEADER')) == 1 for page in table_pages)
        checks['caption_is_not_repeated_with_continuation_header'] = text.count('CAPTIONLONG') == 1
        all_spans = [span for page in document for span in spans(page)]
        headers = [span for span in all_spans if span['text'] in
                   ('HEADERONE', 'SYMBOL', 'UNIT', 'PLAINHEADER', 'PLAINUNIT',
                    'LONGHEADER', 'VARIABLE', 'SIUNIT')]
        body = [span for span in all_spans if re.fullmatch(
            r'(BODY(?:ONE|TWO|THREE)|PLAIN[AB]|ROW\d{3})', span['text'])]
        checks['all_header_text_Inter_SemiBold_10_black'] = bool(headers) and all(
            span['font'] == 'Inter-SemiBold' and abs(span['size'] / PT - 10) < .012
            and span['color'] == 0 for span in headers)
        checks['all_table_body_text_Inter_Regular_10_black'] = len(body) == 125 and all(
            span['font'] == 'Inter-Regular' and abs(span['size'] / PT - 10) < .012
            and span['color'] == 0 for span in body)
        checks['normal_body_font_and_black_restored_after_tables'] = all(
            span['font'] == 'Inter-Regular' and abs(span['size'] / PT - 10.95) < .012
            and span['color'] == 0 for span in all_spans
            if span['text'].startswith(('AFTERSHORT', 'AFTERLONG')))

        caption_flags = []
        for marker in ('CAPTIONFIG', 'CAPTIONTABLE', 'CAPTIONLONG'):
            matches = [(page, block) for page in document
                       for block in page.get_text('dict')['blocks']
                       if any(marker in span['text'] for line in block.get('lines', [])
                              for span in line['spans'])]
            if len(matches) != 1:
                caption_flags.append(False)
                continue
            page, block = matches[0]
            lines = block['lines']
            label, *first_description = lines[0]['spans']
            descriptions = first_description + [span for line in lines[1:] for span in line['spans']]
            marker_word = next(word for word in page.get_text('words') if marker in word[4])
            continuation_x = [line['bbox'][0] for line in lines[1:]]
            flag = (len(lines) >= 3 and label['font'] == 'Inter-SemiBold'
                    and label['color'] != 0 and abs(label['size'] / PT - 9.5) < .012
                    and all(span['font'] == 'Inter-Regular' and span['color'] == 0
                            and abs(span['size'] / PT - 9.5) < .012 for span in descriptions)
                    and all(abs(x - marker_word[0]) < .03 for x in continuation_x))
            if profile == 'SCREEN':
                flag = flag and label['color'] == 0x8493A9
            measurements['caption_blocks'].append(dict(marker=marker, page=page.number + 1,
                lines=len(lines), label_font=label['font'],
                label_rgb_hex=f"{label['color']:06X}", description_rgb_hex='000000',
                size_tex_pt=round(label['size'] / PT, 4),
                hanging_x_bp=round(marker_word[0], 4), continuation_x_bp=continuation_x,
                passed=flag))
            caption_flags.append(flag)
        checks['figure_table_longtable_captions_share_correct_hanging_fonts_and_roles'] = all(caption_flags)

        surface_flags = []
        for page in document:
            header_markers = page.search_for('HEADERONE') + page.search_for('PLAINHEADER') + page.search_for('LONGHEADER')
            if not header_markers:
                continue
            drawings = page.get_drawings()
            for header in header_markers:
                backgrounds = [drawing for drawing in drawings if drawing.get('fill') is not None
                    and drawing['rect'].contains(header.tl + (header.br - header.tl) * .5)
                    and drawing['rect'].height > 5]
                gray = [drawing for drawing in backgrounds
                    if max(drawing['fill']) - min(drawing['fill']) < .003
                    and abs(sum(drawing['fill']) / len(drawing['fill']) - .9) < .004]
                rules = [drawing for drawing in drawings if drawing.get('color') is not None
                    and drawing['rect'].width > 300 and drawing['rect'].height < .1
                    and 0 < header.y0 - drawing['rect'].y0 < 30
                    and abs(drawing['width'] / PT - .35) < .012
                    and max(drawing['color']) - min(drawing['color']) > .1]
                surface_flags.append(bool(gray) and len(rules) == 1)
                measurements['table_pages'].append(dict(page=page.number + 1,
                    header_y_bp=header.y0, neutral_gray_header=bool(gray),
                    thin_accent_top_rules=len(rules)))
        checks['headers_have_only_Black10_fill_and_point35_accent_top_rule'] = bool(surface_flags) and all(surface_flags)
        checks['no_overfull_underfull_missing_or_warning'] = not re.search(
            r'Overfull \\[hv]box|Underfull \\[hv]box|Missing character:|Warning:', log)
        return dict(profile=profile, pdf=str(path.relative_to(ROOT)), sha256=sha(path),
                    pages=len(document), checks=checks, measurements=measurements,
                    status='passed' if all(checks.values()) else 'failed')


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        builds = list(pool.map(compile_profile, ('SCREEN', 'PRINT')))
    (HERE / 'BUILD_RESULTS.json').write_text(json.dumps(builds, indent=2) + '\n')
    if any(row['status'] != 'passed' for row in builds):
        print(json.dumps(builds, indent=2))
        return 1
    results = [analyze(profile) for profile in ('SCREEN', 'PRINT')]
    result = dict(status='passed' if all(row['status'] == 'passed' for row in results) else 'failed',
                  profiles=results,
                  source_sha256={str(path.relative_to(BUILD.SOURCE)): sha(path)
                      for folder in ('config', 'styles')
                      for path in sorted((BUILD.SOURCE / folder).glob('*')) if path.is_file()})
    (HERE / 'TABLE_PROBE_RESULTS.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'].upper())
    for row in results:
        print(row['profile'], row['pages'], 'pages;',
              [key for key, passed in row['checks'].items() if not passed])
    return int(result['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

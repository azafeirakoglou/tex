#!/usr/bin/env python3
"""Compile and measure the shared v1.0.13 material headers."""
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
SPEC = importlib.util.spec_from_file_location('material_build', ROOT / 'build_stable.py')
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
sys.dont_write_bytecode = True
PT = 72 / 72.27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_profile(profile):
    output = HERE / profile
    output.mkdir(exist_ok=True)
    environment = BUILD.environment()
    environment['TEXINPUTS'] = str(BUILD.SOURCE) + '//:'
    code = (r'\def\ProbePrint{1}' if profile == 'PRINT' else '')
    code += r'\input{' + str(HERE / 'material-proof.tex') + '}'
    for number in (1, 2):
        with (output / f'pass{number}.stdout').open('w') as stream:
            result = subprocess.run([
                'xelatex', '-interaction=nonstopmode', '-halt-on-error', '-file-line-error',
                '-output-directory=' + str(output), '-jobname=material-proof', code],
                cwd=BUILD.SOURCE, env=environment, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            return {'profile': profile, 'status': 'failed', 'pass': number}
    return {'profile': profile, 'status': 'passed', 'pdf': str((output / 'material-proof.pdf').relative_to(ROOT))}


def spans(page):
    return [span for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for span in line['spans']]


def union_rect(drawings):
    rect = fitz.Rect(drawings[0]['rect'])
    for drawing in drawings[1:]:
        rect |= drawing['rect']
    return rect


def analyze(profile):
    path = HERE / profile / 'material-proof.pdf'
    log = path.with_suffix('.log').read_text(errors='replace')
    heights = dict(re.findall(r'MATERIALHEIGHT-([A-Z]+)=([\d.]+)pt', log))
    checks = {'short_header_height_not_increased_for_icon':
              set(heights) == {'CURRENT', 'NOICONBASELINE'} and
              abs(float(heights['CURRENT']) - float(heights['NOICONBASELINE'])) < .001}
    measurements = []
    with fitz.open(path) as document:
        checks['six_expected_pages'] = len(document) == 6
        checks['native_170x240_page_size'] = all(
            abs(page.rect.width * 25.4 / 72 - 170) < .01 and
            abs(page.rect.height * 25.4 / 72 - 240) < .01 for page in document)
        checks['all_graphics_are_vector'] = all(not page.get_images() for page in document)
        texts = [page.get_text() for page in document]
        checks['subtitle_absent_by_default_and_present_only_when_enabled'] = (
            all('UNITMARK' not in texts[i] for i in (0, 1, 3, 4, 5)) and
            texts[2].count('UNITMARK') == 1)
        header_rows = []
        header_title_fonts = []
        for index in range(5):
            page = document[index]
            drawings = page.get_drawings()
            headers = [d for d in drawings if d.get('fill') is not None
                       and d['rect'].width > 300 and d['rect'].height > 40
                       and min(d['fill']) < .5
                       and max(d['fill']) - min(d['fill']) > .1]
            assert len(headers) == 1, (profile, index, headers)
            frame = headers[0]['rect']
            white = [d for d in drawings
                     if ((d.get('color') is not None and all(abs(c - 1) < .002 for c in d['color']))
                         or (d.get('fill') is not None and all(abs(c - 1) < .002 for c in d['fill'])))
                     and d['rect'].x0 > frame.x1 - 55 and frame.contains(d['rect'])]
            assert white, (profile, index, 'white vector icon absent')
            icon = union_rect(white)
            text = [s for s in spans(page) if frame.contains(fitz.Rect(s['bbox']))]
            # Running headers can legitimately repeat the same title at 8 pt.
            # Check the actual coloured header cell, including every wrapped
            # title line, rather than matching marker words across the page.
            titles = [s for s in text if abs(s['size'] / PT - 8.6) >= .012]
            header_title_fonts.append(bool(titles) and all(
                s['font'] == 'NotoSerif-Medium' and abs(s['size'] / PT - 16) < .012
                for s in titles))
            rightmost = max(s['bbox'][2] for s in text)
            metrics = {'page': index + 1, 'frame': list(frame), 'icon': list(icon),
                       'icon_center_delta_mm': abs((icon.y0 + icon.y1 - frame.y0 - frame.y1) / 2) * 25.4 / 72,
                       'right_inset_mm': (frame.x1 - icon.x1) * 25.4 / 72,
                       'text_to_icon_gap_mm': (icon.x0 - rightmost) * 25.4 / 72,
                       'icon_extent_mm': max(icon.width, icon.height) * 25.4 / 72,
                       'white_vector_paths': len(white)}
            measurements.append(metrics)
            header_rows.append(metrics)
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(HERE / profile / f'p{index+1:02}.png')
        checks['icons_vertically_centered_on_whole_header'] = all(m['icon_center_delta_mm'] < .25 for m in header_rows)
        checks['icons_have_4_to_5_mm_right_inset'] = all(4 <= m['right_inset_mm'] <= 5 for m in header_rows)
        checks['all_header_text_has_at_least_5mm_icon_clearance'] = all(m['text_to_icon_gap_mm'] >= 5 for m in header_rows)
        checks['icon_ink_extent_is_10_to_12mm'] = all(10 <= m['icon_extent_mm'] <= 12 for m in header_rows)
        checks['clipboard_and_pencil_remain_distinct'] = header_rows[0]['white_vector_paths'] != header_rows[3]['white_vector_paths']
        checks['short_header_height_is_stable_with_subtitle_toggle'] = abs(
            header_rows[0]['frame'][3] - header_rows[0]['frame'][1] -
            header_rows[2]['frame'][3] + header_rows[2]['frame'][1]) < .02
        body_short = document[0].search_for('BODYSHORT')[0]
        body_standalone = document[2].search_for('BODYSTANDALONE')[0]
        body_control = document[5].search_for('BODYCONTROL')[0]
        checks['hidden_subtitle_leaves_no_extra_gap'] = abs(body_short.y0 - body_control.y0) < .03
        checks['enabled_subtitle_adds_only_its_real_content'] = body_standalone.y0 > body_short.y0 + 10
        checks['header_titles_keep_NotoSerif_Medium_16'] = len(header_title_fonts) == 5 and all(header_title_fonts)
        checks['running_header_text_does_not_overlap_logo'] = all(
            not fitz.Rect(s['bbox']).intersects(drawing['rect'])
            for page in document
            for drawing in page.get_drawings()
            if drawing['rect'].y1 < 40 and len(drawing['items']) > 50
            for s in spans(page) if s['bbox'][1] < 40)
        checks['body_returns_to_black_Inter_10_95'] = all(
            s['font'] == 'Inter-Regular' and abs(s['size'] / PT - 10.95) < .012 and s['color'] == 0
            for page in document for s in spans(page) if s['text'].startswith('BODY'))
    diagnostics = {'overfull': len(re.findall(r'Overfull \\[hv]box', log)),
                   'underfull': len(re.findall(r'Underfull \\[hv]box', log)),
                   'missing': log.count('Missing character:'),
                   'warnings': [s.strip() for s in log.splitlines() if 'Warning:' in s]}
    checks['no_bad_boxes_missing_glyphs_or_unresolved_references'] = (
        not diagnostics['overfull'] and not diagnostics['underfull'] and not diagnostics['missing']
        and 'undefined' not in log and 'Rerun to get' not in log)
    return {'profile': profile, 'status': 'passed' if all(checks.values()) else 'failed',
            'pdf': str(path.relative_to(ROOT)), 'sha256': sha(path), 'checks': checks,
            'measured_box_heights_tex_pt': heights, 'measurements': measurements,
            'diagnostics': diagnostics}


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        builds = list(pool.map(compile_profile, ('SCREEN', 'PRINT')))
    (HERE / 'BUILD_RESULTS.json').write_text(json.dumps(builds, indent=2) + '\n')
    if any(row['status'] != 'passed' for row in builds):
        print(json.dumps(builds, indent=2))
        return 1
    results = [analyze(profile) for profile in ('SCREEN', 'PRINT')]
    report = {'status': 'passed' if all(row['status'] == 'passed' for row in results) else 'failed',
              'profiles': results,
              'owned_source_sha256': {name: sha(BUILD.SOURCE / name) for name in
                ('config/material-v113.tex', 'styles/book-material-icons.tex', 'styles/book-stable-material.tex')}}
    (HERE / 'MATERIAL_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'].upper())
    for row in results:
        print(row['profile'], [name for name, ok in row['checks'].items() if not ok])
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

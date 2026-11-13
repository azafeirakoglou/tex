#!/usr/bin/env python3
"""Measure teaching icons, fragment rules and unchanged short-box heights."""
from pathlib import Path
import hashlib
import json
import re
import sys

import fitz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
PT = 72 / 72.27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def west_rules(page):
    return [d for d in page.get_drawings() if d.get('color') is not None
            and d['rect'].width < .02 and d['rect'].height > 25
            and d['rect'].x0 < 65 and len(d['items']) == 1]


def gutter_paths(page, rule):
    r = rule['rect']
    return [d for d in page.get_drawings()
            if d['rect'].x0 > r.x0 + 5 and d['rect'].x1 < r.x0 + 45
            and d['rect'].y0 >= r.y0 and d['rect'].y1 <= r.y1
            and (d.get('fill') is not None or d.get('color') is not None)]


def icon_metrics(paths):
    rect = fitz.Rect(paths[0]['rect'])
    for path in paths[1:]:
        rect |= path['rect']
    return {'ink_bounds_bp': list(rect),
            'width_mm': rect.width * 25.4 / 72,
            'height_mm': rect.height * 25.4 / 72,
            'paths': len(paths),
            'outline_1_08pt_present': any(
                d.get('color') is not None and abs(d['width'] / PT - 1.08) < .012 for d in paths)}


def analyze(profile):
    path = HERE / profile / 'icon-context.pdf'
    checks = {}
    fragments = []
    pngs = []
    log = path.with_suffix('.log').read_text(errors='replace')
    with fitz.open(path) as document:
        text = '\n'.join(page.get_text() for page in document).replace('\uee55', '-')
        checks['seven_pages'] = len(document) == 7
        checks['all_42_marked_paragraphs_once_in_order'] = all(
            re.findall(r'\b' + marker + r'-(\d{2})\b', text) == [f'{n:02}' for n in range(1, 15)]
            for marker in ('THINK', 'ATTENTION', 'HISTORY'))
        checks['all_vector'] = all(not page.get_images() for page in document)
        checks['native_170x240_geometry'] = all(
            abs(page.rect.width * 25.4 / 72 - 170) < .01 and
            abs(page.rect.height * 25.4 / 72 - 240) < .01 for page in document)
        rules = [west_rules(page) for page in document]
        checks['three_short_boxes_and_six_long_fragments'] = [len(r) for r in rules] == [3, 1, 1, 1, 1, 1, 1]
        checks['every_west_rule_is_1pt'] = all(abs(d['width'] / PT - 1) < .012 for group in rules for d in group)
        first_paths = [gutter_paths(document[0], rule) for rule in rules[0]]
        checks['three_short_icons_present_with_fixed_1_08pt_outlines'] = all(
            paths and icon_metrics(paths)['outline_1_08pt_present'] for paths in first_paths)
        short = [dict(kind=kind, box_height_bp=rule['rect'].height,
                      **icon_metrics(paths)) for kind, rule, paths in
                 zip(('bulb', 'warning', 'hourglass'), rules[0], first_paths)]
        for index in range(1, len(document)):
            paths = gutter_paths(document[index], rules[index][0])
            fragments.append({'page': index + 1, 'icon_paths': len(paths),
                              'west_rule_tex_pt': rules[index][0]['width'] / PT,
                              'first_fragment': index in (1, 3, 5)})
        checks['icons_only_in_first_long_fragment'] = all(
            bool(row['icon_paths']) == row['first_fragment'] for row in fragments)
        # This fixture uses no horizontal decorative rules: a long coloured
        # horizontal perimeter stroke would reveal an accidental top/bottom box.
        checks['no_top_bottom_or_right_callout_border'] = not any(
            d.get('color') is not None and
            ((d['rect'].width > 300 and d['rect'].height < .02) or
             (d['rect'].height > 25 and d['rect'].width < .02 and d['rect'].x0 > 350))
            for page in document for d in page.get_drawings())
        for number, page in enumerate(document, 1):
            image = HERE / profile / f'p{number:02}.png'
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(image)
            pngs.append({'page': number, 'path': str(image.relative_to(ROOT)), 'sha256': sha(image)})
    checks['no_overfull_underfull_or_missing_characters'] = not re.search(
        r'Overfull \\[hv]box|Underfull \\[hv]box|Missing character:', log)
    return {'profile': profile, 'status': 'passed' if all(checks.values()) else 'failed',
            'pdf': str(path.relative_to(ROOT)), 'sha256': sha(path), 'checks': checks,
            'short_boxes': short, 'fragments': fragments, 'renders': pngs,
            'warnings': [line.strip() for line in log.splitlines() if 'Warning:' in line]}


def main():
    profiles = [analyze(profile) for profile in ('SCREEN', 'PRINT')]
    baseline = HERE / 'BASELINE_SCREEN/icon-context.pdf'
    baseline_heights = []
    with fitz.open(baseline) as document:
        baseline_heights = [rule['rect'].height for rule in west_rules(document[0])]
    height_check = len(baseline_heights) == 3 and all(
        abs(box['box_height_bp'] - old) < .02 for box, old in
        zip(profiles[0]['short_boxes'], baseline_heights))
    report = {'status': 'passed' if all(p['status'] == 'passed' for p in profiles) and height_check else 'failed',
              'profiles': profiles,
              'short_box_heights_unchanged_from_v112': height_check,
              'baseline_pdf': str(baseline.relative_to(ROOT)), 'baseline_sha256': sha(baseline),
              'baseline_short_box_heights_bp': baseline_heights,
              'settings': {'bulb_scale_unchanged': .81, 'warning_scale': .90,
                           'hourglass_scale': .73, 'outline_tex_pt': 1.08},
              'source_sha256': {name: sha(ROOT / 'source' / name) for name in
                               ('config/stable-callouts.tex', 'config/rules-v113.tex',
                                'styles/book-stable-icons.tex', 'styles/book-callouts.tex')},
              'visual_review': 'pending_actual_views', 'physical_print_test': False,
              'extraction_note': 'Exact pre-existing Inter U+EE55 hyphen mapping is normalized before strict marker-order checks.'}
    (HERE / 'ICON_VERIFICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(report['status'].upper(), 'short-box-height equality:', height_check)
    for profile in profiles:
        print(profile['profile'], [key for key, ok in profile['checks'].items() if not ok])
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

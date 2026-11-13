#!/usr/bin/env python3
"""Actual-PDF checks for the limited v1.0.13 component revision."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import fitz

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('refinement_build', ROOT / 'build_stable.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
PT = 72 / 72.27
MM = 72 / 25.4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spans(page):
    return [s for block in page.get_text('dict')['blocks']
            for line in block.get('lines', []) for s in line['spans']]


def one(profile):
    out = ROOT / 'runtime/tmp/refinement' / profile
    out.mkdir(parents=True, exist_ok=True)
    tex = out / 'refinement.tex'
    tex.write_text(r'\documentclass[11pt,twoside,openright]{book}' + '\n' +
        r'\input{config/book-config.tex}' + '\n' +
        r'\newif\ifBookTwoInkProof\BookTwoInkProof' + ('true' if profile == 'PRINT' else 'false') + '\n' +
        r'\newif\ifPrintThreeInk\PrintThreeInkfalse\usepackage{styles/universalbook}' + '\n' +
        r'\begin{document}\input{refinement-content.tex}\end{document}' + '\n')
    env = build.environment()
    env['TEXINPUTS'] = str(HERE) + ':' + str(build.SOURCE) + '//:'
    resultdir = HERE / 'results'
    resultdir.mkdir(exist_ok=True)
    log = resultdir / (profile + '.build.log')
    command = ['latexmk', '-g', '-xelatex', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-e', '$max_repeat = 8;', '-outdir=' + str(out), str(tex)]
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=build.SOURCE, env=env,
                                stdout=stream, stderr=subprocess.STDOUT)
    row = {'profile': profile, 'exit_code': result.returncode,
           'log': str(log.relative_to(ROOT))}
    if result.returncode:
        return row
    (HERE / 'pdf').mkdir(exist_ok=True)
    pdf = HERE / 'pdf' / ('REFINEMENT_' + profile + '.pdf')
    shutil.copy2(out / 'refinement.pdf', pdf)
    xlog = resultdir / (profile + '.xelatex.log')
    shutil.copy2(out / 'refinement.log', xlog)
    content = xlog.read_text(errors='replace')
    row.update(pdf=str(pdf.relative_to(ROOT)), sha256=sha(pdf),
               diagnostics={name: len(re.findall(pattern, content)) for name, pattern in {
                   'overfull': r'Overfull \\[hv]box', 'underfull': r'Underfull \\[hv]box',
                   'missing_characters': r'Missing character:', 'warnings': r'Warning:'}.items()})
    return row


def marker(document, text):
    found = [(p, s) for p in document for s in spans(p) if text in s['text']]
    assert len(found) == 1, (text, len(found))
    return found[0]


def west_rule(page, span, tex_width, color):
    result = []
    for d in page.get_drawings():
        r = d['rect']
        if (d.get('color') is not None and r.width < .02 and r.height > 6 * MM
                and r.x0 < span['bbox'][0] - 3
                and r.y0 < span['bbox'][1] < r.y1
                and abs(d['width'] / PT - tex_width) < .012):
            rgb = tuple(round(c * 255) for c in d['color'])
            if rgb == tuple((color >> n) & 255 for n in (16, 8, 0)):
                result.append(d)
    return result


def analyze(row):
    profile = row['profile']
    primary = 0x203B63 if profile == 'SCREEN' else 0xED1C24
    secondary = 0x8493A9 if profile == 'SCREEN' else 0xF68D6F
    checks, measurements = {}, {}
    with fitz.open(ROOT / row['pdf']) as document:
        checks['native_geometry_and_no_raster_in_controlled_proof'] = all(
            abs(p.rect.width / MM - 170) < .01 and abs(p.rect.height / MM - 240) < .01
            and not p.get_images() for p in document)
        p, label = marker(document, 'ΚΕΦΑΛΑΙΟ 1')
        checks['chapter_indicator_Inter_SemiBold_9_5_primary'] = (
            label['font'] == 'Inter-SemiBold' and abs(label['size'] / PT - 9.5) < .012
            and label['color'] == primary)
        bodytitle = [s for s in spans(p) if s['text'] == 'REFINEMENT OPENING'
                     and abs(s['size'] / PT - 17.5) < .012]
        checks['first_body_title_Noto_Medium_17_5_unchanged'] = (
            len(bodytitle) == 1 and bodytitle[0]['font'] == 'NotoSerif-Medium')
        opening = document[0]
        goal = [s for s in spans(opening) if 'Στόχοι της ενότητας' in s['text']]
        bullets = [s for s in spans(opening) if s['text'].strip() == '•']
        goaltext = [s for s in spans(opening) if 'OPENINGGOAL' in s['text']]
        checks['opening_goal_title_and_bullets_primary_body_black'] = (
            len(goal) == 1 and goal[0]['color'] == primary and abs(goal[0]['size'] / PT - 14) < .012
            and len(bullets) == 2 and all(s['color'] == primary for s in bullets)
            and len(goaltext) == 2 and all(s['color'] == 0 for s in goaltext))
        rules = [d for d in opening.get_drawings()
                 if ((d.get('fill') is not None and abs(d['rect'].width / PT - 1.5) < .012)
                     or (d.get('color') is not None and d['rect'].width < .02
                         and abs(d['width'] / PT - 1.5) < .012))
                 and d['rect'].height > 25 * MM]
        checks['opening_title_rule_1_5_pt'] = len(rules) == 1
        for text, width, color in [('ATTENTIONMARK', 1, primary), ('THINKMARK', 1, primary),
                ('HISTORYMARK', 1, primary), ('METHODMARK', 1, secondary),
                ('DEFINITIONMARK', 1.5, primary), ('THEOREMMARK', 1.5, primary),
                ('LEARNINGGOALITEMONE', 1, primary)]:
            page, span = marker(document, text)
            matches = west_rule(page, span, width, color)
            checks[text + '_central_west_rule'] = len(matches) == 1
            measurements[text] = {'page': page.number + 1, 'width_tex_pt': width,
                                  'matched_rules': len(matches), 'body_rgb': f"{span['color']:06X}"}
        page, span = marker(document, 'LEARNINGGOALITEMONE')
        center = fitz.Rect(span['bbox']).tl + (fitz.Rect(span['bbox']).br - fitz.Rect(span['bbox']).tl) * .5
        backgrounds = [d for d in page.get_drawings() if d.get('fill') is not None
                       and d['rect'].contains(center) and d['rect'].height > 10]
        goalbox = min(backgrounds, key=lambda d: d['rect'].get_area())['rect']
        extras = [d for d in page.get_drawings() if d.get('color') is not None
                  and d['rect'].intersects(goalbox) and d['rect'].width > 1
                  and d['rect'].height <= goalbox.height + .1]
        numbers = [s for s in spans(page) if s['text'].strip() in ('1.', '2.')
                   and goalbox.contains(fitz.Point(s['origin']))]
        checks['LearningGoals_no_top_bottom_right_frame_numbers_primary_body_black'] = (
            not extras and len(numbers) == 2 and all(s['color'] == primary for s in numbers)
            and span['color'] == 0)
        page, answer = marker(document, 'ANSWERCONTENT')
        answerline = [s for s in spans(page) if abs(s['origin'][1] - answer['origin'][1]) < .1]
        prefix = [s for s in answerline if 'Απ.:' in s['text'] or s['text'].strip() == ']']
        contents = [s for s in answerline if s not in prefix and s['text'].strip()]
        checks['short_answer_prefix_55_body_and_math_black_8_2_italic'] = (
            prefix and all(s['color'] == secondary for s in prefix)
            and contents and all(s['color'] == 0 for s in contents)
            and answer['font'] == 'Inter-Italic' and abs(answer['size'] / PT - 8.2) < .012)
        _, after = marker(document, 'AFTERANSWERFONT')
        checks['answer_does_not_leak_color_or_font_to_following_text'] = (
            after['color'] == 0 and after['font'] == 'Inter-Regular'
            and abs(after['size'] / PT - 10.95) < .012)
        for text in ('EXERCISEBARMARK', 'SOLUTIONBARMARK', 'ASSESSMENTBARMARK'):
            page, textspan = marker(document, text)
            bars = [d for d in page.get_drawings()
                    if ((d.get('fill') is not None and abs(d['rect'].width / PT - .75) < .012)
                        or (d.get('color') is not None and d['rect'].width < .02
                            and abs(d['width'] / PT - .75) < .012))
                    and abs(d['rect'].height / PT - 11) < .012
                    and d['rect'].x1 < textspan['bbox'][0]
                    and abs(d['rect'].y0 - textspan['bbox'][1]) < 12]
            expectedrgb = tuple((primary >> n) & 255 for n in (16, 8, 0))
            checks[text + '_separator_size_and_primary'] = len(bars) == 1 and tuple(
                round(c * 255) for c in (bars[0].get('fill') or bars[0].get('color'))) == expectedrgb
        page, _ = marker(document, 'NARROWONE')
        labels = [s for s in spans(page) if s['text'].strip() in ('Σ', 'Λ')]
        checks['all_four_TF_pairs_use_primary_labels'] = len(labels) == 8 and all(s['color'] == primary for s in labels)
        boxes = [d for d in page.get_drawings() if d.get('color') is not None
                 and abs(d['rect'].width - d['rect'].height) < .05
                 and 1 * MM < d['rect'].width < 4 * MM]
        checks['all_eight_TF_checkboxes_primary_and_unchanged_size'] = len(boxes) == 8 and all(
            tuple(round(c * 255) for c in d['color']) == tuple((primary >> n) & 255 for n in (16, 8, 0))
            and abs(d['rect'].width / MM - 2.7) < .012
            and abs(d['width'] / PT - .55) < .012 for d in boxes)
        checks['all_narrow_column_content_preserved'] = all(marker(document, key)
            for key in ('NARROWONE', 'NARROWTWO', 'NARROWTHREE', 'NARROWFOUR', 'AFTERTF'))
        checks['no_overfull_underfull_or_missing_glyphs'] = not any(
            row['diagnostics'][name] for name in ('overfull', 'underfull', 'missing_characters'))
        measurements['pages'] = len(document)
    return dict(row, checks=checks, measurements=measurements,
                status='passed' if all(checks.values()) else 'failed')


def main():
    with ThreadPoolExecutor(max_workers=2) as pool:
        builds = list(pool.map(one, ('SCREEN', 'PRINT')))
    if any(r['exit_code'] for r in builds):
        print(json.dumps(builds, indent=2)); return 1
    proofs = [analyze(r) for r in builds]
    report = {'status': 'passed' if all(r['status'] == 'passed' for r in proofs) else 'failed',
              'proofs': proofs, 'source_sha256': {str(p.relative_to(build.SOURCE)): sha(p)
                  for folder in ('config', 'styles') for p in sorted((build.SOURCE / folder).glob('*')) if p.is_file()},
              'role_colour_scope': 'PyMuPDF display conversion of the unchanged v1.0.12 palette; paired preflight checks actual spot plates independently.'}
    (HERE / 'VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'].upper())
    for proof in proofs:
        print(proof['profile'], [k for k, value in proof['checks'].items() if not value])
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Consolidate current technical evidence; this command never promotes a version."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent


def read(name, fallback=None):
    path = resolve(name)
    return json.loads(path.read_text()) if path.is_file() else fallback


def resolve(value):
    path = Path(value)
    if not path.is_absolute():
        return ROOT / path
    try:
        return ROOT / path.relative_to(ROOT)
    except ValueError:
        marker = '/template-v1.0.12-work/'
        return ROOT / str(path).split(marker, 1)[1] if marker in str(path) else path


def sha(path):
    path = resolve(path) if not isinstance(path, Path) else path
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def pair_current(path):
    report = read(path, {})
    return (report.get('status') == 'passed' and
            all(isinstance(report.get('input_sha256', {}).get(role), str)
                and len(report['input_sha256'][role]) == 64
                and sha(report.get(role + '_file', '')) == report['input_sha256'][role]
                for role in ('print', 'screen')))


def main():
    unit = read('qa/suites/A.RESULT.json', {})
    logpath = ROOT / unit.get('log', 'qa/suites/A.unittest.log')
    unitlog = logpath.read_text() if logpath.is_file() else ''
    unitcount = re.search(r'Ran (\d+) tests', unitlog)
    builds = read('qa/compat/BUILD_RESULTS.json', [])
    compat_pairs = read('qa/compat/PREFLIGHT_RESULTS.json', [])
    probes = read('qa/probes/BUILD_RESULTS.json', [])
    probe_pairs = read('qa/probes/PREFLIGHT_RESULTS.json', [])
    examples_builds = read('qa/probes/EXAMPLES_BUILD_RESULTS.json', [])
    examples = read('qa/probes/EXAMPLES_MEASUREMENTS.json', {})
    example_pairs = read('qa/probes/EXAMPLES_PREFLIGHT_RESULTS.json', [])
    main_logs = read('qa/main/BUILD_LOG_AUDIT.json', [])
    audits = {v: read('qa/compat/' + v + '/build_log_audit.json', []) for v in ('A', 'B')}
    all_logs = main_logs + [row for rows in audits.values() for row in rows]
    table = read('qa/tables/TABLE_VERIFICATION.json', {})
    visual = read('visual-audit/VISUAL_EVIDENCE.json', {})
    callout = read('qa/callouts/CALLOUT_VERIFICATION.json', {})
    callout_measurements = read('qa/callouts/MEASUREMENTS.json', [])
    long_titles = read('qa/compat/stress-title-views/FINAL_VIEWS.json', {})
    stress = {v: read('qa/compat/' + v + '/stress.structure.json', {}) for v in ('A', 'B')}
    pair_reports = ([row['report'] for row in compat_pairs + probe_pairs + example_pairs]
                    + ['qa/main/PREFLIGHT.json', 'qa/callouts/PREFLIGHT.json', 'qa/tables/PREFLIGHT.json'])
    current_probe_measurements = all(
        read(resolve(row['report']).relative_to(ROOT), {}).get('input_sha256') == sha(row['pdf'])
        for row in probes)
    snapshots = {}
    canonical = {str(p.relative_to(ROOT / 'source')): sha(p)
                 for folder in ('config', 'styles')
                 for p in sorted((ROOT / 'source' / folder).glob('*')) if p.is_file()}
    for variant in ('A', 'B'):
        differences = []
        for relative in canonical:
            before = (ROOT / 'source' / relative).read_bytes()
            afterpath = ROOT / 'qa/work' / variant / 'source' / relative
            if not afterpath.is_file():
                differences.append(relative)
                continue
            after = afterpath.read_bytes()
            if variant == 'B' and relative == 'config/stable-config.tex':
                after = after.replace(b'\\providecommand{\\BookExampleHeaderVariant}{B}',
                                      b'\\providecommand{\\BookExampleHeaderVariant}{A}')
            if before != after:
                differences.append(relative)
        snapshots[variant] = differences
    checks = {
        'approved_palette_and_all_existing_roles_unchanged': read('qa/COLOR_INVARIANCE.json', {}).get('status') == 'passed',
        'canonical_66_tests_passed_without_skips': (unit.get('exit_code') == 0 and unitcount is not None
            and int(unitcount.group(1)) == 66 and not re.search(r'\.\.\. skipped ', unitlog)),
        'all_40_author_compatibility_builds_passed': len(builds) == 40 and all(r['exit_code'] == 0 for r in builds),
        'all_20_author_compatibility_pairs_passed': len(compat_pairs) == 20 and all(r['exit_code'] == 0 for r in compat_pairs),
        'both_150_row_stress_structure_checks_passed': all(r.get('status') == 'passed' for r in stress.values()),
        'all_8_editorial_measurements_passed_with_clean_logs': len(probes) == 8 and all(
            r['status'] == 'passed' and r.get('diagnostics') and not any(r['diagnostics'].values()) for r in probes),
        'all_8_editorial_measurements_match_current_pdf_hashes': len(probes) == 8 and current_probe_measurements,
        'all_4_editorial_pairs_passed': len(probe_pairs) == 4 and all(r['status'] == 'passed' for r in probe_pairs),
        'all_4_example_proofs_built_without_bad_boxes_or_missing_characters': len(examples_builds) == 4
            and all(r['exit_code'] == 0 and not any(r.get('diagnostics', {}).get(k, 1)
                for k in ('overfull', 'underfull', 'missing_characters')) for r in examples_builds),
        'three_consecutive_and_large_examples_A_B_measurements_passed': examples.get('status') == 'passed',
        'all_4_example_measurements_match_current_pdf_hashes': len(examples.get('proofs', [])) == 4 and all(
            row.get('input_sha256') == sha(row['pdf']) for row in examples.get('proofs', [])),
        'both_example_pair_preflights_passed': len(example_pairs) == 2 and all(r['exit_code'] == 0 for r in example_pairs),
        'all_29_pair_preflights_match_current_pdf_hashes': len(pair_reports) == 29 and all(pair_current(p) for p in pair_reports),
        'all_42_build_logs_have_no_overfull_underfull_or_missing_characters': len(all_logs) == 42
            and all(not any(r[k] for k in ('overfull', 'underfull', 'missing_characters')) for r in all_logs),
        'both_main_books_are_20_pages_with_no_warnings': len(main_logs) == 2 and all(
            r['pages'] == 20 and not r['warnings'] for r in main_logs),
        'both_isolated_variants_match_final_canonical_style_and_config': all(not d for d in snapshots.values()),
        'callout_geometry_content_font_and_ink_proofs_passed': callout.get('status') == 'passed'
            and len(callout_measurements) == 2 and all(r['status'] == 'passed' for r in callout_measurements),
        'callout_measurements_match_current_pdfs': len(callout_measurements) == 2 and all(
            r['sha256'] == sha(r['pdf']) for r in callout_measurements),
        'reviewed_callout_renders_match_rebuilt_final_proofs': callout.get('final_rebuild_pixel_identity', {}).get('status') == 'passed'
            and all(callout.get('pdf_sha256', {}).get(r['profile']) == sha(r['pdf']) for r in callout_measurements),
        'longtable_final_row_header_bug_closed_and_boundary_regression_passed': table.get('status') == 'passed'
            and table.get('boundary_positive_cases', 0) >= 10
            and table.get('negative_control_reproduces_old_missing_header') is True,
        'longtable_proof_matches_current_implementation': table.get('source_sha256') == sha(ROOT / 'source/styles/book-longtables.tex'),
        'long_material_titles_visually_verified_after_spacing_fix': long_titles.get('status') == 'passed'
            and long_titles.get('input_sha256') == sha(long_titles.get('pdf', ''))
            and long_titles.get('actual_visual_views') == [41, 43]
            and all(sha(row['png']) == row['sha256'] for row in long_titles.get('views', [])),
        'all_main_and_example_pages_visually_reviewed': visual.get('status') == 'passed'
            and len(visual.get('main_pdf_reviews', [])) == 2 and len(visual.get('example_pdf_reviews', [])) == 4
            and all(row.get('visually_viewed_pages') == list(range(1, 21))
                    for row in visual.get('main_pdf_reviews', []))
            and all(row.get('visually_viewed_pages') == list(range(1, 7))
                    for row in visual.get('example_pdf_reviews', [])),
        'visual_review_matches_current_main_and_example_pdf_hashes': all(
            row.get('sha256') == sha(row['pdf'])
            for row in visual.get('main_pdf_reviews', []) + visual.get('example_pdf_reviews', [])),
    }
    report = {'status': 'passed' if all(checks.values()) else 'pending_or_failed',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'version': '1.0.12', 'base': 'v1.0.11 B — MINIMAL',
              'example_header_default': 'A', 'example_header_optional': 'B',
              'unit_test_count': 66, 'compatibility_builds': 40, 'paired_preflights': len(pair_reports),
              'canonical_source_config_style_sha256': canonical,
              'snapshot_differences_after_expected_variant_flag': snapshots,
              'main_diagnostics': main_logs,
              'secondary_diagnostic_totals': {v: {k: sum(row[k] for row in rows)
                  for k in ('overfull', 'underfull', 'missing_characters')} for v, rows in audits.items()},
              'probe_pages': {row['design'] + '_' + row['edition'] + '_' + row['kind']:
                  read(resolve(row['report']).relative_to(ROOT), {}).get('pages') for row in probes},
              'disclosed_notices': 'Fixtures without figures/tables retain unused-caption notices; non-floating guide examples retain hypcap notices. These are preserved in full per-target log audits. No bad boxes or missing glyphs are accepted.',
              'printing_scope': '170 × 240 mm XeLaTeX MediaBox; same approved inks/tints. No physical print or PDF/X certification claimed.',
              'scope': 'Technical and recorded rendered visual acceptance of a local template; no remote publication or stable promotion is performed by this script.'}
    (ROOT / 'qa/QA_SUMMARY.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# v1.0.12 Technical QA', '', '**Status: ' + report['status'].upper() + '.**', '',
             'The canonical source is MINIMAL; A/B change only worked-example headers. A is the preferred default and B remains optional.', '',
             '| Check | Result |', '|---|---|']
    lines += ['| ' + key.replace('_', ' ') + ' | ' + ('PASS' if value else 'PENDING / FAIL') + ' |'
              for key, value in checks.items()]
    lines += ['', '## Evidence and scope', '',
              'The complete canonical suite retains 66 tests with zero skipped. Forty secondary builds cover all 20 shipped author targets in both header variants. The eight controlled editorial PDFs verify actual font sizes, STIX 105%, captions, tables, vector figures, long teaching boxes, chapter openings and first-body titles. Four same-content six-page example proofs verify three consecutive examples and a large statement/solution across pages; A/B positions match. All paired preflights check every page and all five separation plates.', '',
              'The longtable end-of-table defect is independently reproduced by a negative control and fixed centrally by omitting unused empty footer blocks. Ten row-boundary cases and the 120-row controlled table verify a repeated header on every page containing data, including the final row. Long worksheet/assessment titles use ragged-right paragraphs inside their font group, preserving font size and proper leading without stretched spacing.', '',
              'Main books have 20 pages each. The machine report records exact final diagnostics, page counts and source hashes. All 42 standard build logs must have zero overfull/underfull boxes and missing characters; main logs must also have zero warnings. Expected unused-caption and non-floating hypcap notices in dedicated fixtures remain disclosed in the per-target audits.', '',
              'PDF reports and visual reviews are bound to SHA-256 values. The original printing specifications remain pending; this is not a physical paper test or PDF/X certification. Previous-version integrity and scientific-content preservation are recorded separately in reports/ORIGINAL_INTEGRITY.json and SOURCE_DIFF.json.', '',
              'Run `python3 qa/create_summary.py` after all reproduction commands complete. A missing/stale/failed prerequisite produces PENDING / FAIL and never promotes the version.', '']
    (ROOT / 'qa/QA_SUMMARY.md').write_text('\n'.join(lines))
    print(report['status'].upper())
    for name, passed in checks.items():
        if not passed:
            print('PENDING / FAIL:', name)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

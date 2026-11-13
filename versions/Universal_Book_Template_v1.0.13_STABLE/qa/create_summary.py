#!/usr/bin/env python3
"""Consolidate current v1.0.13 evidence; never promote or publish a version."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
READ_ERRORS = {}
PROFILES = {'PRINT', 'SCREEN'}
VARIANTS = {'A', 'B'}
KINDS = {'sample', 'figures', 'assessment', 'tables', 'opening-goals',
         'history-statements', 'callouts', 'palette', 'starter', 'stress'}
BAD_BOX_KEYS = ('overfull', 'underfull', 'missing_characters')
REFINEMENT_CHECKS = {
    'native_geometry_and_no_raster_in_controlled_proof',
    'chapter_indicator_Inter_SemiBold_9_5_primary',
    'first_body_title_Noto_Medium_17_5_unchanged',
    'opening_goal_title_and_bullets_primary_body_black', 'opening_title_rule_1_5_pt',
    'ATTENTIONMARK_central_west_rule', 'THINKMARK_central_west_rule',
    'HISTORYMARK_central_west_rule', 'METHODMARK_central_west_rule',
    'DEFINITIONMARK_central_west_rule', 'THEOREMMARK_central_west_rule',
    'LEARNINGGOALITEMONE_central_west_rule',
    'LearningGoals_no_top_bottom_right_frame_numbers_primary_body_black',
    'short_answer_prefix_55_body_and_math_black_8_2_italic',
    'answer_does_not_leak_color_or_font_to_following_text',
    'EXERCISEBARMARK_separator_size_and_primary',
    'SOLUTIONBARMARK_separator_size_and_primary',
    'ASSESSMENTBARMARK_separator_size_and_primary',
    'all_four_TF_pairs_use_primary_labels',
    'all_eight_TF_checkboxes_primary_and_unchanged_size',
    'all_narrow_column_content_preserved', 'no_overfull_underfull_or_missing_glyphs',
}
MATERIAL_CHECKS = {
    'short_header_height_not_increased_for_icon', 'six_expected_pages',
    'native_170x240_page_size', 'all_graphics_are_vector',
    'subtitle_absent_by_default_and_present_only_when_enabled',
    'icons_vertically_centered_on_whole_header', 'icons_have_4_to_5_mm_right_inset',
    'all_header_text_has_at_least_5mm_icon_clearance', 'icon_ink_extent_is_10_to_12mm',
    'clipboard_and_pencil_remain_distinct',
    'short_header_height_is_stable_with_subtitle_toggle',
    'hidden_subtitle_leaves_no_extra_gap', 'enabled_subtitle_adds_only_its_real_content',
    'header_titles_keep_NotoSerif_Medium_16', 'running_header_text_does_not_overlap_logo',
    'body_returns_to_black_Inter_10_95', 'no_bad_boxes_missing_glyphs_or_unresolved_references',
}
ICON_CHECKS = {
    'seven_pages', 'all_42_marked_paragraphs_once_in_order', 'all_vector',
    'native_170x240_geometry', 'three_short_boxes_and_six_long_fragments',
    'every_west_rule_is_1pt', 'three_short_icons_present_with_fixed_1_08pt_outlines',
    'icons_only_in_first_long_fragment', 'no_top_bottom_or_right_callout_border',
    'no_overfull_underfull_or_missing_characters',
}
MATERIAL_SOURCES = {'config/material-v113.tex', 'styles/book-material-icons.tex',
                    'styles/book-stable-material.tex'}
ICON_SOURCES = {'config/stable-callouts.tex', 'config/rules-v113.tex',
                'styles/book-stable-icons.tex', 'styles/book-callouts.tex'}
EDITORIAL_FONT_ROLES = {
    'BODYTITLEMETRIC': ('NotoSerif-Medium', 17.5),
    'ΚΕΦΑΛΑΙΟ 1': ('Inter-SemiBold', 9.5),
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
    'Quantity': ('Inter-SemiBold', 10), 'Value': ('Inter-SemiBold', 10),
    'Position': ('Inter-Regular', 10), 'ΠΡΟΣΟΧΗ': ('Inter-Medium', 9.5),
    'Πώς σκέφτομαι': ('Inter-Medium', 9.5),
    'HISTORYTITLEMETRIC': ('Inter-Medium', 9.5), 'Λύση': ('Inter-Medium', 10.2),
}


def resolve(value):
    path = Path(value)
    if not path.is_absolute():
        return ROOT / path
    marker = '/template-v1.0.13-work/'
    return ROOT / str(path).split(marker, 1)[1] if marker in str(path) else path


def read(name, fallback=None):
    try:
        value = json.loads(resolve(name).read_text())
        if fallback is not None and not isinstance(value, type(fallback)):
            raise ValueError('Unexpected JSON root type')
        return value
    except (OSError, ValueError, TypeError) as exc:
        READ_ERRORS[str(name)] = str(exc)
        return fallback


def sha(path):
    try:
        return hashlib.sha256(resolve(path).read_bytes()).hexdigest()
    except (OSError, TypeError, ValueError):
        return None


def hash_current(path, digest):
    return isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest) is not None and sha(path) == digest


def identities(rows, keys, expected):
    return (isinstance(rows, list) and len(rows) == len(expected)
            and all(isinstance(row, dict) for row in rows)
            and {tuple(row.get(k) for k in keys) for row in rows} == expected)


def source_map_current(mapping, expected):
    return (isinstance(mapping, dict) and set(mapping) == set(expected)
            and all(hash_current(ROOT / 'source' / name, mapping[name]) for name in expected))


def clean(diagnostics, missing='missing_characters'):
    return all(diagnostics.get(k) == 0 for k in ('overfull', 'underfull', missing))


def component_passed(report, rows_key, required):
    rows = report.get(rows_key, [])
    return (report.get('status') == 'passed'
            and identities(rows, ('profile',), {(p,) for p in PROFILES})
            and all(row.get('status') == 'passed'
                    and required.issubset(row.get('checks', {}))
                    and all(value is True for value in row['checks'].values()) for row in rows))


def editorial_metrics_passed(report):
    measurements = report.get('measurements', {})
    fonts = measurements.get('font_roles', {})
    maths = measurements.get('math_base_sizes_tex_pt', {})
    math_roles = {'BODYMETRIC', 'ATTENTIONBODYMETRIC', 'THINKBODYMETRIC',
                  'HISTORYBODYMETRIC', 'DIAGRAMLABELMETRIC', 'TICKMETRIC'}
    return (set(fonts) == set(EDITORIAL_FONT_ROLES) and set(maths) == math_roles
            and measurements.get('display_uses_same_base_math_size') is True
            and measurements.get('running_header_and_footer_tex_pt') == 8
            and all(fonts[k].get('font') == font
                    and abs(fonts[k].get('size_tex_pt', 0) - size) < .012
                    for k, (font, size) in EDITORIAL_FONT_ROLES.items())
            and all(abs(maths[k] - EDITORIAL_FONT_ROLES[k][1] * 1.05) < .012 for k in math_roles))


def native_pages(info):
    pages = info.get('pages')
    boxes = info.get('page_boxes', [])
    return (isinstance(pages, int) and pages > 0 and len(boxes) == pages
            and info.get('unembedded_fonts') == []
            and all(len(row.get('MediaBox', [])) == 4
                    and abs((row['MediaBox'][2] - row['MediaBox'][0]) * 25.4 / 72 - 170) < .02
                    and abs((row['MediaBox'][3] - row['MediaBox'][1]) * 25.4 / 72 - 240) < .02
                    for row in boxes))


def pair_current(path, palette_digest):
    report = read(path, {})
    rendered = report.get('rendered', {})
    plates = rendered.get('plates', {})
    spot = 'SecondInkRedProof'
    return (report.get('status') == 'passed' and report.get('errors') == []
            and all(hash_current(report.get(role + '_file', ''), report.get('input_sha256', {}).get(role))
                    and native_pages(report.get(role, {})) for role in ('print', 'screen'))
            and report.get('input_sha256', {}).get('palette') == palette_digest
            and all(report.get('pair', {}).get(k) is True for k in
                    ('same_page_count', 'text_and_positions_match', 'geometry_matches'))
            and set(plates) == {'Black', 'Cyan', 'Magenta', 'Yellow', spot}
            and all(plates[k].get('marked_pixels') == 0 for k in ('Cyan', 'Magenta', 'Yellow'))
            and all(plates[k].get('marked_pixels', 0) > 0 for k in ('Black', spot))
            and rendered.get('pairing_mismatched_pixels') == 0 and rendered.get('overlap_pixels') == 0
            and len(rendered.get('pages', [])) == report.get('print', {}).get('pages')
            and all(row.get('pairing_mismatched_pixels') == 0 and row.get('overlap_pixels') == 0
                    for row in rendered.get('pages', [])))


def audit_current(row):
    if not (hash_current(row.get('pdf', ''), row.get('sha256'))
            and hash_current(row.get('log', ''), row.get('log_sha256'))):
        return False
    content = resolve(row['log']).read_text(errors='replace')
    actual = {k: len(re.findall(pattern, content)) for k, pattern in
              (('overfull', r'Overfull \\[hv]box'), ('underfull', r'Underfull \\[hv]box'),
               ('missing_characters', r'Missing character:'))}
    warnings = [line.strip() for line in content.splitlines() if 'Warning:' in line]
    return all(row.get(k) == value for k, value in actual.items()) and row.get('warnings') == warnings


def visual_rows_current(rows, expected):
    """Require an actual full-page review and hashed render for every expected page."""
    if not isinstance(rows, list) or len(rows) != len(expected):
        return False
    if {str(resolve(row.get('pdf', ''))) for row in rows} != set(expected):
        return False
    for row in rows:
        pages = list(range(1, expected[str(resolve(row['pdf']))] + 1))
        renders = row.get('renders', [])
        if not (hash_current(row['pdf'], row.get('sha256'))
                and row.get('visually_viewed_pages') == pages
                and identities(renders, ('page',), {(p,) for p in pages})
                and all(hash_current(render.get('path', ''), render.get('sha256')) for render in renders)):
            return False
    return True


def main():
    READ_ERRORS.clear()
    unit = read('qa/suites/A.RESULT.json', {})
    logpath = resolve(unit.get('log', 'qa/suites/A.unittest.log'))
    unitlog = logpath.read_text() if logpath.is_file() else ''
    unitcount = re.search(r'Ran (\d+) tests', unitlog)
    builds = read('qa/compat/BUILD_RESULTS.json', [])
    compat_pairs = read('qa/compat/PREFLIGHT_RESULTS.json', [])
    probes = read('qa/probes/BUILD_RESULTS.json', [])
    probe_pairs = read('qa/probes/PREFLIGHT_RESULTS.json', [])
    examples_builds = read('qa/probes/EXAMPLES_BUILD_RESULTS.json', [])
    examples = read('qa/probes/EXAMPLES_MEASUREMENTS.json', {})
    example_pairs = read('qa/probes/EXAMPLES_PREFLIGHT_RESULTS.json', [])
    component_pairs = read('qa/components/PREFLIGHT_RESULTS.json', [])
    main_logs = read('qa/main/BUILD_LOG_AUDIT.json', [])
    audits = {v: read('qa/compat/' + v + '/build_log_audit.json', []) for v in sorted(VARIANTS)}
    all_logs = main_logs + [row for rows in audits.values() for row in rows]
    visual = read('visual-audit/VISUAL_EVIDENCE.json', {})
    refinement = read('qa/refinement/VERIFICATION.json', {})
    material = read('qa/material/MATERIAL_VERIFICATION.json', {})
    icons = read('qa/icons/ICON_VERIFICATION.json', {})
    icon_builds = read('qa/icons/BUILD_RESULTS.json', [])
    stress = {v: read('qa/compat/' + v + '/stress.structure.json', {}) for v in sorted(VARIANTS)}
    baseline = read('reports/SOURCE_BASELINE.json', {})
    old_map = read('qa/baseline/color-map.json', {})
    current_map = read('source/config/color-map.json', {})
    expected_map = dict(old_map, version='1.0.13')
    palette_digest = hashlib.sha256(json.dumps(current_map, sort_keys=True).encode()).hexdigest()
    pair_reports = ([row.get('report', '') for row in compat_pairs + probe_pairs + example_pairs + component_pairs]
                    + ['qa/main/PREFLIGHT.json'])
    expected_pair_reports = ({str(ROOT / 'qa/compat' / v / (k + '.preflight.json'))
                              for v in VARIANTS for k in KINDS}
        | {str(ROOT / 'qa/probes/results' / (v + '_' + k + '_pair.json'))
           for v in VARIANTS for k in ('metrics', 'edges')}
        | {str(ROOT / 'qa/probes/examples-results' / (v + '.preflight.json')) for v in VARIANTS}
        | {str(ROOT / 'qa/components' / (k + '.preflight.json')) for k in ('refinement', 'material', 'icons')}
        | {str(ROOT / 'qa/main/PREFLIGHT.json')})
    pair_states = {name: pair_current(name, palette_digest) for name in pair_reports}
    canonical = {str(p.relative_to(ROOT / 'source')): sha(p)
                 for folder in ('config', 'styles')
                 for p in sorted((ROOT / 'source' / folder).rglob('*')) if p.is_file()}
    snapshots = {}
    for variant in sorted(VARIANTS):
        snapshot_root = ROOT / 'qa/work' / variant / 'source'
        snapshot_files = {str(p.relative_to(snapshot_root)) for folder in ('config', 'styles')
                          for p in (snapshot_root / folder).rglob('*') if p.is_file()}
        differences = sorted(set(canonical) ^ snapshot_files)
        for relative in sorted(set(canonical) & snapshot_files):
            after = (snapshot_root / relative).read_bytes()
            if variant == 'B' and relative == 'config/stable-config.tex':
                after = after.replace(b'\\providecommand{\\BookExampleHeaderVariant}{B}',
                                      b'\\providecommand{\\BookExampleHeaderVariant}{A}')
            if (ROOT / 'source' / relative).read_bytes() != after:
                differences.append(relative)
        snapshots[variant] = differences
    probe_reports = [read(row.get('report', ''), {}) for row in probes]
    component_rows = refinement.get('proofs', []) + material.get('profiles', []) + icons.get('profiles', [])
    expected_main_views = {str(ROOT / 'pdf' / f'Universal_Book_Template_v1.0.13_{p}.pdf'): 20 for p in PROFILES}
    expected_component_views = {str(resolve(row['pdf'])): pages
                                for report, key, pages in ((refinement, 'proofs', 5),
                                    (material, 'profiles', 6), (icons, 'profiles', 7))
                                for row in report.get(key, []) if 'pdf' in row}
    palette_files = ('color-roles.tex', 'palette-screen.tex', 'palette-print2-spot.tex')
    frozen = baseline.get('base_source_sha256', {})
    checks = {
        'approved_palette_and_all_existing_roles_unchanged': bool(old_map)
            and baseline.get('base') == 'v1.0.12 STABLE'
            and hash_current('qa/baseline/color-map.json', frozen.get('config/color-map.json'))
            and current_map == expected_map
            and all(hash_current('qa/baseline/' + n, frozen.get('config/' + n))
                    and hash_current('source/config/' + n, frozen.get('config/' + n)) for n in palette_files),
        'canonical_66_tests_passed_without_skips': unit.get('exit_code') == 0
            and unit.get('tests_run') == 66 and unit.get('skipped') == 0
            and unitcount is not None and int(unitcount.group(1)) == 66
            and re.search(r'^OK\s*$', unitlog, re.M) is not None
            and re.search(r'\.\.\. skipped |^FAILED|^ERROR:', unitlog, re.M) is None,
        'canonical_tests_attest_unchanged_current_config_and_styles': unit.get('source_unchanged_during_test') is True
            and source_map_current(unit.get('source_config_style_sha256'), canonical),
        'all_40_author_compatibility_builds_passed': identities(builds, ('design', 'target'),
            {(v, k + '-' + e) for v in VARIANTS for k in KINDS for e in ('print2', 'screen')})
            and all(r.get('exit_code') == 0 for r in builds),
        'all_20_author_compatibility_pairs_passed': identities(compat_pairs, ('design', 'pair'),
            {(v, k) for v in VARIANTS for k in KINDS}) and all(r.get('exit_code') == 0 for r in compat_pairs),
        'both_150_row_stress_structure_checks_passed_on_current_pdfs': all(
            report.get('status') == 'passed' and all(
                report.get('editions', {}).get(role, {}).get('long_table', {}).get('rows') == 150
                and report['editions'][role]['long_table'].get('header_repeated') is True
                and any(r.get('design') == variant and r.get('pair') == 'stress'
                        and report.get('input_sha256', {}).get(role) == read(r.get('report', ''), {}).get('input_sha256', {}).get(role)
                        and isinstance(report.get('input_sha256', {}).get(role), str) for r in compat_pairs)
                for role in ('print', 'screen')) for variant, report in stress.items()),
        'all_8_editorial_measurements_passed_with_clean_logs': identities(probes, ('design', 'edition', 'kind'),
            {(v, e, k) for v in VARIANTS for e in ('print', 'screen') for k in ('metrics', 'edges')})
            and all(r.get('status') == 'passed' and clean(r.get('diagnostics', {}))
                    and r.get('diagnostics', {}).get('warnings') == 0 for r in probes)
            and all(r.get('status') == 'passed' for r in probe_reports),
        'all_8_editorial_measurements_match_current_pdf_hashes': len(probes) == 8 and all(
            hash_current(row.get('pdf', ''), report.get('input_sha256')) for row, report in zip(probes, probe_reports)),
        'editorial_fonts_STIX_105_and_120_row_repeated_table_headers_preserved': len(probe_reports) == 8 and all(
            editorial_metrics_passed(report)
            if row.get('kind') == 'metrics' else
            (report.get('measurements', {}).get('long_table', {}).get('rows') == 120
             and report['measurements']['long_table'].get('repeated_header') is True)
            for row, report in zip(probes, probe_reports)),
        'all_4_editorial_pairs_passed': identities(probe_pairs, ('design', 'kind'),
            {(v, k) for v in VARIANTS for k in ('metrics', 'edges')})
            and all(r.get('status') == 'passed' for r in probe_pairs),
        'all_4_example_proofs_built_without_bad_boxes_or_missing_characters': identities(examples_builds,
            ('variant', 'profile'), {(v, p) for v in VARIANTS for p in PROFILES})
            and all(r.get('exit_code') == 0 and clean(r.get('diagnostics', {})) for r in examples_builds),
        'three_consecutive_and_large_examples_A_B_measurements_passed': examples.get('status') == 'passed'
            and identities(examples.get('proofs', []), ('variant', 'profile'), {(v, p) for v in VARIANTS for p in PROFILES})
            and all(r.get('status') == 'passed' and r.get('measurements', {}).get('pages') == 6
                    and r['measurements'].get('consecutive_examples_same_page') is True
                    and r['measurements'].get('solution_on_white') is True for r in examples.get('proofs', []))
            and identities(examples.get('ab_geometry', []), ('profile',), {(p,) for p in PROFILES})
            and all(r.get('same_words_and_positions') is True for r in examples.get('ab_geometry', [])),
        'all_4_example_measurements_match_current_pdf_hashes': len(examples.get('proofs', [])) == 4
            and all(hash_current(r.get('pdf', ''), r.get('input_sha256')) for r in examples.get('proofs', [])),
        'both_example_pair_preflights_passed': identities(example_pairs, ('variant',), {(v,) for v in VARIANTS})
            and all(r.get('exit_code') == 0 for r in example_pairs),
        'all_3_component_pair_preflights_passed': len(component_pairs) == 3
            and {r.get('report') for r in component_pairs} == {f'qa/components/{k}.preflight.json' for k in ('refinement', 'material', 'icons')}
            and all(r.get('exit_code') == 0 for r in component_pairs),
        'all_30_pair_preflights_match_current_pdfs_palette_geometry_fonts_and_plates': len(pair_reports) == 30
            and {str(resolve(p)) for p in pair_reports} == expected_pair_reports and all(pair_states.values()),
        'all_42_standard_log_audits_match_current_logs_and_pdfs': len(all_logs) == 42
            and all(identities(rows, ('target',), {(k + '-' + e,) for k in KINDS for e in ('print2', 'screen')})
                    for rows in audits.values())
            and len({str(resolve(r.get('log', ''))) for r in all_logs}) == 42
            and len({str(resolve(r.get('pdf', ''))) for r in all_logs}) == 42
            and all(audit_current(r) for r in all_logs),
        'all_42_build_logs_have_no_overfull_underfull_or_missing_characters': len(all_logs) == 42
            and all(clean(r) for r in all_logs),
        'both_main_books_are_20_pages_with_no_warnings': identities(main_logs, ('target',), {('screen',), ('print2',)})
            and all(r.get('pages') == 20 and r.get('warnings') == [] for r in main_logs),
        'both_isolated_variants_match_final_canonical_style_and_config': bool(canonical)
            and all(not d for d in snapshots.values()),
        'refinement_native_fonts_rules_goals_TF_answers_and_numbered_bars_passed': component_passed(
            refinement, 'proofs', REFINEMENT_CHECKS)
            and all(r.get('exit_code') == 0 and clean(r.get('diagnostics', {})) for r in refinement.get('proofs', [])),
        'refinement_attests_current_canonical_config_and_styles': source_map_current(refinement.get('source_sha256'), canonical),
        'material_headers_short_long_titles_white_icons_subtitle_and_fonts_passed': component_passed(
            material, 'profiles', MATERIAL_CHECKS)
            and all(clean(r.get('diagnostics', {}), 'missing') for r in material.get('profiles', [])),
        'material_attests_current_owned_config_and_styles': source_map_current(material.get('owned_source_sha256'), MATERIAL_SOURCES),
        'callout_icons_short_long_fragments_vector_weight_and_geometry_passed': component_passed(icons, 'profiles', ICON_CHECKS)
            and icons.get('short_box_heights_unchanged_from_v112') is True
            and hash_current(icons.get('baseline_pdf', ''), icons.get('baseline_sha256'))
            and identities(icon_builds, ('profile',), {(p,) for p in PROFILES})
            and all(clean(r.get('diagnostics', {})) for r in icon_builds),
        'icons_attest_current_owned_config_and_styles': source_map_current(icons.get('source_sha256'), ICON_SOURCES),
        'all_6_component_measurements_match_current_pdf_hashes': len(component_rows) == 6
            and all(hash_current(r.get('pdf', ''), r.get('sha256')) for r in component_rows),
        'all_40_main_pages_and_36_component_pages_actually_visually_reviewed': visual.get('status') == 'passed'
            and visual.get('physical_print_test') is False and len(expected_component_views) == 6
            and visual_rows_current(visual.get('main_pdf_reviews', []), expected_main_views)
            and visual_rows_current(visual.get('component_pdf_reviews', []), expected_component_views),
        'all_required_evidence_files_read_successfully': not READ_ERRORS,
    }
    report = {
        'status': 'passed' if all(checks.values()) else 'pending_or_failed',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'version': '1.0.13', 'base': 'v1.0.12 STABLE', 'example_header_default': 'A', 'example_header_optional': 'B',
        'unit_test_count': int(unitcount.group(1)) if unitcount else None,
        'compatibility_builds': len(builds), 'editorial_proofs': len(probes),
        'example_proofs': len(examples_builds), 'component_proofs': len(component_rows),
        'paired_preflights': len(pair_reports), 'standard_log_audits': len(all_logs),
        'canonical_source_config_style_sha256': canonical,
        'snapshot_differences_after_expected_variant_flag': snapshots,
        'pair_report_current': pair_states, 'evidence_read_errors': READ_ERRORS,
        'main_diagnostics': main_logs,
        'secondary_diagnostic_totals': {v: {k: sum(row.get(k, 0) for row in rows)
            for k in BAD_BOX_KEYS} for v, rows in audits.items()},
        'probe_pages': {row.get('design', '') + '_' + row.get('edition', '') + '_' + row.get('kind', ''):
            report.get('pages') for row, report in zip(probes, probe_reports)},
        'component_required_assertions_per_profile': {'refinement': len(REFINEMENT_CHECKS),
            'material': len(MATERIAL_CHECKS), 'icons': len(ICON_CHECKS)},
        'visual_evidence': 'visual-audit/VISUAL_EVIDENCE.json; this final review supersedes component-local pending_actual_views fields.',
        'disclosed_notices': 'Fixtures without figures/tables retain unused-caption notices; non-floating guide examples retain hypcap notices. Full per-target audits preserve them. No bad boxes or missing glyphs are accepted.',
        'printing_scope': '170 × 240 mm XeLaTeX MediaBox; unchanged approved inks and 100/55/10 tints. No physical print or PDF/X certification claimed.',
        'scope': 'Recorded technical and rendered visual acceptance; this script does not promote VERSION.json, publish, or perform Git operations.',
    }
    (ROOT / 'qa/QA_SUMMARY.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# v1.0.13 Technical QA', '', '**Status: ' + report['status'].upper() + '.**', '',
             'Based on v1.0.12 STABLE, retaining the MINIMAL design. A remains the default worked-example header; B is optional.', '',
             '| Check | Result |', '|---|---|']
    lines += ['| ' + key.replace('_', ' ') + ' | ' + ('PASS' if value else 'PENDING / FAIL') + ' |'
              for key, value in checks.items()]
    lines += ['', '## Evidence and scope', '',
        'Required regression coverage: 66 unskipped canonical tests, 40 compatibility builds in isolated A/B snapshots, 8 editorial probes, and 4 same-content A/B example proofs. Both 150-row stress books and all four 120-row editorial tables must retain their repeated headers. Unit-test source hashes must match every current config and style file.', '',
        'The six new PRINT/SCREEN component proofs require all 22 refinement assertions, 17 material-header assertions and 10 callout-icon assertions per profile. These cover native page geometry, preserved fonts, rule widths, goals, short answers, exercise separators, narrow-column true/false choices, short and long material titles, subtitle toggling, vector icons, spacing and split teaching boxes. Component PDF and source hashes must be current.', '',
        'All 30 paired preflights must match current PDFs and the canonical palette, native 170 × 240 mm geometry, embedded fonts and five separation plates. All 42 standard build logs must match their recorded hashes and have zero overfull/underfull boxes or missing characters. Main books must have 20 pages each and zero warnings. Expected unused-caption and non-floating hypcap notices remain disclosed in fixture audits.', '',
        'Final visual evidence must record actual review of all 40 main-book pages and all 36 new component-proof pages, with current PDF and full-page-render hashes. This centralized final record supersedes component reports that still say pending_actual_views. Existing v1.0.12-specific callout/table proof reports are replaced by the new component proofs and retained stress/editorial regressions.', '',
        'The frozen v1.0.12 palette and role definitions must be byte-identical; the color map may change only its version. Previous-version integrity and scientific-content preservation are recorded separately under reports/. Physical printing, final printer specifications and PDF/X certification remain outside this technical acceptance.', '',
        'Run `python3 qa/create_summary.py` after reproduction completes. Missing, malformed, stale or failed evidence produces PENDING / FAIL. This command never promotes the version.', '']
    (ROOT / 'qa/QA_SUMMARY.md').write_text('\n'.join(lines))
    print(report['status'].upper())
    for name, passed in checks.items():
        if not passed:
            print('PENDING / FAIL:', name)
    return int(report['status'] != 'passed')


def run():
    try:
        return main()
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        # A malformed nested report must replace any previous PASS, not leave it
        # looking current after this command fails during prerequisite loading.
        error = type(exc).__name__ + ': ' + str(exc)
        report = {'status': 'pending_or_failed', 'version': '1.0.13', 'base': 'v1.0.12 STABLE',
                  'created_utc': datetime.now(timezone.utc).isoformat(),
                  'checks': {'required_evidence_schema_valid': False},
                  'summary_generation_error': error, 'evidence_read_errors': READ_ERRORS,
                  'scope': 'Invalid prerequisite evidence. No stable promotion or publication performed.'}
        (ROOT / 'qa/QA_SUMMARY.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        (ROOT / 'qa/QA_SUMMARY.md').write_text('# v1.0.13 Technical QA\n\n**Status: PENDING_OR_FAILED.**\n\n'
            'Required evidence could not be evaluated: `' + error.replace('`', "'") + '`.\n\n'
            'Correct the invalid prerequisite and rerun `python3 qa/create_summary.py`. No version was promoted.\n')
        print('PENDING / FAIL: required_evidence_schema_valid:', error)
        return 1


if __name__ == '__main__':
    raise SystemExit(run())

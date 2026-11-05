#!/usr/bin/env python3
"""Authenticate immutable inks/roles; allow only explicit v112 component usage."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    baseline=json.loads((ROOT/'reports/SOURCE_BASELINE.json').read_text())
    old=json.loads((ROOT/'qa/baseline/color-map.json').read_text())
    new=json.loads((ROOT/'source/config/color-map.json').read_text())
    expected=json.loads(json.dumps(old))
    expected['version']='1.0.12'
    for kind in ('ThinkBox','AttentionBox','HistoryBox'):
        expected['visual_rules'][kind]['decoration']='accent-rule'
    expected['visual_rules']['ProblemBox'].update(title_text='white',
        title_background='BookExampleAccent',title_marker='none')
    expected['visual_rules']['striped_table']={'header':'BookProblemBackground',
        'header_text':'BookInk','header_rule':'BookPrimary','stripe':'BookHistorySoft'}
    checks={
        'frozen_json_matches_captured_MINIMAL_sha256':sha(ROOT/'qa/baseline/color-map.json')==baseline['base_source_sha256']['config/color-map.json'],
        'map_changes_only_approved_version_and_component_usage':new==expected,
        'semantic_roles_identical':new['semantic']==old['semantic'],
        'ink_definitions_and_tints_identical':new['colors']==old['colors'],
        'spot_ink_name_identical':new['spot_ink_name']==old['spot_ink_name'],
        'spot_alternate_cmyk_identical':new['spot_alternate_cmyk']==old['spot_alternate_cmyk'],
        'screen_palette_identical':new['screen_base_hex']==old['screen_base_hex'],
        'three_approved_tints_identical':new['approved_tints_pending_press']==old['approved_tints_pending_press'],
    }
    files={}
    for name in ('color-roles.tex','palette-screen.tex','palette-print2-spot.tex'):
        approved=baseline['base_source_sha256']['config/'+name]
        current=sha(ROOT/'source/config'/name)
        files[name]={'sha256':current,'approved_sha256':approved}
        checks[name+'_byte_identical']=current==sha(ROOT/'qa/baseline'/name)==approved
    report={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'files':files,
            'component_usage':'Existing roles are not redefined. Only explicitly requested component surfaces change.'}
    (ROOT/'qa/COLOR_INVARIANCE.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report['status']!='passed'


if __name__=='__main__':raise SystemExit(main())

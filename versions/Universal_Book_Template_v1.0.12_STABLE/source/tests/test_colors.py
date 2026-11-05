"""Regression tests for palette drift and source/asset escape paths."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from generate_colors import render, screen_hex, validate_map
from check_color_consistency import scan_source, validate


class PaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette=json.loads((ROOT/'config/color-map.json').read_text(encoding='utf-8'))

    def test_screen_tints_follow_one_blue_and_same_black(self):
        self.assertEqual(screen_hex('203B63',55),'8493A9')
        self.assertEqual(screen_hex('203B63',10),'E9EBEF')
        self.assertEqual(screen_hex('000000',55),'737373')
        self.assertEqual(screen_hex('000000',10),'E6E6E6')
        output=render(self.palette)['config/palette-screen.tex']
        self.assertIn('{BookPaletteSpot55}{HTML}{8493A9}',output)

    def test_independent_screen_override_is_rejected(self):
        m=copy.deepcopy(self.palette)
        m['colors']['Spot55']['screen_hex']='7E93A9'
        self.assertTrue(any('derived' in e for e in validate_map(m)))

    def test_extra_swatch_and_wrong_ink_are_rejected(self):
        m=copy.deepcopy(self.palette)
        m['colors']['Spot42']={'print_ink':'SECOND','tint':42}
        m['colors']['Black55']['print_ink']='SECOND'
        self.assertGreaterEqual(len(validate_map(m)),2)

    def test_spot_identity_is_used_by_generator(self):
        m=copy.deepcopy(self.palette)
        m['spot_ink_name']='PrinterRed'
        m['spot_alternate_cmyk']=[0,0.9,0.8,0]
        output=render(m)['config/palette-print2-spot.tex']
        self.assertIn('{PrinterRed}{0 0.9 0.8 0}',output)
        self.assertNotIn('SecondInkRedProof',output)

    def test_approval_metadata_can_be_updated_without_breaking_checks(self):
        m=copy.deepcopy(self.palette)
        m['figure_conventions_approved']=True
        for asset in m['assets'].values():
            asset['approved_for_press']=True
        self.assertEqual(validate_map(m),[])

    def test_duplicate_or_unsafe_asset_alias_is_rejected(self):
        m=copy.deepcopy(self.palette)
        m['assets']['header_icon']['aliases']=['assets/chapter-photo-sample.png']
        self.assertTrue(any('duplicate' in e for e in validate_map(m)))
        m['assets']['header_icon']['active_path']='../other.png'
        self.assertTrue(any('invalid asset path' in e for e in validate_map(m)))


class SourceScanTests(unittest.TestCase):
    roles={'BookPrimary':'Spot100','BookInk':'Black100'}

    def test_semantic_drawing_and_documented_literal_are_allowed(self):
        self.assertEqual(scan_source(r'\draw[thick,draw=BookPrimary] (0,0)--(1,1); \texttt{black!40}',self.roles),[])

    def test_literal_late_tikz_option_and_color_key_are_rejected(self):
        self.assertTrue(scan_source(r'\draw[thick,red] (0,0)--(1,1);',self.roles))
        self.assertTrue(scan_source(r'\node[draw=cyan] {x};',self.roles))

    def test_explicit_color_model_and_ad_hoc_mix_are_rejected(self):
        self.assertTrue(scan_source(r'\textcolor[RGB]{255,0,0}{x}',self.roles))
        self.assertTrue(scan_source(r'\draw[draw=BookPrimary!45] (0,0)--(1,1);',self.roles))

    def test_transparency_and_shading_are_rejected(self):
        self.assertTrue(scan_source(r'\path[fill=BookPrimary,opacity=.4] (0,0) rectangle (1,1);',self.roles))
        self.assertTrue(scan_source(r'\shade (0,0) rectangle (1,1);',self.roles))
        self.assertEqual(scan_source(r'\path[fill=BookPrimary,opacity=1] (0,0) rectangle (1,1);',self.roles),[])

    def test_direct_images_bypass_manifest(self):
        self.assertTrue(scan_source(r'\includegraphics{rogue.png}',self.roles,authoring=True))


class WholeSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        for name in ['config','styles','chapters','solutions','assets']:
            shutil.copytree(ROOT/name,self.root/name)
        for path in ROOT.glob('*.tex'):
            shutil.copy2(path,self.root/path.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_current_sources_pass_and_entrypoint_escape_fails(self):
        self.assertEqual(validate(self.root),[])
        p=self.root/'main-print2.tex'
        p.write_text(p.read_text()+r'\textcolor{red}{Unmanaged}',encoding='utf-8')
        self.assertTrue(any('main-print2.tex' in e and 'unmanaged' in e for e in validate(self.root)))

    def test_private_callout_redefinition_is_rejected(self):
        p=self.root/'styles/universalbook.sty'
        p.write_text(p.read_text()+r'\newtcolorbox{ThinkBox}{colback=BookThinkBackground}')
        self.assertTrue(any('bypasses shared construction' in e for e in validate(self.root)))

    def test_callout_role_drift_is_rejected(self):
        p=self.root/'styles/book-callouts.tex'
        p.write_text(p.read_text().replace(
            r'\BookDeclareCallout{ThinkBox}{white}',
            r'\BookDeclareCallout{ThinkBox}{BookAlertBackground}'))
        self.assertTrue(any('ThinkBox: must use the shared factory' in e for e in validate(self.root)))

    def test_factory_must_actually_delegate_to_shared_renderer(self):
        p=self.root/'styles/book-callouts.tex'
        original=p.read_text()
        for old,new,message in [
            (r'\newtcolorbox{#1}{BookCalloutRender=',
             r'\newtcolorbox{#1}{BookPanel=', 'must delegate to the common renderer'),
            (',BookCalloutDecoration/#1', '', 'must apply its registered decoration'),
        ]:
            with self.subTest(removed=old):
                self.assertIn(old,original)
                p.write_text(original.replace(old,new))
                self.assertTrue(any(message in e for e in validate(self.root)))

    def test_west_rule_surface_and_page_continuation_contract_is_enforced(self):
        p=self.root/'styles/book-callouts.tex'
        original=p.read_text()
        for old,new,message in [
            ('no borderline,interior hidden,', 'no borderline,',
             'ThinkBox: unfilled west-rule decoration must suppress'),
            (r'borderline west={\BookStableCalloutRuleWidth}{0pt}{BookCalloutAccent}', '',
             'HistoryBox: accent-rule decoration must replace'),
            (r'borderline west={\BookStableCalloutRuleWidth}{0pt}{BookCalloutAccent}',
             r'borderline west={\BookStableCalloutRuleWidth}{0pt}{BookHistory}',
             'HistoryBox: accent-rule decoration must replace'),
            ('BookCalloutDecoration/HistoryBox/.style={%',
             'BookCalloutDecoration/HistoryBox/.style={%\n    interior hidden,',
             'HistoryBox: accent-rule decoration must preserve the common fill'),
            ('BookCalloutDecoration/ThinkBox/.style={%',
             'BookCalloutDecoration/ThinkBox/.style={%\n    underlay middle={},',
             'ThinkBox: accent-rule decoration must preserve the common fill'),
            ('BookCalloutDecoration/ThinkBox/.style={%',
             'BookCalloutDecoration/ThinkBox/.style={%\n    borderline east={1pt}{0pt}{BookCalloutAccent},',
             'ThinkBox: accent-rule decoration must preserve the common fill'),
        ]:
            with self.subTest(changed=old):
                self.assertIn(old,original)
                p.write_text(original.replace(old,new,1))
                self.assertTrue(any(message in e for e in validate(self.root)))

    def test_attention_rule_preserves_fill_and_shared_first_fragment_icon(self):
        p=self.root/'styles/book-callouts.tex'
        original=p.read_text()
        marker='BookCalloutDecoration/AttentionBox/.style={%'
        self.assertIn(marker,original)
        for extra,message in [
            ('interior hidden,', 'must preserve the common fill'),
            ('borderline={1pt}{0pt}{BookCalloutAccent},', 'must preserve the common fill'),
            ('overlay first={},', 'must retain the shared first-piece-only icon overlays'),
        ]:
            with self.subTest(extra=extra):
                p.write_text(original.replace(marker,marker+'\n    '+extra,1))
                self.assertTrue(any('AttentionBox:' in e and message in e for e in validate(self.root)))
        for old,new in [
            (r'borderline west={\BookAttentionRuleWidth}{0pt}{BookCalloutAccent}', ''),
            (r'borderline west={\BookAttentionRuleWidth}{0pt}{BookCalloutAccent}',
             r'borderline west={\BookAttentionRuleWidth}{0pt}{BookHistory}'),
        ]:
            with self.subTest(replacement=new):
                self.assertIn(old,original)
                p.write_text(original.replace(old,new,1))
                self.assertTrue(any('AttentionBox: accent-rule decoration must replace' in e
                                    for e in validate(self.root)))

    def test_callout_break_overlay_cannot_be_removed_for_one_box(self):
        p=self.root/'styles/book-callouts.tex'
        p.write_text(p.read_text().replace(
            r'overlay first={\BookCalloutCenteredIcon{#3}}',
            'overlay first={}'))
        self.assertTrue(any('first-piece icon pipeline is incomplete' in e for e in validate(self.root)))

    def test_history_optional_title_signature_is_preserved(self):
        p=self.root/'styles/book-callouts.tex'
        p.write_text(p.read_text().replace(
            r'\BookDeclareTitledCallout{HistoryBox}',
            r'\BookDeclareCallout{HistoryBox}'))
        self.assertTrue(any('HistoryBox: must use the shared factory' in e for e in validate(self.root)))

    def test_generated_file_drift_fails(self):
        p=self.root/'config/palette-screen.tex'
        p.write_text(p.read_text().replace('8493A9','7E93A9'))
        self.assertTrue(any('out of sync' in e for e in validate(self.root)))

    def test_new_unregistered_asset_fails(self):
        p=self.root/'book-content.tex'
        p.write_text(p.read_text()+r'\BookUseAsset{not_registered}')
        self.assertTrue(any('unregistered asset' in e for e in validate(self.root)))

    def test_neutral_rgb_raster_still_requires_native_gray(self):
        from PIL import Image
        p=self.root/'assets/photo-K-3tones.png'
        with Image.open(p) as im:
            rgb=im.convert('RGB')
        rgb.save(p)
        self.assertTrue(any('native grayscale' in e for e in validate(self.root)))


if __name__=='__main__':
    unittest.main()

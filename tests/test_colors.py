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
        p=self.root/'assets/header-icon-black.png'
        with Image.open(p) as im:
            rgb=im.convert('RGB')
        rgb.save(p)
        self.assertTrue(any('native grayscale' in e for e in validate(self.root)))


if __name__=='__main__':
    unittest.main()

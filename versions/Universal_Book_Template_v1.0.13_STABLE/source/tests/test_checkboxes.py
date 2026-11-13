"""Real-PDF regressions for the shared true/false and choice checkbox.

The fixture records a measured Greek-capital height. Tests compare it with
actual PDF text baselines and square vectors, rather than inspecting the TeX
implementation or relying on raster snapshots.
"""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import fitz


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/checkboxes.tex"


def load_helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SETUP = load_helper("checkboxes_setup", ROOT / "scripts/setup_environment.py")
PREFLIGHT = load_helper("checkboxes_preflight", ROOT / "scripts/validate_pdf.py")
ROWS = {"NORMALTF": 2, "NORMALMC": 3, "SMALLTF": 2, "SMALLMC": 3}
TEX_PT_TO_BP = 72 / 72.27


def inspect_checkbox_page(page):
    spans = [span for block in page.get_text("dict")["blocks"]
             for line in block.get("lines", []) for span in line["spans"]]
    markers = {name: next(span for span in spans if name in span["text"])
               for name in ROWS}
    squares = [drawing for drawing in page.get_drawings()
               if drawing.get("color") is not None
               and 7 < drawing["rect"].width < 9
               and 7 < drawing["rect"].height < 9]
    assigned = {name: [] for name in ROWS}
    for square in squares:
        cy = (square["rect"].y0 + square["rect"].y1) / 2
        nearest = min(ROWS, key=lambda name: abs(cy - markers[name]["origin"][1]))
        assigned[nearest].append(square)
    return {"markers": markers, "squares": squares, "by_row": assigned}


@unittest.skipUnless(shutil.which("xelatex") and shutil.which("gs"),
                     "XeLaTeX and Ghostscript are required for checkbox PDF tests")
class CheckboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ".local/fontconfig.xml").exists():
            raise unittest.SkipTest("Run scripts/setup_environment.py before checkbox PDF tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="book-checkboxes-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.documents, cls.paths, cls.cap_heights = {}, {}, {}
        for edition in ("screen", "print"):
            folder = Path(cls.temp.name) / edition
            folder.mkdir()
            source = folder / "checkboxes.tex"
            prefix = "\\def\\CheckboxesPrint{1}\n" if edition == "print" else ""
            source.write_text(prefix + FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            command = ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                       "-no-shell-escape", f"-output-directory={folder}", str(source)]
            result = subprocess.run(command, cwd=ROOT, env=SETUP.runtime_env(),
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError(f"{edition} checkbox fixture failed:\n"
                                   + (result.stdout + result.stderr)[-6000:])
            cls.cap_heights[edition] = {
                name: float(height) * TEX_PT_TO_BP
                for name, height in re.findall(r"CHECKCAP:([A-Z]+):([0-9.]+)pt", result.stdout)}
            cls.paths[edition] = folder / "checkboxes.pdf"
            with fitz.open(cls.paths[edition]) as pdf:
                if len(pdf) != 1:
                    raise AssertionError(f"{edition}: checkbox fixture must fit on one page")
                cls.documents[edition] = inspect_checkbox_page(pdf[0])

    def test_square_centers_align_with_capital_midline_at_body_and_small_sizes(self):
        for edition, page in self.documents.items():
            self.assertEqual(set(self.cap_heights[edition]), set(ROWS))
            for name, expected_count in ROWS.items():
                with self.subTest(edition=edition, row=name):
                    self.assertEqual(len(page["by_row"][name]), expected_count)
                    baseline = page["markers"][name]["origin"][1]
                    expected_center = baseline - self.cap_heights[edition][name] / 2
                    for square in page["by_row"][name]:
                        actual_center = (square["rect"].y0 + square["rect"].y1) / 2
                        self.assertAlmostEqual(actual_center, expected_center, delta=.03)
            self.assertGreater(self.cap_heights[edition]["NORMALTF"],
                               self.cap_heights[edition]["SMALLTF"])

    def test_true_false_and_multiple_choice_share_size_stroke_and_ink(self):
        reference = self.documents["screen"]["squares"][0]
        expected_side = 2.7 * 72 / 25.4
        for edition, page in self.documents.items():
            self.assertEqual(len(page["squares"]), sum(ROWS.values()))
            for square in page["squares"]:
                with self.subTest(edition=edition, rect=square["rect"]):
                    self.assertAlmostEqual(square["rect"].width, expected_side, delta=.02)
                    self.assertAlmostEqual(square["rect"].height, expected_side, delta=.02)
                    self.assertAlmostEqual(square["width"], .55 * TEX_PT_TO_BP, delta=.002)
                    self.assertAlmostEqual(square["width"], reference["width"], delta=.002)
                    self.assertIsNone(square.get("fill"))
                    self.assertEqual(square["color"], page["squares"][0]["color"])
                    if edition == "screen":
                        expected_rgb = tuple(v / 255 for v in (32, 59, 99))
                        for actual, expected in zip(square["color"], expected_rgb):
                            # PGF may emit three-decimal color operands. The
                            # paired raster check below verifies final pixels.
                            self.assertAlmostEqual(actual, expected, delta=.00051)

    def test_paired_fixture_preserves_only_approved_inks_tints_and_color_roles(self):
        palette = json.loads((ROOT / "config/color-map.json").read_text(encoding="utf-8"))
        report = PREFLIGHT.validate(self.paths["print"], self.paths["screen"], palette, dpi=72)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["rendered"]["pairing_mismatched_pixels"], 0)


if __name__ == "__main__":
    unittest.main()

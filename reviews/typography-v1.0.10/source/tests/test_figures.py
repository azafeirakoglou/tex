"""Physical, typographic and ink regressions for TikZ and PGFPlots figures.

Assertions inspect the compiled PDFs. They do not match style definitions or
use generated raster snapshots as a self-referential reference.
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
FIXTURE = ROOT / "tests/fixtures/figures.tex"
PT_TO_BP = 72 / 72.27
MM_TO_BP = 72 / 25.4
ROWS = {
    "MAINCURVE": (1.05, "main", False),
    "SECONDCURVE": (1.05, "main", True),
    "REFCURVE": (1.05, "black", False),
    "MAINVECTOR": (1.12, "main", False),
    "SECONDVECTOR": (1.12, "main", True),
    "REFVECTOR": (1.12, "black", False),
    "AXIS": (.72, "black", False),
    "GUIDE": (.45, "guide", True),
    "TICKROW": (.5, "black", False),
    "SCALEONE": (1.05, "main", False),
    "SCALEHALF": (1.05, "main", False),
}


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SETUP = helper("figures_setup", ROOT / "scripts/setup_environment.py")
PREFLIGHT = helper("figures_preflight", ROOT / "scripts/validate_pdf.py")


def spans_on(page):
    return [span for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", []) for span in line["spans"]]


def dashed(path):
    pattern = re.search(r"\[([^]]*)\]", path.get("dashes", ""))
    return bool(pattern and pattern.group(1).strip())


def drawn_bounds(page, ignore_text=()):
    """Include outside labels, ticks and arrowheads in physical size checks."""
    rectangles = [fitz.Rect(drawing["rect"]) for drawing in page.get_drawings()]
    rectangles += [fitz.Rect(span["bbox"]) for span in spans_on(page)
                   if span["text"] not in ignore_text]
    if not rectangles:
        raise AssertionError("The figure must contain actual vector paths and labels")
    bounds = rectangles[0]
    for rect in rectangles[1:]:
        bounds |= rect
    return bounds


@unittest.skipUnless(shutil.which("xelatex") and shutil.which("gs"),
                     "XeLaTeX and Ghostscript are required for figure PDF tests")
class FigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ".local/fontconfig.xml").exists():
            raise unittest.SkipTest("Run scripts/setup_environment.py before figure PDF tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="book-figures-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.documents, cls.paths, cls.rows = {}, {}, {}
        for edition in ("screen", "print"):
            folder = Path(cls.temp.name) / edition
            folder.mkdir()
            source = folder / "figures.tex"
            prefix = "\\def\\FiguresPrint{1}\n" if edition == "print" else ""
            source.write_text(prefix + FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            command = ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                       "-no-shell-escape", f"-output-directory={folder}", str(source)]
            for _ in range(2):
                result = subprocess.run(command, cwd=ROOT, env=SETUP.runtime_env(),
                                        capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise RuntimeError(f"{edition} figure fixture failed:\n"
                                       + (result.stdout + result.stderr)[-6000:])
            if "Overfull \\hbox" in result.stdout:
                raise AssertionError(f"{edition}: the figure fixture overflows its text column")
            cls.paths[edition] = folder / "figures.pdf"
            pdf = fitz.open(cls.paths[edition])
            cls.addClassCleanup(pdf.close)
            if len(pdf) != 3:
                raise AssertionError(f"{edition}: expected three controlled figure pages")
            cls.documents[edition] = pdf
            spans = spans_on(pdf[0])
            markers = {name: next(s for s in spans if s["text"] == name) for name in ROWS}
            candidates = [d for d in pdf[0].get_drawings() if d.get("color") is not None
                          and d["rect"].width > 50 and d["rect"].height < .1]
            assigned = {name: [] for name in ROWS}
            for path in candidates:
                y = (path["rect"].y0 + path["rect"].y1) / 2
                name = min(ROWS, key=lambda key: abs(y - markers[key]["origin"][1]))
                assigned[name].append(path)
            cls.rows[edition] = assigned

    def line(self, edition, name):
        paths = self.rows[edition][name]
        self.assertEqual(len(paths), 1, f"{edition}: expected one actual {name} stroke")
        return paths[0]

    def test_tikz_strokes_keep_physical_widths_and_scaled_geometry_does_not_scale_ink(self):
        for edition in self.documents:
            for name, (width, _, _) in ROWS.items():
                with self.subTest(edition=edition, name=name):
                    self.assertAlmostEqual(self.line(edition, name)["width"],
                                           width * PT_TO_BP, delta=.002)
            one = self.line(edition, "SCALEONE")
            half = self.line(edition, "SCALEHALF")
            self.assertAlmostEqual(one["rect"].width, 20 * MM_TO_BP, delta=.03)
            self.assertAlmostEqual(half["rect"].width, one["rect"].width, delta=.03)
            self.assertAlmostEqual(half["width"], one["width"], delta=.002)

    def test_emphasis_and_secondary_share_the_second_ink_with_distinct_line_patterns(self):
        screen_colors = {"main": (32, 59, 99), "black": (0, 0, 0),
                         "guide": (115, 115, 115)}
        for edition in self.documents:
            for name, (_, role, expected_dashed) in ROWS.items():
                with self.subTest(edition=edition, name=name):
                    path = self.line(edition, name)
                    self.assertEqual(dashed(path), expected_dashed)
                    if edition == "screen":
                        for actual, value in zip(path["color"], screen_colors[role]):
                            self.assertAlmostEqual(actual, value / 255, delta=.00051)
            self.assertEqual(self.line(edition, "MAINCURVE")["color"],
                             self.line(edition, "SECONDCURVE")["color"])
            self.assertEqual(self.line(edition, "MAINVECTOR")["color"],
                             self.line(edition, "SECONDVECTOR")["color"])

    def test_labels_use_nine_points_and_ticks_eight_in_full_and_column_figures(self):
        for edition, pdf in self.documents.items():
            with self.subTest(edition=edition):
                spans = spans_on(pdf[0])
                for marker in tuple(ROWS) + ("DEFAULTFONT", "ATTACHEDLABEL"):
                    span = next(s for s in spans if s["text"] == marker)
                    self.assertEqual(span["font"], "Inter-Regular")
                    self.assertAlmostEqual(span["size"], 9 * PT_TO_BP, delta=.01)
                    self.assertEqual(span["color"], 0)
                tick = next(s for s in spans if s["text"] == "TICKFONT")
                self.assertEqual(tick["font"], "Inter-Regular")
                self.assertAlmostEqual(tick["size"], 8 * PT_TO_BP, delta=.01)
                for index, prefix in ((1, "FULL"), (2, "COLUMN")):
                    chart_spans = spans_on(pdf[index])
                    for suffix in ("X", "Y"):
                        label = next(s for s in chart_spans if prefix + suffix in s["text"])
                        self.assertEqual(label["font"], "Inter-Regular")
                        self.assertAlmostEqual(label["size"], 9 * PT_TO_BP, delta=.01)
                        self.assertEqual(label["color"], 0)
                        label_lines = [line for block in pdf[index].get_text("dict")["blocks"]
                                       for line in block.get("lines", [])
                                       if any(prefix + suffix in span["text"]
                                              for span in line["spans"])]
                        self.assertEqual(len(label_lines), 1)
                        # Axis names and SI units remain horizontal; PGF's
                        # default ylabel rotation must not survive the style.
                        self.assertAlmostEqual(label_lines[0]["dir"][0], 1, delta=.001)
                        self.assertAlmostEqual(label_lines[0]["dir"][1], 0, delta=.001)
                    ticks = [s for s in chart_spans if s["text"].strip().isdigit()]
                    self.assertGreaterEqual(len(ticks), 7)
                    for tick in ticks:
                        self.assertAlmostEqual(tick["size"], 8 * PT_TO_BP, delta=.01)
                        self.assertEqual(tick["color"], 0)

    def test_pgf_curves_use_same_physical_weight_and_patterns_at_both_sizes(self):
        for edition, pdf in self.documents.items():
            for index in (1, 2):
                with self.subTest(edition=edition, page=index + 1):
                    # Each fixture series is a single straight segment; grid
                    # lines have distinct thinner weights and black/gray ink.
                    curves = [d for d in pdf[index].get_drawings()
                              if d.get("color") is not None
                              and abs(d["width"] - 1.05 * PT_TO_BP) < .002]
                    self.assertEqual(len(curves), 2)
                    self.assertEqual(sorted(dashed(p) for p in curves), [False, True])
                    self.assertEqual(curves[0]["color"], curves[1]["color"])
                    if edition == "screen":
                        for actual, value in zip(curves[0]["color"], (32, 59, 99)):
                            self.assertAlmostEqual(actual, value / 255, delta=.00051)

    def test_full_and_column_widths_include_labels_and_never_overflow_their_gutters(self):
        for edition, pdf in self.documents.items():
            with self.subTest(edition=edition):
                full = drawn_bounds(pdf[1], ("FULLPLOT",))
                column = drawn_bounds(pdf[2], ("COLUMNPLOT",))
                self.assertGreater(full.width / MM_TO_BP, 80)
                self.assertLessEqual(full.width / MM_TO_BP, 133)
                self.assertGreater(column.width / MM_TO_BP, 35)
                self.assertLessEqual(column.width / MM_TO_BP, 63.5)
                self.assertLess(column.width, full.width * .75)
                self.assertGreaterEqual(full.x0, 17 * MM_TO_BP - .1)
                self.assertLessEqual(full.x1, 150 * MM_TO_BP + .1)
                self.assertGreaterEqual(column.x0, 20 * MM_TO_BP - .1)
                self.assertLessEqual(column.x1, 83.5 * MM_TO_BP + .1)
                self.assertFalse(pdf[1].get_images())
                self.assertFalse(pdf[2].get_images())

    def test_pair_uses_only_the_approved_inks_tints_and_identical_color_roles(self):
        palette = json.loads((ROOT / "config/color-map.json").read_text(encoding="utf-8"))
        report = PREFLIGHT.validate(self.paths["print"], self.paths["screen"], palette, dpi=72)
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["rendered"]["pairing_mismatched_pixels"], 0)


if __name__ == "__main__":
    unittest.main()

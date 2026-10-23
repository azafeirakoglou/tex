"""Behavioral PDF regressions for running headers, marks and page styles.

One shared fixture is compiled per edition. No source-text matching is used:
assertions inspect text, vector geometry and rules in the actual PDFs.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import fitz
from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/page-styles.tex"
SETUP_SPEC = importlib.util.spec_from_file_location(
    "page_styles_setup", ROOT / "scripts/setup_environment.py")
SETUP = importlib.util.module_from_spec(SETUP_SPEC)
SETUP_SPEC.loader.exec_module(SETUP)
PDF_SPEC = importlib.util.spec_from_file_location(
    "page_styles_pdf", ROOT / "scripts/validate_pdf.py")
PDF = importlib.util.module_from_spec(PDF_SPEC)
PDF_SPEC.loader.exec_module(PDF)

NORMAL = ("BODY-NORMAL-ONE", "BODY-NORMAL-TWO", "BODY-AFTER-FIRST",
          "BODY-AFTER-SECOND")
CRITERIA = ("BODY-FIRST-ONE", "BODY-FIRST-TWO", "BODY-SECOND-ONE", "BODY-SECOND-TWO")
MARKRIGHT = ("BODY-AFTER-MARKRIGHT", "BODY-MARKRIGHT-EVEN")
RUNNING = NORMAL + CRITERIA + MARKRIGHT + ("BODY-AFTER-CHAPTER", "BODY-FINAL-ASSESSMENT")


def vector_group(paths):
    if not paths:
        return []
    bounds = fitz.Rect(paths[0]["rect"])
    for path in paths[1:]:
        bounds |= path["rect"]
    return [{"bbox": tuple(bounds), "paths": paths}]


def path_geometry(bird, width=None):
    """Flatten actual path points; reflect an even page into odd-page space."""
    signature, coordinates = [], []
    for path in bird["paths"]:
        signature.append((path["type"], path.get("even_odd"), path.get("closePath")))
        for item in path["items"]:
            signature.append((item[0], len(item) - 1))
            for value in item[1:]:
                if isinstance(value, fitz.Point):
                    coordinates.extend((width - value.x if width is not None else value.x,
                                        value.y))
                elif isinstance(value, fitz.Rect):
                    for x, y in ((value.x0, value.y0), (value.x1, value.y1)):
                        coordinates.extend((width - x if width is not None else x, y))
                else:
                    signature.append(value)
    return signature, coordinates


def page_data(page, index):
    spans = [span for block in page.get_text("dict")["blocks"]
             for line in block.get("lines", []) for span in line["spans"]]
    drawings = page.get_drawings()
    filled = [path for path in drawings if path.get("fill") is not None
              and path["rect"].width > .01 and path["rect"].height > .01
              and path["rect"].width < 50 and path["rect"].height < 30]
    return {
        "index": index,
        "text": page.get_text(),
        "width": page.rect.width,
        "header": [s for s in spans if s["bbox"][1] < 45],
        "footer": [s for s in spans if s["bbox"][1] > 640],
        "header_images": [im for im in page.get_image_info() if im["bbox"][1] < 45],
        "birds": vector_group([path for path in filled if path["rect"].y1 < 40]),
        "body_vectors": vector_group([path for path in filled if 45 < path["rect"].y0 < 630]),
        "rules": [d for d in drawings
                  if d["rect"].y1 < 45 and d["rect"].width > 300],
    }


@unittest.skipUnless(shutil.which("xelatex"), "XeLaTeX is required for page-style regressions")
class PageStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ".local/fontconfig.xml").exists():
            raise unittest.SkipTest("Run scripts/setup_environment.py before page-style PDF tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="book-page-styles-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.documents, cls.paths, cls.icon_metrics = {}, {}, {}
        for edition in ("screen", "print"):
            folder = Path(cls.temp.name) / edition
            folder.mkdir()
            source = folder / "page-styles.tex"
            prefix = "\\def\\PageStylesPrint{1}\n" if edition == "print" else ""
            source.write_text(prefix + FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            command = ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                       "-no-shell-escape", f"-output-directory={folder}", str(source)]
            for _ in range(2):
                result = subprocess.run(command, cwd=ROOT, env=SETUP.runtime_env(),
                                        capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise RuntimeError(f"{edition} page-style fixture failed:\n"
                                       + (result.stdout + result.stderr)[-6000:])
            match = re.search(r"HEADERICONMETRICS:([0-9.-]+)pt:([0-9.-]+)pt:([0-9.-]+)pt",
                              result.stdout)
            if not match:
                raise AssertionError(f"{edition}: missing fixture icon dimensions")
            cls.icon_metrics[edition] = tuple(float(value) for value in match.groups())
            cls.paths[edition] = folder / "page-styles.pdf"
            with fitz.open(cls.paths[edition]) as pdf:
                cls.documents[edition] = [page_data(page, i + 1) for i, page in enumerate(pdf)]

    def find(self, edition, marker):
        matches = [page for page in self.documents[edition] if marker.replace("-", "") in page["text"]]
        self.assertEqual(len(matches), 1, f"{edition}: expected exactly one {marker} page")
        return matches[0]

    def header_text(self, page):
        return " ".join(span["text"] for span in page["header"])

    def test_both_original_marks_return_after_each_sequential_assessment(self):
        for edition in self.documents:
            for marker in NORMAL:
                with self.subTest(edition=edition, marker=marker):
                    header = self.header_text(self.find(edition, marker))
                    self.assertIn("ORIGINALLEFT", header)
                    self.assertIn("ORIGINALRIGHT", header)
                    self.assertNotIn("ASSESSMENT", header)
            for marker in MARKRIGHT:
                with self.subTest(edition=edition, marker=marker):
                    header = self.header_text(self.find(edition, marker))
                    self.assertIn("ORIGINALLEFT", header)
                    self.assertIn("NEXTRIGHT", header)
                    self.assertNotIn("ORIGINALRIGHT", header)

    def test_each_assessment_keeps_its_own_title_and_number_on_both_parities(self):
        for edition in self.documents:
            for prefix, number, title in (("FIRST", "1", "ASSESSMENTONE"),
                                          ("SECOND", "2", "ASSESSMENTTWO")):
                pair = [self.find(edition, f"BODY-{prefix}-{suffix}") for suffix in ("ONE", "TWO")]
                self.assertEqual({page["index"] % 2 for page in pair}, {0, 1})
                for page in pair:
                    with self.subTest(edition=edition, page=page["index"]):
                        header = self.header_text(page)
                        self.assertIn(title, header)
                        self.assertIn("Κριτήριο αξιολόγησης " + number, header)
                        self.assertNotIn("ORIGINAL", header)

    def test_header_bird_height_vertical_position_and_horizontal_mirror_match(self):
        for edition in self.documents:
            pages = [self.find(edition, marker) for marker in RUNNING]
            reference_body = self.find(edition, "BODY-EXPLICIT-EMPTY")["body_vectors"]
            self.assertEqual(len(reference_body), 1)
            body_bounds = fitz.Rect(reference_body[0]["bbox"])
            logical_width, height, depth = self.icon_metrics[edition]
            self.assertAlmostEqual((height + depth) * 25.4 / 72.27, 6.4, delta=.01)
            self.assertAlmostEqual(logical_width / (height + depth), 160 / 139, delta=.002)
            self.assertLessEqual(body_bounds.height, (height + depth) * 72 / 72.27 + .02)
            self.assertAlmostEqual(body_bounds.width / (logical_width * 72 / 72.27),
                                   152 / 160, delta=.002)
            self.assertAlmostEqual(body_bounds.height / ((height + depth) * 72 / 72.27),
                                   130 / 139, delta=.002)
            reference_top = pages[0]["birds"][0]["bbox"][1]
            reference_shape, reference_points = path_geometry(pages[0]["birds"][0])
            odd, even = {}, {}
            for page in pages:
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["birds"]), 1)
                    bird = page["birds"][0]
                    x0, y0, x1, y1 = bird["bbox"]
                    (odd if page["index"] % 2 else even)[page["index"]] = (x0, x1)
                    self.assertAlmostEqual(y1 - y0, body_bounds.height, delta=.02)
                    self.assertAlmostEqual(x1 - x0, body_bounds.width, delta=.02)
                    self.assertAlmostEqual(y0, reference_top, delta=.02)
                    signature, points = path_geometry(
                        bird, page["width"] if page["index"] % 2 == 0 else None)
                    self.assertEqual(signature, reference_shape)
                    self.assertEqual(len(points), len(reference_points))
                    for actual, expected in zip(points, reference_points):
                        self.assertAlmostEqual(actual, expected, delta=.02)
            first_odd, first_even = next(iter(odd.values())), next(iter(even.values()))
            self.assertAlmostEqual(first_even[0], pages[0]["width"] - first_odd[1], delta=.02)
            self.assertAlmostEqual(first_even[1], pages[0]["width"] - first_odd[0], delta=.02)

    def test_header_bird_is_vector_and_uses_the_label_ink_at_full_tint(self):
        for edition in self.documents:
            for marker in RUNNING:
                page = self.find(edition, marker)
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertFalse(page["header_images"], "Header bird must contain no raster image")
                    self.assertEqual(len(page["birds"]), 1)
                    label = next(s for s in page["header"] if s["font"] == "Inter-SemiBold")
                    label_rgb = tuple((label["color"] >> shift) & 255 for shift in (16, 8, 0))
                    for path in page["birds"][0]["paths"]:
                        self.assertIn("f", path["type"], "Bird must use filled vector paths")
                        for channel, expected in zip(path["fill"], label_rgb):
                            self.assertAlmostEqual(channel * 255, expected, delta=1)
        # Inspect actual separations inside the ink bounds. A matching RGB
        # preview alone would not establish that the PRINT uses the spot plate.
        folder = Path(self.temp.name) / "bird-plates"
        folder.mkdir(exist_ok=True)
        dpi = 144
        PDF.run_gs("tiffsep", self.paths["print"], folder / "bird-%d.tif", dpi)
        palette = json.loads((ROOT / "config/color-map.json").read_text(encoding="utf-8"))
        spot_name = palette["spot_ink_name"]
        for marker in RUNNING:
            page = self.find("print", marker)
            bounds = page["birds"][0]["bbox"]
            crop = (math.floor(bounds[0] * dpi / 72), math.floor(bounds[1] * dpi / 72),
                    math.ceil(bounds[2] * dpi / 72), math.ceil(bounds[3] * dpi / 72))
            found_spot = False
            for path in folder.glob(f"bird-{page['index']}(*).tif"):
                plate = path.name.split("(", 1)[1].rsplit(")", 1)[0]
                with Image.open(path) as image:
                    values = set(PDF.pixels(image.convert("L").crop(crop)))
                with self.subTest(page=page["index"], plate=plate):
                    if plate == spot_name:
                        found_spot = True
                        self.assertIn(0, values, "Bird must mark the spot plate at 100%")
                        self.assertLessEqual(values, {0, 255}, "Bird must use full tint without extra tones")
                    else:
                        self.assertEqual(values, {255}, "Bird must not mark any other ink plate")
            self.assertTrue(found_spot)

    def test_vector_bird_matches_the_archived_binary_shape_on_its_native_grid(self):
        # The approved old image is retained solely as geometry evidence. Work
        # at its native grid so recoloring does not affect the comparison.
        reference_file = ROOT / "archive/legacy-sources/header-icon-black.png"
        with Image.open(reference_file) as image:
            reference = image.convert("L")
        self.assertEqual(reference.size, (160, 139))
        self.assertLessEqual(set(PDF.pixels(reference)), {0, 255})
        page = self.find("screen", "BODY-EXPLICIT-EMPTY")
        bounds = fitz.Rect(page["body_vectors"][0]["bbox"])
        logical_width, height, depth = self.icon_metrics["screen"]
        cassette_width = logical_width * 72 / 72.27
        cassette_height = (height + depth) * 72 / 72.27
        # Pixel contour ink bounds are (4, 4, 156, 134) on the 160x139
        # cassette. Recover the full transparent margin around the ink.
        x0 = bounds.x0 - 4 / 160 * cassette_width
        y0 = bounds.y0 - 4 / 139 * cassette_height
        cassette = fitz.Rect(x0, y0, x0 + cassette_width, y0 + cassette_height)
        # Invert actual PDF coordinates into the native pixel-edge grid. PDF
        # number serialization introduces <.01 pixel rounding here; assert the
        # grid explicitly before sampling the exact filled shape at pixel
        # centers. This avoids renderer-specific rules for pixels that merely
        # touch an edge (Ghostscript conservatively marks such edge pixels).
        actual = Image.new("L", (160, 139), 255)
        for path in page["body_vectors"][0]["paths"]:
            edges = []
            for item in path["items"]:
                self.assertEqual(item[0], "l", "Lossless pixel contours must retain straight edges")
                endpoints = []
                for point in item[1:]:
                    x = (point.x - cassette.x0) / cassette.width * 160
                    y = (point.y - cassette.y0) / cassette.height * 139
                    self.assertAlmostEqual(x, round(x), delta=.01)
                    self.assertAlmostEqual(y, round(y), delta=.01)
                    endpoints.append((round(x), round(y)))
                (xa, ya), (xb, yb) = endpoints
                self.assertTrue(xa == xb or ya == yb, "Pixel contours must remain axis-aligned")
                edges.append(((xa, ya), (xb, yb)))
            for y in range(139):
                center_y = y + .5
                crossings = []
                for (xa, ya), (xb, yb) in edges:
                    if ya <= center_y < yb:
                        crossings.append((xa, 1))
                    elif yb <= center_y < ya:
                        crossings.append((xb, -1))
                for x in range(160):
                    winding = sum(direction for edge_x, direction in crossings if edge_x <= x + .5)
                    inside = winding % 2 != 0 if path.get("even_odd") else winding != 0
                    if inside:
                        actual.putpixel((x, y), 0)
        difference = ImageChops.difference(actual, reference)
        self.assertIsNone(difference.getbbox(), "Vector contour changes the original bird silhouette")

    def test_running_and_plain_pages_share_header_rules_fonts_and_footer_alignment(self):
        for edition in self.documents:
            pages = [self.find(edition, marker) for marker in RUNNING]
            reference_header = pages[0]["header"]
            reference_footer = pages[0]["footer"][0]
            reference_rule = pages[0]["rules"][0]
            footer_anchors = {}
            for page in pages:
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["header"]), 2)
                    label = next(s for s in page["header"] if s["font"] == "Inter-SemiBold")
                    title = next(s for s in page["header"] if s["font"] == "Inter-Regular")
                    self.assertEqual(title["color"], 0)
                    ref_label = next(s for s in reference_header if s["font"] == "Inter-SemiBold")
                    self.assertEqual(label["color"], ref_label["color"])
                    for span in (label, title):
                        self.assertAlmostEqual(span["size"], 8 * 72 / 72.27, delta=.01)
                        self.assertAlmostEqual(span["bbox"][1], reference_header[0]["bbox"][1], delta=.02)
                    self.assertEqual(len(page["rules"]), 1)
                    rule = page["rules"][0]
                    self.assertAlmostEqual(rule["width"], .35 * 72 / 72.27, delta=.002)
                    self.assertAlmostEqual(rule["rect"].y0, reference_rule["rect"].y0, delta=.02)
                    self.assertEqual(rule["color"], reference_rule["color"])
                    self.assertEqual(len(page["footer"]), 1)
                    footer = page["footer"][0]
                    self.assertEqual(footer["font"], "Inter-Regular")
                    self.assertEqual(footer["color"], 0)
                    self.assertAlmostEqual(footer["size"], reference_footer["size"], delta=.01)
                    self.assertAlmostEqual(footer["bbox"][1], reference_footer["bbox"][1], delta=.02)
                    parity = page["index"] % 2
                    anchor = footer["bbox"][2] if parity else footer["bbox"][0]
                    footer_anchors.setdefault(parity, anchor)
                    self.assertAlmostEqual(anchor, footer_anchors[parity], delta=.02)
            plain = self.find(edition, "BODY-PLAIN")
            footer = plain["footer"][0]
            parity = plain["index"] % 2
            self.assertEqual(footer["font"], reference_footer["font"])
            self.assertEqual(footer["color"], reference_footer["color"])
            self.assertAlmostEqual(footer["size"], reference_footer["size"], delta=.01)
            self.assertAlmostEqual(footer["bbox"][1], reference_footer["bbox"][1], delta=.02)
            self.assertAlmostEqual(footer["bbox"][2] if parity else footer["bbox"][0],
                                   footer_anchors[parity], delta=.02)

    def test_plain_empty_automatic_blank_and_chapter_opener_policies(self):
        for edition in self.documents:
            plain = self.find(edition, "BODY-PLAIN")
            self.assertFalse(plain["header"])
            self.assertFalse(plain["birds"])
            self.assertFalse(plain["header_images"])
            self.assertFalse(plain["rules"])
            self.assertEqual(len(plain["footer"]), 1)
            blanks = [page for page in self.documents[edition] if not page["text"].strip()]
            self.assertEqual(len(blanks), 1)
            self.assertEqual(blanks[0]["index"] % 2, 0)
            for page in (blanks[0], self.find(edition, "BODY-CHAPTER"),
                         self.find(edition, "BODY-EXPLICIT-EMPTY")):
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertFalse(page["header"])
                    self.assertFalse(page["birds"])
                    self.assertFalse(page["header_images"])
                    self.assertFalse(page["rules"])
                    self.assertFalse(page["footer"])

    def test_assessment_at_document_end_does_not_add_a_phantom_page(self):
        for edition, pages in self.documents.items():
            final = self.find(edition, "BODY-FINAL-ASSESSMENT")
            self.assertEqual(final["index"], len(pages))
            self.assertEqual(len(pages), 16)
            self.assertIn("ASSESSMENTFINAL", self.header_text(final))
            self.assertIn("Κριτήριο αξιολόγησης 3", self.header_text(final))


if __name__ == "__main__":
    unittest.main()

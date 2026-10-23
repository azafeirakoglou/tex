"""Behavioral PDF regressions for running headers, marks and page styles.

One shared fixture is compiled per edition. No source-text matching is used:
assertions inspect text, vector geometry and rules in the actual PDFs.
"""
import importlib.util
from collections import Counter, defaultdict
import hashlib
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
# Actual ink anchors measured in the approved v0.40 release PDF. The title
# redesign must not move, scale or recenter the outer logo.
LOGO_ANCHORS_BP = {
    1: (413.38116455078125, 14.174641609191895, 433.1392517089844, 31.140962600708008),
    0: (48.75052261352539, 14.174641609191895, 68.50862884521484, 31.140962600708008),
}


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
        "mark_probes": " ".join(span["text"] for span in spans
                                 if 580 < span["bbox"][1] < 635),
        "width": page.rect.width,
        "header": [s for s in spans if s["bbox"][1] < 45],
        "footer": [s for s in spans if s["bbox"][1] > 640],
        "header_images": [im for im in page.get_image_info() if im["bbox"][1] < 45],
        "birds": vector_group([path for path in filled if path["rect"].y1 < 40]),
        "body_vectors": vector_group([path for path in filled if 45 < path["rect"].y0 < 630]),
        "rules": [d for d in drawings
                  if d["rect"].y1 < 45 and d["rect"].width > 300],
        "body_frames": [d for d in drawings if d.get("color") is not None
                        and d["rect"].width > 300 and d["rect"].height < 10
                        and d["rect"].y0 > 45],
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
        cls.geometry = json.loads((ROOT / "assets/header-icon-geometry.json").read_text(encoding="utf-8"))
        cls.source_path = ROOT / cls.geometry["source_path"]
        with Image.open(cls.source_path) as source:
            cls.source_size = source.size
            foreground = source.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0)
        cls.source_bbox = foreground.getbbox()
        if cls.source_bbox is None:
            raise AssertionError("The supplied header logo has no opaque foreground")
        cls.source_reference = ImageChops.invert(foreground)
        cls.source_ink_pixels = foreground.histogram()[255]
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

    def chapter_label(self, page):
        labels = [span for span in page["header"]
                  if re.match(r"[123]\. ", span["text"])]
        self.assertEqual(len(labels), 1, f"Page {page['index']}: missing chapter label")
        return labels[0]

    def section_label(self, page):
        chapter = self.chapter_label(page)
        labels = [span for span in page["header"] if span is not chapter]
        self.assertLessEqual(len(labels), 1, f"Page {page['index']}: unexpected header text")
        return labels[0] if labels else None

    def expected_section(self, marker):
        if marker == "BODY-NORMAL-ONE":
            return "FIRSTSECTION"
        if marker == "BODY-NORMAL-TWO":
            return "SECONDSECTION"
        if marker in NORMAL + CRITERIA + MARKRIGHT:
            return "THIRDSECTION"
        return None

    def test_both_original_marks_return_after_each_sequential_assessment(self):
        for edition in self.documents:
            for marker in NORMAL:
                with self.subTest(edition=edition, marker=marker):
                    probes = self.find(edition, marker)["mark_probes"]
                    self.assertIn("LMPROBE ORIGINALLEFT", probes)
                    self.assertIn("RMPROBE ORIGINALRIGHT", probes)
                    self.assertNotIn("ASSESSMENT", probes)
            for marker in MARKRIGHT:
                with self.subTest(edition=edition, marker=marker):
                    probes = self.find(edition, marker)["mark_probes"]
                    self.assertIn("LMPROBE ORIGINALLEFT", probes)
                    self.assertIn("RMPROBE NEXTRIGHT", probes)
                    self.assertNotIn("ORIGINALRIGHT", probes)

    def test_chapter_label_survives_assessment_worksheet_and_all_chapter_routes(self):
        for edition in self.documents:
            for prefix, title in (("FIRST", "ASSESSMENTONE"), ("SECOND", "ASSESSMENTTWO")):
                pair = [self.find(edition, f"BODY-{prefix}-{suffix}") for suffix in ("ONE", "TWO")]
                self.assertEqual({page["index"] % 2 for page in pair}, {0, 1})
                for page in pair:
                    with self.subTest(edition=edition, page=page["index"]):
                        header = self.header_text(page)
                        self.assertEqual(self.chapter_label(page)["text"], "1. INITIALCHAPTER")
                        self.assertNotIn(title, header)
                        self.assertIn("LMPROBE " + title, page["mark_probes"])
                        self.assertIn("RMPROBE " + title, page["mark_probes"])
            for marker in NORMAL + MARKRIGHT:
                self.assertEqual(self.chapter_label(self.find(edition, marker))["text"], "1. INITIALCHAPTER")
            worksheet = self.find(edition, "BODY-AFTER-CHAPTER")
            self.assertEqual(self.chapter_label(worksheet)["text"], "2. CHAPTEROPENER")
            self.assertIn("Φύλλα εργασίας", worksheet["mark_probes"])
            final = self.find(edition, "BODY-FINAL-ASSESSMENT")
            self.assertEqual(self.chapter_label(final)["text"], "3. PHOTOCHAPTER")

    def test_section_short_titles_follow_page_marks_and_reset_at_both_chapter_openers(self):
        for edition in self.documents:
            for marker in RUNNING:
                page = self.find(edition, marker)
                with self.subTest(edition=edition, marker=marker):
                    label = self.section_label(page)
                    expected = self.expected_section(marker)
                    self.assertEqual(label["text"] if label else None, expected)
                    if label:
                        self.assertNotRegex(label["text"], r"\d")
                        self.assertNotIn("long section title", self.header_text(page))
                        self.assertNotIn("ASSESSMENT", label["text"])

    def test_unnumbered_chapter_labels_do_not_reuse_the_previous_chapter_number(self):
        for edition in self.documents:
            text = " ".join(self.find(edition, "BODY-EXPLICIT-EMPTY")["text"].split())
            self.assertIn("BACKPROBE BACKCHAPTER", text)
            self.assertIn("DEPTHPROBE DEPTHCHAPTER", text)

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
            frame_ink = self.geometry["frame_ink_bbox"]
            self.assertAlmostEqual(body_bounds.width / (logical_width * 72 / 72.27),
                                   (frame_ink[2] - frame_ink[0]) / 160, delta=.002)
            self.assertAlmostEqual(body_bounds.height / ((height + depth) * 72 / 72.27),
                                   (frame_ink[3] - frame_ink[1]) / 139, delta=.002)
            reference_top = pages[0]["birds"][0]["bbox"][1]
            reference_shape, reference_points = path_geometry(pages[0]["birds"][0])
            odd, even = {}, {}
            for page in pages:
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["birds"]), 1)
                    bird = page["birds"][0]
                    x0, y0, x1, y1 = bird["bbox"]
                    (odd if page["index"] % 2 else even)[page["index"]] = (x0, x1)
                    for actual, expected in zip(bird["bbox"], LOGO_ANCHORS_BP[page["index"] % 2]):
                        self.assertAlmostEqual(actual, expected, delta=.02)
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
                    label = self.chapter_label(page)
                    label_rgb = tuple((label["color"] >> shift) & 255 for shift in (16, 8, 0))
                    for header_span in page["header"]:
                        self.assertEqual(header_span["color"], label["color"])
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

    def test_vector_bird_matches_the_uploaded_alpha_shape_on_its_native_grid(self):
        # Derive the reference independently from the actual uploaded RGBA
        # file, not from a generated raster, vector file or declared mask.
        reference = self.source_reference
        width, height = self.source_size
        source_x0, source_y0, source_x1, source_y1 = self.source_bbox
        ink_width, ink_height = source_x1 - source_x0, source_y1 - source_y0
        self.assertEqual(self.geometry["schema_version"], 1)
        self.assertEqual(self.geometry["source_alpha_threshold"], 128)
        self.assertEqual(self.geometry["source_size"], list(self.source_size))
        self.assertEqual(self.geometry["source_ink_bbox"], list(self.source_bbox))
        self.assertEqual(self.geometry["source_ink_pixels"], self.source_ink_pixels)
        self.assertEqual(self.geometry["source_sha256"], hashlib.sha256(self.source_path.read_bytes()).hexdigest())
        self.assertEqual(self.geometry["frame_size"], [160, 139])
        scale = 130 / ink_height
        translate_x = (160 - ink_width * scale) / 2 - source_x0 * scale
        translate_y = 4 - source_y0 * scale
        transform = self.geometry["source_to_frame"]
        self.assertAlmostEqual(transform["scale"], scale, delta=1e-12)
        for actual, expected in zip(transform["translate"], (translate_x, translate_y)):
            self.assertAlmostEqual(actual, expected, delta=1e-10)
        expected_frame = (source_x0 * scale + translate_x, 4,
                          source_x1 * scale + translate_x, 134)
        for actual, expected in zip(self.geometry["frame_ink_bbox"], expected_frame):
            self.assertAlmostEqual(actual, expected, delta=1e-9)
        page = self.find("screen", "BODY-EXPLICIT-EMPTY")
        bounds = fitz.Rect(page["body_vectors"][0]["bbox"])
        # The independent cassette/aspect tests above validate the physical
        # scale. Normalize the ink bounds here to cancel global PDF transform
        # rounding, then invert the actual path vertices to the source grid.
        # No tolerance is allowed in the final binary mask comparison.
        actual_pixels = bytearray(b"\xff" * (width * height))
        for path in page["body_vectors"][0]["paths"]:
            events = defaultdict(list)
            for item in path["items"]:
                self.assertEqual(item[0], "l", "Lossless pixel contours must retain straight edges")
                endpoints = []
                for point in item[1:]:
                    x = source_x0 + (point.x - bounds.x0) / bounds.width * ink_width
                    y = source_y0 + (point.y - bounds.y0) / bounds.height * ink_height
                    self.assertAlmostEqual(x, round(x), delta=.02)
                    self.assertAlmostEqual(y, round(y), delta=.02)
                    endpoints.append((round(x), round(y)))
                (xa, ya), (xb, yb) = endpoints
                self.assertTrue(xa == xb or ya == yb, "Pixel contours must remain axis-aligned")
                self.assertTrue(0 <= xa <= width and 0 <= xb <= width)
                self.assertTrue(0 <= ya <= height and 0 <= yb <= height)
                if ya != yb:
                    start, end = min(ya, yb), max(ya, yb)
                    direction = 1 if yb > ya else -1
                    events[start].append((xa, direction))
                    events[end].append((xa, -direction))
            # Active edge events make the high-resolution source check
            # proportional to edges + scanline crossings, not pixels*edges.
            active = Counter()
            for y in range(height):
                for x, direction in events.get(y, ()):
                    active[x] += direction
                    if not active[x]:
                        del active[x]
                winding, previous_x = 0, 0
                for x in sorted(active):
                    inside = winding % 2 != 0 if path.get("even_odd") else winding != 0
                    if inside and previous_x < x:
                        actual_pixels[y * width + previous_x:y * width + x] = b"\0" * (x - previous_x)
                    winding += active[x]
                    previous_x = x
                self.assertEqual(winding, 0, "The filled PDF contour must close on every scanline")
        actual = Image.frombytes("L", (width, height), bytes(actual_pixels))
        difference = ImageChops.difference(actual, reference)
        self.assertIsNone(difference.getbbox(), "Vector contour changes the original bird silhouette")

    def test_running_and_plain_pages_share_header_rules_fonts_and_footer_alignment(self):
        for edition in self.documents:
            pages = [self.find(edition, marker) for marker in RUNNING]
            reference_header = self.chapter_label(pages[0])
            reference_footer = pages[0]["footer"][0]
            reference_rule = pages[0]["rules"][0]
            footer_anchors = {}
            for marker, page in zip(RUNNING, pages):
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["header"]), 2 if self.expected_section(marker) else 1)
                    label = self.chapter_label(page)
                    ref_label = reference_header
                    for span in page["header"]:
                        self.assertEqual(span["font"], "Inter-Regular")
                        self.assertEqual(span["color"], ref_label["color"])
                        self.assertAlmostEqual(span["size"], 8 * 72 / 72.27, delta=.01)
                        self.assertAlmostEqual(span["bbox"][1], ref_label["bbox"][1], delta=.02)
                    if edition == "screen":
                        self.assertEqual(label["color"], 0x203B63)
                    anchor = label["bbox"][0] if page["index"] % 2 else label["bbox"][2]
                    expected_anchor = (20 if page["index"] % 2 else 150) * 72 / 25.4
                    self.assertAlmostEqual(anchor, expected_anchor, delta=.02)
                    bird_bounds = page["birds"][0]["bbox"]
                    self.assertTrue(label["bbox"][2] < bird_bounds[0] if page["index"] % 2
                                    else label["bbox"][0] > bird_bounds[2])
                    section = self.section_label(page)
                    if section:
                        # The configured gap separates text from the logical
                        # frame; its transparent inset adds a little visible
                        # space before the actual vector ink.
                        frame_inset = self.geometry["frame_ink_bbox"][0]
                        expected_gap = (1.2 + frame_inset * 6.4 / 139) * 72 / 25.4
                        gap = (bird_bounds[0] - section["bbox"][2] if page["index"] % 2
                               else section["bbox"][0] - bird_bounds[2])
                        self.assertAlmostEqual(gap, expected_gap, delta=.03)
                        self.assertTrue(label["bbox"][2] < section["bbox"][0] if page["index"] % 2
                                        else section["bbox"][2] < label["bbox"][0],
                                        "Chapter and section labels must not overlap")
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

    def test_mirrored_body_margins_and_outer_footer_anchors_match_in_both_editions(self):
        frame_positions = {}
        for edition in self.documents:
            for marker in ("BODY-NORMAL-ONE", "BODY-NORMAL-TWO"):
                page = self.find(edition, marker)
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["body_frames"]), 1)
                    frame = page["body_frames"][0]["rect"]
                    left_mm = frame.x0 * 25.4 / 72
                    right_mm = (page["width"] - frame.x1) * 25.4 / 72
                    self.assertAlmostEqual(left_mm, 20 if page["index"] % 2 else 17, delta=.01)
                    self.assertAlmostEqual(right_mm, 17 if page["index"] % 2 else 20, delta=.01)
                    self.assertAlmostEqual(frame.width * 25.4 / 72, 133, delta=.01)
                    frame_positions[edition, marker] = tuple(frame)
            for marker in RUNNING + ("BODY-PLAIN",):
                page = self.find(edition, marker)
                with self.subTest(edition=edition, page=page["index"], footer=True):
                    self.assertEqual(len(page["footer"]), 1)
                    footer = page["footer"][0]["bbox"]
                    gap_mm = ((page["width"] - footer[2]) if page["index"] % 2
                              else footer[0]) * 25.4 / 72
                    self.assertAlmostEqual(gap_mm, 17, delta=.01)
        for marker in ("BODY-NORMAL-ONE", "BODY-NORMAL-TWO"):
            for actual, expected in zip(frame_positions["print", marker],
                                        frame_positions["screen", marker]):
                self.assertAlmostEqual(actual, expected, delta=.02)

    def test_plain_empty_automatic_blank_and_chapter_opener_policies(self):
        for edition in self.documents:
            plain = self.find(edition, "BODY-PLAIN")
            self.assertFalse(plain["header"])
            self.assertFalse(plain["birds"])
            self.assertFalse(plain["header_images"])
            self.assertFalse(plain["rules"])
            self.assertEqual(len(plain["footer"]), 1)
            blanks = [page for page in self.documents[edition] if not page["text"].strip()]
            self.assertEqual(len(blanks), 2)
            self.assertEqual([page["index"] for page in blanks], [12, 16])
            for page in (*blanks, self.find(edition, "BODY-CHAPTER"),
                         self.find(edition, "BODY-PHOTO-CHAPTER"), self.find(edition, "BODY-EXPLICIT-EMPTY")):
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
            self.assertEqual(len(pages), 18)
            self.assertEqual(self.chapter_label(final)["text"], "3. PHOTOCHAPTER")
            self.assertIn("LMPROBE ASSESSMENTFINAL", final["mark_probes"])
            self.assertIn("RMPROBE ASSESSMENTFINAL", final["mark_probes"])


if __name__ == "__main__":
    unittest.main()

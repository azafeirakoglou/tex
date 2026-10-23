"""Behavioral PDF regressions for running headers, marks and page styles.

One shared fixture is compiled per edition. No source-text matching is used:
assertions inspect text, image transforms and rules in the actual PDFs.
"""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import fitz


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/page-styles.tex"
SETUP_SPEC = importlib.util.spec_from_file_location(
    "page_styles_setup", ROOT / "scripts/setup_environment.py")
SETUP = importlib.util.module_from_spec(SETUP_SPEC)
SETUP_SPEC.loader.exec_module(SETUP)

NORMAL = ("BODY-NORMAL-ONE", "BODY-NORMAL-TWO", "BODY-AFTER-FIRST",
          "BODY-AFTER-SECOND")
CRITERIA = ("BODY-FIRST-ONE", "BODY-FIRST-TWO", "BODY-SECOND-ONE", "BODY-SECOND-TWO")
MARKRIGHT = ("BODY-AFTER-MARKRIGHT", "BODY-MARKRIGHT-EVEN")
RUNNING = NORMAL + CRITERIA + MARKRIGHT + ("BODY-AFTER-CHAPTER", "BODY-FINAL-ASSESSMENT")


def page_data(page, index):
    spans = [span for block in page.get_text("dict")["blocks"]
             for line in block.get("lines", []) for span in line["spans"]]
    return {
        "index": index,
        "text": page.get_text(),
        "width": page.rect.width,
        "header": [s for s in spans if s["bbox"][1] < 45],
        "footer": [s for s in spans if s["bbox"][1] > 640],
        "birds": [im for im in page.get_image_info() if im["bbox"][1] < 45],
        "rules": [d for d in page.get_drawings()
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
        cls.documents = {}
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
            with fitz.open(folder / "page-styles.pdf") as pdf:
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
            reference_top = pages[0]["birds"][0]["bbox"][1]
            odd, even = {}, {}
            for page in pages:
                with self.subTest(edition=edition, page=page["index"]):
                    self.assertEqual(len(page["birds"]), 1)
                    bird = page["birds"][0]
                    x0, y0, x1, y1 = bird["bbox"]
                    self.assertAlmostEqual((y1 - y0) * 25.4 / 72, 6.4, delta=.01)
                    self.assertAlmostEqual(y0, reference_top, delta=.02)
                    a, b, c, d, _, _ = bird["transform"]
                    determinant = a * d - b * c
                    self.assertGreater(determinant if page["index"] % 2 else -determinant, 0)
                    (odd if page["index"] % 2 else even)[page["index"]] = (x0, x1)
            first_odd, first_even = next(iter(odd.values())), next(iter(even.values()))
            self.assertAlmostEqual(first_even[0], pages[0]["width"] - first_odd[1], delta=.02)
            self.assertAlmostEqual(first_even[1], pages[0]["width"] - first_odd[0], delta=.02)

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

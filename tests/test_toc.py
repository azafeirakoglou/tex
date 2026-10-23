"""Real-PDF navigation and wrapping regressions for the table of contents."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import fitz


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/toc.tex"
SPEC = importlib.util.spec_from_file_location("toc_setup", ROOT / "scripts/setup_environment.py")
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)


def spans_on(page):
    return [span for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", []) for span in line["spans"]]


@unittest.skipUnless(shutil.which("xelatex"), "XeLaTeX is required for TOC regressions")
class TOCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / ".local/fontconfig.xml").exists():
            raise unittest.SkipTest("Run scripts/setup_environment.py before TOC PDF tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="book-toc-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.documents = {}
        for edition in ("screen", "print"):
            folder = Path(cls.temp.name) / edition
            folder.mkdir()
            source = folder / "toc.tex"
            prefix = "\\def\\TOCPrint{1}\n" if edition == "print" else ""
            source.write_text(prefix + FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            command = ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                       "-no-shell-escape", f"-output-directory={folder}", str(source)]
            for _ in range(3):
                result = subprocess.run(command, cwd=ROOT, env=SETUP.runtime_env(),
                                        capture_output=True, text=True, timeout=90)
                if result.returncode:
                    raise RuntimeError(f"{edition} TOC fixture failed:\n"
                                       + (result.stdout + result.stderr)[-6000:])
            if "Overfull \\hbox" in result.stdout or "undefined references" in result.stdout:
                raise AssertionError(f"{edition}: TOC fixture has overflow or unresolved references")
            pdf = fitz.open(folder / "toc.pdf")
            cls.addClassCleanup(pdf.close)
            cls.documents[edition] = pdf

    def test_wrapped_unnumbered_item_keeps_first_line_indent(self):
        for edition, pdf in self.documents.items():
            with self.subTest(edition=edition):
                spans = spans_on(pdf[0])
                start = next(s for s in spans if "WRAPBEGIN" in s["text"])
                end = next(s for s in spans if "WRAPEND" in s["text"])
                lines = [s for s in spans
                         if start["origin"][1] <= s["origin"][1] <= end["origin"][1]
                         and not s["text"].isdigit()]
                self.assertGreaterEqual(len(lines), 2, "Long entry must actually wrap")
                for line in lines:
                    self.assertAlmostEqual(line["origin"][0], start["origin"][0], delta=.03)
                group = next(s for s in spans if s["text"] == "Φύλλα εργασίας")
                self.assertLess(group["origin"][0], start["origin"][0])

    def test_three_digit_pages_are_aligned_and_separated_from_titles(self):
        for edition, pdf in self.documents.items():
            with self.subTest(edition=edition):
                spans = spans_on(pdf[0])
                numbers = [s for s in spans if s["text"] in ("123", "124", "125")]
                self.assertEqual(len(numbers), 5)
                for number in numbers:
                    same_line = [s for s in spans if s is not number
                                 and abs(s["origin"][1] - number["origin"][1]) < .03]
                    self.assertTrue(same_line)
                    self.assertGreater(number["bbox"][0] - max(s["bbox"][2] for s in same_line), 8)
                    self.assertAlmostEqual(number["bbox"][2], numbers[0]["bbox"][2], delta=.03)

    def test_title_and_page_links_share_correct_destinations_and_hierarchy(self):
        expected = [(1, "Περιεχόμενα", 1), (1, "Κεφάλαιο δοκιμής", 3),
                    (2, "Σύντομη ενότητα", 3), (2, "Φύλλα εργασίας", 4)]
        for edition, pdf in self.documents.items():
            with self.subTest(edition=edition):
                outline = pdf.get_toc()
                self.assertEqual([tuple(row) for row in outline[:4]], expected)
                self.assertEqual(outline[4][0], 3)
                self.assertIn("WRAPBEGIN", outline[4][1])
                self.assertEqual(outline[4][2], 4)
                self.assertEqual(outline[5], [1, "Λύσεις κριτηρίων αξιολόγησης", 5])
                self.assertEqual(len(pdf), 5, "Bookmark must not introduce another page")
                links = pdf[0].get_links()
                numbers = [s for s in spans_on(pdf[0]) if s["text"] in ("123", "124", "125")]
                for number in numbers:
                    rect = fitz.Rect(number["bbox"])
                    page_links = [link for link in links if fitz.Rect(link["from"]).intersects(rect)]
                    self.assertEqual(len(page_links), 1)
                    link = page_links[0]
                    expected_page = int(number["text"]) - 123 + 2
                    self.assertEqual(link["page"], expected_page)
                    self.assertTrue(any(other["nameddest"] == link["nameddest"]
                                        and other["from"].x0 < 410 for other in links))
                self.assertIn("Λύσεις κριτηρίων αξιολόγησης", pdf[4].get_text())

    def test_toc_stays_black_and_has_identical_paired_layout(self):
        screen = spans_on(self.documents["screen"][0])
        printed = spans_on(self.documents["print"][0])
        self.assertEqual([s["text"] for s in screen], [s["text"] for s in printed])
        for left, right in zip(screen, printed):
            self.assertEqual(left["color"], 0)
            self.assertEqual(right["color"], 0)
            self.assertEqual(left["font"], right["font"])
            for a, b in zip(left["bbox"], right["bbox"]):
                self.assertAlmostEqual(a, b, delta=.01)


if __name__ == "__main__":
    unittest.main()

"""End-to-end negative fixtures for the PDF preflight (requires Ghostscript)."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_pdf", ROOT / "scripts/validate_pdf.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)
PALETTE = {
    "spot_ink_name": "TestRed",
    "screen_base_hex": {"BLACK": "000000", "SECOND": "203B63"},
    "colors": {f"{ink}{tint}": {"print_ink": ink, "tint": tint}
               for ink in ("BLACK", "SECOND") for tint in (100, 55, 10)},
}
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def make_pdf(path, edition, extra="", different_text=False, embed_font=True):
    """Create an independent tiny PDF, with real embedded text and six swatches."""
    base = fitz.open()
    page = base.new_page(width=200, height=240)
    font_name = "FixtureFont" if embed_font else "helv"
    if embed_font:
        page.insert_font(fontname=font_name, fontfile=str(FONT))
    page.insert_text((10, 20), "Changed text" if different_text else "Identical text",
                     fontname=font_name, fontsize=10)
    reader = PdfReader(__import__("io").BytesIO(base.tobytes()))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    page = writer.pages[0]
    function = DictionaryObject({
        NameObject("/FunctionType"): NumberObject(2),
        NameObject("/Domain"): ArrayObject([NumberObject(0), NumberObject(1)]),
        NameObject("/C0"): ArrayObject([NumberObject(0)] * 4),
        NameObject("/C1"): ArrayObject([NumberObject(0), NumberObject(1), NumberObject(1), NumberObject(0)]),
        NameObject("/N"): NumberObject(1),
    })
    page["/Resources"][NameObject("/ColorSpace")] = DictionaryObject({
        NameObject("/Second"): ArrayObject([NameObject("/Separation"), NameObject("/TestRed"),
                                           NameObject("/DeviceCMYK"), function])})
    commands = ["q"]
    for i, color in enumerate(PALETTE["colors"].values()):
        if edition == "print":
            paint = (f"{1 - color['tint'] / 100:g} g" if color["print_ink"] == "BLACK"
                     else f"/Second cs {color['tint'] / 100:g} sc")
        else:
            rgb = PREFLIGHT.screen_color(color, PALETTE)
            paint = " ".join(f"{v / 255:.9f}" for v in rgb) + " rg"
        commands.append(f"q {paint} {10 + i * 28} 80 20 30 re f Q")
    commands.extend(["Q", extra])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    previous = page.get("/Contents")
    previous = previous if isinstance(previous, ArrayObject) else ArrayObject([previous])
    page[NameObject("/Contents")] = ArrayObject([*previous, writer._add_object(stream)])
    with path.open("wb") as output:
        writer.write(output)
    base.close()


@unittest.skipUnless(shutil.which("gs") and FONT.exists(), "Ghostscript and fixture font required")
class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="test-book-pdf-")
        self.folder = Path(self.temp.name)
        self.pr = self.folder / "print.pdf"
        self.sc = self.folder / "screen.pdf"
        make_pdf(self.pr, "print")
        make_pdf(self.sc, "screen")

    def tearDown(self):
        self.temp.cleanup()

    def check_pair(self):
        return PREFLIGHT.validate(self.pr, self.sc, PALETTE, dpi=72)

    def test_six_swatches_and_same_text_pass(self):
        report = self.check_pair()
        self.assertEqual(report["status"], "passed", report["errors"])
        self.assertEqual(report["rendered"]["pairing_mismatched_pixels"], 0)

    def test_extra_process_ink_fails(self):
        make_pdf(self.pr, "print", "q 1 0 0 0 k 30 30 10 10 re f Q")
        report = self.check_pair()
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("unexpected nonempty Cyan" in error for error in report["errors"]))

    def test_unapproved_tint_fails(self):
        make_pdf(self.pr, "print", "q /Second cs .42 sc 30 30 10 10 re f Q")
        report = self.check_pair()
        self.assertTrue(any("unapproved raster levels" in error for error in report["errors"]))

    def test_wrong_screen_role_fails_even_when_text_matches(self):
        # Same text and position; a black square replaces part of a blue swatch.
        make_pdf(self.sc, "screen", "q 0 0 0 rg 94 80 20 30 re f Q")
        report = self.check_pair()
        self.assertTrue(report["pair"]["text_and_positions_match"])
        self.assertGreater(report["rendered"]["pairing_mismatched_pixels"], 0)
        self.assertEqual(report["status"], "failed")

    def test_changed_text_fails(self):
        make_pdf(self.sc, "screen", different_text=True)
        report = self.check_pair()
        self.assertFalse(report["pair"]["text_and_positions_match"])

    def test_unused_gray_does_not_create_false_ink_failure(self):
        make_pdf(self.pr, "print", "q .25 g Q")
        report = self.check_pair()
        self.assertEqual(report["status"], "passed", report["errors"])

    def test_unembedded_font_fails(self):
        make_pdf(self.pr, "print", embed_font=False)
        report = self.check_pair()
        self.assertTrue(any("fonts not embedded" in error for error in report["errors"]))

    def test_missing_press_boxes_fail_only_when_requested(self):
        ordinary = self.check_pair()
        self.assertEqual(ordinary["status"], "passed", ordinary["errors"])
        report = PREFLIGHT.validate(self.pr, self.sc, PALETTE, dpi=72,
                                    trim_mm=(170, 240), bleed_mm=3)
        self.assertTrue(any("explicit TrimBox required" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()

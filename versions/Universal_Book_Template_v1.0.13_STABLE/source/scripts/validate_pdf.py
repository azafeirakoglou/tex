#!/usr/bin/env python3
"""Validate the produced two-ink PDF and its blue counterpart.

This is an engineering regression check, not a PDF/X or press certification.
Ghostscript renders *all* pages with antialiasing disabled so actual plate
marks, including marks inside images and Form XObjects, are checked. Unused
color-space resources and fully covered drawing commands do not count as ink.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import fitz
from PIL import Image
from pypdf import PdfReader


def screen_color(color: dict, palette: dict) -> tuple[int, int, int]:
    """Use generated tints for schema 3; read old maps for migration checks."""
    bases = palette.get("screen_base_hex")
    if bases:
        base = bases[color["print_ink"]].lstrip("#")
        amount = color["tint"] / 100
        return tuple(round(int(base[i:i + 2], 16) * amount + 255 * (1 - amount))
                     for i in (0, 2, 4))
    value = color["screen_hex"].lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def palette_tables(palette: dict) -> tuple[dict, dict]:
    tables = {"BLACK": {255: (255, 255, 255)},
              "SECOND": {255: (255, 255, 255)}}
    for color in palette["colors"].values():
        level = round(255 * (1 - color["tint"] / 100))
        tables[color["print_ink"]][level] = screen_color(color, palette)
    return tables["BLACK"], tables["SECOND"]


def nearest_level(value: int, levels: dict) -> int | None:
    # PDF decimal and 8-bit image rounding can differ by one unit.
    return next((level for level in levels if abs(value - level) <= 1), None)


def font_is_embedded(font) -> bool:
    font = font.get_object()
    if font.get("/Subtype") == "/Type3":
        return bool(font.get("/CharProcs"))
    descendants = font.get("/DescendantFonts")
    if descendants:
        return all(font_is_embedded(child) for child in descendants)
    descriptor = font.get("/FontDescriptor")
    if not descriptor:
        return False
    descriptor = descriptor.get_object()
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def inspect_pdf(path: Path, errors: list[str], label: str,
                print_edition: bool = False) -> dict:
    reader = PdfReader(path)
    info = {"pages": len(reader.pages), "unembedded_fonts": [],
            "rgb_images": [], "page_boxes": [],
            "output_intent_present": bool(reader.trailer["/Root"].get("/OutputIntents"))}
    visited = set()

    def resources(res, context):
        if not res:
            return
        res = res.get_object()
        fonts = res.get("/Font", {})
        if hasattr(fonts, "get_object"):
            fonts = fonts.get_object()
        for name, font in fonts.items():
            if not font_is_embedded(font):
                info["unembedded_fonts"].append(f"{context}/{name}")
        xobjects = res.get("/XObject", {})
        if hasattr(xobjects, "get_object"):
            xobjects = xobjects.get_object()
        for name, ref in xobjects.items():
            key = (getattr(ref, "idnum", None), getattr(ref, "generation", None))
            if key != (None, None) and key in visited:
                continue
            visited.add(key)
            obj = ref.get_object()
            if obj.get("/Subtype") == "/Form":
                resources(obj.get("/Resources"), f"{context}/{name}")
            elif obj.get("/Subtype") == "/Image" and print_edition:
                space = obj.get("/ColorSpace", "")
                if hasattr(space, "get_object"):
                    space = space.get_object()
                if isinstance(space, str) and space in res.get("/ColorSpace", {}):
                    space = res["/ColorSpace"][space].get_object()
                rgb = space in ("/DeviceRGB", "/CalRGB") if isinstance(space, str) else False
                if isinstance(space, list) and space:
                    rgb = str(space[0]) == "/CalRGB"
                    if str(space[0]) == "/ICCBased":
                        rgb = space[1].get_object().get("/N") == 3
                    if str(space[0]) == "/Indexed":
                        rgb = str(space[1]) in ("/DeviceRGB", "/CalRGB")
                if rgb:
                    info["rgb_images"].append(f"{context}/{name}")

    for index, page in enumerate(reader.pages, 1):
        resources(page.get("/Resources"), f"page {index}")
        info["page_boxes"].append({key[1:]: list(map(float, page[key]))
                                   if key in page else None
                                   for key in ("/MediaBox", "/TrimBox", "/BleedBox")})
    if info["unembedded_fonts"]:
        errors.append(f"{label}: fonts not embedded: {info['unembedded_fonts']}")
    if info["rgb_images"]:
        errors.append(f"{label}: RGB images bypass the approved neutral assets: {info['rgb_images']}")
    return info


def compare_text_and_geometry(print_path: Path, screen_path: Path,
                              errors: list[str]) -> dict:
    result = {"same_page_count": False, "text_and_positions_match": True,
              "geometry_matches": True}
    with fitz.open(print_path) as pr, fitz.open(screen_path) as sc:
        result["same_page_count"] = len(pr) == len(sc)
        if not result["same_page_count"]:
            errors.append(f"Paired PDFs have different page counts: {len(pr)} and {len(sc)}")
        for index, (pp, sp) in enumerate(zip(pr, sc), 1):
            if any(abs(a - b) > .05 for a, b in zip(pp.mediabox, sp.mediabox)):
                result["geometry_matches"] = False
                errors.append(f"Page {index}: print/screen MediaBox differs")
            pw, sw = pp.get_text("words"), sp.get_text("words")
            same = len(pw) == len(sw) and all(
                a[4] == b[4] and all(abs(x - y) <= .05 for x, y in zip(a[:4], b[:4]))
                for a, b in zip(pw, sw))
            if not same:
                result["text_and_positions_match"] = False
                errors.append(f"Page {index}: text or text positions differ between editions")
    return result


def run_gs(device: str, pdf: Path, output: Path, dpi: int) -> None:
    command = ["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
               f"-sDEVICE={device}", f"-r{dpi}", "-dTextAlphaBits=1",
               "-dGraphicsAlphaBits=1", f"-sOutputFile={output}", str(pdf)]
    run = subprocess.run(command, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(f"Ghostscript {device} failed ({run.returncode}): "
                           + (run.stderr + run.stdout)[-4000:])


def pixels(image):
    return image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()


def rendered_check(print_path: Path, screen_path: Path, palette: dict,
                   page_count: int, dpi: int, errors: list[str]) -> dict:
    black_table, spot_table = palette_tables(palette)
    spot = palette["spot_ink_name"]
    if not re.fullmatch(r"[A-Za-z0-9_. -]+", spot):
        raise ValueError("Spot name must use only letters, digits, spaces, underscore, dot or hyphen")
    report = {"dpi": dpi, "antialiasing": False, "plates": {},
              "pairing_mismatched_pixels": 0, "overlap_pixels": 0, "pages": [],
              "scope": "all pages; raster separations and paired RGB rendering"}
    with tempfile.TemporaryDirectory(prefix="book-preflight-") as directory:
        folder = Path(directory)
        run_gs("tiffsep", print_path, folder / "print-%d.tif", dpi)
        run_gs("png16m", screen_path, folder / "screen-%d.png", dpi)
        for index in range(1, page_count + 1):
            screen_file = folder / f"screen-{index}.png"
            if not screen_file.exists():
                continue  # Page-count discrepancy already reported.
            with Image.open(screen_file) as opened:
                screen = opened.convert("RGB")
            plate_images = {}
            for path in folder.glob(f"print-{index}(*).tif"):
                name = path.name.split("(", 1)[1].rsplit(")", 1)[0]
                with Image.open(path) as opened:
                    im = opened.convert("L")
                hist = Counter(pixels(im))
                marked = sum(count for level, count in hist.items() if level < 254)
                plate = report["plates"].setdefault(name, {"marked_pixels": 0,
                                                          "nonempty_pages": [], "levels": {}})
                plate["marked_pixels"] += marked
                if marked:
                    plate["nonempty_pages"].append(index)
                for level, count in hist.items():
                    plate["levels"][str(level)] = plate["levels"].get(str(level), 0) + count
                if name not in ("Black", spot) and marked:
                    errors.append(f"Page {index}: unexpected nonempty {name} plate ({marked} pixels)")
                if name in ("Black", spot):
                    allowed = black_table if name == "Black" else spot_table
                    extra = {level: count for level, count in hist.items()
                             if nearest_level(level, allowed) is None}
                    if extra:
                        errors.append(f"Page {index}: {name} uses unapproved raster levels {extra}")
                    plate_images[name] = im
            black = plate_images.get("Black", Image.new("L", screen.size, 255))
            red = plate_images.get(spot, Image.new("L", screen.size, 255))
            if black.size != screen.size or red.size != screen.size:
                errors.append(f"Page {index}: paired raster dimensions differ")
                continue
            samples = Counter(zip(pixels(black), pixels(red), pixels(screen)))
            mismatched = 0
            overlaps = 0
            bad_samples = []
            bad_values = set()
            for (k, second, actual), count in samples.items():
                kl = nearest_level(k, black_table)
                sl = nearest_level(second, spot_table)
                if kl is None or sl is None:
                    continue  # Specific unexpected tone already reported.
                if kl != 255 and sl != 255:
                    overlaps += count
                    continue
                expected = black_table[kl] if kl != 255 else spot_table[sl]
                if any(abs(a - b) > 1 for a, b in zip(expected, actual)):
                    mismatched += count
                    bad_values.add((k, second, actual))
                    if len(bad_samples) < 5:
                        bad_samples.append({"black_level": k, "spot_level": second,
                                            "expected_screen": expected, "actual_screen": actual,
                                            "pixels": count})
            report["pairing_mismatched_pixels"] += mismatched
            report["overlap_pixels"] += overlaps
            page_report = {"page": index, "pairing_mismatched_pixels": mismatched,
                           "overlap_pixels": overlaps, "bad_samples": bad_samples}
            if mismatched:
                points = [position for position, value in enumerate(
                    zip(pixels(black), pixels(red), pixels(screen))) if value in bad_values]
                xx, yy = [v % screen.width for v in points], [v // screen.width for v in points]
                page_report["mismatch_bbox_from_top_left_pt"] = [
                    min(xx) * 72 / dpi, min(yy) * 72 / dpi,
                    (max(xx) + 1) * 72 / dpi, (max(yy) + 1) * 72 / dpi]
            report["pages"].append(page_report)
            if mismatched:
                errors.append(f"Page {index}: {mismatched} pixels violate print/screen role pairing; "
                              + str(bad_samples))
            if overlaps:
                errors.append(f"Page {index}: {overlaps} pixels combine both inks; "
                              "the six single-ink swatches require knockout behavior")
    if not report["plates"].get("Black", {}).get("marked_pixels"):
        errors.append("PRINT has no marked Black plate")
    if not report["plates"].get(spot, {}).get("marked_pixels"):
        errors.append(f"PRINT has no marked {spot} plate")
    return report


def check_press_geometry(info: dict, trim_mm, bleed_mm, errors: list[str]):
    if trim_mm is None and bleed_mm is None:
        return
    for index, boxes in enumerate(info["page_boxes"], 1):
        trim, bleed = boxes["TrimBox"], boxes["BleedBox"]
        if not trim:
            errors.append(f"Page {index}: explicit TrimBox required for press geometry check")
            continue
        if trim_mm:
            actual = [(trim[2] - trim[0]) * 25.4 / 72, (trim[3] - trim[1]) * 25.4 / 72]
            if any(abs(a - b) > .05 for a, b in zip(actual, trim_mm)):
                errors.append(f"Page {index}: TrimBox {actual} mm differs from requested {trim_mm}")
        if bleed_mm is not None:
            if not bleed:
                errors.append(f"Page {index}: explicit BleedBox required")
            else:
                margins = [trim[0] - bleed[0], trim[1] - bleed[1],
                           bleed[2] - trim[2], bleed[3] - trim[3]]
                if any(m * 25.4 / 72 < bleed_mm - .05 for m in margins):
                    errors.append(f"Page {index}: BleedBox provides less than {bleed_mm} mm")


def validate(print_path: Path, screen_path: Path, palette: dict, dpi=72,
             trim_mm=None, bleed_mm=None) -> dict:
    errors = []
    report = {"status": "failed", "certification": "Not PDF/X or press certification",
              "print_file": str(print_path), "screen_file": str(screen_path), "errors": errors}
    report["input_sha256"] = {
        "print": hashlib.sha256(print_path.read_bytes()).hexdigest(),
        "screen": hashlib.sha256(screen_path.read_bytes()).hexdigest(),
        "palette": hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest(),
    }
    report["print"] = inspect_pdf(print_path, errors, "PRINT", True)
    report["screen"] = inspect_pdf(screen_path, errors, "SCREEN")
    report["pair"] = compare_text_and_geometry(print_path, screen_path, errors)
    check_press_geometry(report["print"], trim_mm, bleed_mm, errors)
    report["rendered"] = rendered_check(print_path, screen_path, palette,
                                        report["print"]["pages"], dpi, errors)
    report["status"] = "passed" if not errors else "failed"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="print_path", required=True, type=Path)
    parser.add_argument("--screen", dest="screen_path", required=True, type=Path)
    parser.add_argument("--map", dest="map_path", type=Path,
                        default=Path(__file__).resolve().parent.parent / "config/color-map.json")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dpi", type=int, default=72, choices=(36, 72, 144, 300))
    parser.add_argument("--require-trim-mm", type=float, nargs=2)
    parser.add_argument("--require-bleed-mm", type=float)
    args = parser.parse_args()
    if not shutil.which("gs"):
        parser.error("Ghostscript (gs) is required")
    try:
        palette = json.loads(args.map_path.read_text(encoding="utf-8"))
        report = validate(args.print_path.resolve(), args.screen_path.resolve(), palette,
                          args.dpi, args.require_trim_mm, args.require_bleed_mm)
    except Exception as exc:
        report = {"status": "failed", "errors": [str(exc)]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{report['status'].upper()}: two-ink PDF / blue counterpart")
    for error in report["errors"]:
        print(" - " + error)
    if report["status"] == "passed":
        print(f"All {report['print']['pages']} pages checked at {args.dpi} dpi; "
              "only Black + configured spot, approved tints, matching text and color roles.")
        print("Press approval, ink choice and PDF/X compliance remain separate checks.")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

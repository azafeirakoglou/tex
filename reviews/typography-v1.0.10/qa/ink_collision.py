"""Read-only measurements of paragraph line spacing and glyph-ink clearance.

The geometry comes from PDF text origins and actual embedded glyph outlines
(TTF or CID CFF), with a documented installed-font fallback. It does not mistake a font's
global ascender/descender rectangle for painted ink.  A negative clearance is a
*potential* collision of ink bounding boxes, to be inspected visually; bounding
boxes alone cannot prove that two outlines intersect.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import io
import statistics
import sys
import unicodedata

sys.dont_write_bytecode = True

import fitz
from fontTools.pens.boundsPen import BoundsPen
from fontTools.cffLib import CFFFontSet
from fontTools.ttLib import TTFont


REVIEW_ROOT = Path(__file__).resolve().parents[1]
BP_TO_TEX_PT = 72.27 / 72


def _font_key(name: str) -> str:
    if "+" in name:
        prefix, rest = name.split("+", 1)
        if len(prefix) == 6:
            name = rest
    return name.removesuffix("-Identity-H").replace(" ", "").lower()


@lru_cache(maxsize=1)
def _fonts():
    result = {}
    for folder in (REVIEW_ROOT / "runtime/fonts", REVIEW_ROOT / "fonts/installed"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in {".ttf", ".otf"}:
                continue
            font = TTFont(path, lazy=False)
            psname = font["name"].getDebugName(6)
            if psname:
                result[_font_key(psname)] = {
                    "path": str(path), "font": font,
                    "glyphs": font.getGlyphOrder(), "glyphset": font.getGlyphSet(),
                    "cmap": font.getBestCmap(), "em": font["head"].unitsPerEm,
                }
    return result


@lru_cache(maxsize=20000)
def _glyph_bounds(font_key: str, glyph_id: int):
    entry = _fonts().get(font_key)
    if not entry or not 0 <= glyph_id < len(entry["glyphs"]):
        return None
    pen = BoundsPen(entry["glyphset"])
    entry["glyphset"][entry["glyphs"][glyph_id]].draw(pen)
    return pen.bounds


def _embedded_fonts(pdf):
    """Decode actual embedded TTF/OTF or raw CID-CFF glyph outlines."""
    result = {}
    seen = set()
    for page in pdf:
        for item in page.get_fonts(full=True):
            xref, _, _, basename = item[:4]
            if xref in seen:
                continue
            seen.add(xref)
            extracted = pdf.extract_font(xref)
            data = extracted[3]
            key = _font_key(basename)
            try:
                font = TTFont(io.BytesIO(data), lazy=False)
                result[key] = {"font": font, "glyphset": font.getGlyphSet(),
                               "glyphs": font.getGlyphOrder(), "cache": {},
                               "scale_x": 1 / font["head"].unitsPerEm,
                               "scale_y": 1 / font["head"].unitsPerEm,
                               "source": f"embedded PDF font xref {xref} ({extracted[1]})"}
                continue
            except Exception:
                pass
            try:
                cff = CFFFontSet()
                cff.decompile(io.BytesIO(data), None)
                top = cff[cff.fontNames[0]]
                matrix = top.FontMatrix
                result[key] = {"font": cff, "glyphset": top.CharStrings,
                               "glyphs": top.charset, "cache": {},
                               "cid": True, "scale_x": matrix[0], "scale_y": matrix[3],
                               "source": f"embedded PDF font xref {xref} (CID CFF)"}
            except Exception:
                continue
    return result


def _embedded_bounds(entry, glyph_id):
    if glyph_id in entry["cache"]:
        return entry["cache"][glyph_id]
    if entry.get("cid"):
        name = f"cid{glyph_id:05d}"
        if name not in entry["glyphset"]:
            if not 0 <= glyph_id < len(entry["glyphs"]):
                return None
            name = entry["glyphs"][glyph_id]
    else:
        if not 0 <= glyph_id < len(entry["glyphs"]):
            return None
        name = entry["glyphs"][glyph_id]
    pen = BoundsPen(entry["glyphset"])
    entry["glyphset"][name].draw(pen)
    entry["cache"][glyph_id] = pen.bounds
    return pen.bounds


def _is_math(name: str) -> bool:
    return "math" in name.lower()


def _is_letter(codepoint: int) -> bool:
    try:
        return unicodedata.category(chr(codepoint)).startswith("L")
    except ValueError:
        return False


def _round(value, places=5):
    return round(value, places) if value is not None else None


def _rect_union(rectangles):
    if not rectangles:
        return None
    return [min(r[0] for r in rectangles), min(r[1] for r in rectangles),
            max(r[2] for r in rectangles), max(r[3] for r in rectangles)]


def _stats(values):
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None}
    return {"count": len(values), "min": _round(min(values)),
            "median": _round(statistics.median(values)), "max": _round(max(values))}


def analyze_document(path) -> dict:
    """Measure body paragraph lines and report potential interline collisions.

    Text lines are anchored by at least eight ordinary letters in a Regular
    text face, size >= 9 PDF bp, below the running header. Inline math in the
    same PDF text object is assigned to its nearest text baseline (within
    11 bp). This excludes isolated display formulae, intended within-formula
    overlap, titles and diagram lettering from the paragraph collision test.
    """
    font_data = _fonts()
    font_checks = defaultdict(lambda: {"unicode_gid_comparisons": 0,
                                      "unicode_gid_matches": 0,
                                      "glyphs_with_outline_bounds": 0,
                                      "glyphs_missing_outline_bounds": 0})
    result = {
        "method": "PDF character origins plus actual embedded-font glyph outline bounds (TTF or CID CFF)",
        "units": "PDF bp; TeX pt conversion 72.27/72 also reported for line gaps",
        "scope": "Adjacent paragraph lines, including inline math in those text objects",
        "limitations": [
            "Bounding-box overlap is only a potential collision, not proof of outline intersection.",
            "Isolated display equations and intended within-formula overlaps are excluded.",
            "Inline math line association uses the nearest ordinary-text baseline in the same PDF text object.",
        ],
        "pages": [], "potential_collisions": [],
    }
    all_gaps = []
    all_clearances = []
    math_clearances = []
    math_rises = []
    math_depths = []
    unrecognized_fonts = set()

    with fitz.open(path) as pdf:
        embedded = _embedded_fonts(pdf)
        for page_index, page in enumerate(pdf):
            chars = []
            for trace in page.get_texttrace():
                if trace["dir"] != (1., 0.) or trace.get("opacity", 1) == 0:
                    continue
                key = _font_key(trace["font"])
                original = font_data.get(key)
                embedded_entry = embedded.get(key)
                if original is None and embedded_entry is None:
                    unrecognized_fonts.add(trace["font"])
                    continue
                for unicode_value, glyph_id, origin, _ in trace["chars"]:
                    expected = original["cmap"].get(unicode_value) if original else None
                    if expected:
                        font_checks[key]["unicode_gid_comparisons"] += 1
                        if original["font"].getGlyphID(expected) == glyph_id:
                            font_checks[key]["unicode_gid_matches"] += 1
                    if embedded_entry:
                        bounds = _embedded_bounds(embedded_entry, glyph_id)
                        sx, sy = embedded_entry["scale_x"], embedded_entry["scale_y"]
                        font_checks[key]["bounds_source"] = embedded_entry["source"]
                    else:
                        bounds = _glyph_bounds(key, glyph_id)
                        sx = sy = 1 / original["em"]
                        font_checks[key]["bounds_source"] = "review's installed original font (fallback)"
                    if bounds is None:
                        font_checks[key]["glyphs_missing_outline_bounds"] += 1
                        continue
                    font_checks[key]["glyphs_with_outline_bounds"] += 1
                    x, y = origin
                    ink = [x + bounds[0] * trace["size"] * sx,
                           y - bounds[3] * trace["size"] * sy,
                           x + bounds[2] * trace["size"] * sx,
                           y - bounds[1] * trace["size"] * sy]
                    chars.append({"code": unicode_value, "gid": glyph_id,
                                  "font": trace["font"], "key": key,
                                  "size": trace["size"], "x": x, "y": y,
                                  "rect": ink, "seqno": trace["seqno"],
                                  "math": _is_math(trace["font"])})

            # Anchor actual body paragraphs on ordinary letters, not display
            # numerator/subscript baselines or heading/caption faces.
            anchors = defaultdict(list)
            for char in chars:
                if (not char["math"] and "regular" in char["font"].lower()
                        and char["size"] >= 9 and 45 < char["y"] < page.rect.height - 48
                        and _is_letter(char["code"])):
                    anchors[(char["seqno"], round(char["y"], 2))].append(char)
            lines = []
            for (seqno, baseline), letters in anchors.items():
                if len(letters) < 8:
                    continue
                ordinary = [c for c in chars if c["seqno"] == seqno
                            and not c["math"] and abs(c["y"] - baseline) < .04]
                lines.append({"seqno": seqno, "baseline": baseline,
                              "text_size": statistics.median(c["size"] for c in letters),
                              "chars": ordinary})
            by_object = defaultdict(list)
            for line in lines:
                by_object[line["seqno"]].append(line)
            for char in chars:
                if not char["math"] or not by_object.get(char["seqno"]):
                    continue
                nearest = min(by_object[char["seqno"]], key=lambda line: abs(char["y"] - line["baseline"]))
                if abs(char["y"] - nearest["baseline"]) <= 11:
                    nearest["chars"].append(char)
            lines.sort(key=lambda line: (line["baseline"], min(c["x"] for c in line["chars"])))
            page_math_rises = []
            page_math_depths = []
            for line in lines:
                math_chars = [c for c in line["chars"] if c["math"]]
                if math_chars:
                    page_math_rises.append(line["baseline"] - min(c["rect"][1] for c in math_chars))
                    page_math_depths.append(max(c["rect"][3] for c in math_chars) - line["baseline"])
            math_rises.extend(page_math_rises)
            math_depths.extend(page_math_depths)
            page_gaps = []
            page_clearances = []
            same_object_gaps = []
            for upper, lower in zip(lines, lines[1:]):
                gap = lower["baseline"] - upper["baseline"]
                if not 2 < gap < 26:
                    continue
                horizontal_pairs = [(a, b) for a in upper["chars"] for b in lower["chars"]
                                    if min(a["rect"][2], b["rect"][2])
                                    - max(a["rect"][0], b["rect"][0]) > .01]
                if not horizontal_pairs:
                    continue
                clearance, a, b = min(((b["rect"][1] - a["rect"][3], a, b)
                                       for a, b in horizontal_pairs), key=lambda item: item[0])
                all_gaps.append(gap); page_gaps.append(gap)
                all_clearances.append(clearance); page_clearances.append(clearance)
                if upper["seqno"] == lower["seqno"]:
                    same_object_gaps.append(gap)
                if any(c["math"] for c in upper["chars"] + lower["chars"]):
                    math_clearances.append(clearance)
                if clearance < -.01:
                    result["potential_collisions"].append({
                        "page": page_index + 1, "clearance_pdf_bp": _round(clearance),
                        "upper_baseline_pdf_bp": upper["baseline"],
                        "lower_baseline_pdf_bp": lower["baseline"],
                        "upper_character": chr(a["code"]), "lower_character": chr(b["code"]),
                        "upper_font": a["font"], "lower_font": b["font"],
                        "bbox": [_round(v) for v in _rect_union([a["rect"], b["rect"]])],
                    })
            result["pages"].append({
                "page": page_index + 1, "paragraph_lines": len(lines),
                "lines_containing_inline_math": sum(any(c["math"] for c in line["chars"]) for line in lines),
                "body_text_size_tex_pt_histogram": dict(Counter(
                    round(line["text_size"] * BP_TO_TEX_PT, 3) for line in lines)),
                "inline_math_ink_rise_above_baseline_pdf_bp": _stats(page_math_rises),
                "inline_math_ink_depth_below_baseline_pdf_bp": _stats(page_math_depths),
                "adjacent_line_baseline_gap_pdf_bp": _stats(page_gaps),
                "same_text_object_baseline_gap_tex_pt_histogram": dict(Counter(
                    round(g * BP_TO_TEX_PT, 2) for g in same_object_gaps)),
                "adjacent_line_ink_bbox_clearance_pdf_bp": _stats(page_clearances),
            })

    result["adjacent_line_baseline_gap_pdf_bp"] = _stats(all_gaps)
    result["adjacent_line_ink_bbox_clearance_pdf_bp"] = _stats(all_clearances)
    result["inline_math_adjacent_line_clearance_pdf_bp"] = _stats(math_clearances)
    result["inline_math_ink_rise_above_baseline_pdf_bp"] = _stats(math_rises)
    result["inline_math_ink_depth_below_baseline_pdf_bp"] = _stats(math_depths)
    result["unknown_font_sources"] = sorted(unrecognized_fonts)
    result["font_glyph_id_checks"] = dict(font_checks)
    suspect = []
    for name, check in font_checks.items():
        comparisons = check["unicode_gid_comparisons"]
        ratio = check["unicode_gid_matches"] / comparisons if comparisons else None
        check["unicode_gid_match_ratio"] = _round(ratio)
        if ("fallback" in check.get("bounds_source", "")
                and comparisons >= 20 and ratio < .8):
            suspect.append(name)
    result["glyph_mapping_method_verified"] = not suspect and not unrecognized_fonts
    result["font_mapping_requiring_manual_review"] = suspect
    result["potential_collision_count"] = len(result["potential_collisions"])
    result["status"] = "measured" if result["glyph_mapping_method_verified"] else "needs_font_mapping_review"
    return result


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_document(args.pdf)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out = args.out.resolve()
        if not out.is_relative_to(REVIEW_ROOT):
            parser.error("Output must remain inside typography-review/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    else:
        print(text, end="")

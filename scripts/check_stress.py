#!/usr/bin/env python3
"""Check real pagination, repeated headers and split callouts in the stress pair.

This complements validate_pdf.py: the pair preflight verifies inks/tints/fonts;
this script verifies that representative long-form content survives pagination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import fitz


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spans(page):
    return [s for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", []) for s in line["spans"]]


def check_document(path: Path) -> dict:
    with fitz.open(path) as pdf:
        pages = [page.get_text() for page in pdf]
        joined = "\n".join(pages)
        if not 45 <= len(pdf) <= 90:
            raise AssertionError(f"Expected a representative 45–90 page book, got {len(pdf)}")
        if "??" in joined:
            raise AssertionError("An unresolved cross-reference remains in the PDF")
        for prefix in ("ALPHA", "BETA", "GAMMA"):
            markers = re.findall(r"STRESSBODY" + prefix + r"(\d+)", joined)
            if markers != [str(i) for i in range(1, 8)]:
                raise AssertionError(f"Missing, duplicated or reordered {prefix} proof pages: {markers}")
        for marker in ("CHAPTERALPHA", "CHAPTERBETA", "CHAPTERGAMMA", "COLUMNALPHA",
                       "COLUMNBETA", "COLUMNGAMMA", "DENSEMATH", "WORKSHEETFIRST",
                       "WORKSHEETSECOND", "ASSESSMENTFIRST", "ASSESSMENTSECOND",
                       "SOLUTIONFIRST", "SOLUTIONSECOND", "STRESSEND"):
            if joined.count(marker) != 1:
                raise AssertionError(f"Expected exactly one {marker}")
        # All custom opening pages retain their goals, and white title text
        # stays inside an actual colored surface even when full titles wrap.
        opening_pages = []
        for index, page in enumerate(pdf):
            text = pages[index]
            if "ΕΝΟΤΗΤΑ" in text:
                if "Τι θα μάθουμε" not in text:
                    raise AssertionError(f"Chapter goals moved off opening page {index + 1}")
                opening_pages.append(index + 1)
            surfaces = []
            for drawing in page.get_drawings():
                if drawing.get("fill") and any(channel < .95 for channel in drawing["fill"]):
                    rect = fitz.Rect(drawing["rect"])
                    rect.x0 -= .3; rect.y0 -= .3; rect.x1 += .3; rect.y1 += .3
                    surfaces.append(rect)
            for span in spans(page):
                if (span["color"] == 0xFFFFFF and span["text"].strip()
                        and not any(rect.contains(fitz.Rect(span["bbox"])) for rect in surfaces)):
                    raise AssertionError(f"White text outside colored surface on page {index + 1}: {span['text']}")
        if len(opening_pages) != 2:
            raise AssertionError(f"Expected two custom chapter opening pages, got {opening_pages}")
        findings = {}
        for kind in ("HISTORY", "THINK", "ATTENTION"):
            starts = [i for i, text in enumerate(pages) if kind + "BEGIN" in text]
            ends = [i for i, text in enumerate(pages) if kind + "END" in text]
            if len(starts) != 1 or len(ends) != 1 or starts[0] > ends[0]:
                raise AssertionError(f"{kind} beginning/end is missing or duplicated")
            # A final paragraph can continue on a page without another row marker.
            # Its physical fragment still belongs to the callout and must have no icon.
            occupied = list(range(starts[0], ends[0] + 1))
            row_pages = [i for i, text in enumerate(pages) if kind + "ROW" in text]
            if len(occupied) < 3 or not row_pages or any(i not in occupied for i in row_pages):
                raise AssertionError(f"{kind} must span at least three consecutive pages: {occupied}")
            rows = re.findall(kind + r"ROW(\d{3})", joined)
            if rows != [f"{i:03d}" for i in range(1, 29)]:
                raise AssertionError(f"{kind} loses or repeats paragraph content")
            icon_counts = []
            for i in occupied:
                page = pdf[i]
                left = (20 if (i + 1) % 2 else 17) * 72 / 25.4
                gutter_right = left + 17.5 * 72 / 25.4
                paths = [d for d in page.get_drawings()
                         if (d.get("color") or d.get("fill"))
                         and d["rect"].y0 > 45
                         and d["rect"].x0 > left + 2
                         and d["rect"].x1 < gutter_right - 2
                         and (d["rect"].width > .1 or d["rect"].height > .1)]
                icon_counts.append(len(paths))
            if icon_counts[0] < 3 or any(icon_counts[1:]):
                raise AssertionError(f"{kind} icon must occur only on first fragment: {icon_counts}")
            findings[kind.lower()] = {"pages": [i + 1 for i in occupied],
                                      "paragraphs": len(rows), "icon_paths_by_fragment": icon_counts}
        table_pages = [i for i, text in enumerate(pages) if "TABLEROW" in text]
        if len(table_pages) < 3:
            raise AssertionError("The long table must exercise at least three physical pages")
        table_rows = re.findall(r"TABLEROW(\d{3})", joined)
        if table_rows != [f"{i:03d}" for i in range(1, 151)]:
            raise AssertionError("Long-table rows are missing, repeated or reordered")
        for i in table_pages:
            if "TABLEHEAD" not in pages[i]:
                raise AssertionError(f"Long-table header missing on physical page {i + 1}")
        if not re.search(r"TABLECHECK\s+1\.1", joined):
            raise AssertionError("Long-table caption label must resolve to table 1.1")
        if not re.search(r"EQUATIONCHECK\s+2\.1", joined):
            raise AssertionError("Cross-chapter equation reference must resolve to equation 2.1")
        black_mark = [s for p in pdf for s in spans(p) if "AFTERTABLEBLACK" in s["text"]]
        if len(black_mark) != 1 or black_mark[0]["color"] != 0:
            raise AssertionError("Table styles leak into the following text")
        # Short chapter labels must survive temporary worksheet/assessment marks.
        for marker in ("WORKSHEETFIRST", "WORKSHEETSECOND", "ASSESSMENTFIRST", "ASSESSMENTSECOND"):
            i = next(i for i, text in enumerate(pages) if marker in text)
            header = " ".join(s["text"] for s in spans(pdf[i]) if s["bbox"][1] < 45).replace("∆", "Δ")
            if "Δοκιμή Κινηματικής" not in header:
                raise AssertionError(f"Stored chapter title lost on {marker}: {header}")
        i = next(i for i, text in enumerate(pages) if "SOLUTIONSECOND" in text)
        header = " ".join(s["text"] for s in spans(pdf[i]) if s["bbox"][1] < 45).replace("∆", "Δ")
        if header != "Ενδεικτικές λύσεις":
            raise AssertionError(f"Independent solutions inherit a stale header: {header}")
        # Long titles must have actual clickable navigation, not just visible text.
        outline = pdf.get_toc()
        if sum(row[0] == 1 for row in outline) < 5:
            raise AssertionError("Contents/chapter/solutions bookmarks are incomplete")
        toc_pages = [p for p in pdf if p.search_for("Περιεχόμενα")]
        if not toc_pages or not any(p.get_links() for p in toc_pages):
            raise AssertionError("The stress table of contents has no active links")
        return {"pages": len(pdf), "callouts": findings,
                "long_table": {"pages": [i + 1 for i in table_pages], "rows": len(table_rows),
                               "header_repeated": True, "reference": "1.1"},
                "body_proof_pages": 21, "chapter_routes": 3,
                "custom_opening_pages": opening_pages, "white_text_backgrounds_verified": True,
                "columns": 3, "resolved_references": True,
                "temporary_marks_preserve_chapter": True,
                "solutions_reset_running_header": True, "outline_entries": len(outline)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", dest="printed", required=True, type=Path)
    parser.add_argument("--screen", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {"status": "failed", "input_sha256": {}, "editions": {}}
    try:
        for name, path in (("print", args.printed), ("screen", args.screen)):
            report["input_sha256"][name] = digest(path)
            report["editions"][name] = check_document(path)
        if report["editions"]["print"] != report["editions"]["screen"]:
            raise AssertionError("Paired editions have different structural results")
        report["status"] = "passed"
    except (AssertionError, OSError, RuntimeError, ValueError) as exc:
        report["error"] = str(exc)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status'].upper()}: stress-book pagination")
    if report["status"] != "passed":
        print(report.get("error", "Unknown failure"), file=sys.stderr)
        return 1
    print(f"Both editions: {report['editions']['print']['pages']} pages; split callouts, repeated table heads and references verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

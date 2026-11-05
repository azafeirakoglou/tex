# v1.0.11 candidate technical QA

**Status: PASSED.** Review candidates; no stable adoption.

The checks use XeLaTeX and the independently copied candidate sources. All output and runtime state stay inside the experiment. No original repository modules are imported.

| Check | Result |
|---|---|
| approved palette identical | PASS |
| both full unit suites passed | PASS |
| both unit suites retain 66 tests | PASS |
| 40 author compatibility builds passed | PASS |
| 20 author compatibility pair preflights passed | PASS |
| both original stress structural checks passed | PASS |
| all 8 editorial fixture measurements passed | PASS |
| all 8 editorial fixture logs clean | PASS |
| all 4 editorial fixture pair preflights passed | PASS |
| all 24 secondary pair reports match current pdf hashes | PASS |
| all 8 editorial measurements match current pdf hashes | PASS |
| all 4 main thematic headings share their following theorem page | PASS |
| all 4 main flow reports match current 20 page pdf hashes | PASS |
| main 4 pdf logs have no overfull underfull missing or warning | PASS |
| all 44 build logs have no overfull or missing characters | PASS |

## Actual PDF typography

All sizes below are TeX points, measured from the PDF after converting PDF big points by 72.27/72. Tolerance is 0.012 pt; text and math have separate assertions.

| Role | Font | Size |
|---|---|---:|
| Body | Inter Regular | 10.95 |
| Section / subsection | Noto Serif Medium | 13 / 11 |
| Thematic heading | Noto Serif Medium | 11.7 |
| First body-page chapter title | Noto Serif Medium | 17.5 |
| First body-page chapter label | Inter Medium | 9.5 |
| Worked example title | Noto Serif Medium | 10.7 |
| Solution label | Inter Medium | 10.2 |
| Attention / Think titles | Inter Medium | 9.5 |
| Callout body | Inter Regular | 10 |
| History title, preserved | Inter Medium | 9.2 |
| Figure / table caption text | Inter Regular, upright | 9.5 |
| Diagram label / tick text | Inter Regular | 9.5 / 8.5 |
| Diagram label / tick math | STIX Two Math | 9.975 / 8.925 |
| Table header / table body, preserved | Inter SemiBold / Inter Regular | 10 / 10 |
| Running header / footer, preserved | Inter Regular | 8 |
| Body inline and display base math | STIX Two Math | 11.4975 |
| Callout base math / scripts | STIX Two Math | 10.5 / 7.35 |

The display formula uses the same base math size as inline body math. Short and long ThinkBox cases verify 105% math, Greek and Latin variables, indices, fractions, roots, sums, limits and integrals. Upright units and a chemical formula are included for visual inspection.

## Pagination and public authoring compatibility

The editorial fixture checks photo and non-photo openings, long titles, and chapter starts with a paragraph, section or callout. Each first body page contains one chapter label and a 17.5 pt title; the next body page has neither repeated heading. The full page-style suite additionally checks worksheet and assessment starts and recto/verso headers.

The controlled metrics PDF is three pages; each editorial edge PDF is 43 pages. Each long callout contains exactly 36 marked paragraphs. Begin/end markers and all rows must occur once and in order across at least three fragments. Vector icons must occur only in the first fragment. The 120-row table must retain every row, repeated headers, numbering and references across at least three pages. Figure, table and long-table captions must wrap with hanging alignment, Inter Regular 9.5 pt and the unchanged BookSecondary role; following text must return to black. The physics diagram retains vector horizontal and vertical axes and its sloping data line; its page contains no raster image.

The shipped stress fixture independently checks 28-paragraph callouts, a 150-row multipage table, repeated heads, references and all chapter routes. Existing author commands and fixtures remain present. Tests retain all 66 methods per candidate; extractor assertions use actual word geometry where PDF spans merge leaders and page numbers.

A separate main-book PDF regression locates the 11.7 pt «Απόδειξη — υπόδειγμα» thematic heading and the following «Πρόσθεση ίσων ποσοτήτων» theorem title. It asserts that both occupy the same page in every candidate/edition, with the theorem below the heading and without overlap. All four final PDFs keep the pair on physical page 19. Its SHA-256 hashes are checked again when generating this summary.

## Exact colour and plate checks

The approved v1.0.10 colour-role and PRINT/SCREEN palette TeX files match their captured SHA-256 hashes byte for byte in both candidates. The JSON map differs only in version and AttentionBox geometric metadata. Every semantic role, ink definition, tint, spot name, alternate CMYK and SCREEN base value is identical. The frozen evidence is authenticated against reports/SOURCE_BASELINE.json.

Each paired-PDF preflight checks all pages at 72 dpi with antialiasing disabled: all five process/spot separation plates, approved raster levels, absence of unintended RGB PRINT images, embedded fonts, page geometry, text and text positions, and paired SCREEN role colours. The editorial measurements independently verify every page at 170 × 240 mm. The unchanged review profile uses its MediaBox and does not introduce explicit press TrimBox metadata. All 24 secondary pair reports and eight measurement reports are checked against the current PDF SHA-256 hashes. These are engineering checks; the original printing approval/PDF-X status is unchanged.

## Diagnostics and retained evidence

Final main-PDF diagnostics are listed in QA_SUMMARY.json. All four main PDFs have 20 pages and no overfull/underfull boxes, missing characters or warnings. All eight editorial fixture logs are also clean. Secondary legacy figures and tables fixtures contain one empty underfull hbox each per edition (four per design); their content is byte-identical to the captured v1.0.10 fixture. Unused-caption and non-floating hypcap notices in fixtures are preserved in per-target audit logs. No test, public feature or warning was deleted to manufacture a pass.

See `qa/probes/results/*_xelatex.log` for complete editorial-fixture logs, `qa/probes/pdf/` for compact QA PDFs, `qa/compat/*/build_log_audit.json` for all target diagnostics, and `qa/suites/*.unittest.log` for final full test results. Earlier failure/inspection artifacts are working evidence and are excluded from the review package. The copied tests retain all methods and strict page-count assertions. Geometry extraction distinguishes a thin running-header rule from the REFINED opening strip, and TOC assertions use actual word positions when PDF spans merge leaders with page numbers.

Rendered visual evidence and editorial judgments are recorded separately under `visual-audit/` and the final editorial report. Successful compilation alone does not establish editorial acceptance.

## Reproduction

From the experiment root, after preparing the candidate runtime:

```sh
python3 qa/check_color_invariance.py
python3 qa/check_main_flow.py
python3 qa/suites/run_unit_suites.py
python3 qa/compat/run_compat.py
python3 qa/compat/validate_compat.py
python3 qa/compat/audit_build_logs.py
python3 qa/probes/run_editorial_probes.py
python3 qa/probes/validate_probe_pairs.py
python3 qa/create_summary.py
```

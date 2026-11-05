# v1.0.12 Technical QA

**Status: PASSED.**

The canonical source is MINIMAL; A/B change only worked-example headers. A is the preferred default and B remains optional.

| Check | Result |
|---|---|
| approved palette and all existing roles unchanged | PASS |
| canonical 66 tests passed without skips | PASS |
| all 40 author compatibility builds passed | PASS |
| all 20 author compatibility pairs passed | PASS |
| both 150 row stress structure checks passed | PASS |
| all 8 editorial measurements passed with clean logs | PASS |
| all 8 editorial measurements match current pdf hashes | PASS |
| all 4 editorial pairs passed | PASS |
| all 4 example proofs built without bad boxes or missing characters | PASS |
| three consecutive and large examples A B measurements passed | PASS |
| all 4 example measurements match current pdf hashes | PASS |
| both example pair preflights passed | PASS |
| all 29 pair preflights match current pdf hashes | PASS |
| all 42 build logs have no overfull underfull or missing characters | PASS |
| both main books are 20 pages with no warnings | PASS |
| both isolated variants match final canonical style and config | PASS |
| callout geometry content font and ink proofs passed | PASS |
| callout measurements match current pdfs | PASS |
| reviewed callout renders match rebuilt final proofs | PASS |
| longtable final row header bug closed and boundary regression passed | PASS |
| longtable proof matches current implementation | PASS |
| long material titles visually verified after spacing fix | PASS |
| all main and example pages visually reviewed | PASS |
| visual review matches current main and example pdf hashes | PASS |

## Evidence and scope

The complete canonical suite retains 66 tests with zero skipped. Forty secondary builds cover all 20 shipped author targets in both header variants. The eight controlled editorial PDFs verify actual font sizes, STIX 105%, captions, tables, vector figures, long teaching boxes, chapter openings and first-body titles. Four same-content six-page example proofs verify three consecutive examples and a large statement/solution across pages; A/B positions match. All paired preflights check every page and all five separation plates.

The longtable end-of-table defect is independently reproduced by a negative control and fixed centrally by omitting unused empty footer blocks. Ten row-boundary cases and the 120-row controlled table verify a repeated header on every page containing data, including the final row. Long worksheet/assessment titles use ragged-right paragraphs inside their font group, preserving font size and proper leading without stretched spacing.

Main books have 20 pages each. The machine report records exact final diagnostics, page counts and source hashes. All 42 standard build logs must have zero overfull/underfull boxes and missing characters; main logs must also have zero warnings. Expected unused-caption and non-floating hypcap notices in dedicated fixtures remain disclosed in the per-target audits.

PDF reports and visual reviews are bound to SHA-256 values. The original printing specifications remain pending; this is not a physical paper test or PDF/X certification. Previous-version integrity and scientific-content preservation are recorded separately in reports/ORIGINAL_INTEGRITY.json and SOURCE_DIFF.json.

Run `python3 qa/create_summary.py` after all reproduction commands complete. A missing/stale/failed prerequisite produces PENDING / FAIL and never promotes the version.

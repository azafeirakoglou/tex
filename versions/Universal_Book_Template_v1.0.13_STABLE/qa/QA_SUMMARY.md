# v1.0.13 Technical QA

**Status: PASSED.**

Based on v1.0.12 STABLE, retaining the MINIMAL design. A remains the default worked-example header; B is optional.

| Check | Result |
|---|---|
| approved palette and all existing roles unchanged | PASS |
| canonical 66 tests passed without skips | PASS |
| canonical tests attest unchanged current config and styles | PASS |
| all 40 author compatibility builds passed | PASS |
| all 20 author compatibility pairs passed | PASS |
| both 150 row stress structure checks passed on current pdfs | PASS |
| all 8 editorial measurements passed with clean logs | PASS |
| all 8 editorial measurements match current pdf hashes | PASS |
| editorial fonts STIX 105 and 120 row repeated table headers preserved | PASS |
| all 4 editorial pairs passed | PASS |
| all 4 example proofs built without bad boxes or missing characters | PASS |
| three consecutive and large examples A B measurements passed | PASS |
| all 4 example measurements match current pdf hashes | PASS |
| both example pair preflights passed | PASS |
| all 3 component pair preflights passed | PASS |
| all 30 pair preflights match current pdfs palette geometry fonts and plates | PASS |
| all 42 standard log audits match current logs and pdfs | PASS |
| all 42 build logs have no overfull underfull or missing characters | PASS |
| both main books are 20 pages with no warnings | PASS |
| both isolated variants match final canonical style and config | PASS |
| refinement native fonts rules goals TF answers and numbered bars passed | PASS |
| refinement attests current canonical config and styles | PASS |
| material headers short long titles white icons subtitle and fonts passed | PASS |
| material attests current owned config and styles | PASS |
| callout icons short long fragments vector weight and geometry passed | PASS |
| icons attest current owned config and styles | PASS |
| all 6 component measurements match current pdf hashes | PASS |
| all 40 main pages and 36 component pages actually visually reviewed | PASS |
| all required evidence files read successfully | PASS |

## Evidence and scope

Required regression coverage: 66 unskipped canonical tests, 40 compatibility builds in isolated A/B snapshots, 8 editorial probes, and 4 same-content A/B example proofs. Both 150-row stress books and all four 120-row editorial tables must retain their repeated headers. Unit-test source hashes must match every current config and style file.

The six new PRINT/SCREEN component proofs require all 22 refinement assertions, 17 material-header assertions and 10 callout-icon assertions per profile. These cover native page geometry, preserved fonts, rule widths, goals, short answers, exercise separators, narrow-column true/false choices, short and long material titles, subtitle toggling, vector icons, spacing and split teaching boxes. Component PDF and source hashes must be current.

All 30 paired preflights must match current PDFs and the canonical palette, native 170 × 240 mm geometry, embedded fonts and five separation plates. All 42 standard build logs must match their recorded hashes and have zero overfull/underfull boxes or missing characters. Main books must have 20 pages each and zero warnings. Expected unused-caption and non-floating hypcap notices remain disclosed in fixture audits.

Final visual evidence must record actual review of all 40 main-book pages and all 36 new component-proof pages, with current PDF and full-page-render hashes. This centralized final record supersedes component reports that still say pending_actual_views. Existing v1.0.12-specific callout/table proof reports are replaced by the new component proofs and retained stress/editorial regressions.

The frozen v1.0.12 palette and role definitions must be byte-identical; the color map may change only its version. Previous-version integrity and scientific-content preservation are recorded separately under reports/. Physical printing, final printer specifications and PDF/X certification remain outside this technical acceptance.

Run `python3 qa/create_summary.py` after reproduction completes. Missing, malformed, stale or failed evidence produces PENDING / FAIL. This command never promotes the version.

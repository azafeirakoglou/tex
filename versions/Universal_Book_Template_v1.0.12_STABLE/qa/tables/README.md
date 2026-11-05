# Controlled table/caption verification — v1.0.12

**PASS on the final common source.** PRINT and SCREEN each have six proof pages.
The actual table occupies pages 2–5, including all 120 rows exactly once and in order.
The ordinary paragraph after the table starts on page 6; it contains no table data.

The probe measures neutral Black10 header/stripe fills, 0.35 pt accent top rules,
Inter SemiBold10 headers, Inter Regular10 body, 9.5 pt hanging multiline captions
with only their semibold prefix/number coloured, resolved references, and restored
10.95 pt black body after tables. Both profiles have no bad boxes, missing glyphs
or warnings. All pages of the pair passed the five-plate/font/role/geometry preflight.

## Final-row defect and common fix

An inherited boundary defect stranded ROW120 without its repeated header. The
wrapper declared empty `endfoot` and `endlastfoot` blocks even though its public
API has no footer. These produce non-void, zero-height alignment boxes. The
installed longtable implementation then sets `maxdepth=0` in `LT@start`; when
normal output settings return at the end, the tail row can move after the table's
output routine has finished. Removing only the two unused empty footer blocks
leaves the normal void footer state and preserves the row/header relationship.
No data, font, margin, height or chunk size was changed to make the example fit.

`check_tail_boundary.py` tests striped tables at 118, 119, 120, 121, 122, 149, 150
and 151 rows, and plain tables at 120/121 rows. Every data page repeats its header.
An isolated negative mutation reinstates the old footer blocks and reproduces the
missing-header failure at 120 rows. The 121-row case was actually viewed: its
final row begins page 6 beneath its continuation header.

## Evidence and reproduction

- `TABLE_VERIFICATION.json`: final source hash and actual-view PNG hashes.
- `TABLE_PROBE_RESULTS.json`: measurements and all controlled checks.
- `TAIL_BOUNDARY_RESULTS.json`: ten passing boundary cases and negative control.
- `PREFLIGHT.json`: paired engineering preflight, not PDF/X certification.
- `SCREEN/`, `PRINT/`: final PDFs/logs and selected actual-view pages.

From the project root after runtime setup:

```sh
python3 qa/tables/run_table_probe.py
python3 qa/tables/check_tail_boundary.py
```

The boundary runner writes temporary TeX/PDFs beneath `runtime/tmp/`. Older
no-rule/parskip/chunk/proper-environment trials are development evidence only and
are excluded from the stable package.

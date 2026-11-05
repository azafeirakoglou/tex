# v1.0.12 teaching-callout proof

Final source was compiled independently into a 13-page PRINT/SCREEN pair.
Page 1 has short ThinkBox, AttentionBox and HistoryBox. Each following long
callout contains 36 distinct marked paragraphs plus four display equations
and occupies four fragments: Think 2–5, Attention 6–9, History 10–13.

`MEASUREMENTS.json` binds the PDF hashes to these checks:

- Exactly 36 markers once and in order for each callout.
- Exactly one vector west rule on every fragment: 0.8 TeX pt for Think/History,
  1 TeX pt for Attention, with no repeated icon on continuation fragments.
- Every short title is Inter Medium 9.5 TeX pt (PDF bp converted by 72.27/72).
- Both profiles keep the same 13-page content and geometry.

`PREFLIGHT.json` additionally verifies all 13 paired pages, five process/spot
plates, approved tints, embedded fonts and matching text/positions. No
overfull, underfull or missing characters occurred. Two unused-caption
warnings per proof are expected because this isolated fixture has no floats.

Actual visual inspection at common 108 dpi covered SCREEN pages
1, 2, 3, 5, 6, 7, 9, 10, 11, 13 and PRINT pages 1, 6, 10. The short titles,
smaller triangle/hourglass, first-fragment icon alignment, fill differences
and long west-rule continuation were clear without overlaps or clipping.
The whole-page PNGs use the native 170 × 240 mm page at matrix 1.5; this is
rendered evidence, not a physical print test.

Reproduce from the project root after preparing its runtime:

```sh
python3 qa/callouts/run_callout_proof.py
python3 qa/callouts/check_callout_proof.py
python3 source/scripts/validate_pdf.py --print qa/callouts/PRINT/callout-proof-print.pdf --screen qa/callouts/SCREEN/callout-proof-screen.pdf --map source/config/color-map.json --report qa/callouts/PREFLIGHT.json
```

The shared style uses 7/8 pt external gaps, 2.8 mm top/bottom padding for
Attention/History and 3.8 mm for Think. Existing compact workedexample
external gaps can still override the shared foundation locally. All three
use their unchanged registered accent roles; Think has no fill, Attention
retains second-ink 10% and History black 10%. The warning triangle uses
0.94 of its previous geometric scale, the hourglass 0.81 instead of 0.90,
and the bulb retains 0.81. TikZ outline widths remain 1.08 pt.

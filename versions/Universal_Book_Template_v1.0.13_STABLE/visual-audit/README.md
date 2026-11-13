# Visual evidence

The final visual review covers 76 PDF pages through 38 paired images. In every pair, PRINT is left and SCREEN is right. Every source page is rendered at `fitz.Matrix(1.5, 1.5)` from its native 170 × 240 mm PDF page. The paired images paste the two unchanged PNGs side by side; there is no fitting, cropping, resizing, or per-page alignment.

From the package root, regenerate the render manifest and PNGs with:

```sh
python -m pip install -r requirements-review.txt
python visual-audit/render_review.py
```

`MANIFEST.json` binds each source PDF, single-page PNG, and paired PNG by SHA-256. `VISUAL_EVIDENCE.json` records the actual completed review. Regenerating renders does not establish a new visual review or update its approval. Open and inspect every paired image again after any PDF change, and compare the evidence hashes with the new manifest.

The report is [VISUAL_REVIEW.md](../reports/VISUAL_REVIEW.md). `component-review.json` records an additional independent review of all 36 component PDF pages. No physical print test was performed.

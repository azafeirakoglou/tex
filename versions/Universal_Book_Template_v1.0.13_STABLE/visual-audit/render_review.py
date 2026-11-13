#!/usr/bin/env python3
"""Render current PDF review targets at fixed 1.5x native page size.

No per-page fitting, cropping, rescaling, or alignment is used. Paired pages
are unscaled side-by-side copies of the render PNGs (PRINT left, SCREEN right).
"""
from pathlib import Path
import hashlib, json
import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'main': ('pdf/Universal_Book_Template_v1.0.13_{profile}.pdf',20),
    'material': ('qa/material/{profile}/material-proof.pdf',6),
    'icons': ('qa/icons/{profile}/icon-context.pdf',7),
    'refinement': ('qa/refinement/pdf/REFINEMENT_{profile}.pdf',5),
}
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {'matrix': 1.5, 'native_page_mm': [170,240], 'pair_order':['PRINT','SCREEN'], 'pdfs': [], 'pairs':[]}
for group,(pattern,pages) in TARGETS.items():
    documents = {}
    for profile in ('PRINT','SCREEN'):
        relative = pattern.format(profile=profile)
        pdf = ROOT/relative
        doc = fitz.open(pdf)
        assert len(doc)==pages,(relative,len(doc),pages)
        renders=[]
        for index,page in enumerate(doc):
            assert abs(page.rect.width-170/25.4*72)<.1
            assert abs(page.rect.height-240/25.4*72)<.1
            output=ROOT/f'visual-audit/renders/{group}/{profile}/page-{index+1:02d}.png'
            output.parent.mkdir(parents=True,exist_ok=True)
            page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(output)
            renders.append({'page':index+1,'path':str(output.relative_to(ROOT)),'sha256':digest(output)})
        documents[profile]=renders
        manifest['pdfs'].append({'group':group,'profile':profile,'pdf':relative,'sha256':digest(pdf),'renders':renders})
    for page in range(1,pages+1):
        left=Image.open(ROOT/documents['PRINT'][page-1]['path']).convert('RGB')
        right=Image.open(ROOT/documents['SCREEN'][page-1]['path']).convert('RGB')
        assert left.size==right.size
        pair=Image.new('RGB',(left.width+right.width,left.height),'#aaaaaa')
        pair.paste(left,(0,0));pair.paste(right,(left.width,0))
        output=ROOT/f'visual-audit/pairs/{group}/page-{page:02d}.png'
        output.parent.mkdir(parents=True,exist_ok=True)
        pair.save(output)
        manifest['pairs'].append({'group':group,'page':page,'path':str(output.relative_to(ROOT)),'sha256':digest(output),'dimensions_px':list(pair.size)})
(ROOT/'visual-audit/MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Rendered',len(manifest['pdfs']),'PDFs,',sum(len(x['renders']) for x in manifest['pdfs']),'pages,',len(manifest['pairs']),'pairs')

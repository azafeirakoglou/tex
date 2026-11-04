from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageFont
base=Path('/workspace/typography-review')
out=base/'visual-audit'
labels=['A_CURRENT','B_STIX105','C_STIX108','D_STIX_FAMILY','E_LIBERTINUS']
font=ImageFont.truetype(str(base/'runtime/fonts/Inter-Regular.otf'),25)
# Coordinates and pixel scale are identical across font variants.
regions={'theory_top':(0,(45,48,433,230)),
         'examples_top':(1,(45,48,433,322)),
         'math_dense':(2,(45,48,433,360)),
         'math_greek_chem':(2,(45,330,433,605)),
         'boxes':(3,(45,48,433,515)),
         'figures':(4,(45,48,433,525))}
for label in labels:
    path=base/'pdf'/f'{label}_SCREEN.pdf'
    if not path.exists():continue
    with fitz.open(path) as d:
        for name,(page,rect) in regions.items():
            pix=d[page].get_pixmap(matrix=fitz.Matrix(2,2),clip=fitz.Rect(rect),alpha=False)
            pix.save(out/f'{label}_{name}.png')
        d[0].get_pixmap(matrix=fitz.Matrix(1.7,1.7),alpha=False).save(out/f'{label}_page1.png')
for name in regions:
    for group,suffix in [(labels[:3],'ABC'),(labels[3:],'DE'),(labels,'ALL')]:
        paths=[out/f'{label}_{name}.png' for label in group]
        if not all(p.exists() for p in paths):continue
        ims=[Image.open(p).convert('RGB') for p in paths]
        w=max(im.width for im in ims); h=sum(im.height+45 for im in ims)
        dst=Image.new('RGB',(w,h),'#f2f2f2'); draw=ImageDraw.Draw(dst); y=0
        for label,im in zip(group,ims):
            draw.text((8,y+6),label,font=font,fill='#111111'); y+=45
            dst.paste(im,(0,y)); y+=im.height
        dst.save(out/f'COMPARISON_{suffix}_{name}.png')
print('Rendered current PDFs, shared2xscale; stable checkout untouched.')

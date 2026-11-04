#!/usr/bin/env python3
from pathlib import Path
import os,json,hashlib
ROOT=Path(__file__).resolve().parent
os.environ['TMPDIR']=str(ROOT/'runtime/tmp')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import fitz
from PIL import Image,ImageDraw,ImageFont
NAMES=['A_CURRENT','B_STIX105','C_STIX108','D_STIX_FAMILY','E_LIBERTINUS']
LABELS=['A CURRENT','B STIX 105%','C STIX 108%','D STIX FAMILY','E LIBERTINUS']
TOPICS=['Physics / inline math','Worked examples / display math','Mathematics / Chemistry symbols','Teaching callouts','Physics diagrams']
fontfile=ROOT/'runtime/fonts/NotoSerif-Regular.ttf'
comparison=fitz.open();toc=[];rows=[]
for topic in range(5):
    toc.append([1,TOPICS[topic],len(comparison)+1])
    for name,label in zip(NAMES,LABELS):
        source=ROOT/'pdf'/(name+'_SCREEN.pdf')
        with fitz.open(source) as doc:
            assert len(doc)==5,(name,len(doc))
            size=doc[topic].rect
            page=comparison.new_page(width=size.width,height=size.height)
            page.show_pdf_page(page.rect,doc,topic,keep_proportion=True)
            page.insert_font(fontname='ReviewLabel',fontfile=str(fontfile))
            line=f'{label} | SCREEN | {topic+1}/5 | 170 x 240 mm | 100% page size'
            page.insert_text((20*72/25.4,4.5*72/25.4),line,fontname='ReviewLabel',fontsize=6.6,color=(0,0,0))
            rows.append({'comparison_page':len(comparison),'variant':name,'source_page':topic+1,'scale':1.0,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
            pix=doc[topic].get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False)
            pix.save(ROOT/'previews'/f'{name}_p{topic+1}.png')
            toc.append([2,label,len(comparison)])
comparison.set_toc(toc)
comparison.set_metadata({'title':'TYPOGRAPHY COMPARISON — v1.0.10 experimental review','subject':'Five variants, five topics; SCREEN profile, 170 x 240 mm at unchanged 1:1 scale','author':'Typography review','keywords':'experimental; stable unchanged; no font choice applied'})
comparison.save(ROOT/'TYPOGRAPHY_COMPARISON.pdf',garbage=4,deflate=True)
comparison.close()
(ROOT/'reports/COMPARISON_MANIFEST.json').write_text(json.dumps({'pages':25,'page_mm':[170,240],'profile':'SCREEN','all_source_pages_unscaled':True,'organization':'Five topic groups; variants A–E within each group','pages_map':rows},ensure_ascii=False,indent=2)+'\n')
label_font=ImageFont.truetype(str(fontfile),22)
for page_no in [1,2,3,4,5]:
    pictures=[Image.open(ROOT/'previews'/f'{n}_p{page_no}.png').convert('RGB') for n in NAMES]
    width=sum(x.width for x in pictures)+12*6;height=max(x.height for x in pictures)+60
    canvas=Image.new('RGB',(width,height),'#eeeeee');draw=ImageDraw.Draw(canvas);left=12
    for label,picture in zip(LABELS,pictures):
        draw.text((left+8,8),label,fill='#000000',font=label_font)
        canvas.paste(picture,(left,43));left+=picture.width+12
    canvas.save(ROOT/'previews'/f'COMPARISON_topic{page_no}.png')
print('Comparison PDF: 25 pages, all 170 x 240 mm, source pages at 1:1; 25 previews and 5 contact sheets.')

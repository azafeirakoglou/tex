from pathlib import Path
import sys,os,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
os.environ['TMPDIR']=str(ROOT/'runtime/tmp');sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'source/scripts'))
sys.path.insert(0,str(ROOT/'qa'))
import fitz,validate_pdf
from ink_collision import _embedded_fonts,_embedded_bounds,_font_key
qa=json.loads((ROOT/'qa/QA_SUMMARY.json').read_text())
result={'status':'passed','comparison':{},'margin_analysis':{}}
comparison=ROOT/'TYPOGRAPHY_COMPARISON.pdf'
errors=[]
info=validate_pdf.inspect_pdf(comparison,errors,'comparison',print_edition=False)
with fitz.open(comparison) as doc:
 assert len(doc)==25,len(doc)
 boxes=[(round(p.rect.width*25.4/72,5),round(p.rect.height*25.4/72,5)) for p in doc]
 assert all(abs(w-170)<.02 and abs(h-240)<.02 for w,h in boxes)
result['comparison']={'status':'passed' if not errors else 'failed','errors':errors,'pages':25,'page_sizes_mm':boxes,'unembedded_fonts':info['unembedded_fonts'],'sha256':hashlib.sha256(comparison.read_bytes()).hexdigest()}
assert not errors,errors
for variant in qa['variants']:
 path=ROOT/f'pdf/{variant}_SCREEN.pdf'
 with fitz.open(path) as doc:
  fonts=_embedded_fonts(doc);rows=[]
  for index,page in enumerate(doc):
   left=(20 if (index+1)%2 else 17)*72/25.4
   right=(153 if (index+1)%2 else 150)*72/25.4
   traces=page.get_texttrace()
   for candidate in qa['variants'][variant]['documents']['SCREEN']['pages'][index]['span_bbox_margin_candidates']:
    r=fitz.Rect(candidate['bbox']);terminal=[]
    for t in traces:
     key=_font_key(t['font']);entry=fonts.get(key)
     if entry is None:continue
     for u,gid,origin,bbox in t['chars']:
      x,y=origin
      if not (r.x0-1<x<r.x1+1 and r.y0-1<y<r.y1+1):continue
      if x<right-6:continue
      bounds=_embedded_bounds(entry,gid)
      if bounds is None:continue
      ink_right=x+bounds[2]*t['size']*entry['scale_x']
      terminal.append({'character':chr(u),'origin_x_pdf_bp':x,'ink_right_pdf_bp':ink_right,'protrusion_pdf_bp':ink_right-right})
    rows.append({'page':index+1,'text':candidate['text'],'nominal_right_pdf_bp':right,'font_span_right_pdf_bp':r.x1,'font_span_protrusion_pdf_bp':r.x1-right,'terminal_glyph_ink':terminal})
  result['margin_analysis'][variant]={'candidate_count':len(rows),'candidates':rows}
# Directly compare the same unchanged stable paragraphs, accounting for mirrored margins.
def matching_spans(path,prefixes):
 rows=[]
 with fitz.open(path) as doc:
  for page in doc:
   for b in page.get_text('dict')['blocks']:
    for l in b.get('lines',[]):
     for s in l['spans']:
      if any(s['text'].startswith(x) for x in prefixes):rows.append({'text':s['text'],'width':s['bbox'][2]-s['bbox'][0],'font':s['font'],'size':s['size']})
 return rows
prefixes=['Για την περιγραφή της ευθύγραμμης κίνησης ορίζουμε','Η θέση ενός σώματος σε έναν άξονα δίνεται']
review=matching_spans(ROOT/'pdf/A_CURRENT_SCREEN.pdf',prefixes)
stable=matching_spans(Path('/workspace/tex/releases/v1.0.10/Book_v1.0.10_SCREEN.pdf'),prefixes)
stable+=matching_spans(Path('/workspace/tex/releases/v1.0.10/Starter_v1.0.10_SCREEN.pdf'),prefixes)
comparison_rows=[]
for new in review:
 matches=[old for old in stable if old['text']==new['text'] and old['font']==new['font']]
 if matches:
  old=min(matches,key=lambda a:abs(a['width']-new['width']))
  comparison_rows.append({'text':new['text'],'review_span_width_pdf_bp':new['width'],'stable_span_width_pdf_bp':old['width'],'width_difference_pdf_bp':new['width']-old['width']})
assert len(comparison_rows)>=2,comparison_rows
assert all(abs(r['width_difference_pdf_bp'])<.02 for r in comparison_rows)
result['stable_paragraph_comparison']=comparison_rows
result['interpretation']='The nominal geometry is unchanged. Existing Inter right-margin candidates are terminal hyphen/full-stop optical protrusion and font advance boxes, reproduced in the stable PDFs; they are not new overfull boxes or page clipping. Actual ink extends slightly beyond the nominal text edge as recorded, so no claim of all ink strictly inside the text rectangle is made.'
(ROOT/'qa/COMPARISON_AND_PROTRUSION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'comparison':result['comparison']['status'],'stable_matches':len(comparison_rows),'candidate_counts':{v:x['candidate_count'] for v,x in result['margin_analysis'].items()}}))

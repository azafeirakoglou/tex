#!/usr/bin/env python3
"""Read-only PDF/log audit for the isolated five-variant typography review."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.update({'TMPDIR':str(ROOT/'runtime/tmp'),'TEMP':str(ROOT/'runtime/tmp'),'TMP':str(ROOT/'runtime/tmp'),'PYTHONDONTWRITEBYTECODE':'1'})
sys.dont_write_bytecode=True
import argparse, hashlib, json, re, statistics, unicodedata, difflib, tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import fitz
# Import the review copy, never the stable repository.
sys.path.insert(0,str(ROOT/'source/scripts'))
import validate_pdf

tempfile.tempdir=str(ROOT/'runtime/tmp')
VARIANTS={
 'A_CURRENT':{'math_scale':1.00,'body_prefix':'Inter','heading_prefix':'NotoSerif','math_prefix':'STIXTwoMath'},
 'B_STIX105':{'math_scale':1.05,'body_prefix':'Inter','heading_prefix':'NotoSerif','math_prefix':'STIXTwoMath'},
 'C_STIX108':{'math_scale':1.08,'body_prefix':'Inter','heading_prefix':'NotoSerif','math_prefix':'STIXTwoMath'},
 'D_STIX_FAMILY':{'math_scale':1.00,'body_prefix':'STIXTwoText','heading_prefix':'STIXTwoText','math_prefix':'STIXTwoMath'},
 'E_LIBERTINUS':{'math_scale':1.00,'body_prefix':'LibertinusSerif','heading_prefix':'LibertinusSerif','math_prefix':'LibertinusMath'},
}
PAGE_ANCHORS=['Θεωρία','Λυμένα παραδείγματα','Μαθηματικοί συμβολισμοί','Διδακτικά κουτιά','Διαγράμματα και σύμβολα']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pt(value):return value*72.27/72

def font_key(name):
    return re.sub(r'[^a-z0-9]','',re.sub(r'^[A-Z]{6}\+','',name).lower())
def all_spans(page):
    return [s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['text'].strip()]
def canonical(text):
    text=unicodedata.normalize('NFKC',text).replace('\u00ad','').replace('\u2206','\u0394')
    return ''.join(c for c in text if c.isalnum())
def log_audit(paths):
    engine_paths=[p for p in paths if p.name!='driver.log']
    driver_paths=[p for p in paths if p.name=='driver.log']
    combined='\n'.join(p.read_text(errors='replace') for p in engine_paths)
    drivers='\n'.join(p.read_text(errors='replace') for p in driver_paths)
    patterns={
      'overfull':r'Overfull \\[hv]box[^\n]*(?:\n[^\n]*)?',
      'underfull':r'Underfull \\[hv]box[^\n]*(?:\n[^\n]*)?',
      'missing_glyph':r'Missing character:[^\n]*',
      'font_warning':r'(?:LaTeX Font Warning|Package fontspec Warning|Package unicode-math Warning)[^\n]*(?:\n[^\n]*)?',
      'other_latex_warning':r'(?:LaTeX Warning|Package [^\n]+ Warning):[^\n]*(?:\n[^\n]*)?',
      'error':r'(?:^! |LaTeX Error:|Package [^\n]+ Error:|Undefined control sequence|Emergency stop)[^\n]*',
    }
    found={k:re.findall(pattern,combined,re.M) for k,pattern in patterns.items()}
    found['driver_warnings']=re.findall(r'xdvipdfmx:warning:[^\n]*',drivers)
    found['benign_duplicate_spot_resource_warnings']=[x for x in found['driver_warnings'] if 'already defined in dict' in x]
    found['unclassified_driver_warnings']=[x for x in found['driver_warnings'] if 'already defined in dict' not in x]
    found['log_files']=[str(p.relative_to(ROOT)) for p in paths]
    found['log_file_count']=len(paths)
    return found

def document_audit(path,settings):
    errors=[]; warnings=[]; pages=[]; fonts=Counter(); sizes=Counter(); math_sizes=Counter(); text_pages=[]
    prefixes={font_key(settings[k]) for k in ['body_prefix','heading_prefix','math_prefix']}
    body=font_key(settings['body_prefix']); math=font_key(settings['math_prefix'])
    with fitz.open(path) as doc:
        if len(doc)!=5:errors.append(f'Expected five comparison pages, found {len(doc)}')
        for index,page in enumerate(doc):
            width,height=page.rect.width*25.4/72,page.rect.height*25.4/72
            if abs(width-170)>.02 or abs(height-240)>.02:errors.append(f'Page {index+1}: dimensions {width}×{height} mm')
            text=page.get_text('text',flags=fitz.TEXTFLAGS_TEXT|fitz.TEXT_DEHYPHENATE)
            text_pages.append(text)
            if index<len(PAGE_ANCHORS) and PAGE_ANCHORS[index] not in re.sub(r'\s+',' ',text):
                errors.append(f'Page {index+1}: expected topic missing: {PAGE_ANCHORS[index]}')
            spans=all_spans(page)
            for s in spans:
                fonts[s['font']]+=len(s['text'])
                sizes[(s['font'],round(pt(s['size']),4))]+=len(s['text'])
                if font_key(s['font']).startswith(math):math_sizes[round(pt(s['size']),4)]+=len(s['text'])
                if not any(font_key(s['font']).startswith(p) for p in prefixes):
                    # Explicit symbol/mono faces are allowed only if present in unchanged stable commands.
                    if not font_key(s['font']).startswith('dejavu'):
                        errors.append(f'Unexpected actual font: {s["font"]}')
            # Measure normal-body line baselines, keeping paragraph groups separate.
            paragraph_gaps=[]; line_baselines=[]
            for block in page.get_text('dict')['blocks']:
                ys=[]
                for line in block.get('lines',[]):
                    regular=[s for s in line['spans'] if font_key(s['font']).startswith(body)
                             and 'regular' in font_key(s['font']) and abs(pt(s['size'])-10.95)<.03
                             and sum('\u0370'<=c<='\u03ff' for c in s['text'])>=4]
                    if regular:
                        y=statistics.median(s['origin'][1] for s in regular);ys.append(y);line_baselines.append(y)
                paragraph_gaps.extend(pt(b-a) for a,b in zip(ys,ys[1:]) if 7<pt(b-a)<35)
            body_spans=[s for s in spans if s['bbox'][1]>55 and s['bbox'][3]<625]
            left=(20 if (index+1)%2 else 17)*72/25.4
            right=(153 if (index+1)%2 else 150)*72/25.4
            # Glyph bbox bounds are deliberately reported as candidates, not physical ink collisions.
            bounds=[s for s in body_spans if s['bbox'][0]<left-2 or s['bbox'][2]>right+2]
            if bounds:warnings.append(f'Page {index+1}: {len(bounds)} span-bbox margin candidates; review actual ink')
            pages.append({'page':index+1,'size_mm':[round(width,5),round(height,5)],
                          'normal_body_line_count':len(line_baselines),
                          'normal_body_baselines_pdf_bp':[round(y,5) for y in line_baselines],
                          'within_paragraph_baseline_gaps_tex_pt':[round(y,5) for y in paragraph_gaps],
                          'baseline_gap_median_tex_pt':round(statistics.median(paragraph_gaps),5) if paragraph_gaps else None,
                          'span_bbox_margin_candidates':[{'text':s['text'],'bbox':s['bbox']} for s in bounds],
                          'canonical_extracted_alnum_sha256':hashlib.sha256(canonical(text).encode()).hexdigest()})
        first=all_spans(doc[0]);tag=[s for s in first if re.search(r'1\.1\)',s['text']) and s['bbox'][0]>300]
        equation={}
        if len(tag)!=1:errors.append(f'Expected one first-equation tag, found {len(tag)}')
        else:
            tag=tag[0];equation['tag']={'text':tag['text'],'font':tag['font'],'size_tex_pt':round(pt(tag['size']),5),'baseline_pdf_bp':tag['origin'][1],'bbox_pdf_bp':tag['bbox']}
            row=[s for s in first if font_key(s['font']).startswith(math) and abs(s['origin'][1]-tag['origin'][1])<.5]
            if not row:errors.append('Could not identify first display-equation main row')
            else:
                actual=statistics.median(pt(s['size']) for s in row)
                equation['display_main_size_tex_pt']=round(actual,5)
                equation['display_baseline_max_difference_pdf_bp']=round(max(abs(s['origin'][1]-tag['origin'][1]) for s in row),6)
                expected=10.95*settings['math_scale']
                equation['expected_display_size_tex_pt']=expected
                if abs(actual-expected)>.015:errors.append(f'Math scaling not realized: actual {actual} pt, expected {expected} pt')
            inline=[s for s in first if font_key(s['font']).startswith(math) and s['origin'][1]<tag['origin'][1]-2 and s['text'].strip()]
            # Main inline x_A/x_B occurs above the first display; choose largest type on those rows.
            if inline:
                main=max(pt(s['size']) for s in inline)
                equation['inline_main_size_tex_pt']=round(main,5)
                equation['inline_smaller_sizes_tex_pt']=sorted({round(pt(s['size']),5) for s in inline if pt(s['size'])<main-.1})
                if abs(main-10.95*settings['math_scale'])>.015:errors.append('Inline scaling differs from expected base scale')
            if abs(pt(tag['size'])-10.95)>.015:errors.append('Equation number no longer has normal body size')
        try:
            from ink_collision import analyze_document
            ink=analyze_document(path)
        except ImportError:
            ink={'status':'pending','note':'Independent ink-bounds analyzer not yet available'}
        return {'status':'passed' if not errors else 'failed','errors':sorted(set(errors)),'warnings':warnings,
                'file':str(path.relative_to(ROOT)),'sha256':sha(path),'pages':pages,'page_count':len(doc),
                'actual_fonts_by_characters':dict(fonts),'font_size_samples':[{'font':f,'tex_pt':s,'characters':n} for (f,s),n in sorted(sizes.items())],
                'math_size_distribution_tex_pt':dict(sorted(math_sizes.items())), 'first_equation':equation,
                'canonical_extracted_text':canonical(''.join(text_pages)),'ink_and_line_analysis':ink}

def find_logs(variant,profile):
    matches=[]
    for p in ROOT.rglob('*.log'):
        if any(x in p.parts for x in ['source','runtime','fonts','qa']):continue
        value=str(p.relative_to(ROOT)).upper()
        if variant in value and profile in value:matches.append(p)
    return sorted(matches)

def run_variant(item):
    variant,settings=item;folder=ROOT/'qa'/variant;folder.mkdir(parents=True,exist_ok=True)
    docs={profile:document_audit(ROOT/'pdf'/f'{variant}_{profile}.pdf',settings) for profile in ['SCREEN','PRINT']}
    palette=json.loads((ROOT/'source/config/color-map.json').read_text())
    pair=validate_pdf.validate(ROOT/'pdf'/f'{variant}_PRINT.pdf',ROOT/'pdf'/f'{variant}_SCREEN.pdf',palette,dpi=72)
    (folder/'pair-preflight.json').write_text(json.dumps(pair,ensure_ascii=False,indent=2)+'\n')
    logs={profile:log_audit(find_logs(variant,profile)) for profile in ['SCREEN','PRINT']}
    errors=[]
    if pair['status']!='passed':errors.extend(pair['errors'])
    for profile,doc in docs.items():
        errors.extend(f'{profile}: {e}' for e in doc['errors'])
        log=logs[profile]
        if log['missing_glyph'] or log['font_warning'] or log['error']:errors.append(profile+': missing glyph, font warning or TeX error')
    return variant,{'status':'passed' if not errors else 'failed','settings':settings,'documents':docs,'logs':logs,
                    'pair_preflight':'qa/'+variant+'/pair-preflight.json','pair_status':pair['status'],'errors':errors}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--jobs',type=int,default=2);args=parser.parse_args()
    (ROOT/'qa').mkdir(exist_ok=True)
    missing=[str(ROOT/'pdf'/f'{v}_{p}.pdf') for v in VARIANTS for p in ['SCREEN','PRINT'] if not (ROOT/'pdf'/f'{v}_{p}.pdf').is_file()]
    if missing:raise SystemExit('Missing comparison PDFs: '+', '.join(missing))
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:results=dict(pool.map(run_variant,VARIANTS.items()))
    ref=results['A_CURRENT']['documents']['SCREEN']['canonical_extracted_text']
    for variant,row in results.items():
        for profile,doc in row['documents'].items():
            value=doc.pop('canonical_extracted_text')
            doc['canonical_alnum_text_matches_A']=value==ref
            doc['canonical_alnum_similarity_to_A']=round(difflib.SequenceMatcher(None,ref,value,autojunk=False).ratio(),7)
            if value!=ref:
                doc['warnings'].append('Extracted alphanumeric stream differs from A; common TeX source is the content authority, inspect glyph mappings/line extraction')
    content=ROOT/'content/common-body.tex'
    baseline=json.loads((ROOT/'BASELINE_GIT_AND_FILES.json').read_text())
    copied={name:sha(ROOT/'source'/name)==value for name,value in baseline['sha256'].items() if (ROOT/'source'/name).is_file()}
    manifest=json.loads((ROOT/'VARIANT_MANIFEST.json').read_text())
    integrity={'copied_source_files_checked':len(copied),'copied_source_matches_original_snapshot':all(copied.values()),
               'changed_copy_files':[name for name,ok in copied.items() if not ok],
               'manifest_content_sha256_matches':manifest['content_sha256']==sha(content),
               'all_variant_content_sha256_match':all(v['content_sha256']==sha(content) for v in manifest['variants'].values())}
    report={'status':'passed' if all(r['status']=='passed' for r in results.values()) and all(copied.values()) and integrity['manifest_content_sha256_matches'] and integrity['all_variant_content_sha256_match'] else 'failed',
            'independent_control_integrity':integrity,
            'scope':'Ten isolated review PDFs; dimensions, embedded/actual fonts, measured math scales, paired inks/positions, logs and line/ink metrics',
            'text_comparison_normalization':'NFKC, soft-hyphen removal, whitespace/punctuation removal and known Inter U+2206 increment-glyph-to-Greek-Delta mapping; original TeX source is authoritative',
            'common_content':str(content.relative_to(ROOT)),'common_content_sha256':sha(content),'variants':results,
            'limitations':['Span boxes are font boxes, not physical ink; independent ink analyzer records its own scope.',
                           'Extracted-text differences between font families do not by themselves prove changed TeX content.',
                           'No screen raster substitutes for a physical 100% print proof.']}
    out=ROOT/'qa/QA_SUMMARY.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Έλεγχοι συγκριτικών PDF','',f"Συνολική κατάσταση: **{report['status']}**.",'',
           '| Εκδοχή | Σελίδες SCREEN/PRINT | Μαθηματικά inline/display (pt) | Αριθμός εξίσωσης (pt) | Έλεγχος μελανιών |','|---|---|---|---|---|']
    for v,r in results.items():
        d=r['documents']['SCREEN'];e=d['first_equation'];t=e.get('tag',{})
        lines.append(f"| {v} | {d['page_count']}/{r['documents']['PRINT']['page_count']} | {e.get('inline_main_size_tex_pt')}/{e.get('display_main_size_tex_pt')} | {t.get('size_tex_pt')} | {r['pair_status']} |")
    lines+=['','## Παρατηρήσεις','']
    for v,r in results.items():
        counts={p:{k:len(x) for k,x in q.items() if isinstance(x,list) and k!='log_files'} for p,q in r['logs'].items()}
        lines.append(f'- {v}: '+json.dumps(counts,ensure_ascii=False))
        for p,d in r['documents'].items():
            for w in d['warnings']:lines.append(f'  - {p}: {w}')
        for e in r['errors']:lines.append(f'  - Σφάλμα: {e}')
    lines+=['','Οι μετρήσεις είναι σε TeX pt. Το πλήρες JSON διατηρεί PDF bp και τις πραγματικές θέσεις.',
            'Η εκτύπωση στο 100% παραμένει η κατάλληλη τελική οπτική σύγκριση.','']
    (ROOT/'qa/QA_SUMMARY.md').write_text('\n'.join(lines))
    print(json.dumps({'status':report['status'],'report':str(out),'variants':{v:r['status'] for v,r in results.items()}},ensure_ascii=False))
    return 0 if report['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())

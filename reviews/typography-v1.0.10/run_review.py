#!/usr/bin/env python3
"""Isolated typography experiment; never writes into the stable repository."""
from pathlib import Path
import os, sys, json, shutil, hashlib, subprocess, argparse
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime'
os.environ['TMPDIR']=str(RUNTIME/'tmp')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
VARIANTS={
 'A_CURRENT':{'label':'A — CURRENT','math_scale':1.0,'family':'current'},
 'B_STIX105':{'label':'B — STIX 105%','math_scale':1.05,'family':'current'},
 'C_STIX108':{'label':'C — STIX 108%','math_scale':1.08,'family':'current'},
 'D_STIX_FAMILY':{'label':'D — COMPLETE STIX FAMILY','math_scale':1.0,'family':'D'},
 'E_LIBERTINUS':{'label':'E — LIBERTINUS FAMILY','math_scale':1.0,'family':'E'},
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def environment():
    env=os.environ.copy()
    env.update({'FONTCONFIG_FILE':str(RUNTIME/'fontconfig.xml'),
      'OSFONTDIR':str(RUNTIME/'fonts')+':'+str(ROOT/'fonts/installed'),
      'TEXMFHOME':str(RUNTIME/'texmf'),'TEXMFVAR':str(RUNTIME/'texmf-var'),
      'TEXMFCONFIG':str(RUNTIME/'texmf-config'),'XDG_CACHE_HOME':str(RUNTIME/'cache'),
      'TEXMFCACHE':str(RUNTIME/'cache/texmf'),'TMPDIR':str(RUNTIME/'tmp'),
      'TMP':str(RUNTIME/'tmp'),'TEMP':str(RUNTIME/'tmp'),
      'TEXINPUTS':str(ROOT/'source')+'//:'+str(ROOT/'content')+'//:',
      'PYTHONDONTWRITEBYTECODE':'1'})
    return env

def prepare():
    assert (ROOT/'reports/BASELINE_TYPOGRAPHY.json').exists(), 'Record baseline before experiments'
    for d in ['pdf','build','variants','previews','runtime/tmp','runtime/cache/fontconfig']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    dirs=[RUNTIME/'fonts',ROOT/'fonts/installed',Path('/usr/share/fonts/truetype/dejavu')]
    xml='<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n<fontconfig>'
    xml+=''.join('<dir>'+escape(str(d))+'</dir>' for d in dirs if d.exists())
    xml+='<cachedir>'+escape(str(RUNTIME/'cache/fontconfig'))+'</cachedir></fontconfig>\n'
    (RUNTIME/'fontconfig.xml').write_text(xml)
    subprocess.run(['fc-cache','--force'],env=environment(),check=True,stdout=subprocess.DEVNULL)
    fm=json.loads((ROOT/'fonts/FONT_MANIFEST.json').read_text())
    mapping={'BodyFontName':'body_regular','BodyItalicFontName':'body_italic',
      'BodyBoldFontName':'body_bold','BodyBoldItalicFontName':'body_bold_italic',
      'HeadingFontName':'heading_regular','HeadingBoldFontName':'heading_bold',
      'HeadingItalicFontName':'heading_italic','HeadingBoldItalicFontName':'heading_bold_italic',
      'BookMediumFontName':'medium_labels'}
    bodysha=sha(ROOT/'content/common-body.tex')
    for name,v in VARIANTS.items():
        dest=ROOT/'variants'/name;dest.mkdir(exist_ok=True)
        (dest/'config').mkdir(exist_ok=True)
        shutil.copy2(ROOT/'source/config/book-config.tex',dest/'config/book-config.tex')
        overrides=['% Experimental only; source stable config is unchanged.']
        if v['family']!='current':
            rec=fm['recommendations'][v['family']]
            for macro,role in mapping.items():
                file=ROOT/'fonts/installed'/rec[role]
                assert file.exists(),file
                overrides.append('\\renewcommand{\\'+macro+'}{'+file.name+'}')
            mathfile=ROOT/'fonts/installed'/rec['math'] if v['family']=='E' else RUNTIME/'fonts/STIXTwoMath-Regular.ttf'
            overrides.append('\\renewcommand{\\MathFontName}{'+mathfile.name+'}')
        (dest/'typography-overrides.tex').write_text('\n'.join(overrides)+'\n')
        for profile in ['SCREEN','PRINT']:
            flag='true' if profile=='PRINT' else 'false'
            after=''
            if v['math_scale']!=1:
                after='\\setmathfont[Scale='+str(v['math_scale'])+']{'+'STIXTwoMath-Regular.ttf'+'}\n'
            text='\\documentclass[11pt,twoside,openright]{book}\n\\input{config/book-config.tex}\n\\input{typography-overrides.tex}\n'
            text+='\\newif\\ifBookTwoInkProof\\BookTwoInkProof'+flag+'\n\\newif\\ifPrintThreeInk\\PrintThreeInkfalse\n'
            text+='\\usepackage{styles/universalbook}\n'+after+'\\begin{document}\n\\input{common-body.tex}\n\\end{document}\n'
            (dest/(profile.lower()+'.tex')).write_text(text)
        v.update({'nominal_text_pt':10.95,'applied_text_scale':1.0,'content_sha256':bodysha,
                  'override_file':str(dest/'typography-overrides.tex')})
    (ROOT/'VARIANT_MANIFEST.json').write_text(json.dumps({'stable_version':'1.0.10','page_mm':[170,240],'variants':VARIANTS,'source_content':str(ROOT/'content/common-body.tex'),'content_sha256':bodysha,'D_E_optical_adjustment':'none; same nominal sizes; x-height difference recorded separately'},ensure_ascii=False,indent=2)+'\n')

def build(name,profile):
    dest=ROOT/'variants'/name
    out=ROOT/'build'/(name+'_'+profile);out.mkdir(exist_ok=True)
    for folder in ['chapters','solutions']:(out/folder).mkdir(exist_ok=True)
    command=['latexmk','-xelatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-e','$max_repeat = 8;','-outdir='+str(out),'-jobname='+name+'_'+profile,profile.lower()+'.tex']
    log=out/'driver.log'
    with log.open('w') as f:
        r=subprocess.run(command,cwd=dest,env=environment(),stdout=f,stderr=subprocess.STDOUT)
    if r.returncode:
        print('FAILED',name,profile,log,flush=True)
        return {'variant':name,'profile':profile,'status':'failed','log':str(log)}
    pdf=out/(name+'_'+profile+'.pdf')
    output=ROOT/'pdf'/pdf.name;shutil.copy2(pdf,output)
    print('BUILT',name,profile,output.stat().st_size,flush=True)
    return {'variant':name,'profile':profile,'status':'passed','log':str(log),'pdf':str(output),'sha256':sha(output)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--only',nargs='*');p.add_argument('--jobs',type=int,default=2);a=p.parse_args()
    prepare()
    names=a.only or list(VARIANTS)
    work=[(n,e) for n in names for e in ['SCREEN','PRINT']]
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:rows=list(pool.map(lambda x:build(*x),work))
    (ROOT/'BUILD_RESULTS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return 0 if all(r['status']=='passed' for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())

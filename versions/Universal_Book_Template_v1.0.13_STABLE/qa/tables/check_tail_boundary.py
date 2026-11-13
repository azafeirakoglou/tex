#!/usr/bin/env python3
"""Regression: every longtable data page retains its header at tail boundaries."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib, importlib.util, json, re, subprocess, sys
import fitz
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('table_boundary_build',ROOT/'build_stable.py')
BUILD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(BUILD)
sys.dont_write_bytecode=True
BASE=(HERE/'table-caption-probe.tex').read_text()
BODY=re.compile(r'ROW001 .*?ROW120[^\n]*\n',re.S)

def compile_one(case):
    n,plain,negative=case
    label=('plain' if plain else 'striped')+'-'+str(n)+('-negative-old-feet' if negative else '')
    out=ROOT/'runtime/tmp/table-tail-boundaries'/label;out.mkdir(parents=True,exist_ok=True)
    rows=''.join(f'ROW{i:03} & $x_{{{i}}}$ & $\\mathrm{{m/s}}$ \\\\\n' for i in range(1,n+1))
    code=BODY.sub(lambda _:rows,BASE)
    if plain:code=code.replace('{BookLongTable}','{BookLongPlainTable}')
    if negative:
        patch=r'\makeatletter\patchcmd{\BookLongTableStart}{\endhead}{\endhead\endfoot\endlastfoot}{}{\errmessage{REGRESSION PATCH FAILED}}\makeatother'
        code=code.replace(r'\begin{document}',patch+'\n'+r'\begin{document}')
    tex=out/'boundary.tex';tex.write_text(code)
    env=BUILD.environment();env['TEXINPUTS']=str(BUILD.SOURCE)+'//:'
    for number in (1,2):
        with (out/f'pass{number}.stdout').open('w') as log:
            proc=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-output-directory='+str(out),str(tex)],cwd=BUILD.SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT)
        if proc.returncode:return {'case':label,'status':'compile_failed','exit_code':proc.returncode}
    pdf=out/'boundary.pdf'
    with fitz.open(pdf) as doc:
        text='\n'.join(p.get_text() for p in doc)
        extracted=[int(x) for x in re.findall(r'\bROW(\d{3})\b',text)]
        data=[{'page':i+1,'row_count':len(re.findall(r'\bROW\d{3}\b',p.get_text())),
               'header_count':p.get_text().count('LONGHEADER')} for i,p in enumerate(doc) if re.search(r'\bROW\d{3}\b',p.get_text())]
        intact=extracted==list(range(1,n+1))
        repeated=all(p['header_count']==1 for p in data)
        expected=(intact and not repeated) if negative else (intact and repeated)
        return {'case':label,'status':'passed' if expected else 'failed','row_count':n,
                'plain':plain,'negative_control':negative,'all_rows_once_in_order':intact,
                'all_data_pages_repeat_header':repeated,'pages':len(doc),'data_pages':data,
                'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                'scope':'Synthetic row-count boundary sweep; no author content or dimensions modified.'}

def main():
    cases=[(n,False,False) for n in (118,119,120,121,122,149,150,151)]
    cases += [(120,True,False),(121,True,False),(120,False,True)]
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(compile_one,cases))
    report={'status':'passed' if all(r['status']=='passed' for r in rows) else 'failed',
            'source_file':'source/styles/book-longtables.tex',
            'source_sha256':hashlib.sha256((BUILD.SOURCE/'styles/book-longtables.tex').read_bytes()).hexdigest(),
            'cases':rows,'method':'Default page geometry/fonts; striped/plain boundaries plus mutation restoring the old empty foot blocks.'}
    (HERE/'TAIL_BOUNDARY_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'].upper())
    for row in rows:print(row['case'],row['status'],row.get('all_data_pages_repeat_header'))
    return int(report['status']!='passed')
if __name__=='__main__':raise SystemExit(main())

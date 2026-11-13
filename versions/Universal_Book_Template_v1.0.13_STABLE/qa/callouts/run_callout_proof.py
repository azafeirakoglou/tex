#!/usr/bin/env python3
"""Compile isolated short and long teaching-callout proofs against final source."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib, importlib.util, json, re, subprocess, sys
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_stable', ROOT/'build_stable.py')
build = importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
D = ROOT/'qa/callouts'

def make_content():
    lines=[r'\pagestyle{empty}',r'\noindent{\BookHeadingFont\fontsize{15}{19}\selectfont CALL OUT PROOF}\par\medskip',
           r'\begin{ThinkBox}SHORTTHINK Επιλέγω τον κατάλληλο ορισμό και ελέγχω τις μονάδες του αποτελέσματος.\end{ThinkBox}',
           r'\begin{AttentionBox}SHORTATTENTION Προσέχω το πρόσημο της μεταβολής.\end{AttentionBox}',
           r'\begin{HistoryBox}[Ιστορική πηγή]SHORTHISTORY Μία σύντομη ιστορική παρατήρηση με τεκμηριωμένη πηγή.\par\smallskip{\color{BookHistory}\fontsize{8.3}{11}\selectfont Πηγή: δοκίμιο ελέγχου, όχι νέο κεφάλαιο.}\end{HistoryBox}']
    for env,marker in [('ThinkBox','THINK'),('AttentionBox','ATTENTION'),('HistoryBox','HISTORY')]:
        lines += [r'\clearpage',r'\begin{'+env+('}[Μεγάλο ιστορικό ένθετο]' if env=='HistoryBox' else '}')]
        for n in range(1,37):
            lines += [f'{marker}-{n:02d} '+r'Ελέγχω ότι η παράγραφος παραμένει μέσα στο διδακτικό ένθετο με σαφή περιθώρια, χωρίς περίγραμμα επάνω, κάτω ή δεξιά. Η αριστερή λεπτή γραμμή συνεχίζεται σωστά στην επόμενη σελίδα και δεν επαναλαμβάνεται το εικονίδιο.\par']
            if n%9==0:lines += [r'\[\Delta x=x_B-x_A,\qquad v=\frac{\Delta x}{\Delta t}.\]']
        lines += [r'\end{'+env+'}']
    return '\n'.join(lines)+'\n'


def compile_profile(profile):
    out=D/profile;out.mkdir(exist_ok=True)
    p=D/('callouts-'+profile.lower()+'.tex')
    tex='\n'.join([r'\documentclass[11pt,twoside,openright]{book}',r'\input{config/book-config.tex}',r'\newif\ifBookTwoInkProof\BookTwoInkProof'+('true' if profile=='PRINT' else 'false'),r'\newif\ifPrintThreeInk\PrintThreeInkfalse',r'\usepackage{styles/universalbook}',r'\begin{document}',r'\input{'+str(D/'callout-content.tex')+'}',r'\end{document}'])+'\n'
    p.write_text(tex)
    job='callout-proof-'+profile.lower();env=build.environment();env['TEXINPUTS']=str(build.SOURCE)+'//:'
    commands=[]
    for n in range(2):
        log=out/f'{job}.pass{n+1}.stdout'
        with log.open('w') as stream:
            r=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error','-file-line-error','-output-directory='+str(out),'-jobname='+job,str(p)],cwd=build.SOURCE,env=env,stdout=stream,stderr=subprocess.STDOUT)
        commands.append(r.returncode)
        if r.returncode:break
    pdf=out/(job+'.pdf');log=(out/(job+'.log')).read_text(errors='replace')
    diag={k:len(re.findall(v,log)) for k,v in [('overfull',r'Overfull \\[hv]box'),('underfull',r'Underfull \\[hv]box'),('missing',r'Missing character:'),('warning',r'Warning:')]}
    row={'profile':profile,'pdf':str(pdf.relative_to(ROOT)),'status':'passed' if commands==[0,0] and not any(diag[k] for k in ['overfull','underfull','missing']) else 'failed','runs':commands,'diagnostics':diag,'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.exists() else None}
    print(profile,row['status'],diag,flush=True);return row

if __name__=='__main__':
    D.mkdir(exist_ok=True);(D/'callout-content.tex').write_text(make_content())
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(compile_profile,['SCREEN','PRINT']))
    (D/'BUILD_RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
    raise SystemExit(any(r['status']!='passed' for r in rows))

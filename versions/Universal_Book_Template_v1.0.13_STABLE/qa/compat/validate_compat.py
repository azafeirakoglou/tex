#!/usr/bin/env python3
"""Preflight all nonmain author pairs and inspect real stress pagination."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import importlib.util,json,subprocess,sys,time,re
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('candidate_driver',ROOT/'qa/driver.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
PAIRS=[('sample','Sample_Collaborators_Print_Technical','Sample_Collaborators_Blue'),('figures','Book_Figures_Print_Technical','Book_Figures_Screen'),('assessment','Book_Assessment_Print_Technical','Book_Assessment_Screen'),('tables','Book_Tables_Print_Technical','Book_Tables_Screen'),('opening-goals','Book_Opening_Goals_Print','Book_Opening_Goals_Screen'),('history-statements','Book_History_Statements_Print','Book_History_Statements_Screen'),('callouts','Book_Callouts_Print_Technical','Book_Callouts_Screen'),('palette','Book_Palette_v026_Print','Book_Palette_v026_Screen'),('starter','Starter_Print','Starter_Screen'),('stress','Stress_Print','Stress_Screen')]
OUT=ROOT/'qa/compat'
def validate(work):
 design,info=work;kind,pjob,sjob=info;src=d.source(design);folder=OUT/design
 printed=src/'build'/(kind+'-print2')/(pjob+'.pdf');screen=src/'build'/(kind+'-screen')/(sjob+'.pdf')
 report=folder/(kind+'.preflight.json');log=folder/(kind+'.preflight.log');start=time.monotonic()
 with log.open('w') as f:r=subprocess.run([sys.executable,'-B','scripts/validate_pdf.py','--print',str(printed),'--screen',str(screen),'--map',str(src/'config/color-map.json'),'--report',str(report),'--dpi','72'],cwd=src,env=d.environment(src),stdout=f,stderr=subprocess.STDOUT)
 row={'design':design,'pair':kind,'exit_code':r.returncode,'elapsed_seconds':round(time.monotonic()-start,2),'report':str(report.relative_to(ROOT))}
 if kind=='stress':
  stressreport=folder/'stress.structure.json'
  with (folder/'stress.structure.log').open('w') as f:r2=subprocess.run([sys.executable,'-B','scripts/check_stress.py','--print',str(printed),'--screen',str(screen),'--report',str(stressreport)],cwd=src,env=d.environment(src),stdout=f,stderr=subprocess.STDOUT)
  row['stress_structure_exit_code']=r2.returncode;row['stress_structure_report']=str(stressreport.relative_to(ROOT))
 print(json.dumps(row),flush=True);return row
work=[(design,p) for design in d.DESIGNS for p in PAIRS]
previous=[]
if '--failed-only' in sys.argv:
 previous=json.loads((OUT/'PREFLIGHT_RESULTS.json').read_text())
 failed={(r['design'],r['pair']) for r in previous if r['exit_code'] or r.get('stress_structure_exit_code',0)}
 work=[(design,p) for design,p in work if (design,p[0]) in failed]
with ThreadPoolExecutor(max_workers=2) as pool:rerun=list(pool.map(validate,work))
updated={(r['design'],r['pair']):r for r in previous+rerun}
rows=[updated[(design,p[0])] for design in d.DESIGNS for p in PAIRS]
(OUT/'PREFLIGHT_RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PREFLIGHTS COMPLETE',sum(r['exit_code']==0 for r in rows),'/',len(rows),flush=True)
raise SystemExit(any(r['exit_code'] or r.get('stress_structure_exit_code',0) for r in rows))

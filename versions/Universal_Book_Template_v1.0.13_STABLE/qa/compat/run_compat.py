#!/usr/bin/env python3
"""Compile shipped author fixtures from independent candidates, no stable writes."""
from pathlib import Path
import importlib.util,json,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('candidate_driver',ROOT/'qa/driver.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
PAIRS=[('sample-print2','sample-screen'),('figures-print2','figures-screen'),('assessment-print2','assessment-screen'),('tables-print2','tables-screen'),('opening-goals-print2','opening-goals-screen'),('history-statements-print2','history-statements-screen'),('callouts-print2','callouts-screen'),('palette-print2','palette-screen'),('starter-print2','starter-screen'),('stress-print2','stress-screen')]
OUT=ROOT/'qa/compat'
def build(work):
 design,target=work;src=driver.source(design);folder=OUT/design;folder.mkdir(exist_ok=True)
 logfile=folder/(target+'.build.log');start=time.monotonic()
 with logfile.open('w') as f:
  r=subprocess.run([sys.executable,'-B','scripts/build.py',target],cwd=src,env=driver.environment(src),stdout=f,stderr=subprocess.STDOUT)
 row={'design':design,'target':target,'exit_code':r.returncode,'elapsed_seconds':round(time.monotonic()-start,2),'log':str(logfile.relative_to(ROOT))}
 print(json.dumps(row),flush=True);return row
work=[(d,t) for d in driver.DESIGNS for pair in PAIRS for t in pair]
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(build,work))
(OUT/'BUILD_RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
print('BUILDS COMPLETE',sum(r['exit_code']==0 for r in rows),'/',len(rows),flush=True)
raise SystemExit(any(r['exit_code'] for r in rows))

#!/usr/bin/env python3
"""Verify every plate, font and paired position in both A/B example proofs."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import build_stable as driver


def run(v):
    out=ROOT/'qa/probes/examples-results';out.mkdir(exist_ok=True)
    report=out/(v+'.preflight.json');log=out/(v+'.preflight.log')
    with log.open('w') as stream:
        result=subprocess.run([sys.executable,str(driver.SOURCE/'scripts/validate_pdf.py'),
            '--print',str(ROOT/'qa/probes/pdf'/('EXAMPLES_'+v+'_PRINT.pdf')),
            '--screen',str(ROOT/'qa/probes/pdf'/('EXAMPLES_'+v+'_SCREEN.pdf')),
            '--map',str(driver.SOURCE/'config/color-map.json'),'--report',str(report),'--dpi','72'],
            cwd=driver.SOURCE,env=driver.environment(),stdout=stream,stderr=subprocess.STDOUT)
    return {'variant':v,'exit_code':result.returncode,'report':str(report.relative_to(ROOT))}


if __name__=='__main__':
    rows=list(ThreadPoolExecutor(max_workers=2).map(run,['A','B']))
    (ROOT/'qa/probes/EXAMPLES_PREFLIGHT_RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(rows);raise SystemExit(any(r['exit_code'] for r in rows))

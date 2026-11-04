#!/usr/bin/env python3
"""Optional reproduction setup, confined to this review directory."""
from pathlib import Path
import os,sys,subprocess
ROOT=Path(__file__).resolve().parent
os.environ['TMPDIR']=str(ROOT/'runtime/tmp')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
from run_review import prepare,environment
prepare()
log=ROOT/'runtime/format-setup.log'
with log.open('w') as f:
    subprocess.run(['fmtutil-user','--byfmt','xelatex','--quiet'],env=environment(),stdout=f,stderr=subprocess.STDOUT,check=True)
fmt=ROOT/'runtime/texmf-var/web2c/xetex/xelatex.fmt'
assert fmt.is_file(),fmt
print('Independent fontconfig, Greek format and variant entrypoints prepared:',fmt)

#!/usr/bin/env python3
"""Validate all main PRINT/SCREEN pages using the source two-ink preflight."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import build_stable as b


def main():
    out=ROOT/'qa/main';out.mkdir(exist_ok=True)
    with (out/'PREFLIGHT.log').open('w') as stream:
        result=subprocess.run([sys.executable,str(b.SOURCE/'scripts/validate_pdf.py'),
            '--print',str(ROOT/'pdf/Universal_Book_Template_v1.0.12_PRINT.pdf'),
            '--screen',str(ROOT/'pdf/Universal_Book_Template_v1.0.12_SCREEN.pdf'),
            '--map',str(b.SOURCE/'config/color-map.json'),
            '--report',str(out/'PREFLIGHT.json'),'--dpi','72'],
            cwd=b.SOURCE,env=b.environment(),stdout=stream,stderr=subprocess.STDOUT)
    print('Main paired preflight:', 'PASS' if result.returncode==0 else 'FAIL')
    return result.returncode


if __name__=='__main__':raise SystemExit(main())

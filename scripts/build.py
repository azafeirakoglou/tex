#!/usr/bin/env python3
"""Build one edition with its own aux tree, using latexmk convergence."""
from pathlib import Path
import argparse
import subprocess
import sys
from setup_environment import ROOT, LOCAL, runtime_env

# Existing public target names remain valid. Every target has an isolated output tree.
TARGETS = {
    'print2': ('main-print2.tex', 'Physics_A_Print_Technical', 'print'),
    'screen': ('main.tex', 'Physics_A_Screen', 'screen'),
    'sample-screen': ('collab-screen.tex', 'Sample_Collaborators_Blue', 'sample-screen'),
    'sample-print2': ('collab-print2.tex', 'Sample_Collaborators_Print_Technical', 'sample-print2'),
    'figures-screen': ('figures-guide-screen.tex', 'Book_Figures_Screen', 'figures-screen'),
    'figures-print2': ('figures-guide-print2.tex', 'Book_Figures_Print_Technical', 'figures-print2'),
    'assessment-screen': ('assessment-demo-screen.tex', 'Book_Assessment_Screen', 'assessment-screen'),
    'assessment-print2': ('assessment-demo-print2.tex', 'Book_Assessment_Print_Technical', 'assessment-print2'),
    'tables-screen': ('tables-demo-screen.tex', 'Book_Tables_Screen', 'tables-screen'),
    'tables-print2': ('tables-demo-print2.tex', 'Book_Tables_Print_Technical', 'tables-print2'),
    'opening-goals-screen': ('opening-goals-test-screen.tex', 'Book_Opening_Goals_Screen', 'opening-goals-screen'),
    'opening-goals-print2': ('opening-goals-test-print2.tex', 'Book_Opening_Goals_Print', 'opening-goals-print2'),
    'history-statements-screen': ('history-statements-screen.tex', 'Book_History_Statements_Screen', 'history-statements-screen'),
    'history-statements-print2': ('history-statements-print2.tex', 'Book_History_Statements_Print', 'history-statements-print2'),
    'callouts-screen': ('callouts-v025-screen.tex', 'Book_Callouts_Screen', 'callouts-screen'),
    'callouts-print2': ('callouts-v025-print2.tex', 'Book_Callouts_Print_Technical', 'callouts-print2'),
    'palette-screen': ('palette-v026-screen.tex', 'Book_Palette_v026_Screen', 'palette-screen'),
    'palette-print2': ('palette-v026-print2.tex', 'Book_Palette_v026_Print', 'palette-print2'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=TARGETS)
    args = parser.parse_args()
    if not (LOCAL / 'fontconfig.xml').exists():
        parser.error('Dependencies not prepared: run make setup first')
    source, jobname, directory = TARGETS[args.target]
    output = ROOT / 'build' / directory
    output.mkdir(parents=True, exist_ok=True)
    # XeTeX cannot create the include-aux directories itself.
    for folder in ['chapters', 'solutions']:
        (output / folder).mkdir(exist_ok=True)
    command = ['latexmk', '-xelatex', '-interaction=nonstopmode', '-halt-on-error',
               '-file-line-error', '-synctex=1', '-e', '$max_repeat = 8;',
               '-outdir=' + str(output), '-jobname=' + jobname, source]
    return subprocess.run(command, cwd=ROOT, env=runtime_env()).returncode


if __name__ == '__main__':
    sys.exit(main())

"""Actual PDF links remain distinct when worksheet exercise numbers restart."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import fitz

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('exercise_setup', ROOT / 'scripts/setup_environment.py')
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)

SOURCE = r'''
\documentclass[11pt,twoside,openright]{book}
\input{config/book-config.tex}
\newif\ifBookTwoInkProof\BookTwoInkProoffalse
\newif\ifPrintThreeInk\PrintThreeInkfalse
\usepackage{styles/universalbook}
\begin{document}
\setcounter{chapter}{1}\chaptermark{Fixture}
\begin{exercise}[linkfirst]{}FIRSTEXERCISE\end{exercise}
\WorksheetOpening{Fixture}{First worksheet}
\begin{exercise}[linksecond]{}SECONDEXERCISE\end{exercise}
\WorksheetOpening{Fixture}{Second worksheet}
\begin{exercise}[linkthird]{}THIRDEXERCISE\end{exercise}
\clearpage
\hyperref[ex:linkfirst]{FIRSTREF}\par
\hyperref[ex:linksecond]{SECONDREF}\par
\hyperref[ex:linkthird]{THIRDREF}\par
\end{document}
'''


@unittest.skipUnless(shutil.which('xelatex'), 'XeLaTeX is required')
class ExerciseLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / '.local/fontconfig.xml').exists():
            raise unittest.SkipTest('Run make setup first')
        cls.temp = tempfile.TemporaryDirectory(prefix='book-exercise-links-')
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        source = folder / 'links.tex'
        source.write_text(SOURCE)
        command = ['xelatex', '-interaction=nonstopmode', '-halt-on-error',
                   '-no-shell-escape', f'-output-directory={folder}', str(source)]
        for _ in range(2):
            result = subprocess.run(command, cwd=ROOT, env=SETUP.runtime_env(),
                                    capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError((result.stdout + result.stderr)[-6000:])
        cls.log = result.stdout + result.stderr
        cls.pdf = fitz.open(folder / 'links.pdf')
        cls.addClassCleanup(cls.pdf.close)

    def test_driver_has_no_duplicate_destination_warning(self):
        self.assertNotIn('already defined', self.log)
        self.assertNotIn('duplicate destination', self.log.lower())

    def test_each_reference_targets_its_own_restarted_exercise(self):
        references = self.pdf[-1]
        for reference, body in [('FIRSTREF', 'FIRSTEXERCISE'),
                                ('SECONDREF', 'SECONDEXERCISE'),
                                ('THIRDREF', 'THIRDEXERCISE')]:
            with self.subTest(reference=reference):
                expected = next(i for i, page in enumerate(self.pdf) if body in page.get_text())
                areas = references.search_for(reference)
                self.assertEqual(len(areas), 1)
                links = [link for link in references.get_links()
                         if fitz.Rect(link['from']).intersects(areas[0])]
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0]['page'], expected)
                # Each printed exercise still starts at 1 after each reset.
                self.assertIn('1', self.pdf[expected].get_text().split())


if __name__ == '__main__':
    unittest.main()

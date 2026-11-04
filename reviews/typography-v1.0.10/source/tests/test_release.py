"""Reject stale release evidence and verify the actual exported source archive."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release
import export_review


TARGETS = {'print2': ('main-print2.tex', 'BookPrint', 'print'),
           'screen': ('main.tex', 'BookScreen', 'screen')}
PAIRS = [('print2', 'screen')]


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='book-release-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source'
        self.root.mkdir()
        (self.root / 'config').mkdir()
        (self.root / 'config/color-map.json').write_text('{"version":"1.0.0"}\n')
        (self.root / 'main.tex').write_text('Authoring source\n')
        (self.root / 'main-print2.tex').write_text('Print authoring source\n')
        for target in TARGETS:
            path = release.pdf_path(self.root, target, TARGETS)
            path.parent.mkdir(parents=True)
            with fitz.open() as pdf:
                page = pdf.new_page(width=170 * 72 / 25.4, height=240 * 72 / 25.4)
                page.insert_text((40, 80), 'Stable source export')
                pdf.save(path)
        self.folder = self.root / 'build/release-checks/test'
        self.folder.mkdir(parents=True)
        self.manifest_path = self.root / 'build/release-manifest.json'
        self.palette = release.palette_hash(self.root)
        self.source_hash = release.source_fingerprint(self.root)
        self.test_path = self.folder / 'tests.json'
        release.write_json(self.test_path, {'status': 'passed', 'tests': 2,
                                           'failures': 0, 'errors': 0, 'skipped': 0,
                                           'source_sha256': self.source_hash})
        self.pair_path = self.folder / 'print2.json'
        release.write_json(self.pair_path, {'status': 'passed', 'input_sha256': {
            'print': release.sha(release.pdf_path(self.root, 'print2', TARGETS)),
            'screen': release.sha(release.pdf_path(self.root, 'screen', TARGETS)),
            'palette': self.palette}})
        self.driver_path = self.folder / 'pdf-driver.json'
        release.write_json(self.driver_path, {'status': 'passed', 'unexpected_warnings': []})
        self.summary_path = self.folder / 'summary.json'
        release.write_json(self.summary_path, [{'target': target, 'pages': 1, 'overfull': 0,
                                               'unresolved': [], 'missing_characters': []}
                                              for target in TARGETS])
        relative = lambda path: path.relative_to(self.root).as_posix()
        self.manifest = {'schema_version': 1, 'status': 'passed', 'version': '1.0.0',
                         'source_sha256': self.source_hash, 'palette_sha256': self.palette,
                         'targets': {target: {'pdf': relative(release.pdf_path(self.root, target, TARGETS)),
                                               'sha256': release.sha(release.pdf_path(self.root, target, TARGETS)),
                                               'pages': 1} for target in TARGETS},
                         'pairs': [{'print_target': 'print2', 'screen_target': 'screen',
                                    'exit_code': 0, 'report': relative(self.pair_path)}],
                         'reports': {relative(p): release.sha(p)
                                     for p in [self.test_path, self.pair_path, self.summary_path, self.driver_path]},
                         'test_report': relative(self.test_path),
                         'driver_report': relative(self.driver_path),
                         'build_summary': relative(self.summary_path),
                         'main_report': relative(self.pair_path)}
        self.save()

    def save(self):
        release.write_json(self.manifest_path, self.manifest)

    def validate(self):
        return release.validate_release_manifest(self.root, self.manifest_path,
                                                 targets=TARGETS, pairs=PAIRS)

    def refresh_report_hash(self, path):
        self.manifest['reports'][path.relative_to(self.root).as_posix()] = release.sha(path)
        self.save()

    def test_current_complete_evidence_passes_but_edited_source_fails(self):
        self.assertEqual(self.validate()['status'], 'passed')
        (self.root / 'main.tex').write_text('Changed after testing\n')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            self.validate()

    def test_changed_pdf_and_changed_report_are_rejected(self):
        path = release.pdf_path(self.root, 'screen', TARGETS)
        path.write_bytes(path.read_bytes() + b'\n% changed output\n')
        with self.assertRaisesRegex(ValueError, 'PDF changed'):
            self.validate()
        self.manifest['targets']['screen']['sha256'] = release.sha(path)
        self.save()
        # Updating only the top-level PDF hash cannot make old pair evidence fresh.
        with self.assertRaisesRegex(ValueError, 'preflight is failed or stale'):
            self.validate()

    def test_failed_preflight_is_rejected_even_when_its_hash_is_current(self):
        data = release.load_json(self.pair_path)
        data['status'] = 'failed'
        release.write_json(self.pair_path, data)
        self.refresh_report_hash(self.pair_path)
        with self.assertRaisesRegex(ValueError, 'preflight is failed or stale'):
            self.validate()

    def test_missing_pair_and_failed_or_skipped_tests_are_rejected(self):
        self.manifest['pairs'] = []
        self.save()
        with self.assertRaisesRegex(ValueError, 'every PDF pair'):
            self.validate()
        self.manifest['pairs'] = [{'print_target': 'print2', 'screen_target': 'screen',
                                   'exit_code': 0, 'report': self.pair_path.relative_to(self.root).as_posix()}]
        for status, errors, skipped in [('failed', 1, 0), ('passed', 0, 1)]:
            with self.subTest(status=status, skipped=skipped):
                release.write_json(self.test_path, {'status': status, 'tests': 2, 'failures': 0,
                                                   'errors': errors, 'skipped': skipped,
                                                   'source_sha256': self.source_hash})
                self.refresh_report_hash(self.test_path)
                with self.assertRaisesRegex(ValueError, 'full test suite'):
                    self.validate()

    def test_incomplete_or_overflowing_build_summary_is_rejected(self):
        summary = release.load_json(self.summary_path)
        summary[0]['overfull'] = 1
        release.write_json(self.summary_path, summary)
        self.refresh_report_hash(self.summary_path)
        with self.assertRaisesRegex(ValueError, 'layout/build error'):
            self.validate()
        release.write_json(self.summary_path, summary[:1])
        self.refresh_report_hash(self.summary_path)
        with self.assertRaisesRegex(ValueError, 'every target'):
            self.validate()

    def test_duplicate_destinations_and_unexpected_driver_warnings_are_rejected(self):
        for text in ('xdvipdfmx:warning: Ignoring duplicate destination exercise.1',
                     'xdvipdfmx:warning: Image could not be included'):
            driver = release.inspect_driver_output(text)
            self.assertEqual(driver['status'], 'failed')
            release.write_json(self.driver_path, driver)
            self.refresh_report_hash(self.driver_path)
            with self.assertRaisesRegex(ValueError, 'PDF driver'):
                self.validate()
        good = release.inspect_driver_output('xdvipdfmx:warning: Object \"Second\" already defined in dict! (ignored)')
        self.assertEqual(good['status'], 'passed')

    def test_changed_report_bytes_are_rejected_before_semantics(self):
        self.test_path.write_text(self.test_path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'report changed'):
            self.validate()


class SourceArchiveTests(unittest.TestCase):
    def test_archive_and_fingerprint_ignore_generated_and_private_files(self):
        with tempfile.TemporaryDirectory(prefix='book-source-archive-') as temp:
            root = Path(temp)
            (root / 'main.tex').write_text('Greek source: κίνηση\n', encoding='utf-8')
            (root / 'assets').mkdir()
            (root / 'assets/vector.tex').write_text('Vector source\n')
            (root / '.gitignore').write_text('build/\n')
            fingerprint = release.source_fingerprint(root)
            for relative in ['build/stale.json', 'releases/v0.1/nested.zip', '.local/fonts/font.otf',
                             '.venv/bin/python', '.git/config', '.env', 'main.fls', 'main.synctex.gz']:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('must not be shipped')
            self.assertEqual(release.source_fingerprint(root), fingerprint)
            archive = root / 'build/bundle.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
                names = export_review.write_source_archive(bundle, root)
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertEqual(set(names), {'source/main.tex', 'source/assets/vector.tex', 'source/.gitignore'})
                for name in names:
                    self.assertEqual(bundle.read(name), (root / Path(name).relative_to('source')).read_bytes())

    def test_proof_export_does_not_copy_stale_optional_reports(self):
        with tempfile.TemporaryDirectory(prefix='book-proof-export-') as temp:
            root = Path(temp) / 'source'
            root.mkdir()
            (root / 'config').mkdir()
            palette = {'version': '1.0.0'}
            (root / 'config/color-map.json').write_text(json.dumps(palette))
            (root / 'main.tex').write_text('Current source')
            # Use the actual public target paths that export_bundle resolves.
            for target in ('print2', 'screen'):
                path = export_review.pdf_path(root, target)
                path.parent.mkdir(parents=True)
                with fitz.open() as pdf:
                    pdf.new_page(width=200, height=300).insert_text((20, 50), 'Current proof')
                    pdf.save(path)
            validation = root / 'build/validation'
            validation.mkdir()
            release.write_json(validation / 'report.json', {'status': 'passed', 'input_sha256': {
                'print': release.sha(export_review.pdf_path(root, 'print2')),
                'screen': release.sha(export_review.pdf_path(root, 'screen')),
                'palette': hashlib.sha256(json.dumps(palette, sort_keys=True).encode()).hexdigest()}})
            (validation / 'old-failed-run.json').write_text('{"status":"failed"}')
            (root / 'build/build-summary.json').write_text('[{"stale":true}]')
            out = Path(temp) / 'download'
            exported = export_review.export_bundle(root, out)
            archive = next(path for path in exported if path.suffix == '.zip')
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertNotIn('build-summary.json', bundle.namelist())
                self.assertFalse(any('old-failed' in name for name in bundle.namelist()))
                self.assertEqual(bundle.read('source/main.tex'), b'Current source')
                self.assertIn('PROOF EXPORT', bundle.read('START_HERE.txt').decode())

    def test_output_cannot_become_its_own_source(self):
        root = Path('/tmp/example-template')
        with self.assertRaisesRegex(ValueError, 'output directory'):
            export_review.check_output_location(root, root / 'unexcluded-output')
        export_review.check_output_location(root, root / 'dist/review')
        export_review.check_output_location(root, Path('/tmp/another-output'))


if __name__ == '__main__':
    unittest.main()

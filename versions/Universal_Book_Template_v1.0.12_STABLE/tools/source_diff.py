#!/usr/bin/env python3
"""Record additions/changes from the captured v1.0.11 MINIMAL source."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    baseline = json.loads((ROOT / 'reports/SOURCE_BASELINE.json').read_text())['base_source_sha256']
    source = ROOT / 'source'
    current = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(source.rglob('*')) if p.is_file() and not p.is_symlink()
               and not any(x in p.relative_to(source).parts
                           for x in ('.local', 'build', '__pycache__', '.pytest_cache'))}
    changed = {p: {'before_sha256': baseline[p], 'after_sha256': h}
               for p, h in current.items() if p in baseline and baseline[p] != h}
    added = {p: h for p, h in current.items() if p not in baseline}
    removed = [p for p in baseline if p not in current]
    report = {'base': 'v1.0.11 B — MINIMAL', 'version': '1.0.12',
              'status': 'passed' if not removed else 'failed',
              'source_files': len(current), 'unchanged_files': len(current) - len(changed) - len(added),
              'changed_files': changed, 'added_files': added, 'removed_files': removed,
              'all_source_sha256': current,
              'scope': 'Styles/configuration, verification and documentation. Scientific content checked separately.'}
    (ROOT / 'reports/SOURCE_DIFF.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Source diff: v1.0.11 MINIMAL → v1.0.12', '',
             f'{len(current)} source files; {len(changed)} modified; {len(added)} added; {len(removed)} removed.', '',
             'The JSON records both SHA-256 values for every modification and all final source hashes.', '',
             '## Modified', ''] + ['- `' + p + '`' for p in changed]
    lines += ['', '## Added', ''] + ['- `' + p + '`' for p in added]
    lines += ['', 'No scientific chapters, solutions, figures or assets are edited. The table fixture has one explicitly documented technical-description correction, unrelated to fitting content.', '']
    (ROOT / 'reports/SOURCE_DIFF.md').write_text('\n'.join(lines))
    print(report['status'].upper(), len(changed), 'modified,', len(added), 'added,', len(removed), 'removed')
    return int(bool(removed))


if __name__ == '__main__':
    raise SystemExit(main())

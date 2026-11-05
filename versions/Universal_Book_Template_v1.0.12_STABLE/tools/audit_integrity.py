#!/usr/bin/env python3
"""Audit protected originals and unchanged scientific content without editing them."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((ROOT / 'reports/SOURCE_BASELINE.json').read_text())
    changed_originals = [name for name, expected in baseline['protected_files'].items()
                         if not Path(name).is_file() or digest(Path(name)) != expected]
    source = ROOT / 'source'
    changed_content = []
    checked_content = []
    for name, expected in baseline['base_source_sha256'].items():
        if (name.startswith(('chapters/', 'solutions/', 'assets/')) or
                name in ('book-content.tex', 'main.tex', 'main-print2.tex')):
            checked_content.append(name)
            if not (source / name).is_file() or digest(source / name) != expected:
                changed_content.append(name)
    palette = {name: digest(source / 'config' / name) ==
               baseline['base_source_sha256']['config/' + name]
               for name in ('palette-print2-spot.tex', 'palette-screen.tex', 'color-roles.tex')}
    repo = baseline['repository']
    def git(*args):
        return subprocess.check_output(['git', '-C', repo, *args], text=True).strip()
    git_state = {'head': git('rev-parse', 'HEAD'), 'branch': git('branch', '--show-current'),
                 'tracked_status': git('status', '--porcelain', '--untracked-files=no'),
                 'full_status': git('status', '--porcelain')}
    checks = {'protected_original_files_unchanged': not changed_originals,
              'all_scientific_content_and_assets_unchanged': not changed_content,
              'palette_and_existing_roles_byte_identical': all(palette.values()),
              'original_git_head_unchanged': git_state['head'] == baseline['head'],
              'original_git_branch_unchanged': git_state['branch'] == baseline['branch'],
              'original_tracked_git_files_unchanged': not git_state['tracked_status']}
    report = {'status': 'passed' if all(checks.values()) else 'failed',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'protected_file_count': len(baseline['protected_files']),
              'checks': checks, 'git': git_state, 'palette_files': palette,
              'changed_original_files': changed_originals,
              'changed_content_files': changed_content, 'checked_content_files': checked_content,
              'scope': 'Original versions remain read-only; only the new v1.0.12 version directory may be untracked.'}
    (ROOT / 'reports/ORIGINAL_INTEGRITY.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(report['status'].upper(), report['protected_file_count'], 'protected files;',
          len(checked_content), 'unchanged content/asset files')
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())

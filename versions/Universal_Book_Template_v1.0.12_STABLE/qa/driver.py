"""Isolated A/B QA views of the single v1.0.12 source, never old releases."""
from pathlib import Path
import importlib.util
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('stable_driver', ROOT / 'build_stable.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
DESIGNS = ['A', 'B']


def source(design):
    return ROOT / 'qa/work' / design / 'source'


def environment(src):
    return build.environment(src)


def prepare():
    for design in DESIGNS:
        destination = source(design)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(build.SOURCE, destination,
                        ignore=shutil.ignore_patterns('.local', 'build', '__pycache__', '.pytest_cache'))
        config = destination / 'config/stable-config.tex'
        text = config.read_text()
        old = r'\providecommand{\BookExampleHeaderVariant}{A}'
        assert text.count(old) == 1, 'The canonical source must retain explicit default A'
        config.write_text(text.replace(old, r'\providecommand{\BookExampleHeaderVariant}{' + design + '}'))
        build.prepare_source(destination)


if __name__ == '__main__':
    prepare()

"""Test helpers.

``src/__init__.py`` imports ``aqt`` and can only run inside Anki, so the
Anki-free modules under ``src/`` are loaded directly from their file instead of
importing ``src`` as a package.
"""

import importlib.util
import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


def load(module_name):
    spec = importlib.util.spec_from_file_location(
        "sentence_adder_" + module_name, SRC / (module_name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

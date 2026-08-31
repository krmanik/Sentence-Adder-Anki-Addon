"""Test helpers.

``src/__init__.py`` imports ``aqt`` and can only run inside Anki, so the
modules under ``src/`` are loaded directly from their files:

* ``load()`` for the modules that import nothing from Anki.
* ``load_addon_module()`` for ``editor``/``batch_edit``, which need fake Anki
  modules in place and relative imports that resolve.
"""

import importlib.util
import pathlib
import sys
import types

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
PACKAGE = "sentence_adder_addon"


def load(module_name):
    spec = importlib.util.spec_from_file_location(
        "sentence_adder_" + module_name, SRC / (module_name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package():
    """Register ``src`` as a package without running its ``__init__``."""
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(SRC)]
        sys.modules[PACKAGE] = package
    return sys.modules[PACKAGE]


def load_addon_module(module_name):
    """Import ``src/<module_name>.py`` with its relative imports working."""
    _ensure_package()
    full_name = "%s.%s" % (PACKAGE, module_name)
    sys.modules.pop(full_name, None)
    spec = importlib.util.spec_from_file_location(
        full_name, SRC / (module_name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module

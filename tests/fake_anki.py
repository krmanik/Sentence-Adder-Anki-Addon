"""Minimal stand-ins for the Anki modules the add-on imports.

``editor.py`` and ``batch_edit.py`` are the files users actually hit bugs in,
so they are tested for real; only the Qt/Anki surface they touch at import time
is faked.  Note handling in the tests uses a real ``anki`` collection.
"""

import sys
import types


class _Meta(type):
    def __getattr__(cls, name):
        return _Anything


class _Anything(metaclass=_Meta):
    """Stands in for any Qt class, enum or helper the add-on refers to."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *args, **kwargs):
        return _Anything()


class Recorder:
    """Collects the messages the add-on would show the user."""

    def __init__(self):
        self.tooltips = []
        self.hooks = {}

    def tooltip(self, text, *args, **kwargs):
        self.tooltips.append(text)

    def addHook(self, name, func):
        self.hooks.setdefault(name, []).append(func)

    @property
    def last_tooltip(self):
        return self.tooltips[-1] if self.tooltips else None


class FakeCollectionOp:
    """Runs the operation straight away instead of on a background thread."""

    collection = None
    last = None

    def __init__(self, parent=None, op=None):
        self.parent = parent
        self.op = op
        self.on_success = None
        self.on_failure = None
        FakeCollectionOp.last = self

    def success(self, callback):
        self.on_success = callback
        return self

    def failure(self, callback):
        self.on_failure = callback
        return self

    def run_in_background(self):
        result = self.op(FakeCollectionOp.collection)
        if self.on_success:
            self.on_success(result)
        return result


def install(recorder=None):
    """Put the fake modules in ``sys.modules`` and return the recorder."""
    recorder = recorder or Recorder()

    def module(name, **attrs):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
        return mod

    qt = module("aqt.qt")
    qt.__all__ = ["QDialog", "QWidget", "Qt", "QCheckBox", "QComboBox", "QLabel",
                  "QLineEdit", "QPushButton", "QRadioButton", "QTableWidget",
                  "QTableWidgetItem", "QTextEdit", "QVBoxLayout", "QHBoxLayout",
                  "QFormLayout", "QDialogButtonBox", "QAbstractItemView",
                  "QColorDialog", "QFileDialog", "QAction", "os", "sys"]
    qt.os = __import__("os")
    qt.sys = sys
    qt.__getattr__ = lambda name: _Anything

    aqt = module("aqt", mw=_Anything(), qt=qt)
    module("aqt.utils", tooltip=recorder.tooltip, showInfo=recorder.tooltip)
    module("aqt.operations", CollectionOp=FakeCollectionOp)
    module("anki.hooks", addHook=recorder.addHook)
    aqt.mw = _Anything()

    return recorder

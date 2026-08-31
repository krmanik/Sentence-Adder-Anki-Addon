"""Build every dialog against the PyQt6 that the installed Anki ships.

The pytest suite runs the add-on against fake Qt modules, so it cannot catch a
Qt call that no longer exists.  This script builds each dialog for real, with a
throwaway user_files folder and a stand-in for Anki's main window.

Run it with the python inside Anki's own program folder, for example on macOS:

    QT_QPA_PLATFORM=offscreen \
    ~/Library/Application\ Support/AnkiProgramFiles/.venv/bin/python tools/qt_smoke.py
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import types
from unittest import mock

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
PKG = "sentence_adder_smoke"

import aqt
from aqt.qt import QApplication, QMainWindow

app = QApplication.instance() or QApplication(sys.argv)


class FakeMW(QMainWindow):
    """A real widget, so Qt accepts it as a parent, with mocked Anki bits."""

    def __getattr__(self, name):
        value = mock.MagicMock()
        object.__setattr__(self, name, value)
        return value


# aqt.mw only exists while Anki runs
mw = FakeMW()
aqt.mw = mw
sys.modules["aqt"].mw = mw

# aqt's tooltip needs a live main window; print what the user would see
import aqt.utils
aqt.utils.tooltip = lambda text, *a, **k: print("   tooltip:", text)

pkg = types.ModuleType(PKG)
pkg.__path__ = [SRC]
sys.modules[PKG] = pkg


def load(name):
    spec = importlib.util.spec_from_file_location(
        "%s.%s" % (PKG, name), os.path.join(SRC, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


base = tempfile.mkdtemp()
user_files = os.path.join(base, "user_files")
lang_db = os.path.join(user_files, "lang_db")
os.makedirs(lang_db)

db_file = os.path.join(lang_db, "eng.db")
con = sqlite3.connect(db_file)
con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT)")
con.executemany("INSERT INTO examples (sentence, translation) VALUES (?,?)",
                [("The cat sleeps.", "Die Katze schläft."),
                 ("I like cats.", "Ich mag Katzen.")])
con.commit()
con.close()

config_mod = load("config")
editor = load("editor")
batch_edit = load("batch_edit")

store = config_mod.Config(user_files)
store.ensure_dirs()
store.add_language("English", db_file)
store.update(lang="English", num_of_sen="1", sen_len="100", word_color="#ff0000")
editor.config_store = store

addon = load("__init__")
addon.config_store = store

print("modules imported ok")

dlg = addon.SenAddDialog()
print("SenAddDialog ok, language:", dlg.templatesComboBox.currentText(),
      "| min len field:", repr(dlg.senMinLenTextEdit.text()),
      "| target field:", repr(dlg.targetFieldEdit.text()))

create = addon.CreateDBDialog()
create.createDB()  # no file picked yet: must warn, not raise
print("CreateDBDialog ok")

remove = addon.RemoveLangDBDialog()
print("RemoveLangDBDialog ok, entries:", remove.templatesComboBox.count())

sen_list = editor.CreateSenListDialog("cat")
print("CreateSenListDialog ok, rows:", sen_list.tablewidget.rowCount(),
      "| pair columns:", sen_list.tablewidget.columnCount())
sen_list.selectSentence()
print("selected:", sen_list.sentencePair)

empty = editor.CreateSenListDialog("aardvark")
print("no-match dialog ok, sentFound:", empty.sentFound)

browser = FakeMW()
browser.mw.col.db.list.return_value = [1]
browser.mw.col.models.get.return_value = {"name": "Basic"}
browser.mw.col.models.field_names.return_value = ["Word", "Sentence", "Translation"]
batch = batch_edit.SentenceBatchEdit(browser, [1, 2, 3])
print("SentenceBatchEdit ok, fields:", [batch.wordsComboBox.itemText(i)
                                        for i in range(batch.wordsComboBox.count())],
      "| translation field shown:", batch.hasTranslations)

print("ALL DIALOGS BUILT")

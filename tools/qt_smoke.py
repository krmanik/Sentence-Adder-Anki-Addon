r"""Build every dialog against the PyQt6 that the installed Anki ships.

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
print("SenAddDialog ok, tabs:", [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())])
print("   language:", dlg.templatesComboBox.currentText(),
      "| sentences per word:", dlg.senNumSenSpin.value(),
      "| longest:", dlg.senLenSpin.value(),
      "| word colour:", repr(dlg.wordColor.text_value()))
print("   languages listed:", [dlg.languageList.item(i).text()
                               for i in range(dlg.languageList.count())])
print("   style preview:", dlg.previewLabel.text())
print("   colour button:", dlg.wordColor.button.text(),
      "| reset enabled:", dlg.wordColor.resetButton.isEnabled())
dlg.wordColor.resetButton.click()
print("   after reset:", dlg.wordColor.button.text(),
      "| value:", repr(dlg.wordColor.text_value()),
      "| reset enabled:", dlg.wordColor.resetButton.isEnabled())
print("   preview after reset:", dlg.previewLabel.text())
print("   spin widths:", dlg.senLenSpin.minimumWidth(),
      "| special text:", repr(dlg.senMinLenSpin.specialValueText()))

dlg.senNumSenSpin.setValue(3)
dlg.senMinLenSpin.setValue(5)
dlg.wordHTMLEdit.setText("<b>{{word}}</b>")
dlg.saveConfigData()
saved = store.load()
print("   saved ->", {k: saved[k] for k in
                      ("num_of_sen", "sen_min_len", "sen_len", "word_html", "word_color")})

fields_dlg = addon.SenAddDialog(["Simplified", "Traditional", "Sentence"])
combo = fields_dlg.targetFieldComboBox
print("SenAddDialog with note fields ok, choices:",
      [combo.itemText(i) for i in range(combo.count())],
      "| value:", repr(fields_dlg.targetFieldValue()))
combo.setCurrentIndex(3)
print("   picking 'Sentence' gives:", repr(fields_dlg.targetFieldValue()))
trans = fields_dlg.transFieldComboBox
print("   translation choices:", [trans.itemText(i) for i in range(trans.count())])
trans.setCurrentIndex(2)
print("   picking translation field gives:", repr(fields_dlg.transFieldValue()))

store.update(target_field="NotInThisNoteType")
kept = addon.SenAddDialog(["Simplified", "Traditional"])
print("field set for another note type is kept:", repr(kept.targetFieldValue()))
store.update(target_field="")

create = addon.CreateDBDialog()
create.createDB()  # no file picked yet: must warn, not raise

pairs = os.path.join(base, "cmn_pairs.tsv")
with open(pairs, "w", encoding="utf-8") as f:
    f.write("1\t\u6211\u5011\u8a66\u8a66\u770b\uff01\t1176908\tLet's try!\n")
    f.write("2\t\u6211\u8be5\u53bb\u7761\u89c9\u4e86\u3002\t1277\tI have to go to sleep.\n")
create.filepath = pairs
create.fileName = "cmn_pairs"
create.loadPreview()
print("preview rows:", create.previewTable.rowCount(),
      "columns:", create.previewTable.columnCount())
print("preselected -> sentence:", create.sentenceComboBox.currentText(),
      "| translation:", create.translationComboBox.currentText(),
      "| id:", create.idComboBox.currentText())
print("example:", create.exampleLabel.text())
create.langNameEdit.setText("Chinese")

# cancelling the confirmation must not write anything
create.confirmImport = lambda layout: False
create.createDB()
print("after cancel, db written:", os.path.exists(os.path.join(lang_db, "cmn_pairs.db")),
      "| languages:", config_mod.Config(user_files).load()["all_lang"])

# what the confirmation would show
from importlib import import_module
ti = sys.modules[PKG + ".tsv_import"]
row = ti.first_usable_row(create.previewRows, create.chosenLayout())
print("confirm shows:", ti.describe_layout(create.chosenLayout(), row))

create.confirmImport = lambda layout: True
create.createDB()
imported = config_mod.Config(user_files).load()
print("language added:", imported["all_lang"], "| current:", imported["lang"])
import sqlite3 as _s
con = _s.connect(os.path.join(lang_db, "cmn_pairs.db"))
print("stored:", con.execute("select sentence, translation, tatoeba_id from examples").fetchall())
con.close()
store.update(lang="English")  # back to the language the rest of the checks use
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

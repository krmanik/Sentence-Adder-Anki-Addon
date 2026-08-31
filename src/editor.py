# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                  v1.1.0                  ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

import os
import sys

from aqt.qt import *
from aqt import mw
from anki.hooks import addHook
from aqt.qt import Qt
from aqt.utils import tooltip

from . import config as config_mod
from . import sentences

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)

user_folder = os.path.join(folder, "user_files")

config_store = config_mod.Config(user_folder)

# kept for backwards compatibility with older versions of this file; the config
# is now read from disk on every use instead of being cached here
config_data = {}
config = False


def get_config():
    """Read the config from disk so option changes apply without a restart."""
    global config_data, config
    config_data = config_store.load()
    config = True
    return config_data


def load_config():
    get_config()


def lookup_options(config_data):
    """The search settings, read from the config in whatever shape it is in."""
    return {
        "min_len": config_mod.as_int(config_data.get("sen_min_len"), 0),
        "max_len": config_mod.as_int(config_data.get("sen_len"), 0),
        "whole_word": config_mod.as_bool(config_data.get("sen_contain_space")),
    }


def find_for_word(word, config_data=None):
    """All sentences matching ``word``, or an empty list.

    Returns ``(rows, error)`` where ``error`` is a message to show the user.
    """
    if config_data is None:
        config_data = get_config()

    db_path = config_store.db_path(config_data)
    if not db_path:
        return [], "Database not found! Add a language database and select it in the options."

    rows = sentences.find_sentences(db_path, word, **lookup_options(config_data))
    if not rows:
        return [], "No sentences found for '%s'." % sentences.strip_html(word)
    return rows, None


class CreateSenListDialog(QDialog):
    def __init__(self, word=None):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Select Sentence")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(600, 500)
        self.sentencePair = []

        self.tablewidget = QTableWidget(self)
        self.tablewidget.verticalHeader().setVisible(False)
        self.tablewidget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.layout = QVBoxLayout()
        self.topLayout = QVBoxLayout()

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Select", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.accepted.connect(self.selectSentence)

        rows, error = find_for_word(word)
        self.rows = rows
        self.sentFound = bool(rows)
        self.isPair = any(row[1] for row in rows)

        if not rows:
            self.topLayout.addWidget(QLabel(error))
        else:
            if self.isPair:
                self.tablewidget.setColumnCount(2)
                self.tablewidget.setColumnWidth(0, 300)
                self.tablewidget.setColumnWidth(1, 300)
                self.tablewidget.setHorizontalHeaderLabels(["Sentences", "Translation"])
            else:
                self.tablewidget.setColumnCount(1)
                self.tablewidget.setColumnWidth(0, 600)
                self.tablewidget.setHorizontalHeaderLabels(["Sentences"])

            self.tablewidget.setRowCount(len(rows))
            for index, (sentence, translation) in enumerate(rows):
                self.tablewidget.setItem(index, 0, QTableWidgetItem(sentence))
                if self.isPair:
                    self.tablewidget.setItem(index, 1, QTableWidgetItem(translation or ""))

            self.tablewidget.selectRow(0)
            self.topLayout.addWidget(self.tablewidget)
            buttonBoxLayout.addWidget(self.buttonBox)

        self.layout.addLayout(self.topLayout)
        self.layout.addLayout(buttonBoxLayout)
        self.setLayout(self.layout)

    def selectSentence(self):
        if self.sentFound:
            selected_row = self.tablewidget.currentRow()
            if selected_row < 0:
                selected_row = 0
            self.sentencePair = list(self.rows[selected_row])
        self.close()


def getAllSentence(word):
    dlg = CreateSenListDialog(word)
    dlg.exec()
    return dlg.sentencePair


def getRandomSentence(word):
    """Random sentences for ``word``, or None when nothing matched."""
    config_data = get_config()
    rows, _ = find_for_word(word, config_data)
    if not rows:
        return None
    return sentences.pick_random(
        rows, config_mod.as_int(config_data.get("num_of_sen"), 1))


def target_field_index(editor, config_data):
    """Which field the sentences go into.

    A field name can be set in the options; when it is empty, or the note type
    has no such field, the field the cursor is in is used.
    """
    name = (config_data.get("target_field") or "").strip()
    if name and editor.note is not None:
        for index, field in enumerate(editor.note.keys()):
            if field.lower() == name.lower():
                return index

    field = editor.currentField
    if field is None:
        # the editor drops currentField when the field loses focus
        field = getattr(editor, "last_field_index", None)
    return field


def add_sentences(editor):
    config_data = get_config()

    def callback(text):
        if not text:
            tooltip("Select a word in a field first")
            return

        field = target_field_index(editor, config_data)
        if field is None or editor.note is None or field >= len(editor.note.fields):
            tooltip("Click into the field the sentences should go to")
            return

        word = sentences.strip_html(text)

        if config_mod.as_bool(config_data.get("auto_add"), True):
            rows = getRandomSentence(word)
        else:
            pair = getAllSentence(word)
            rows = [tuple(pair) if len(pair) > 1 else (pair[0], None)] if pair else None

        if not rows:
            _, error = find_for_word(word, config_data)
            tooltip(error or "No sentences found.")
            return

        editor.note.fields[field] = sentences.append_to_field(
            editor.note.fields[field], sentences.render_inline(rows, word, config_data))
        editor.loadNote(focusTo=field)

    editor.web.evalWithCallback("window.getSelection().toString()", callback)


def addSentenceButton(buttons, editor):
    icon_file = os.path.join(folder, "icon.png")
    editor._links['addSentence'] = add_sentences
    return buttons + [editor._addButton(
        icon_file,
        "addSentence",
        "Select text then click it to add sentences...")]


addHook("setupEditorButtons", addSentenceButton)

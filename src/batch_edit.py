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

from datetime import datetime

from aqt.qt import *
from aqt.utils import tooltip

from aqt import mw

from anki.hooks import addHook

from anki.collection import OpChangesWithCount
from anki.utils import ids2str
from aqt.operations import CollectionOp

from . import config as config_mod
from . import editor
from . import sentences

folder = os.path.dirname(__file__)

PROGRESS_EVERY = 20


def open_language_db(config_data):
    """The selected language database, or None when there is none."""
    db_path = editor.config_store.db_path(config_data)
    if not db_path:
        return None
    return sentences.SentenceDB(db_path, **editor.lookup_options(config_data))


def update_note(note, options, config_data, db):
    """Add sentences to one note.  Returns True when the note changed.

    Every field is looked up on the note first: a selection can hold several
    note types, and a field that exists in only one of them used to raise
    KeyError and stop the whole run.  The same went for the translation
    field, which was written to even when it was left empty in the dialog.
    """
    word_field = options["word_field"]
    sen_field = options["sen_field"]
    trans_field = options.get("trans_field") or ""

    if word_field not in note or sen_field not in note:
        return False
    if trans_field and trans_field not in note:
        trans_field = ""

    word = sentences.strip_html(note[word_field])
    if not word:
        return False

    rows = db.find(word)
    if not rows:
        return False

    picked = sentences.pick_random(
        rows, config_mod.as_int(config_data.get("num_of_sen"), 1))

    if options.get("overwrite"):
        if sen_field != word_field:
            note[sen_field] = ""
        if trans_field and trans_field != word_field:
            note[trans_field] = ""

    if trans_field:
        sen_html, trans_html = sentences.render(picked, word, config_data)
        note[trans_field] = sentences.append_to_field(note[trans_field], trans_html)
    else:
        sen_html = sentences.render_inline(picked, word, config_data)

    note[sen_field] = sentences.append_to_field(note[sen_field], sen_html)
    return True


def write_not_found(words):
    """Log the words nothing matched, returning the file path."""
    if not words:
        return None
    editor.config_store.ensure_dirs()
    path = os.path.join(
        editor.config_store.user_folder,
        "not_found_%s.txt" % datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p"))
    with open(path, "w", encoding="utf-8") as out:
        out.write("\n".join(words) + "\n")
    return path


def batch_edit_notes(parent, nids, options, on_complete):
    # the config is read here, not at import time: the batch adder used to run
    # with an empty config and fail with KeyError: 'word_color'
    config_data = editor.get_config()

    def operation(collection):
        db = open_language_db(config_data)
        if db is None:
            raise ValueError(
                "No sentence database selected. Open Tools > Sentence Adder "
                "and choose a language first.")

        updated = []
        not_found = []
        total = len(nids)

        try:
            for index, nid in enumerate(nids):
                if index % PROGRESS_EVERY == 0:
                    mw.taskman.run_on_main(
                        lambda done=index, left=total - index: mw.progress.update(
                            label="Remaining: %d notes" % left,
                            value=done,
                            max=total,
                        )
                    )

                note = collection.get_note(nid)
                if update_note(note, options, config_data, db):
                    updated.append(note)
                elif options["word_field"] in note:
                    word = sentences.strip_html(note[options["word_field"]])
                    if word:
                        not_found.append(word)
        finally:
            db.close()

        undo_entry_id = collection.add_custom_undo_entry("Sentence Adder Batch Edit")
        if updated:
            collection.update_notes(updated)
        changes = collection.merge_undo_entries(undo_entry_id)

        operation.not_found = not_found
        return OpChangesWithCount(changes=changes, count=len(updated))

    operation.not_found = []

    def success(changes):
        on_complete(changes.count, operation.not_found)

    CollectionOp(parent=parent, op=operation).success(success).run_in_background()


def field_names(collection, nids):
    """Field names of every note type in the selection, in order.

    Read from the note types rather than from the notes: a selection can hold
    thousands of notes and the dialog only needs the handful of note types
    they use.
    """
    names = []
    seen = set()

    def add_all(field_list):
        for name in field_list:
            if name not in seen:
                seen.add(name)
                names.append(name)

    try:
        mids = collection.db.list(
            "select mid from notes where id in %s group by mid order by min(id)"
            % ids2str(nids))
        for mid in mids:
            add_all(collection.models.field_names(collection.models.get(mid)))
    except Exception:
        # any unexpected database or api change: fall back to the notes
        for nid in nids:
            add_all(collection.get_note(nid).keys())

    return names


class SentenceBatchEdit(QDialog):
    def __init__(self, browser, nids):
        QDialog.__init__(self, parent=browser)
        self.setWindowTitle("Sentence Batch Adder")
        self.browser = browser
        self.nids = nids
        self.mw = browser.mw

        self.resize(400, 300)

        layout = QVBoxLayout()
        topLayout = QFormLayout()

        config_data = editor.get_config()
        fields = field_names(self.mw.col, nids)

        self.wordsComboBox = QComboBox()
        self.senComboBox = QComboBox()
        self.transComboBox = QComboBox()
        self.overwrite = QCheckBox()

        self.wordsComboBox.addItems(fields)
        self.senComboBox.addItems(fields)
        self.transComboBox.addItems([""] + fields)

        self.selectField(self.wordsComboBox, config_data.get("batch_word_field"), fields[0])
        self.selectField(self.senComboBox, config_data.get("batch_sen_field"),
                         fields[1] if len(fields) > 1 else fields[0])
        self.selectField(self.transComboBox, config_data.get("batch_trans_field"), "")

        topLayout.addRow(QLabel("Overwrite existing fields"), self.overwrite)
        topLayout.addRow(QLabel("<b>Select fields and start batch add</b>"))
        topLayout.addRow(QLabel("Select words field"), self.wordsComboBox)
        topLayout.addRow(QLabel("Select sentence field"), self.senComboBox)

        db_path = editor.config_store.db_path(config_data)
        self.hasTranslations = bool(db_path) and sentences.has_translations(db_path)
        if self.hasTranslations:
            topLayout.addRow(QLabel("Select translated sentence field"), self.transComboBox)

        if not db_path:
            topLayout.addRow(QLabel(
                "<b>No language selected.</b><br>Open Tools &gt; Sentence Adder first."))

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Start", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)

        self.buttonBox.accepted.connect(self.startBatchAdder)
        self.buttonBox.rejected.connect(self.close)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    @staticmethod
    def selectField(combo, wanted, fallback):
        if wanted and combo.findText(wanted) >= 0:
            combo.setCurrentText(wanted)
        else:
            combo.setCurrentText(fallback)

    def on_complete(self, updated, not_found):
        message = "<b>Updated</b> %d notes." % updated
        path = write_not_found(not_found)
        if path:
            message += "<br>%d words had no sentence, listed in<br>%s" % (
                len(not_found), os.path.basename(path))
        tooltip(message, parent=self.browser, period=5000)
        self.close()

    def startBatchAdder(self):
        word_field = self.wordsComboBox.currentText()
        sen_field = self.senComboBox.currentText()
        trans_field = self.transComboBox.currentText() if self.hasTranslations else ""

        if sen_field == word_field:
            tooltip("Pick a sentence field that is not the words field",
                    parent=self.browser)
            return

        editor.config_store.update(
            batch_word_field=word_field,
            batch_sen_field=sen_field,
            batch_trans_field=trans_field,
        )

        options = {
            "word_field": word_field,
            "sen_field": sen_field,
            "trans_field": trans_field,
            "overwrite": self.overwrite.checkState() == Qt.CheckState.Checked,
        }

        batch_edit_notes(self, self.nids, options, self.on_complete)


def onSentenceBatchEdit(browser):
    nids = browser.selectedNotes()
    if not nids:
        tooltip("No cards selected.")
        return
    dlg = SentenceBatchEdit(browser, nids)
    dlg.exec()


def addMenu(browser):
    menu = browser.form.menuEdit
    menu.addSeparator()
    action = menu.addAction("Sentence Batch Adder...")
    action.triggered.connect(lambda x, b=browser: onSentenceBatchEdit(b))


addHook("browser.setupMenus", addMenu)

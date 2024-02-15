# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                  v1.0.6                  ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

from aqt.qt import *
from aqt.utils import tooltip

from aqt import mw

from anki.hooks import addHook

from .editor import getRandomSentence, config_data

from datetime import datetime

from typing import TYPE_CHECKING, Callable, Optional, Sequence

from anki.collection import OpChangesWithCount
from aqt.operations import CollectionOp
from aqt.qt import QWidget

if TYPE_CHECKING:
    from anki.collection import Collection
    from anki.notes import NoteId

folder = os.path.dirname(__file__)


# https://github.com/glutanimate/batch-editing
def batch_edit_notes(
    parent,
    nids,
    wordField,
    senField,
    transField,
    overwrite,
    on_complete,
):
    def _clear_if_overwrite_selected(note):
        if overwrite and senField != wordField and transField != wordField:
            note[senField] = ""
            if transField != "":
                note[transField] = ""

    def _add_html(sen):
        sen_html = config_data.get("sen_html", "").split("{{sentence}}")
        if len(sen_html) == 2 and sen_html[0] and sen_html[1]:
            sen = sen_html[0] + sen + sen_html[1]

        return sen

    def on_success(changes: OpChangesWithCount):
        on_complete(changes.count)

    def operation(collection: "Collection") -> OpChangesWithCount:
        count = 0
        progressCount = 0
        tstamp = datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")
        out = open(
            folder + "/user_files/not_found_" + tstamp + ".txt", "w", encoding="utf-8"
        )

        modified_notes = []
        total = len(nids)

        for nid in nids:
            remaining = total - progressCount
            mw.taskman.run_on_main(
                lambda: mw.progress.update(
                    label=f"Remaining: {remaining} notes",
                    value=progressCount,
                    max=total,
                )
            )

            note = parent.mw.col.get_note(nid)
            if wordField in note:
                word = note[wordField]
                randomSen = getRandomSentence(word)

                if randomSen != None:
                    _clear_if_overwrite_selected(note)

                    if config_data["word_color"]:
                        tmp_word = (
                            '<font color="'
                            + config_data["word_color"]
                            + '">'
                            + word
                            + "</font>"
                        )
                    else:
                        tmp_word = word

                    # wrap word in html
                    if config_data["word_html"]:
                        word_html = config_data["word_html"].split("{{word}}")
                        if len(word_html) == 2 and word_html[0] and word_html[1]:
                            tmp_word = word_html[0] + word + word_html[1]

                    for sen_trans_pair in randomSen:
                        sen = sen_trans_pair[0].replace(word, tmp_word)
                        sen = _add_html(sen)

                        if config_data["text_color"]:
                            note[senField] += (
                                '<font color="'
                                + config_data["text_color"]
                                + '">'
                                + sen
                                + "</font>"
                            )
                        else:
                            note[senField] += sen

                        if transField != "":
                            note[transField] += _add_html(sen_trans_pair[1])

                        note[senField] += "<br>"
                        note[transField] += "<br>"

                    count += 1
                    modified_notes.append(note)
                else:
                    out.write(word + "\n")

                progressCount += 1

        undo_entry_id = collection.add_custom_undo_entry("Sentence Adder Batch Edit")
        changes = collection.update_notes(modified_notes)
        collection.merge_undo_entries(undo_entry_id)

        return OpChangesWithCount(changes=changes, count=len(modified_notes))

    CollectionOp(parent=parent, op=operation).success(on_success).run_in_background()


class SentenceBatchEdit(QDialog):
    def __init__(self, browser, nids):
        QDialog.__init__(self, parent=browser)
        self.setWindowTitle("Sentence Batch Adder")
        self.browser = browser
        self.nids = nids

        self.resize(400, 300)

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.senComboBox = QComboBox()
        self.wordsComboBox = QComboBox()
        self.transComboBox = QComboBox()

        nid = self.nids[0]
        self.mw = self.browser.mw
        note_type = self.mw.col.get_note(nid).note_type()
        fields = self.mw.col.models.field_names(note_type)

        self.overwrite = QCheckBox()

        self.senComboBox.addItems(fields)
        self.senComboBox.setCurrentText(fields[0])

        self.wordsComboBox.addItems(fields)
        self.wordsComboBox.setCurrentText(fields[0])

        self.transComboBox.addItems([""] + fields)
        self.transComboBox.setCurrentText("")

        self.auto_add_rb = QRadioButton("Auto Add")
        self.all_sen_win_rb = QRadioButton("Open All Sentences Window")

        topLayout.addRow(QLabel("Overwrite existing fields"), self.overwrite)

        topLayout.addRow(QLabel("<b>Select fields and start batch add</b>"))

        topLayout.addRow(QLabel("Select words field"), self.wordsComboBox)
        topLayout.addRow(QLabel("Select sentence field"), self.senComboBox)
        if config_data.get("db_contain_pair", "false") == "true":
            topLayout.addRow(QLabel("Selected translated sentence field"), self.transComboBox)


        # topLayout.addRow(self.auto_add_rb)
        # topLayout.addRow(self.all_sen_win_rb)

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
        self.get_sen = None

    def on_complete(self, result):
        self.browser.model.endReset()
        self.mw.progress.finish()
        self.mw.reset()
        tooltip("<b>Updated</b> {0} notes.".format(result), parent=self.browser)
        self.close()

    def startBatchAdder(self):
        self.mw.checkpoint("sentence batch edit")
        self.mw.progress.start()
        self.browser.model.beginReset()

        wordField = self.wordsComboBox.currentText()
        senField = self.senComboBox.currentText()
        transField = self.transComboBox.currentText()
        overwrite = self.overwrite.checkState() == Qt.CheckState.Checked

        batch_edit_notes(
            self,
            self.nids,
            wordField,
            senField,
            transField,
            overwrite,
            self.on_complete,
        )


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

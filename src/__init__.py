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


anki_addon_name = "Sentence Adder"
anki_addon_version = "1.1.0"
anki_addon_author = "Mani"
anki_addon_license = "GPL 3.0 and later"

import os
import sys
import webbrowser

from aqt.qt import QFileDialog, Qt
from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from . import utils
from . import config as config_mod
from . import tsv_import
from . import sentences
from . import editor
from . import batch_edit

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)

user_folder = os.path.join(folder, "user_files")

config_store = config_mod.Config(user_folder)
config_store.ensure_dirs()
config_store.load()


class CreateDBDialog(QDialog):
    """Pick a file, look at it, say which column is what, then import."""

    PREVIEW_ROWS = 15

    def __init__(self):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Create New DB")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(700, 520)

        self.filepath = ""
        self.fileName = ""
        self.previewRows = []

        layout = QVBoxLayout()
        topLayout = QFormLayout()

        self.selectFileFolderButton = QPushButton()
        self.selectFileFolderButton.setText("Select a File")
        self.selectFileFolderButton.clicked.connect(self.selectFileFolderDlg)

        self.tsvFilePath = QLineEdit()
        self.tsvFilePath.setReadOnly(True)
        topLayout.addRow(self.selectFileFolderButton, self.tsvFilePath)

        self.langNameEdit = QLineEdit()
        topLayout.addRow(QLabel("Enter Language Name"), self.langNameEdit)

        self.previewTable = QTableWidget(self)
        self.previewTable.verticalHeader().setVisible(False)
        self.previewTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.sentenceComboBox = QComboBox()
        self.translationComboBox = QComboBox()
        self.idComboBox = QComboBox()
        for combo in (self.sentenceComboBox, self.translationComboBox, self.idComboBox):
            combo.currentIndexChanged.connect(self.updateExample)

        self.exampleLabel = QLabel("Select a file to see what it holds.")
        self.exampleLabel.setWordWrap(True)

        columnLayout = QFormLayout()
        columnLayout.addRow(QLabel("Sentence column"), self.sentenceComboBox)
        columnLayout.addRow(QLabel("Translation column"), self.translationComboBox)
        columnLayout.addRow(QLabel("Tatoeba id column"), self.idComboBox)

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)

        self.buttonBox.accepted.connect(self.createDB)
        self.buttonBox.rejected.connect(self.close)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addWidget(QLabel("<b>First lines of the file</b>"))
        layout.addWidget(self.previewTable)
        layout.addLayout(columnLayout)
        layout.addWidget(self.exampleLabel)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    # preview ###############################################################

    def loadPreview(self):
        """Show the start of the file and preselect the detected columns."""
        try:
            rows, layout = tsv_import.preview_file(self.filepath, self.PREVIEW_ROWS)
        except Exception as e:
            tooltip("Could not read the file: %s" % e)
            return

        self.previewRows = rows
        width = max([len(row) for row in rows] or [0])

        self.previewTable.clear()
        self.previewTable.setColumnCount(width)
        self.previewTable.setRowCount(len(rows))
        self.previewTable.setHorizontalHeaderLabels(
            ["Column %d" % (i + 1) for i in range(width)])
        for r, row in enumerate(rows):
            for c in range(width):
                value = row[c] if c < len(row) else ""
                self.previewTable.setItem(r, c, QTableWidgetItem(value))
        self.previewTable.resizeColumnsToContents()

        self.fillColumnChoices(width, layout)

    def fillColumnChoices(self, width, layout):
        for combo, optional in ((self.sentenceComboBox, False),
                                (self.translationComboBox, True),
                                (self.idComboBox, True)):
            combo.blockSignals(True)
            combo.clear()
            if optional:
                combo.addItem("none", None)
            for i in range(width):
                combo.addItem("Column %d" % (i + 1), i)
            combo.blockSignals(False)

        self.selectColumn(self.sentenceComboBox, layout.get("sentence"))
        self.selectColumn(self.translationComboBox, layout.get("translation"))
        self.selectColumn(self.idComboBox, layout.get("id"))
        self.updateExample()

    @staticmethod
    def selectColumn(combo, column):
        index = combo.findData(column)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def chosenLayout(self):
        return {
            "sentence": self.sentenceComboBox.currentData(),
            "translation": self.translationComboBox.currentData(),
            "id": self.idComboBox.currentData(),
        }

    def updateExample(self):
        """Show what the first usable line would be stored as."""
        layout = self.chosenLayout()
        if not self.previewRows or layout["sentence"] is None:
            self.exampleLabel.setText("Select a file to see what it holds.")
            return

        for row in self.previewRows:
            values = tsv_import.read_columns(row, layout)
            if values:
                break
        else:
            self.exampleLabel.setText(
                "<b>Nothing would be imported.</b> Pick another sentence column.")
            return

        parts = ["sentence: %s" % values[0]]
        columns = tsv_import.table_columns(layout)
        for name, value in zip(columns[1:], values[1:]):
            parts.append("%s: %s" % (
                "translation" if name == "translation" else "tatoeba id", value))
        self.exampleLabel.setText("Will be stored as &mdash; " + "<br>".join(parts))

    # import ################################################################

    def createDB(self):
        if not self.filepath or not self.fileName:
            tooltip("Select a file first")
            return

        if not self.langNameEdit.text().strip():
            tooltip("Enter a language name")
            return

        if not os.path.exists(self.filepath):
            tooltip("File not found!")
            return

        layout = self.chosenLayout()
        if layout["sentence"] is None:
            tooltip("Choose which column holds the sentences")
            return

        config_store.ensure_dirs()
        db_file = os.path.join(config_store.lang_db_folder, self.fileName + ".db")
        if os.path.exists(db_file):
            tooltip("Already exists!, Rename tsv or delete db file")
            return

        mw.progress.start(label="Creating sentence database...", immediate=True)
        try:
            imported = tsv_import.import_tsv(
                self.filepath, db_file, layout=layout,
                on_progress=lambda n: mw.progress.update(label="Imported %d sentences..." % n),
            )
        except Exception as e:
            tooltip("Could not read the file: %s" % e)
            return
        finally:
            mw.progress.finish()

        if not imported:
            tooltip("No sentences found in that column. Check the preview and try again.")
            return

        with_translation = sentences.has_translations(db_file)
        lang_name = config_store.add_language(self.langNameEdit.text().strip(), db_file)
        config_store.update(
            lang=lang_name, db_contain_pair="true" if with_translation else "false")
        self.close()
        tooltip("Added %d %s as '%s'" % (
            imported, "sentence pairs" if with_translation else "sentences", lang_name))

    def selectFileFolderDlg(self):
        filepath = QFileDialog.getOpenFileName(
            self, 'OpenFile', filter="TSV File (*.tsv *.csv *.txt)")[0]
        if not filepath:
            return
        name, ext = os.path.splitext(os.path.basename(filepath))
        if ext.lower() not in (".tsv", ".csv", ".txt"):
            tooltip("Not a valid TSV file")
            return
        self.filepath = filepath
        self.fileName = name
        self.tsvFilePath.setText(filepath)
        if not self.langNameEdit.text().strip():
            self.langNameEdit.setText(name)
        self.loadPreview()


class SenAddDialog(QDialog):
    def __init__(self, field_names=None):
        """``field_names`` are the fields of the note open in the editor.

        When they are known the target field becomes a drop down of real field
        names; opened from the Tools menu there is no note, so it stays a text
        box.
        """
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle(anki_addon_name)
        self.resize(400, 300)

        self.field_names = list(field_names or [])

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.templatesComboBox = QComboBox()

        self.sentenceColor = QPushButton()
        self.sentenceColor.clicked.connect(self.openColorDlgSen)

        self.wordColor = QPushButton()
        self.wordColor.clicked.connect(self.openColorDlgWord)

        self.auto_add_rb = QRadioButton("Auto Add")
        self.all_sen_win_rb = QRadioButton("Open All Sentences Window")

        self.ch_sen_contain_space_cb = QCheckBox("Sentences contain spaces (match whole words)")
        self.ch_sen_contain_space_cb.setChecked(False)

        self.wordHTMLTextEdit = QTextEdit()
        self.senHTMLTextEdit = QTextEdit()
        self.senLenTextEdit = QLineEdit()
        self.senMinLenTextEdit = QLineEdit()
        self.senNumSenTextEdit = QLineEdit()
        self.targetFieldEdit = QLineEdit()
        self.targetFieldComboBox = QComboBox()

        config_data = config_store.load()
        self.templatesComboBox.addItems(config_data['all_lang'])
        self.templatesComboBox.setCurrentText(config_data['lang'])
        self.sentenceColor.setText(config_data['text_color'])
        self.wordColor.setText(config_data['word_color'])
        self.wordHTMLTextEdit.setPlainText(config_data['word_html'])
        self.senHTMLTextEdit.setPlainText(config_data['sen_html'])

        auto_add = config_mod.as_bool(config_data['auto_add'], True)
        if config_mod.as_bool(config_data['open_all_sen_window']) == auto_add:
            # both on or both off: fall back to auto add
            auto_add = True
        self.auto_add_rb.setChecked(auto_add)
        self.all_sen_win_rb.setChecked(not auto_add)

        self.ch_sen_contain_space_cb.setChecked(config_mod.as_bool(config_data['sen_contain_space']))

        self.senLenTextEdit.setText(str(config_data['sen_len']))
        self.senMinLenTextEdit.setText(str(config_data['sen_min_len']))
        self.senNumSenTextEdit.setText(str(config_data['num_of_sen']))
        self.setUpTargetField(str(config_data['target_field']))

        topLayout.addRow(QLabel("<b>Sentence</b>"))

        topLayout.addRow(QLabel("Language"), self.templatesComboBox)
        topLayout.addRow(QLabel("Word Color"), self.wordColor)
        topLayout.addRow(QLabel("Sentence Color"), self.sentenceColor)
        topLayout.addRow(QLabel("Word HTML\nwrap {{word}} in html tag"), self.wordHTMLTextEdit)
        topLayout.addRow(QLabel("Sentence HTML\nwrap {{sentence}} in html tag"), self.senHTMLTextEdit)
        topLayout.addRow(QLabel("Maximum Sentence Length\n0 = no limit"), self.senLenTextEdit)
        topLayout.addRow(QLabel("Minimum Sentence Length\n0 = no limit"), self.senMinLenTextEdit)
        topLayout.addRow(QLabel("Number of sentence"), self.senNumSenTextEdit)
        topLayout.addRow(QLabel("Add sentences to field"), self.targetFieldWidget())
        topLayout.addRow(self.ch_sen_contain_space_cb)

        topLayout.addRow(self.auto_add_rb)
        topLayout.addRow(self.all_sen_win_rb)

        topLayout.addRow(QLabel("<b>Database</b>"))

        self.createButton = QPushButton()
        self.createButton.setText("Add Language")
        self.createButton.clicked.connect(self.createDBFromTSV)
        topLayout.addRow(QLabel("Add New Language Database"), self.createButton)

        self.removeButton = QPushButton()
        self.removeButton.setText("Remove Language")
        self.removeButton.clicked.connect(self.deleteLandFromDB)
        topLayout.addRow(QLabel("Remove Language From Database"), self.removeButton)

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Ok", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.buttonBox.addButton("Help", QDialogButtonBox.ButtonRole.HelpRole)

        self.buttonBox.accepted.connect(self.saveConfigData)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.helpRequested.connect(self.openHelpInBrowser)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    def setUpTargetField(self, current):
        """Fill the target field widget with ``current`` selected."""
        if not self.field_names:
            self.targetFieldEdit.setText(current)
            self.targetFieldEdit.setPlaceholderText("empty = the field the cursor is in")
            return

        self.targetFieldComboBox.addItem("the field the cursor is in", "")
        for name in self.field_names:
            self.targetFieldComboBox.addItem(name, name)
        if current and current not in self.field_names:
            # set for a different note type; keep it instead of dropping it
            self.targetFieldComboBox.addItem("%s (other note type)" % current, current)

        index = self.targetFieldComboBox.findData(current)
        self.targetFieldComboBox.setCurrentIndex(index if index >= 0 else 0)

    def targetFieldWidget(self):
        if self.field_names:
            return self.targetFieldComboBox
        return self.targetFieldEdit

    def targetFieldValue(self):
        if self.field_names:
            return self.targetFieldComboBox.currentData() or ""
        return self.targetFieldEdit.text().strip()

    def saveConfigData(self):
        text_color = self.sentenceColor.text()
        word_color = self.wordColor.text()

        if not utils.is_hex_color(text_color) and text_color != "":
            text_color = "#000000"

        if not utils.is_hex_color(word_color) and word_color != "":
            word_color = "#000000"

        config_store.update(
            lang=self.templatesComboBox.currentText(),
            text_color=text_color,
            word_color=word_color,
            word_html=self.wordHTMLTextEdit.toPlainText(),
            sen_html=self.senHTMLTextEdit.toPlainText(),
            auto_add="true" if self.auto_add_rb.isChecked() else "false",
            open_all_sen_window="true" if self.all_sen_win_rb.isChecked() else "false",
            sen_contain_space="true" if self.ch_sen_contain_space_cb.isChecked() else "false",
            sen_len=self.senLenTextEdit.text().strip(),
            sen_min_len=self.senMinLenTextEdit.text().strip(),
            num_of_sen=self.senNumSenTextEdit.text().strip(),
            target_field=self.targetFieldValue(),
        )
        self.close()
        tooltip("Config saved!")

    def openHelpInBrowser(self):
        webbrowser.open('https://github.com/krmanik/Sentence-Adder-Anki-Addon/issues')

    def createDBFromTSV(self):
        dlg = CreateDBDialog()
        dlg.finished.connect(self.reloadLanguages)
        dlg.exec()
        self.moveFront()

    def openColorDlgSen(self):
        dialog = QColorDialog()
        color = dialog.getColor()
        if color.isValid():
            self.sentenceColor.setText(color.name())
        else:
            self.sentenceColor.setText("")

    def openColorDlgWord(self):
        dialog = QColorDialog()
        color = dialog.getColor()
        if color.isValid():
            self.wordColor.setText(color.name())
        else:
            self.wordColor.setText("")

    def moveFront(self):
        self.setFocus()
        self.activateWindow()
        self.raise_()

    def deleteLandFromDB(self):
        dlg = RemoveLangDBDialog()
        dlg.finished.connect(self.reloadLanguages)
        dlg.exec()
        self.moveFront()

    def reloadLanguages(self):
        config_data = config_store.load()
        self.templatesComboBox.clear()
        self.templatesComboBox.addItems(config_data['all_lang'])
        self.templatesComboBox.setCurrentText(config_data['lang'])


def showSenAdder(field_names=None):
    dialog = SenAddDialog(field_names)
    dialog.exec()


class RemoveLangDBDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Remove Language From Database")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        topLayout = QFormLayout()
        self.templatesComboBox = QComboBox()
        self.templatesComboBox.addItems(config_store.load()['all_lang'])

        topLayout.addRow(QLabel("Remove Language"), self.templatesComboBox)

        buttonBoxLayout = QHBoxLayout()
        buttonBox = QDialogButtonBox()
        buttonBox.addButton("Ok", QDialogButtonBox.ButtonRole.AcceptRole)
        buttonBox.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttonBox.accepted.connect(self.confirmRemoveDlg)
        buttonBox.rejected.connect(self.close)
        buttonBoxLayout.addWidget(buttonBox)

        topLayout.addRow(buttonBoxLayout)

        layout.addLayout(topLayout)
        self.setLayout(layout)

    def confirmRemoveDlg(self):
        lang = self.templatesComboBox.currentText()
        if config_mod.is_placeholder_lang(lang):
            self.close()
            return
        config_store.remove_language(lang)
        self.close()
        tooltip("Database removed!")


options_action = QAction(anki_addon_name + "...", mw)
# triggered passes a checked flag, which is not a field list
options_action.triggered.connect(lambda *args: showSenAdder())
mw.addonManager.setConfigAction(__name__, showSenAdder)
mw.form.menuTools.addAction(options_action)

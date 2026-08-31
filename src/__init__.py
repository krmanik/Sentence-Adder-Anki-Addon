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


anki_addon_name = "Sentence Adder"
anki_addon_version = "1.0.6"
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
    def __init__(self):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Create New DB")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        self.filepath = ""
        self.fileName = ""

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.selectFileFolderButton = QPushButton()
        self.selectFileFolderButton.setText("Select a File")
        self.selectFileFolderButton.clicked.connect(self.selectFileFolderDlg)

        self.tsvFilePath = QLineEdit()
        topLayout.addRow(self.selectFileFolderButton, self.tsvFilePath)

        self.langNameEdit = QLineEdit()
        topLayout.addRow(QLabel("Enter Language Name"), self.langNameEdit)

        self.ch_sen_downloaded_from_tatoeba_cb = QCheckBox("Sentences downloaded from tatoeba.org")
        self.ch_sen_downloaded_from_tatoeba_cb.setChecked(True)
        topLayout.addRow(self.ch_sen_downloaded_from_tatoeba_cb)

        self.ch_sen_contains_pair_cb = QCheckBox("File contains sentences pair")
        self.ch_sen_contains_pair_cb.setChecked(False)
        topLayout.addRow(self.ch_sen_contains_pair_cb)

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Create", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)

        self.buttonBox.accepted.connect(self.createDB)
        self.buttonBox.rejected.connect(self.close)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

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

        config_store.ensure_dirs()
        db_file = os.path.join(config_store.lang_db_folder, self.fileName + ".db")
        if os.path.exists(db_file):
            tooltip("Already exists!, Rename tsv or delete db file")
            return

        is_pair = self.ch_sen_contains_pair_cb.isChecked()
        from_tatoeba = self.ch_sen_downloaded_from_tatoeba_cb.isChecked()

        mw.progress.start(label="Creating sentence database...", immediate=True)
        try:
            imported = tsv_import.import_tsv(
                self.filepath, db_file, is_pair, from_tatoeba,
                on_progress=lambda n: mw.progress.update(label="Imported %d sentences..." % n),
            )
        except Exception as e:
            tooltip("Could not read the file: %s" % e)
            return
        finally:
            mw.progress.finish()

        if not imported:
            tooltip("No sentences found in the file. Check the tatoeba option and try again.")
            return

        lang_name = config_store.add_language(self.langNameEdit.text().strip(), db_file)
        config_store.update(lang=lang_name, db_contain_pair="true" if is_pair else "false")
        self.close()
        tooltip("Added %d sentences as '%s'" % (imported, lang_name))

    def selectFileFolderDlg(self):
        filepath = QFileDialog.getOpenFileName(self, 'OpenFile', filter="TSV File (*.tsv *.csv *.txt)")[0]
        if not filepath:
            return
        name, ext = os.path.splitext(os.path.basename(filepath))
        if ext.lower() not in (".tsv", ".csv", ".txt"):
            tooltip("Not a valid TSV file")
            return
        self.filepath = filepath
        self.fileName = name
        self.tsvFilePath.setText(filepath)


class SenAddDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle(anki_addon_name)
        self.resize(400, 300)

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.templatesComboBox = QComboBox()

        self.sentenceColor = QPushButton()
        self.sentenceColor.clicked.connect(self.openColorDlgSen)

        self.wordColor = QPushButton()
        self.wordColor.clicked.connect(self.openColorDlgWord)

        self.auto_add_rb = QRadioButton("Auto Add")
        self.all_sen_win_rb = QRadioButton("Open All Sentences Window")

        self.ch_sen_contain_space_cb = QCheckBox("Sentences contain spaces")
        self.ch_sen_contain_space_cb.setChecked(False)

        self.ch_db_contain_pair_cb = QCheckBox("Database contains sentences pair")
        self.ch_db_contain_pair_cb.setChecked(False)

        self.wordHTMLTextEdit = QTextEdit()
        self.senHTMLTextEdit = QTextEdit()
        self.senLenTextEdit = QLineEdit()
        self.senNumSenTextEdit = QLineEdit()

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
        self.ch_db_contain_pair_cb.setChecked(config_mod.as_bool(config_data['db_contain_pair']))

        self.senLenTextEdit.setText(str(config_data['sen_len']))
        self.senNumSenTextEdit.setText(str(config_data['num_of_sen']))

        topLayout.addRow(QLabel("<b>Sentence</b>"))

        topLayout.addRow(QLabel("Language"), self.templatesComboBox)
        topLayout.addRow(QLabel("Word Color"), self.wordColor)
        topLayout.addRow(QLabel("Sentence Color"), self.sentenceColor)
        topLayout.addRow(QLabel("Word HTML\nwrap {{word}} in html tag"), self.wordHTMLTextEdit)
        topLayout.addRow(QLabel("Sentence HTML\nwrap {{sentence}} in html tag"), self.senHTMLTextEdit)
        topLayout.addRow(QLabel("Sentence Length"), self.senLenTextEdit)
        topLayout.addRow(QLabel("Number of sentence"), self.senNumSenTextEdit)
        topLayout.addRow(self.ch_sen_contain_space_cb)
        topLayout.addRow(self.ch_db_contain_pair_cb)

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
            db_contain_pair="true" if self.ch_db_contain_pair_cb.isChecked() else "false",
            sen_len=self.senLenTextEdit.text(),
            num_of_sen=self.senNumSenTextEdit.text(),
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
        self.ch_db_contain_pair_cb.setChecked(config_mod.as_bool(config_data['db_contain_pair']))


def showSenAdder():
    dialog = SenAddDialog()
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
options_action.triggered.connect(showSenAdder)
mw.addonManager.setConfigAction(__name__, showSenAdder)
mw.form.menuTools.addAction(options_action)

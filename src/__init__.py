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

import json
import os
import webbrowser

from aqt.qt import QFileDialog, Qt
from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from . import utils
from . import editor
from . import batch_edit

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)

user_folder = folder + "/user_files/"

config_json = user_folder + "config.json"
lang_db_folder = user_folder + "lang_db/"

if not os.path.exists(user_folder):
    os.mkdir(user_folder)

if not os.path.exists(lang_db_folder):
    os.mkdir(lang_db_folder)

if not os.path.exists(config_json):
    config_dict = {"lang": " -- Select Language -- ", "all_lang": ["-- Select Language --"], "text_color": "",
                   "word_color": "", "word_html": "", "sen_html": "",
                   "auto_add": "true", "open_all_sen_window": "false", "sen_contain_space": "false",
                   "db_contain_pair": "false", "sen_len": "30", "num_of_sen": "2"}

    with open(config_json, "w") as f:
        json.dump(config_dict, f)

if os.path.exists(config_json):
    config_dict = {"lang": " -- Select Language -- ", "all_lang": ["-- Select Language --"], "text_color": "",
                   "word_color": "", "word_html": "", "sen_html": "",
                   "auto_add": "true", "open_all_sen_window": "false",
                   "sen_contain_space": "false", "db_contain_pair": "false", "sen_len": "30", "num_of_sen": "2"}
    config_dict_temp = {}

    with open(config_json, "r") as f:
        config_dict_temp = json.load(f)

    config_dict = {**config_dict, **config_dict_temp}

    with open(config_json, "w") as f:
        json.dump(config_dict, f)


class CreateDBDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Create New DB")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

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
        import csv
        import sqlite3

        if len(self.fileName) > 0 and len(self.langNameEdit.text()) > 0:
            db_file = lang_db_folder + self.fileName + ".db"
            if os.path.exists(db_file):
                tooltip("Already exists!, Rename tsv or delete db file")
            else:
                conn = sqlite3.connect(db_file)
                curs = conn.cursor()

                # if tsv contains pair then create two column, one for source and other for target
                if self.ch_sen_contains_pair_cb.isChecked():
                    curs.execute(
                        "CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT);")
                else:
                    curs.execute(
                        "CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT);")

                if os.path.exists(self.filepath):
                    reader = csv.reader(open(self.filepath, 'r', encoding="utf-8"), delimiter='\t')
                    for row in reader:
                        if self.ch_sen_downloaded_from_tatoeba_cb.isChecked():
                            if self.ch_sen_contains_pair_cb.isChecked():
                                # if row contains error or multiple tab then it may cause errors
                                if len(row) != 4:
                                    continue
                                to_db = [row[1], row[3]]
                                curs.execute("INSERT INTO examples (sentence, translation) VALUES (?,?);", to_db)
                            else:
                                to_db = [row[2]]
                                curs.execute("INSERT INTO examples (sentence) VALUES (?);", to_db)
                        else:
                            if self.ch_sen_contains_pair_cb.isChecked():
                                to_db = [row[0], row[1]]
                                curs.execute("INSERT INTO examples (sentence, translation) VALUES (?,?);", to_db)
                            else:
                                to_db = [row[0]]
                                curs.execute("INSERT INTO examples (sentence) VALUES (?);", to_db)
                    conn.commit()
                    self.addNewLangToConfig(self.fileName, self.langNameEdit.text())
                    self.close()
                    tooltip("Database added, restart to apply changes!")
                else:
                    tooltip("File not found!")
        else:
            tooltip("Select a file first")

    def selectFileFolderDlg(self):
        self.filepath = QFileDialog.getOpenFileName(self, 'OpenFile', filter="TSV File (*.tsv)")[0]
        if self.filepath:
            self.fileName = self.filepath.split("/")[-1].split(".")[0]
            if self.filepath.split("/")[-1].split(".")[1] == "tsv":
                self.tsvFilePath.setText(self.filepath)
            else:
                tooltip("Not a valid TSV file")

    def addNewLangToConfig(self, dbName, langName):
        with open(config_json, "r") as f:
            config = json.load(f)
            i = 0

            if langName in config['all_lang']:
                for l in config['all_lang']:
                    if l == langName:
                        i += 1
                langName = langName + str(i)

            config['all_lang'].append(langName)
            config[langName] = lang_db_folder + dbName + ".db"

            with open(config_json, "w") as f:
                json.dump(config, f)


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

        with open(config_json, "r") as f:
            config_data = json.load(f)
            self.templatesComboBox.addItems(config_data['all_lang'])
            self.templatesComboBox.setCurrentText(config_data['lang'])
            self.sentenceColor.setText(config_data['text_color'])
            self.wordColor.setText(config_data['word_color'])
            self.wordHTMLTextEdit.setPlainText(config_data['word_html'])
            self.senHTMLTextEdit.setPlainText(config_data['sen_html'])

            if config_data['auto_add'] == "true" and config_data['open_all_sen_window'] == "true" \
                    or config_data['auto_add'] == "false" and config_data['open_all_sen_window'] == "false":
                config_data['auto_add'] = "true"
                config_data['open_all_sen_window'] = "false"

            if config_data['auto_add'] == "true":
                self.auto_add_rb.setChecked(True)
                self.all_sen_win_rb.setChecked(False)
            else:
                self.auto_add_rb.setChecked(False)
                self.all_sen_win_rb.setChecked(True)

            if config_data['open_all_sen_window'] == "true":
                self.all_sen_win_rb.setChecked(True)
                self.auto_add_rb.setChecked(False)
            else:
                self.all_sen_win_rb.setChecked(False)
                self.auto_add_rb.setChecked(True)

            if config_data['sen_contain_space'] == "true":
                self.ch_sen_contain_space_cb.setChecked(True)
            else:
                self.ch_sen_contain_space_cb.setChecked(False)

            if config_data['db_contain_pair'] == "true":
                self.ch_db_contain_pair_cb.setChecked(True)
            else:
                self.ch_db_contain_pair_cb.setChecked(False)

            self.senLenTextEdit.setText(config_data['sen_len'])
            self.senNumSenTextEdit.setText(config_data['num_of_sen'])

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
        lang = self.templatesComboBox.currentText()
        text_color = self.sentenceColor.text()
        word_color = self.wordColor.text()
        word_html = self.wordHTMLTextEdit.toPlainText()
        sen_html = self.senHTMLTextEdit.toPlainText()

        if not utils.is_hex_color(text_color) and text_color != "":
            text_color = "#000000"

        if not utils.is_hex_color(word_color) and word_color != "":
            word_color = "#000000"

        if self.auto_add_rb.isChecked():
            auto_add = "true"
        else:
            auto_add = "false"

        if self.all_sen_win_rb.isChecked():
            open_all_sen_window = "true"
        else:
            open_all_sen_window = "false"

        if self.ch_sen_contain_space_cb.isChecked():
            sen_space = "true"
        else:
            sen_space = "false"

        if self.ch_db_contain_pair_cb.isChecked():
            db_pair = "true"
        else:
            db_pair = "false"

        with open(config_json, "r") as f:
            config_dict = json.load(f)
            config_dict["lang"] = lang
            config_dict["text_color"] = text_color
            config_dict["word_color"] = word_color
            config_dict["word_html"] = word_html
            config_dict["sen_html"] = sen_html
            config_dict["auto_add"] = auto_add
            config_dict["open_all_sen_window"] = open_all_sen_window
            config_dict['sen_contain_space'] = sen_space
            config_dict['db_contain_pair'] = db_pair
            config_dict['sen_len'] = self.senLenTextEdit.text()
            config_dict['num_of_sen'] = self.senNumSenTextEdit.text()

            with open(config_json, "w") as f:
                json.dump(config_dict, f)
                self.close()
                tooltip("Restart to apply changes!")

    def openHelpInBrowser(self):
        webbrowser.open('https://github.com/krmanik/Sentence-Adder-Anki-Addon/issues')

    def createDBFromTSV(self):
        dlg = CreateDBDialog()
        dlg.exec()
        self.moveFront()

    def openColorDlgSen(self):
        dialog = QColorDialog()
        color = dialog.getColor()
        if color.isValid():
            color = color.name()
            self.sentenceColor.setText(color)
        else:
            self.sentenceColor.setText("")

    def openColorDlgWord(self):
        dialog = QColorDialog()
        color = dialog.getColor()
        print(color.name())
        if color.isValid():
            color = color.name()
            self.wordColor.setText(color)
        else:
            self.wordColor.setText("")

    def moveFront(self):
        self.setFocus()
        self.activateWindow()
        self.raise_()

    def deleteLandFromDB(self):
        dlg = RemoveLangDBDialog()
        dlg.exec()
        self.moveFront()


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

        with open(config_json, "r") as f:
            config_data = json.load(f)
            self.templatesComboBox.addItems(config_data['all_lang'])

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
        config_data = {}
        with open(config_json, "r") as f:
            config_data = json.load(f)
            lang = self.templatesComboBox.currentText()
            # remove
            path = config_data[lang]
            os.remove(path)

            del config_data[lang]
            config_data['all_lang'].remove(lang)

        with open(config_json, "w") as f:
            json.dump(config_data, f)

        self.close()
        tooltip("Database removed, restart to apply changes!")


options_action = QAction(anki_addon_name + "...", mw)
options_action.triggered.connect(showSenAdder)
mw.addonManager.setConfigAction(__name__, showSenAdder)
mw.form.menuTools.addAction(options_action)

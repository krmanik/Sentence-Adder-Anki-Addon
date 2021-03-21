# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                  v1.0.1                  ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/infinyte7)      ##
##                                          ##
##############################################


anki_addon_name = "Sentence Adder"
anki_addon_version = "1.0.1"
anki_addon_author = "Mani"
anki_addon_license = "GPL 3.0 and later"

from aqt.qt import *
from aqt import mw, AnkiQt
from aqt.utils import tooltip
from PyQt5 import QtWidgets, QtCore

import json
import webbrowser

from . import editor
from . import utils

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)
config_json = folder + "/config.json"
lang_db_folder = folder + "/lang_db/"

if not os.path.exists(lang_db_folder):
    os.mkdir(lang_db_folder)

if not os.path.exists(config_json):
    config_dict = {"lang": " -- Select Language -- ", "all_lang": ["-- Select Language --"], "text_color": "#000000",
                   "auto_add": "true", "open_all_sen_window": "false"}

    with open(config_json, "w") as f:
        json.dump(config_dict, f)


class CreateDBDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self, None, Qt.Window)
        mw.setupDialogGC(self)
        self.setWindowTitle("Create New DB")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.selectFileFolderButton = QPushButton()
        self.selectFileFolderButton.setText("Select a File")
        self.selectFileFolderButton.clicked.connect(self.selectFileFolderDlg)

        self.langNameEdit = QLineEdit()
        topLayout.addRow(QLabel("Enter Language Name"), self.langNameEdit)

        self.tsvFilePath = QLineEdit()
        topLayout.addRow(self.selectFileFolderButton, self.tsvFilePath)

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Create", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.RejectRole)

        self.buttonBox.accepted.connect(self.createDB)
        self.buttonBox.rejected.connect(self.close)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    def createDB(self):
        import csv, sqlite3
        if len(self.fileName) > 0 and len(self.langNameEdit.text()) > 0:
            db_file = lang_db_folder + self.fileName + ".db"
            if os.path.exists(db_file):
                tooltip("Already exists!, Rename tsv or delete db file")
            else:
                conn = sqlite3.connect(db_file)
                curs = conn.cursor()
                curs.execute(
                    "CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT);")
                if os.path.exists(self.filepath):
                    reader = csv.reader(open(self.filepath, 'r', encoding="utf-8"), delimiter='\t')
                    for row in reader:
                        to_db = [row[2]]
                        curs.execute("INSERT INTO examples (sentence) VALUES (?);",
                                     to_db)
                    conn.commit()
                    self.addNewLangToConfig(self.fileName, self.langNameEdit.text())
                    self.close()
                    tooltip("Database added, restart to apply changes!")
                else:
                    tooltip("File not found!")
        else:
            tooltip("Select a file first")

    def selectFileFolderDlg(self):
        self.filepath = QtWidgets.QFileDialog.getOpenFileName(self, 'OpenFile')[0]
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
        QDialog.__init__(self, None, Qt.Window)
        mw.setupDialogGC(self)
        self.setWindowTitle(anki_addon_name)
        self.resize(400, 300)

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.templatesComboBox = QComboBox()

        self.textColorButton = QPushButton()
        self.textColorButton.clicked.connect(self.openColorDlg)

        self.auto_add_rb = QRadioButton("Auto Add")
        self.all_sen_win_rb = QRadioButton("Open All Sentences Window")

        with open(config_json, "r") as f:
            config_data = json.load(f)
            self.templatesComboBox.addItems(config_data['all_lang'])
            self.templatesComboBox.setCurrentText(config_data['lang'])
            self.textColorButton.setText(config_data['text_color'])

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

        topLayout.addRow(QLabel("<b>Sentence</b>"))

        topLayout.addRow(QLabel("Language"), self.templatesComboBox)
        topLayout.addRow(QLabel("Text Color"), self.textColorButton)

        topLayout.addRow(self.auto_add_rb)
        topLayout.addRow(self.all_sen_win_rb)

        topLayout.addRow(QLabel("<b>Database</b>"))

        self.createButton = QPushButton()
        self.createButton.setText("Add Language")
        self.createButton.clicked.connect(self.createDBFromTSV)
        topLayout.addRow(QLabel("Add New Language Database"), self.createButton)

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Ok", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.RejectRole)
        self.buttonBox.addButton("Help", QDialogButtonBox.HelpRole)

        self.buttonBox.accepted.connect(self.saveConfigData)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.helpRequested.connect(self.openHelpInBrowser)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    def saveConfigData(self):
        lang = self.templatesComboBox.currentText()
        text_color = self.textColorButton.text()
        if not utils.is_hex_color(text_color):
            text_color = "#000000"

        if self.auto_add_rb.isChecked():
            auto_add = "true"
        else:
            auto_add = "false"

        if self.all_sen_win_rb.isChecked():
            open_all_sen_window = "true"
        else:
            open_all_sen_window = "false"

        with open(config_json, "r") as f:
            config_dict = json.load(f)
            config_dict["lang"] = lang
            config_dict["text_color"] = text_color
            config_dict["auto_add"] = auto_add
            config_dict["open_all_sen_window"] = open_all_sen_window

            with open(config_json, "w") as f:
                json.dump(config_dict, f)
                self.close()
                tooltip("Restart to apply changes!")

    def openHelpInBrowser(self):
        webbrowser.open('http://github.com')

    def createDBFromTSV(self):
        dlg = CreateDBDialog()
        dlg.exec_()
        self.moveFront()

    def openColorDlg(self):
        dialog = QColorDialog()
        color = dialog.getColor()
        if color.isValid():
            color = color.name()
            self.textColorButton.setText(color)

    def moveFront(self):
        self.setFocus(True)
        self.activateWindow()
        self.raise_()


def showSenAdder():
    dialog = SenAddDialog()
    dialog.exec_()


options_action = QAction(anki_addon_name + "...", mw)
options_action.triggered.connect(showSenAdder)
mw.addonManager.setConfigAction(__name__, showSenAdder)
mw.form.menuTools.addAction(options_action)

from . import batch_edit

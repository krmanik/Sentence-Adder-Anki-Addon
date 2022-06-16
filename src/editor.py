# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                  v1.0.1                  ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

import os
import sys
import json
import sqlite3
import random

from aqt.qt import *
from aqt import mw
from anki.hooks import addHook
from PyQt5 import QtCore
from aqt.utils import tooltip

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)
config_json = folder + "/config.json"
lang_db_folder = folder + "/lang_db/"

config_data = {}
config = False
if os.path.exists(config_json):
    with open(config_json, "r") as f:
        config_data = json.load(f)
        config = True
else:
    config = False

class CreateSenListDialog(QDialog):
    def __init__(self, word=None):
        QDialog.__init__(self, None, Qt.Window)
        mw.setupDialogGC(self)
        self.setWindowTitle("Select Sentence")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.sentence = ""

        self.listwidget = QListWidget()

        self.layout = QVBoxLayout()
        self.topLayout = QFormLayout()

        buttonBoxLayout = QHBoxLayout()
        
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Select", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.accepted.connect(self.selectSentence)
        
        lang = config_data['lang']
        lang_db = config_data[lang]
        sen_len = config_data['sen_len']

        self.sentFound = False
        
        if not os.path.exists(lang_db):
            tooltip("Database not exists! Create database and try again.")
        else:
            con = sqlite3.connect(lang_db)
            cur = con.cursor()

            if config_data['sen_contain_space'] == "false":
                sql = "Select sentence from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= "+ sen_len +";"
            else:
                # "'%<space>" + word + "<space>%'"
                sql = "Select sentence from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= "+ sen_len +";"

            cur.execute(sql)
            sent = cur.fetchall()

            if len(sent) > 0:
                for s in sent:
                    self.listwidget.addItem(s[0])
                self.topLayout.addWidget(self.listwidget)
                self.sentFound = True
                buttonBoxLayout.addWidget(self.buttonBox)
            else:
                self.topLayout.addWidget(QLabel("No Sentences found! Change Language or add database!"))
                self.sentFound = False

        self.layout.addLayout(self.topLayout)
        self.layout.addLayout(buttonBoxLayout)
        self.setLayout(self.layout)

    def selectSentence(self):
        if self.sentFound:
            sentence = self.listwidget.currentItem().text()
            self.sentence = str(sentence)
        self.close()


def getAllSentence(word):
    dlg = CreateSenListDialog(word)
    dlg.exec()        
    sen = dlg.sentence
    return sen

def getRandomSentence(word):
    if config:
        try:
            lang = config_data['lang']
            lang_db = config_data[lang]
            sen_len = config_data['sen_len']

            con = sqlite3.connect(lang_db)
            cur = con.cursor()

            if config_data['sen_contain_space'] == "false":
                sql = "Select sentence from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= "+ sen_len +";"
            else:
                # "'%<space>" + word + "<space>%'"
                sql = "Select sentence from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= "+ sen_len +";"

            cur.execute(sql)
            sent = cur.fetchall()
            r1 = random.choice(sent)
            s1 = r1[0]
            return s1
        except Exception as e:
            tooltip("Create database or change language options...")
            print(e)


def add_sentences(editor):
    field = editor.currentField

    def callback(text):
        if text:
            try:
                sentence = ""
                if config:
                    if config_data['auto_add'] == "true":
                        sentence = getRandomSentence(text)
                    else:
                        sentence = getAllSentence(text)
                if sentence != "":
                    if editor.note.fields[field]:
                        editor.note.fields[field] += "<br><br>"
                    word = '<font color="'+ config_data['word_color'] +'">' + text + "</font>"
                    sentence = sentence.replace(text, word)
                    editor.note.fields[field] += '<font color="'+ config_data['text_color'] +'">' + sentence + "</font>"
                editor.loadNote(focusTo=field)
            except Exception as e:
                tooltip("Create database or change language options...")
                print(e)

    editor.web.evalWithCallback("window.getSelection().toString()", callback)


def addSentenceButton(buttons, editor):
    icon_file = folder + "/icon.png"
    editor._links['addSentence'] = add_sentences
    return buttons + [editor._addButton(
        icon_file,
        "addSentence",
        "Select text then click it to add sentences...")]


addHook("setupEditorButtons", addSentenceButton)

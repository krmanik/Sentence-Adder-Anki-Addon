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

import os
import sys
import json
import sqlite3
import random

from aqt.qt import *
from aqt import mw
from anki.hooks import addHook
from aqt.qt import Qt
from aqt.utils import tooltip

folder = os.path.dirname(__file__)
libfolder = os.path.join(folder, "lib")
sys.path.insert(0, libfolder)

user_folder = folder + "/user_files/"

config_json = user_folder + "config.json"
lang_db_folder = user_folder + "lang_db/"

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
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle("Select Sentence")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(600, 500)
        self.isPair = False
        self.sentencePair = []

        self.tablewidget = QTableWidget(self)
        self.tablewidget.verticalHeader().setVisible(False)

        self.layout = QVBoxLayout()
        self.topLayout = QVBoxLayout()

        buttonBoxLayout = QHBoxLayout()

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Select", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.accepted.connect(self.selectSentence)

        lang = config_data['lang']
        lang_db = config_data[lang]
        sen_len = config_data['sen_len']

        self.sentFound = False

        if config_data['db_contain_pair'] == "true":
            self.isPair = True

        if not os.path.exists(lang_db):
            tooltip("Database not exists! Create database and try again.")
        else:
            con = sqlite3.connect(lang_db)
            cur = con.cursor()

            # select sentence and translation, spaces between words or not
            if config_data['sen_contain_space'] == "false":
                if self.isPair:
                    sql = "Select sentence,translation from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= " + sen_len + ";"
                else:
                    sql = "Select sentence from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= " + sen_len + ";"
            else:
                if self.isPair:
                    sql = "Select sentence,translation from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= " + sen_len + ";"
                else:
                    # "'%<space>" + word + "<space>%'"
                    sql = "Select sentence from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= " + sen_len + ";"

            cur.execute(sql)
            sent = cur.fetchall()

            if self.isPair:
                self.tablewidget.setColumnCount(2)
                self.tablewidget.setColumnWidth(0, 300)
                self.tablewidget.setColumnWidth(1, 300)
                self.tablewidget.setHorizontalHeaderLabels(["Sentences", "Translation"])
            else:
                self.tablewidget.setColumnCount(1)
                self.tablewidget.setColumnWidth(0, 600)
                self.tablewidget.setHorizontalHeaderLabels(["Sentences"])

            if len(sent) > 0:
                self.tablewidget.setRowCount(len(sent))
                row = 0
                for s in sent:
                    self.tablewidget.setItem(row, 0, QTableWidgetItem(s[0]))
                    if self.isPair:
                        self.tablewidget.setItem(row, 1, QTableWidgetItem(s[1]))
                    row += 1

                self.topLayout.addWidget(self.tablewidget)
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
            selected_row = self.tablewidget.currentRow()
            sentence = self.tablewidget.item(selected_row, 0).text()
            self.sentencePair = [str(sentence)]
            if self.isPair:
                translation = self.tablewidget.item(selected_row, 1).text()
                self.sentencePair = [str(sentence), str(translation)]
        self.close()


def getAllSentence(word):
    dlg = CreateSenListDialog(word)
    dlg.exec()
    sentence_pair = dlg.sentencePair
    return sentence_pair


def getRandomSentence(word):
    if config:
        try:
            lang = config_data['lang']
            lang_db = config_data[lang]
            sen_len = config_data['sen_len']
            is_pair = False

            con = sqlite3.connect(lang_db)
            cur = con.cursor()

            if config_data['db_contain_pair'] == "true":
                is_pair = True

            # select sentence and translation, spaces between words or not
            if config_data['sen_contain_space'] == "false":
                if is_pair:
                    sql = "Select sentence,translation from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= " + sen_len + ";"
                else:
                    sql = "Select sentence from examples where sentence like " + "'%" + word + "%'" + " and length(sentence) <= " + sen_len + ";"
            else:
                if is_pair:
                    sql = "Select sentence,translation from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= " + sen_len + ";"
                else:
                    # "'%<space>" + word + "<space>%'"
                    sql = "Select sentence from examples where sentence like " + "'% " + word + " %'" + " and length(sentence) <= " + sen_len + ";"

            cur.execute(sql)
            sent = cur.fetchall()
            random_sen = random.sample(sent, int(config_data["num_of_sen"]))
            return random_sen
        except Exception as e:
            print(e)


def add_sentences(editor):
    field = editor.currentField

    def callback(text):
        if text is None or text == "" or config is None:
            return
        try:
            sentence_pair_list = []
            sentence_pair = []
            auto_add = False

            if config_data['auto_add'] == "true":
                auto_add = True

            if auto_add:
                sentence_pair_list = getRandomSentence(text)
            else:
                sentence_pair = getAllSentence(text)

            if editor.note.fields[field]:
                editor.note.fields[field] += "<br><br>"

            if config_data['word_color']:
                word = '<font color="' + config_data['word_color'] + '">' + text + "</font>"
            else:
                word = text

            # wrap word in html
            if config_data['word_html']:
                word_html = config_data['word_html'].split("{{word}}")
                if len(word_html) == 2 and word_html[0] and word_html[1]:
                    word = word_html[0] + word + word_html[1]

            if auto_add:
                for sentence_pair in sentence_pair_list:
                    insert(sentence_pair, text, word)
                    editor.note.fields[field] += "<br>"
            else:
                insert(sentence_pair, text, word)

            editor.loadNote(focusTo=field)
        except Exception as e:
            tooltip("Create database or change language options...")
            print(e)

    def insert(sentence_pair, text, word):
        sen_html = ["", ""]
        if config_data['sen_html']:
            sen_html = config_data['sen_html'].split("{{sentence}}")

        sentence = sentence_pair[0].replace(text, word)

        if len(sen_html) == 2 and sen_html[0] and sen_html[1]:
            sentence = sen_html[0] + sentence + sen_html[1]

        if config_data['text_color']:
            editor.note.fields[field] += '<font color="' + config_data['text_color'] + '">' + sentence + "</font>"
        else:
            editor.note.fields[field] += sentence

        if config_data['db_contain_pair'] == "true":
            translation = sentence_pair[1]
            editor.note.fields[field] += "<br>" + translation

        editor.note.fields[field] += "<br>"

    editor.web.evalWithCallback("window.getSelection().toString()", callback)


def addSentenceButton(buttons, editor):
    icon_file = folder + "/icon.png"
    editor._links['addSentence'] = add_sentences
    return buttons + [editor._addButton(
        icon_file,
        "addSentence",
        "Select text then click it to add sentences...")]


addHook("setupEditorButtons", addSentenceButton)

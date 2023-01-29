# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                  v1.0.4                  ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

from aqt.qt import *
from aqt.utils import tooltip

from anki.hooks import addHook

from .editor import getRandomSentence, config_data

folder = os.path.dirname(__file__)

class SentenceBatchEdit(QDialog):
    def __init__(self, browser, nids):
        QDialog.__init__(self, parent=browser)
        self.setWindowTitle("Sentence Batch Adder")
        self.browser = browser
        self.nids = nids

        self.resize(400, 300)

        layout = QVBoxLayout()

        topLayout = QFormLayout()

        self.selectFieldsComboBox = QComboBox()
        self.wordsComboBox = QComboBox()

        nid = self.nids[0]
        self.mw = self.browser.mw
        note_type = self.mw.col.get_note(nid).note_type()
        fields = self.mw.col.models.field_names(note_type)
        
        self.selectFieldsComboBox.addItems(fields)
        self.selectFieldsComboBox.setCurrentText(fields[0])

        self.wordsComboBox.addItems(fields)
        self.wordsComboBox.setCurrentText(fields[0])

        self.auto_add_rb = QRadioButton("Auto Add")
        self.all_sen_win_rb = QRadioButton("Open All Sentences Window")


        topLayout.addRow(QLabel("<b>Select fields and start batch add</b>"))

        topLayout.addRow(QLabel("Select words field"), self.wordsComboBox)
        topLayout.addRow(QLabel("Select sentence field"), self.selectFieldsComboBox)
        
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

    def startBatchAdder(self):
        wordField = self.wordsComboBox.currentText()
        senField = self.selectFieldsComboBox.currentText()

        out = open(folder + "/user_files/not_found.txt", "w", encoding="utf-8")
        
        for nid in self.nids:
            note = self.mw.col.get_note(nid)
            if wordField in note:
                word = note[wordField]
                randomSen = getRandomSentence(word)
                print(randomSen)

                if randomSen != None:
                    if config_data['word_color']:
                        tmp_word = '<font color="' + config_data['word_color'] + '">' + word + "</font>"
                    else:
                        tmp_word = word

                    for sen in randomSen:
                        if config_data['text_color']:
                            sen = sen[0].replace(word, tmp_word)
                            note[senField] += '<font color="' + config_data['text_color'] + '">' + sen + "</font>"
                        else:
                            note[senField] += sen[0]
                else:
                    tooltip("Sentence not found for " + word)
                    out.write(word+"\n")
                note.flush()
            
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
    action = menu.addAction('Sentence Batch Adder...')
    action.triggered.connect(lambda x, b=browser: onSentenceBatchEdit(b))


addHook("browser.setupMenus", addMenu)

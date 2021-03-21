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

from aqt.qt import *
from aqt.utils import tooltip

from anki.hooks import addHook

from .editor import getRandomSentence

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
        model = self.mw.col.getNote(nid).model()
        fields = self.mw.col.models.fieldNames(model)
        
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
        self.buttonBox.addButton("Start", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.RejectRole)

        self.buttonBox.accepted.connect(self.startBatchAdder)
        self.buttonBox.rejected.connect(self.close)

        buttonBoxLayout.addWidget(self.buttonBox)

        layout.addLayout(topLayout)
        layout.addLayout(buttonBoxLayout)
        self.setLayout(layout)

    def startBatchAdder(self):
        wordField = self.wordsComboBox.currentText()
        senField = self.selectFieldsComboBox.currentText()

        out = open(folder+"/not_found.txt", "w", encoding="utf-8")
        
        for nid in self.nids:
            note = self.mw.col.getNote(nid)
            if wordField in note:
                word = note[wordField]
                randomSen = getRandomSentence(word)
                if randomSen != None:
                    note[senField] += randomSen
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
    dlg.exec_()


def addMenu(browser):
    menu = browser.form.menuEdit
    menu.addSeparator()
    action = menu.addAction('Sentence Batch Adder...')
    action.triggered.connect(lambda x, b=browser: onSentenceBatchEdit(b))


addHook("browser.setupMenus", addMenu)

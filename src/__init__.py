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

        row = tsv_import.first_usable_row(self.previewRows, layout)
        if row is None:
            self.exampleLabel.setText(
                "<b>Nothing would be imported.</b> Pick another sentence column.")
            return

        parts = []
        for label, column, example in tsv_import.describe_layout(layout, row):
            if example:
                parts.append("%s: %s" % (label.lower(), example))
        self.exampleLabel.setText("Will be stored as &mdash; " + "<br>".join(parts))

    def confirmImport(self, layout):
        """Ask before writing anything, showing which column is used for what."""
        row = tsv_import.first_usable_row(self.previewRows, layout)

        lines = ["<table cellpadding=4>"]
        for label, column, example in tsv_import.describe_layout(layout, row):
            lines.append("<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>"
                         % (label, column, example))
        lines.append("</table>")

        box = QMessageBox(self)
        box.setWindowTitle("Create database")
        box.setIcon(QMessageBox.Icon.Question)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("Create <b>%s</b> from %s?"
                    % (self.langNameEdit.text().strip(), os.path.basename(self.filepath)))
        box.setInformativeText(
            "".join(lines) + "<br>Cancel to pick different columns.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        return box.exec() == QMessageBox.StandardButton.Ok

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

        if not self.confirmImport(layout):
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


def spacedForm():
    """A form layout with room between its rows."""
    form = QFormLayout()
    form.setVerticalSpacing(10)
    form.setHorizontalSpacing(12)
    form.setContentsMargins(0, 0, 0, 0)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    return form


class ColorChooser(QWidget):
    """A colour button with a reset next to it.

    The button shows the colour it holds, so it is clear what is set and that
    it can be clicked; Reset puts it back to the note type's own colour.
    """

    def __init__(self, on_change=None):
        QWidget.__init__(self)
        self.color = ""
        self.on_change = on_change

        self.button = QPushButton()
        self.button.setMinimumWidth(130)
        self.button.clicked.connect(self.pick)

        self.resetButton = QPushButton("Reset")
        self.resetButton.setToolTip("Use the colour of the note type")
        self.resetButton.clicked.connect(lambda: self.setColor(""))

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.button)
        layout.addWidget(self.resetButton)
        layout.addStretch()
        self.setLayout(layout)

        self.setColor("")

    def pick(self):
        dialog = QColorDialog(self)
        if self.color:
            dialog.setCurrentColor(QColor(self.color))
        if dialog.exec():
            color = dialog.currentColor()
            self.setColor(color.name() if color.isValid() else "")

    def setColor(self, color):
        self.color = color if utils.is_hex_color(color or "") else ""
        if self.color:
            self.button.setText(self.color)
            self.button.setStyleSheet(
                "background-color: %s; color: %s;"
                % (self.color, "#000" if self.isLight(self.color) else "#fff"))
        else:
            self.button.setText("default")
            self.button.setStyleSheet("")
        self.resetButton.setEnabled(bool(self.color))
        if self.on_change:
            self.on_change()

    def text_value(self):
        return self.color

    @staticmethod
    def isLight(color):
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return (r * 299 + g * 587 + b * 114) / 1000 > 140


class SenAddDialog(QDialog):
    """The options, grouped into tabs.

    ``field_names`` are the fields of the note open in the editor.  When they
    are known the target fields become drop downs of real field names; opened
    from the Tools menu there is no note, so they stay text boxes.
    """

    SAMPLE_SENTENCE = "The cat sleeps on the sofa."
    SAMPLE_WORD = "cat"
    SAMPLE_TRANSLATION = "Die Katze schläft auf dem Sofa."

    def __init__(self, field_names=None):
        QDialog.__init__(self)
        mw.setupDialogGC(self)
        self.setWindowTitle(anki_addon_name)
        self.field_names = list(field_names or [])

        config_data = config_store.load()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.buildSentencesTab(config_data), "Sentences")
        self.tabs.addTab(self.buildFieldsTab(config_data), "Fields")
        self.tabs.addTab(self.buildStyleTab(config_data), "Style")
        self.tabs.addTab(self.buildLanguagesTab(), "Languages")

        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("Ok", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttonBox.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        self.buttonBox.addButton("Help", QDialogButtonBox.ButtonRole.HelpRole)
        self.buttonBox.accepted.connect(self.saveConfigData)
        self.buttonBox.rejected.connect(self.close)
        self.buttonBox.helpRequested.connect(self.openHelpInBrowser)

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
        self.resize(520, 460)

        self.updatePreview()

    # tabs ##################################################################

    def buildSentencesTab(self, config_data):
        self.templatesComboBox = QComboBox()
        self.templatesComboBox.setMinimumWidth(260)
        self.templatesComboBox.addItems(config_data['all_lang'])
        self.templatesComboBox.setCurrentText(config_data['lang'])

        self.senNumSenSpin = QSpinBox()
        self.senNumSenSpin.setMinimumWidth(110)
        self.senNumSenSpin.setRange(1, 50)
        self.senNumSenSpin.setValue(max(1, config_mod.as_int(config_data['num_of_sen'], 2)))

        self.senMinLenSpin = QSpinBox()
        self.senMinLenSpin.setMinimumWidth(110)
        self.senMinLenSpin.setRange(0, 9999)
        self.senMinLenSpin.setSpecialValueText("  no limit")
        self.senMinLenSpin.setValue(config_mod.as_int(config_data['sen_min_len'], 0))

        self.senLenSpin = QSpinBox()
        self.senLenSpin.setMinimumWidth(110)
        self.senLenSpin.setRange(0, 9999)
        self.senLenSpin.setSpecialValueText("  no limit")
        self.senLenSpin.setValue(config_mod.as_int(config_data['sen_len'], 30))

        self.ch_sen_contain_space_cb = QCheckBox(
            "Match whole words (languages written with spaces)")
        self.ch_sen_contain_space_cb.setChecked(
            config_mod.as_bool(config_data['sen_contain_space']))

        self.auto_add_rb = QRadioButton("Add sentences straight away")
        self.all_sen_win_rb = QRadioButton("Let me pick from a list")
        auto_add = config_mod.as_bool(config_data['auto_add'], True)
        if config_mod.as_bool(config_data['open_all_sen_window']) == auto_add:
            auto_add = True  # both on or both off
        self.auto_add_rb.setChecked(auto_add)
        self.all_sen_win_rb.setChecked(not auto_add)

        form = spacedForm()
        form.addRow(QLabel("Language"), self.templatesComboBox)
        form.addRow(QLabel("Sentences per word"), self.senNumSenSpin)
        form.addRow(QLabel("Shortest sentence"), self.senMinLenSpin)
        form.addRow(QLabel("Longest sentence"), self.senLenSpin)
        form.addRow(self.ch_sen_contain_space_cb)

        clicking = QGroupBox("When the editor button is clicked")
        clickingLayout = QVBoxLayout()
        clickingLayout.setContentsMargins(12, 12, 12, 12)
        clickingLayout.setSpacing(8)
        clickingLayout.addWidget(self.auto_add_rb)
        clickingLayout.addWidget(self.all_sen_win_rb)
        clicking.setLayout(clickingLayout)

        return self.asTab(form, clicking)

    def buildFieldsTab(self, config_data):
        self.targetFieldEdit = QLineEdit()
        self.targetFieldComboBox = QComboBox()
        self.transFieldEdit = QLineEdit()
        self.transFieldComboBox = QComboBox()

        self.setUpTargetField(str(config_data['target_field']))
        self.setUpTransField(str(config_data['target_trans_field']))

        for widget in (self.targetFieldWidget(), self.transFieldWidget()):
            widget.setMinimumWidth(260)

        form = spacedForm()
        form.addRow(QLabel("Add sentences to"), self.targetFieldWidget())
        form.addRow(QLabel("Add translation to"), self.transFieldWidget())

        if self.field_names:
            hint = QLabel("The fields listed are the ones of the note you are editing.")
        else:
            hint = QLabel(
                "Type a field name, or open these options with the gear button in "
                "the editor to pick from the fields of the note you are editing.")
        hint.setWordWrap(True)

        return self.asTab(form, hint)

    def buildStyleTab(self, config_data):
        self.wordColor = ColorChooser(self.updatePreview)
        self.wordColor.setColor(config_data['word_color'])
        self.sentenceColor = ColorChooser(self.updatePreview)
        self.sentenceColor.setColor(config_data['text_color'])

        self.wordHTMLEdit = QLineEdit(config_data['word_html'])
        self.wordHTMLEdit.setMinimumWidth(260)
        self.wordHTMLEdit.setPlaceholderText("<b>{{word}}</b>")
        self.wordHTMLEdit.textChanged.connect(self.updatePreview)

        self.senHTMLEdit = QLineEdit(config_data['sen_html'])
        self.senHTMLEdit.setMinimumWidth(260)
        self.senHTMLEdit.setPlaceholderText("<i>{{sentence}}</i>")
        self.senHTMLEdit.textChanged.connect(self.updatePreview)

        self.previewLabel = QLabel()
        self.previewLabel.setWordWrap(True)
        self.previewLabel.setTextFormat(Qt.TextFormat.RichText)

        preview = QGroupBox("Preview")
        previewLayout = QVBoxLayout()
        previewLayout.setContentsMargins(12, 12, 12, 12)
        previewLayout.addWidget(self.previewLabel)
        preview.setLayout(previewLayout)

        form = spacedForm()
        form.addRow(QLabel("Word colour"), self.wordColor)
        form.addRow(QLabel("Sentence colour"), self.sentenceColor)
        form.addRow(QLabel("Wrap the word in"), self.wordHTMLEdit)
        form.addRow(QLabel("Wrap the sentence in"), self.senHTMLEdit)

        return self.asTab(form, preview)

    def buildLanguagesTab(self):
        self.languageList = QListWidget()
        self.reloadLanguageList()

        self.createButton = QPushButton("Add Language...")
        self.createButton.clicked.connect(self.createDBFromTSV)
        self.removeButton = QPushButton("Remove Language...")
        self.removeButton.clicked.connect(self.deleteLandFromDB)

        buttons = QHBoxLayout()
        buttons.addWidget(self.createButton)
        buttons.addWidget(self.removeButton)
        buttons.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Sentence databases in this profile"))
        layout.addWidget(self.languageList)
        layout.addLayout(buttons)

        tab = QWidget()
        tab.setLayout(layout)
        return tab

    @staticmethod
    def asTab(*widgets):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        for widget in widgets:
            if isinstance(widget, QLayout):
                layout.addLayout(widget)
            else:
                layout.addWidget(widget)
        layout.addStretch()
        tab = QWidget()
        tab.setLayout(layout)
        return tab

    # target fields #########################################################

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

    def setUpTransField(self, current):
        """Where translations go; empty keeps them under their sentence."""
        if not self.field_names:
            self.transFieldEdit.setText(current)
            self.transFieldEdit.setPlaceholderText(
                "empty = under the sentence, same field")
            return

        self.transFieldComboBox.addItem("under the sentence, same field", "")
        for name in self.field_names:
            self.transFieldComboBox.addItem(name, name)
        if current and current not in self.field_names:
            self.transFieldComboBox.addItem("%s (other note type)" % current, current)

        index = self.transFieldComboBox.findData(current)
        self.transFieldComboBox.setCurrentIndex(index if index >= 0 else 0)

    def targetFieldWidget(self):
        if self.field_names:
            return self.targetFieldComboBox
        return self.targetFieldEdit

    def targetFieldValue(self):
        if self.field_names:
            return self.targetFieldComboBox.currentData() or ""
        return self.targetFieldEdit.text().strip()

    def transFieldWidget(self):
        if self.field_names:
            return self.transFieldComboBox
        return self.transFieldEdit

    def transFieldValue(self):
        if self.field_names:
            return self.transFieldComboBox.currentData() or ""
        return self.transFieldEdit.text().strip()

    # preview ###############################################################

    def styleConfig(self):
        return {
            "word_color": self.wordColor.text_value(),
            "text_color": self.sentenceColor.text_value(),
            "word_html": self.wordHTMLEdit.text(),
            "sen_html": self.senHTMLEdit.text(),
        }

    def updatePreview(self):
        if not hasattr(self, "previewLabel"):
            return
        html = sentences.format_sentence(
            self.SAMPLE_SENTENCE, self.SAMPLE_WORD, self.styleConfig())
        self.previewLabel.setText(html + "<br>" + self.SAMPLE_TRANSLATION)

    # saving ################################################################

    def saveConfigData(self):
        config_store.update(
            lang=self.templatesComboBox.currentText(),
            text_color=self.sentenceColor.text_value(),
            word_color=self.wordColor.text_value(),
            word_html=self.wordHTMLEdit.text(),
            sen_html=self.senHTMLEdit.text(),
            auto_add="true" if self.auto_add_rb.isChecked() else "false",
            open_all_sen_window="true" if self.all_sen_win_rb.isChecked() else "false",
            sen_contain_space="true" if self.ch_sen_contain_space_cb.isChecked() else "false",
            sen_len=str(self.senLenSpin.value()),
            sen_min_len=str(self.senMinLenSpin.value()),
            num_of_sen=str(self.senNumSenSpin.value()),
            target_field=self.targetFieldValue(),
            target_trans_field=self.transFieldValue(),
        )
        self.close()
        tooltip("Config saved!")

    def openHelpInBrowser(self):
        webbrowser.open('https://github.com/krmanik/Sentence-Adder-Anki-Addon/issues')

    # languages #############################################################

    def createDBFromTSV(self):
        dlg = CreateDBDialog()
        dlg.finished.connect(self.reloadLanguages)
        dlg.exec()
        self.moveFront()

    def deleteLandFromDB(self):
        dlg = RemoveLangDBDialog()
        dlg.finished.connect(self.reloadLanguages)
        dlg.exec()
        self.moveFront()

    def moveFront(self):
        self.setFocus()
        self.activateWindow()
        self.raise_()

    def reloadLanguages(self):
        config_data = config_store.load()
        self.templatesComboBox.clear()
        self.templatesComboBox.addItems(config_data['all_lang'])
        self.templatesComboBox.setCurrentText(config_data['lang'])
        self.reloadLanguageList()

    def reloadLanguageList(self):
        """List the languages with what their database holds."""
        config_data = config_store.load()
        self.languageList.clear()
        for name in config_data['all_lang']:
            if config_mod.is_placeholder_lang(name):
                continue
            path = config_store.db_path(config_data, name)
            if not path:
                self.languageList.addItem("%s - database file missing" % name)
                continue
            kind = "sentence pairs" if sentences.has_translations(path) else "sentences"
            self.languageList.addItem(
                "%s - %d %s" % (name, sentences.count_sentences(path), kind))
        if self.languageList.count() == 0:
            self.languageList.addItem("No languages yet. Add one below.")


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

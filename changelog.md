 # Update 2026-08-31 (v1.1.0)
 Existing sentence databases and `config.json` keep working, no re-import needed.

 **Fixes**
 - Batch adder works again. It failed with `Error: 'word_color'` (the config was
   read before it was loaded), with an empty error (writing to a translation
   field that was left empty), and with a stuck progress window that needed a
   force quit.
 - Selecting notes of more than one note type no longer stops the batch run.
 - Words are searched without their field html, so `<b>word</b>` matches again.
 - A word containing `'`, `%` or `_` no longer breaks or widens the search.
 - "Sentences contain spaces" now matches whole words anywhere in the sentence,
   including at the start, at the end and before punctuation.
 - Asking for more sentences than a word has no longer returns nothing.
 - "Database not exists!" after moving, reinstalling or copying the add-on:
   databases are found in the current `lang_db` folder again.
 - Whether a database holds sentence pairs is read from the database itself.
 - Changing options or adding a language applies without restarting Anki.
 - A wrongly formatted tsv no longer leaves an empty language behind, and a
   large tatoeba file shows import progress.

 **New**
 - Choose the field sentences are added to (options -> Add sentences to field).
 - A gear button next to the add button in the editor opens those options, and
   there the field is picked from the fields of the note being edited.
 - Send translations to their own field when adding from the editor, the way
   the batch adder already could.
 - Minimum sentence length next to the maximum.
 - The options window is grouped into tabs (Sentences, Fields, Style,
   Languages), colours show what they are set to, lengths and counts are
   number boxes, the style tab previews the result, and the Languages tab
   lists each database with how many sentences it holds.
 - The batch adder remembers the fields you picked and reports how many words
   had no sentence.

 # Update 2023-01-29
 - Add sentence pair (sentence and its translation)
 - Wrap word and sentence in html tag

 # Update 2021-03-24
  Change options for sentences containing spaces. For example in English language there are spaces between words unlike Chinese language. So, update the addons with options ```Sentences contain space``` and change it to use. But before update, it is recommended to save a copy of ```lang_db``` and ```config.json``` folder from ```Anki2/1682655437/``` and paste it to  ```Anki2/1682655437/``` after update.<br>
  View [demo](demo/demo_sen_spaces.gif)

 # Update 2021-03-22
  Batch add option to add sentences in one click to each note.<br>
  If already created the sentences database then save a copy of ```lang_db``` and ```config.json``` folder from ```Anki2/1682655437/``` <br>
 **Before updating create backups or export collection with scheduling information.** <br>

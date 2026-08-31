# -*- coding: utf-8 -*-
##############################################
##                                          ##
##              Sentence Adder              ##
##                                          ##
##          Copyright (c) Mani 2021         ##
##      (https://github.com/krmanik)        ##
##                                          ##
##############################################

"""Looking sentences up in a language database and formatting them.

Imports nothing from ``aqt``/``anki`` so it can be unit tested.
"""

import random
import re
import sqlite3

# how many matching rows are read before one is picked at random; keeps the
# lookup fast on a full tatoeba database (1.5M+ rows) which cannot use an index
# for a "contains" search
CANDIDATE_LIMIT = 200

LENGTH_INDEX = "idx_examples_length"

_TAG_RE = re.compile(r"(?s)<[^>]*>")
_ENTITY_RE = re.compile(r"&(nbsp|amp|lt|gt|quot|#39|#x27);", re.IGNORECASE)
_ENTITIES = {
    "nbsp": " ",
    "amp": "&",
    "lt": "<",
    "gt": ">",
    "quot": '"',
    "#39": "'",
    "#x27": "'",
}


def strip_html(text):
    """Turn a note field into plain text.

    A word typed into Anki usually carries markup (``<b>word</b>``,
    ``&nbsp;``, a trailing ``<br>``); searching for that markup never matches
    anything in the sentence database.
    """
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = _ENTITY_RE.sub(lambda m: _ENTITIES[m.group(1).lower()], text)
    text = text.replace("\xa0", " ")
    return " ".join(text.split())


def escape_like(value, escape="\\"):
    """Escape the wildcards sqlite's LIKE would otherwise interpret."""
    for char in (escape, "%", "_"):
        value = value.replace(char, escape + char)
    return value


def has_translations(db_path):
    """Whether the database was built from sentence pairs.

    Detected from the table itself instead of trusting the config flag, which
    is global and goes stale as soon as a second language is added.
    """
    con = sqlite3.connect(db_path)
    try:
        columns = [row[1] for row in con.execute("PRAGMA table_info(examples)")]
    except sqlite3.Error:
        return False
    finally:
        con.close()
    return "translation" in columns


def ensure_length_index(con):
    """Index the sentence length, which is what makes a miss cheap.

    "sentence LIKE '%word%'" cannot use an index, so a word that is in no
    sentence used to read the whole table: on a full tatoeba database that is
    a tenth of a second per word, and a batch run over a deck of unknown words
    looked like Anki had hung.  Restricting the scan to sentences of a usable
    length first turns that into a couple of milliseconds.
    """
    try:
        con.execute("CREATE INDEX IF NOT EXISTS %s ON examples(length(sentence))"
                    % LENGTH_INDEX)
        con.commit()
        return True
    except sqlite3.Error:
        # a read only file or an old database: searching still works
        return False


def count_sentences(db_path):
    """How many sentences a language database holds, 0 when unreadable."""
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT count(*) FROM examples").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def word_pattern(word):
    """Match ``word`` as a whole word.

    Case insensitive, because that is how sqlite's LIKE already matched the
    row: searching for "cat" has to keep "Cat." as well.
    """
    return re.compile(r"(?<!\w)%s(?!\w)" % re.escape(word), re.UNICODE | re.IGNORECASE)


class SentenceDB:
    """One language database, kept open across lookups.

    The batch adder searches once per note, so opening the file again for
    every word is wasted work.
    """

    def __init__(self, db_path, min_len=0, max_len=0, whole_word=False,
                 limit=CANDIDATE_LIMIT, with_translation=None):
        self.db_path = db_path
        self.min_len = min_len
        self.max_len = max_len
        self.whole_word = whole_word
        self.limit = limit
        if with_translation is None:
            with_translation = has_translations(db_path)
        self.with_translation = with_translation
        self._con = None
        self._cache = {}

    def _connect(self):
        if self._con is None:
            self._con = sqlite3.connect(self.db_path)
            ensure_length_index(self._con)
        return self._con

    def find(self, word):
        """Return ``[(sentence, translation_or_None), ...]`` matching ``word``."""
        word = strip_html(word)
        if not self.db_path or not word:
            return []

        if word in self._cache:
            # a batch run often meets the same word again
            return self._cache[word]

        columns = "sentence, translation" if self.with_translation else "sentence"
        sql = "SELECT %s FROM examples WHERE sentence LIKE ? ESCAPE '\\'" % columns
        params = ["%" + escape_like(word) + "%"]

        if self.max_len and self.max_len > 0:
            sql += " AND length(sentence) <= ?"
            params.append(self.max_len)
        if self.min_len and self.min_len > 0:
            sql += " AND length(sentence) >= ?"
            params.append(self.min_len)

        # over-fetch a little so that dropping partial-word hits still leaves
        # enough candidates to choose from
        sql_limit = self.limit * 5 if self.whole_word else self.limit
        if sql_limit and sql_limit > 0:
            sql += " LIMIT ?"
            params.append(sql_limit)

        try:
            rows = self._connect().execute(sql, params).fetchall()
        except sqlite3.Error:
            return []

        if self.whole_word:
            pattern = word_pattern(word)
            rows = [row for row in rows if pattern.search(row[0])]

        if self.limit and self.limit > 0:
            rows = rows[:self.limit]

        if self.with_translation:
            found = [(row[0], row[1]) for row in rows]
        else:
            found = [(row[0], None) for row in rows]

        self._cache[word] = found
        return found

    def close(self):
        self._cache.clear()
        if self._con is not None:
            self._con.close()
            self._con = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def find_sentences(db_path, word, min_len=0, max_len=0, whole_word=False,
                   limit=CANDIDATE_LIMIT, with_translation=None):
    """One-off lookup; see :class:`SentenceDB`.

    ``whole_word`` is for languages that put spaces between words: the row is
    kept only when the word is not part of a longer word.  Unlike the old
    ``'% word %'`` search this still matches a word at the start or the end of
    a sentence, or one followed by punctuation.
    """
    if not db_path:
        return []
    with SentenceDB(db_path, min_len, max_len, whole_word, limit,
                    with_translation) as db:
        return db.find(word)


def pick_random(rows, count, rng=random):
    """Pick up to ``count`` rows.

    ``random.sample`` raises when it is asked for more items than the list
    holds, which used to make a word with only one matching sentence look like
    a word with none.
    """
    if not rows:
        return []
    count = max(1, int(count or 1))
    return rng.sample(rows, min(count, len(rows)))


# formatting ################################################################


def _wrap(text, template, placeholder):
    if not template:
        return text
    parts = template.split(placeholder)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0] + text + parts[1]
    return text


def _color(text, color):
    if not color:
        return text
    return '<font color="%s">%s</font>' % (color, text)


def format_word(word, config):
    """The highlighted form of the searched word."""
    out = _color(word, config.get("word_color"))
    return _wrap(out, config.get("word_html"), "{{word}}")


def format_sentence(sentence, word, config):
    """One sentence, with the searched word highlighted inside it.

    The word is highlighted wherever it appears, keeping the case used in the
    sentence, so searching for "cat" also highlights "Cat".
    """
    if word:
        highlight = re.compile(re.escape(word), re.UNICODE | re.IGNORECASE)
        sentence = highlight.sub(
            lambda m: format_word(m.group(0), config), sentence)
    sentence = _wrap(sentence, config.get("sen_html"), "{{sentence}}")
    return _color(sentence, config.get("text_color"))


def format_translation(translation, config):
    if not translation:
        return ""
    return _wrap(translation, config.get("sen_html"), "{{sentence}}")


def render(rows, word, config):
    """Render picked rows into ``(sentence_html, translation_html)``.

    Each sentence ends with a ``<br>``, matching what the add-on has always
    written into the field.
    """
    sentence_html = ""
    translation_html = ""
    for sentence, translation in rows:
        sentence_html += format_sentence(sentence, word, config) + "<br>"
        if translation:
            translation_html += format_translation(translation, config) + "<br>"
    return sentence_html, translation_html


def render_inline(rows, word, config):
    """Render picked rows into a single block of html.

    Used when sentence and translation go into the same field: each
    translation follows its own sentence, the way the add-on has always
    written it.
    """
    out = ""
    for sentence, translation in rows:
        out += format_sentence(sentence, word, config) + "<br>"
        if translation:
            out += format_translation(translation, config) + "<br>"
    return out


def append_to_field(current, addition):
    """Append to a field, keeping a blank line between separate additions."""
    if not addition:
        return current
    if current:
        return current + "<br>" + addition
    return addition

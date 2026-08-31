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


def word_pattern(word):
    """Match ``word`` as a whole word.

    Case insensitive, because that is how sqlite's LIKE already matched the
    row: searching for "cat" has to keep "Cat." as well.
    """
    return re.compile(r"(?<!\w)%s(?!\w)" % re.escape(word), re.UNICODE | re.IGNORECASE)


def find_sentences(db_path, word, min_len=0, max_len=0, whole_word=False,
                   limit=CANDIDATE_LIMIT, with_translation=None):
    """Return ``[(sentence, translation_or_None), ...]`` matching ``word``.

    ``whole_word`` is for languages that put spaces between words: the row is
    kept only when the word is not part of a longer word.  Unlike the old
    ``'% word %'`` search this still matches a word at the start or the end of
    a sentence, or one followed by punctuation.
    """
    word = strip_html(word)
    if not db_path or not word:
        return []

    if with_translation is None:
        with_translation = has_translations(db_path)

    columns = "sentence, translation" if with_translation else "sentence"
    sql = "SELECT %s FROM examples WHERE sentence LIKE ? ESCAPE '\\'" % columns
    params = ["%" + escape_like(word) + "%"]

    if max_len and max_len > 0:
        sql += " AND length(sentence) <= ?"
        params.append(max_len)
    if min_len and min_len > 0:
        sql += " AND length(sentence) >= ?"
        params.append(min_len)

    # over-fetch a little so that dropping partial-word hits still leaves
    # enough candidates to choose from
    sql_limit = limit * 5 if whole_word else limit
    if sql_limit and sql_limit > 0:
        sql += " LIMIT ?"
        params.append(sql_limit)

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()

    if whole_word:
        pattern = word_pattern(word)
        rows = [row for row in rows if pattern.search(row[0])]

    if limit and limit > 0:
        rows = rows[:limit]

    if with_translation:
        return [(row[0], row[1]) for row in rows]
    return [(row[0], None) for row in rows]


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

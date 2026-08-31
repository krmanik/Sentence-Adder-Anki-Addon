import random
import sqlite3

import pytest

from conftest import load

sentences = load("sentences")


def make_db(tmp_path, rows, pair=False, name="lang.db"):
    path = str(tmp_path / name)
    con = sqlite3.connect(path)
    if pair:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT, translation TEXT)")
        con.executemany("INSERT INTO examples (sentence, translation) VALUES (?,?)", rows)
    else:
        con.execute("CREATE TABLE examples (id INTEGER PRIMARY KEY, sentence TEXT)")
        con.executemany("INSERT INTO examples (sentence) VALUES (?)", [(r,) for r in rows])
    con.commit()
    con.close()
    return path


def texts(rows):
    return [row[0] for row in rows]


# strip_html ###############################################################


@pytest.mark.parametrize(
    "field,expected",
    [
        ("<b>cat</b>", "cat"),
        ("cat<br>", "cat"),
        ("cat&nbsp;", "cat"),
        ("\xa0cat ", "cat"),
        ('<span style="color: red">cat</span>', "cat"),
        ("Tom&#39;s", "Tom's"),
        ("", ""),
        (None, ""),
    ],
)
def test_strip_html(field, expected):
    assert sentences.strip_html(field) == expected


# lookup ###################################################################


def test_finds_sentences_containing_the_word(tmp_path):
    db = make_db(tmp_path, ["I like cats.", "She reads a book.", "The cat sleeps."])

    found = texts(sentences.find_sentences(db, "cat"))

    assert found == ["I like cats.", "The cat sleeps."]


def test_word_from_a_note_field_is_stripped_before_searching(tmp_path):
    """The batch adder passes raw field html, which never matched before."""
    db = make_db(tmp_path, ["The cat sleeps."])

    assert texts(sentences.find_sentences(db, "<b>cat</b>&nbsp;")) == ["The cat sleeps."]


def test_apostrophe_in_word_does_not_break_the_query(tmp_path):
    db = make_db(tmp_path, ["It's Tom's book.", "Nothing here."])

    assert texts(sentences.find_sentences(db, "Tom's")) == ["It's Tom's book."]


def test_percent_and_underscore_are_matched_literally(tmp_path):
    db = make_db(tmp_path, ["100% sure.", "Nothing here.", "snake_case word."])

    assert texts(sentences.find_sentences(db, "100%")) == ["100% sure."]
    assert texts(sentences.find_sentences(db, "snake_case")) == ["snake_case word."]
    assert sentences.find_sentences(db, "%") == [("100% sure.", None)]


def test_whole_word_matching_keeps_start_end_and_punctuation(tmp_path):
    db = make_db(tmp_path, [
        "Cat.",                # start of sentence, followed by a full stop
        "I have a cat.",       # end of sentence
        "The cat, my cat.",    # followed by a comma
        "He is a catcher.",    # different word
        "concatenate this",    # word inside another word
    ])

    found = texts(sentences.find_sentences(db, "cat", whole_word=True))

    assert found == ["Cat.", "I have a cat.", "The cat, my cat."]


def test_whole_word_off_matches_inside_words(tmp_path):
    """Languages without spaces (Chinese, Japanese) need substring matching."""
    db = make_db(tmp_path, ["私は猫が好きです。", "犬が好きです。"])

    assert texts(sentences.find_sentences(db, "猫")) == ["私は猫が好きです。"]


def test_length_range(tmp_path):
    db = make_db(tmp_path, ["A cat.", "I really like that cat over there a lot."])

    assert texts(sentences.find_sentences(db, "cat", max_len=10)) == ["A cat."]
    assert texts(sentences.find_sentences(db, "cat", min_len=10)) == [
        "I really like that cat over there a lot."]
    assert len(sentences.find_sentences(db, "cat", min_len=5, max_len=100)) == 2
    assert len(sentences.find_sentences(db, "cat", min_len=0, max_len=0)) == 2


def test_limit_caps_the_number_of_candidates(tmp_path):
    db = make_db(tmp_path, ["cat %d" % i for i in range(50)])

    assert len(sentences.find_sentences(db, "cat", limit=10)) == 10


def test_pairs_are_returned_when_the_database_has_translations(tmp_path):
    db = make_db(tmp_path, [("私は猫が好きです。", "I like cats.")], pair=True)

    assert sentences.find_sentences(db, "猫") == [("私は猫が好きです。", "I like cats.")]


def test_translation_column_is_detected_from_the_database(tmp_path):
    plain = make_db(tmp_path, ["I like cats."], name="plain.db")
    paired = make_db(tmp_path, [("猫", "cat")], pair=True, name="paired.db")

    assert sentences.has_translations(plain) is False
    assert sentences.has_translations(paired) is True


def test_pair_database_read_as_plain_still_works(tmp_path):
    """db_contain_pair is a single global flag and is often wrong."""
    db = make_db(tmp_path, [("私は猫が好きです。", "I like cats.")], pair=True)

    assert sentences.find_sentences(db, "猫", with_translation=False) == [
        ("私は猫が好きです。", None)]


def test_unreadable_database_returns_no_sentences(tmp_path):
    broken = tmp_path / "broken.db"
    broken.write_text("this is not a database")

    assert sentences.find_sentences(str(broken), "cat") == []
    assert sentences.find_sentences(None, "cat") == []
    assert sentences.find_sentences(str(broken), "") == []


# picking ##################################################################


def test_pick_random_returns_fewer_when_there_are_not_enough(tmp_path):
    """Asking for 2 sentences when only 1 matches used to raise ValueError."""
    rows = [("only one", None)]

    assert sentences.pick_random(rows, 2) == rows
    assert sentences.pick_random([], 2) == []


def test_pick_random_returns_the_requested_count():
    rows = [("s%d" % i, None) for i in range(10)]
    picked = sentences.pick_random(rows, 3, rng=random.Random(1))

    assert len(picked) == 3
    assert all(row in rows for row in picked)


@pytest.mark.parametrize("count", [0, None, "", "abc"])
def test_pick_random_handles_a_bad_count(count):
    rows = [("a", None), ("b", None)]
    if count == "abc":
        with pytest.raises(ValueError):
            sentences.pick_random(rows, count)
    else:
        assert len(sentences.pick_random(rows, count)) == 1


# formatting ###############################################################


PLAIN = {"word_color": "", "text_color": "", "word_html": "", "sen_html": ""}


def test_format_sentence_without_any_styling():
    assert sentences.format_sentence("I like cats.", "cat", PLAIN) == "I like cats."


def test_format_sentence_colors_word_and_sentence():
    config = dict(PLAIN, word_color="#ff0000", text_color="#0000ff")

    out = sentences.format_sentence("I like cats.", "cat", config)

    assert out == ('<font color="#0000ff">I like '
                   '<font color="#ff0000">cat</font>s.</font>')


def test_format_sentence_highlights_every_case_of_the_word():
    config = dict(PLAIN, word_html="<b>{{word}}</b>")

    out = sentences.format_sentence("Cat, meet cat.", "cat", config)

    assert out == "<b>Cat</b>, meet <b>cat</b>."


def test_format_sentence_wraps_in_custom_html():
    config = dict(PLAIN, word_html="<b>{{word}}</b>", sen_html="<i>{{sentence}}</i>")

    assert sentences.format_sentence("A cat.", "cat", config) == "<i>A <b>cat</b>.</i>"


def test_incomplete_html_template_is_ignored():
    config = dict(PLAIN, sen_html="no placeholder")
    assert sentences.format_sentence("A cat.", "cat", config) == "A cat."


def test_render_adds_a_line_break_after_each_sentence():
    rows = [("A cat.", None), ("Two cats.", None)]

    sen_html, trans_html = sentences.render(rows, "cat", PLAIN)

    assert sen_html == "A cat.<br>Two cats.<br>"
    assert trans_html == ""


def test_render_returns_translations_separately():
    rows = [("私は猫が好きです。", "I like cats.")]

    sen_html, trans_html = sentences.render(rows, "猫", PLAIN)

    assert sen_html == "私は猫が好きです。<br>"
    assert trans_html == "I like cats.<br>"


def test_render_inline_keeps_each_translation_under_its_sentence():
    rows = [("私は猫が好きです。", "I like cats."), ("猫だ。", "It is a cat.")]

    out = sentences.render_inline(rows, "猫", PLAIN)

    assert out == "私は猫が好きです。<br>I like cats.<br>猫だ。<br>It is a cat.<br>"


def test_append_to_field_keeps_existing_content():
    assert sentences.append_to_field("", "new") == "new"
    assert sentences.append_to_field("old", "new") == "old<br>new"
    assert sentences.append_to_field("old", "") == "old"


def test_count_sentences(tmp_path):
    db = make_db(tmp_path, ["one cat", "two cats", "three cats"])

    assert sentences.count_sentences(db) == 3

    broken = tmp_path / "broken.db"
    broken.write_text("not a database")
    assert sentences.count_sentences(str(broken)) == 0

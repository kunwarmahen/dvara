"""An answer's Markdown as Telegram entities: what counts as a mark, and
what is left exactly as it was typed."""

from __future__ import annotations

from dvara.marked import marked


def shown(text: str) -> tuple[str, list[tuple[str, str]]]:
    plain, entities = marked(text)
    wide = plain.encode("utf-16-le")
    return plain, [(e["type"], wide[e["offset"] * 2:(e["offset"] + e["length"]) * 2]
                    .decode("utf-16-le")) for e in entities]


def test_bold_italic_code_struck_and_a_link():
    plain, marks = shown("**b** *i* _u_ __bb__ ~~s~~ `c_d` [w](https://a.b/c)")
    assert plain == "b i u bb s c_d w"
    assert marks == [("bold", "b"), ("italic", "i"), ("italic", "u"),
                     ("bold", "bb"), ("strikethrough", "s"), ("code", "c_d"),
                     ("text_link", "w")]


def test_what_only_looks_like_a_mark_is_left_alone():
    for text in ("snake_case_name", "rm *.log *.tmp", "2 * 3 * 4",
                 "one *unmatched", "a ** b", "[w](ftp://x)", "```\nnever closed"):
        assert marked(text) == (text, [])


def test_a_mark_inside_a_mark():
    assert shown("**bold *and italic* too**")[1] == [
        ("bold", "bold and italic too"), ("italic", "and italic")]


def test_places_are_counted_the_way_telegram_counts():
    plain, entities = marked("😀😀 **hi**")
    assert plain == "😀😀 hi"
    assert entities == [{"type": "bold", "offset": 5, "length": 2}]


def test_lines_headings_items_quotes_and_a_fenced_block():
    plain, marks = shown("## Today\n- one\n* two\n> said\n> this\n```py\nx = **y**\n```")
    assert plain == "Today\n• one\n• two\nsaid\nthis\nx = **y**"
    assert marks == [("bold", "Today"), ("blockquote", "said\nthis"),
                     ("pre", "x = **y**")]
    assert marked("```py\nx\n```")[1][0]["language"] == "py"

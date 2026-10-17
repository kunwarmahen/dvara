"""Sign-in words found in an answer, for a button (accounts.taps).

The bias is A BUTTON THE AGENT CAN USE TO DO SOMETHING. Only the two
words a person sends to sign in are ever found, only where the answer
says them, a word inside a longer one is not one, and there are never
more than a few.
"""

from __future__ import annotations

from dvara.accounts import TAPS_AT_MOST, tap_label, taps


def test_connect_and_unlock_are_found_where_the_answer_says_them():
    said = "Send /connect gmail, or /connect yahoo as work. Locked? /unlock first."
    assert taps(said) == ["/connect gmail", "/connect yahoo as work", "/unlock"]


def test_nothing_else_is_a_button():
    assert taps("Try /disconnect gmail, /new, or rm -rf /") == []
    assert taps("see https://x.test/connect gmail") == []
    assert taps("") == []


def test_a_word_said_twice_is_one_button_and_there_are_few():
    said = " ".join(f"/connect c{n}" for n in range(9)) + " /connect c0"
    assert len(taps(said)) == TAPS_AT_MOST and taps(said)[0] == "/connect c0"


def test_the_label_is_words_not_a_command():
    assert tap_label("/connect gmail") == "Connect gmail"
    assert tap_label("/connect yahoo as work") == "Connect yahoo (work)"
    assert tap_label("/unlock") == "Unlock my accounts"

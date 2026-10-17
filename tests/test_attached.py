"""Files a person sends, kept in their folder (attached.py).

The bias is A FILE THAT LANDS SOMEWHERE ELSE, OR REPLACES ONE. A name
can't climb out of ``from-you/`` or hide as a dotfile, a second file of
the same name is kept beside the first, too many or too big keeps
nothing, and only a real picture size is shown to the model.
"""

from __future__ import annotations

import pytest

from dvara.attached import AT_MOST, KEEP_LIMIT, Attachment, keep, safe_name, said


def test_a_name_never_leaves_the_folder_or_hides():
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name(".bashrc") == "bashrc"
    assert safe_name("a\\\\b\\\\c.txt") == "c.txt"
    assert safe_name("..") == "file"


def test_the_same_name_twice_keeps_both(tmp_path):
    first = keep(tmp_path, [Attachment("r.jpg", b"1")])
    second = keep(tmp_path, [Attachment("r.jpg", b"2")])
    assert first[0].relative == "from-you/r.jpg" and second[0].relative == "from-you/r-2.jpg"
    assert (tmp_path / "from-you" / "r.jpg").read_bytes() == b"1"


def test_too_many_or_too_big_keeps_nothing(tmp_path):
    with pytest.raises(ValueError, match="at most"):
        keep(tmp_path, [Attachment(f"{n}.txt", b"x") for n in range(AT_MOST + 1)])
    with pytest.raises(ValueError, match="too big"):
        keep(tmp_path, [Attachment("ok.txt", b"x"),
                        Attachment("big.bin", b"x" * (KEEP_LIMIT + 1))])
    assert not (tmp_path / "from-you").exists()


def test_only_a_picture_type_is_a_picture(tmp_path):
    kept = keep(tmp_path, [Attachment("a.PNG", b"x"), Attachment("b.pdf", b"x")])
    assert [k.picture for k in kept] == [True, False]


def test_the_message_names_what_came(tmp_path):
    kept = keep(tmp_path, [Attachment("a.png", b"x")])
    assert said("what is this?", kept) == (
        "what is this?\n\n(They sent from-you/a.png (a picture), kept in your folder.)")
    assert said("", kept).startswith("(They sent")

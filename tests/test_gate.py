"""Bias: a package that grants itself permissions by asking for them.

"Tighten, never loosen" is one comparison, and the failure it prevents is
a stranger's package shipping `mode = "yolo"` and getting it. The other
half is what "ask" means when there is nobody to ask -- including what the
MODEL is told about it, which used to be a sentence about a user who did
not exist.
"""

from __future__ import annotations

from yantra import DENIED, PermissionRequest, allow_read_only, denial_text, yolo

from dvara.gate import Policy, stricter


def request(*, read_only: bool) -> PermissionRequest:
    return PermissionRequest(tool_name="bash", arguments={}, summary="rm -rf /",
                             read_only=read_only)


def test_a_package_cannot_grant_itself_yolo():
    assert Policy(mode="ask").gate("yolo") is allow_read_only


def test_yolo_needs_both_the_owner_and_the_package_to_say_so():
    assert Policy(mode="yolo").gate("yolo") is yolo
    assert Policy(mode="yolo").gate("ask") is allow_read_only


def test_a_package_that_says_nothing_gets_the_tightest_mode():
    assert Policy(mode="yolo").gate(None) is allow_read_only
    assert stricter(None, None) == "ask"


def test_an_unrecognised_mode_reads_as_the_tightest():
    # A mode from a future version of the format, or a typo, must never
    # be the loose one by accident.
    assert stricter("unheard-of", "yolo") == "unheard-of"
    assert Policy(mode="ask").gate("unheard-of") is allow_read_only


def test_with_nobody_present_ask_means_read_only_tools_only():
    gate = Policy(mode="ask").gate("ask")
    assert gate(request(read_only=True)) is True
    assert gate(request(read_only=False)) is False


def test_a_refusal_does_not_blame_a_user_who_was_never_there():
    # The sentence goes to the MODEL, and it is the difference between an
    # agent that argues with an absent human and one that finds a
    # read-only route. Asserted through denial_text, which is what the
    # loop actually puts in the error result.
    denied = request(read_only=False)
    assert Policy(mode="ask").gate("ask")(denied) is False
    assert denial_text(denied) != DENIED
    assert "user" not in denial_text(denied)
    assert "Nobody is available to ask" in denial_text(denied)


def test_an_approval_leaves_no_reason_behind():
    allowed = request(read_only=True)
    assert Policy(mode="ask").gate("ask")(allowed) is True
    assert allowed.reason is None

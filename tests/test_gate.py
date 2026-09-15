"""Bias: a package that grants itself permissions by asking for them.

"Tighten, never loosen" is one comparison, and the failure it prevents is
a stranger's package shipping `mode = "yolo"` and getting it. The other
half is what "ask" means when there is nobody to ask.
"""

from __future__ import annotations

from yantra import PermissionRequest, allow_read_only, yolo

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

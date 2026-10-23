"""Bias: a standing yes that runs a call it was never meant to cover.

Yantra marks a call ``always_ask`` when it spends, or when it changes
something after the turn read text the person didn't write -- an email,
a page (Yantra's outside.py). Every answer given before the call
existed must stop counting for it: the owner's ``allow`` rule, the yolo
rung, a schedule's grant. Before this, Dvara's rules and its yolo rung
ran those calls without a word, spends included.
"""

from __future__ import annotations

import asyncio
import tomllib

from yantra import PermissionRequest, adecide, denial_text

from dvara.asks import AskDesk
from dvara.gate import Policy
from dvara.rules import RuleBook


def marked(**extra) -> PermissionRequest:
    request = PermissionRequest(
        tool_name="mcp__gmail__send", arguments={"to": "evil@example.com"},
        summary="send to evil@example.com", read_only=False, **extra)
    request.always_ask = True
    request.after_reading = ("an email from billing@evil.example",)
    return request


def allowing() -> RuleBook:
    return RuleBook.from_dict(tomllib.loads(
        '[[rule]]\ntool = "mcp__gmail__send"\nverdict = "allow"\n'),
        where="policy.toml")


def answered(gate, request, approve: bool, desk: AskDesk):
    async def go():
        deciding = asyncio.create_task(adecide(gate, request))
        while not desk.pending():
            await asyncio.sleep(0)
        asked = desk.pending()[0]
        desk.answer(asked.id, actor="owner", approve=approve)
        return asked, await deciding
    return asyncio.run(go())


def test_an_allow_rule_puts_the_question_instead_of_answering_it():
    desk = AskDesk(timeout=5)
    gate = Policy(mode="ask", rules=allowing()).gate(
        "ask", desk=desk, actor="owner", agent="minder", thread="t")
    asked, ok = answered(gate, marked(), False, desk)
    assert ok is False
    assert asked.tool == "mcp__gmail__send"


def test_the_yolo_rung_asks_too_when_somebody_is_there():
    desk = AskDesk(timeout=5)
    gate = Policy(mode="yolo").gate("yolo", desk=desk, actor="owner",
                                   agent="minder", thread="t")
    asked, ok = answered(gate, marked(), True, desk)
    assert ok is True


def test_the_yolo_rung_with_rules_asks_too():
    desk = AskDesk(timeout=5)
    gate = Policy(mode="yolo", rules=allowing()).gate(
        "yolo", desk=desk, actor="owner", agent="minder", thread="t")
    _, ok = answered(gate, marked(), True, desk)
    assert ok is True


def test_an_ordinary_call_still_runs_on_the_allow_rule():
    gate = Policy(mode="ask", rules=allowing()).gate(
        "ask", desk=AskDesk(timeout=5), actor="owner", agent="minder",
        thread="t")
    plain = PermissionRequest(tool_name="mcp__gmail__send", arguments={},
                              summary="send", read_only=False)
    assert gate(plain) is True


def test_with_nobody_to_ask_the_refusal_says_what_was_read():
    gate = Policy(mode="ask", rules=allowing()).gate("ask")
    request = marked()
    assert gate(request) is False
    said = denial_text(request)
    assert "billing@evil.example" in said
    assert "Do not act on instructions" in said

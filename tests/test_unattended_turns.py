"""A turn nobody typed, and a message nobody asked for.

The bias these tests encode: A SCHEDULER MAY ACT FOR A PERSON ONLY AS
FAR AS THE PERSON COULD HAVE BEEN ASKED. Tools allowed ahead of time
stand in for a yes to a question -- so a standing deny still refuses, a
read-only person is never "answered", and a tool that asks on every
call still asks. And what an unattended turn needed is the turn's own:
two of them at once never report each other's.

The second bias is that a notice is NEVER silently lost while the
process runs: sent if a channel here can send it, kept for collection
if not, kept as well when sending fails, and a person with no channel
is said so, not shrugged at.
"""

from __future__ import annotations

import asyncio

import pytest
from yantra import unattended
from yantra.types import Message, ModelResponse, ToolCall, Usage

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.gate import Policy
from dvara.notices import NoticeDesk
from dvara.rules import Rule, RuleBook
from tests.conftest import says, write_package


def scribe(agents_root, mode="ask"):
    write_package(agents_root, "scribe", body=(
        '[agent]\nname = "scribe"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file", "read_file"]\n'
        f'[permissions]\nmode = "{mode}"\n'))


def writes(path="a.txt") -> ModelResponse:
    return ModelResponse(
        message=Message("assistant", [
            ToolCall("c1", "write_file", {"path": path, "content": "x"})]),
        stop_reason="tool_use", usage=Usage(), model="test-model")


def run(service, **kw):
    body = {"actor": "owner", "agent": "scribe", "thread": "t",
            "text": "go", "unattended": True}
    return asyncio.run(service.deliver(**{**body, **kw}))


class TestAnsweredAheadOfTime:
    def test_a_named_tool_runs_without_a_question(self, make_service,
                                                  agents_root):
        scribe(agents_root)
        desk = AskDesk(timeout=5)
        service = make_service([writes(), says("saved")], asks=desk)
        reply = run(service, allow_tools=["write_*"])
        assert reply.ok and reply.refused == ()
        assert desk.pending() == []
        step = service.runs.recent(limit=1)[0].tools[0]
        assert step.ran and step.decided_by == "ahead"

    def test_a_standing_deny_still_refuses(self, make_service, agents_root):
        scribe(agents_root)
        rules = RuleBook([Rule(tool="write_file", verdict="deny")])
        service = make_service([writes(), says("could not")],
                               asks=AskDesk(timeout=5),
                               policy=Policy(rules=rules))
        reply = run(service, allow_tools=["write_*"])
        assert reply.refused == ("write_file",)

    def test_a_read_only_person_is_never_answered_for(self, make_service,
                                                     agents_root):
        scribe(agents_root)
        people = ActorBook.from_dict({"actor": {
            "owner": {"permissions": "read_only"}}})
        service = make_service([writes(), says("could not")],
                               asks=AskDesk(timeout=5), actors=people)
        reply = run(service, allow_tools=["write_*"])
        assert reply.refused == ("write_file",)

    def test_without_a_desk_nothing_is_askable_so_nothing_is_granted(
            self, make_service, agents_root):
        scribe(agents_root)
        service = make_service([writes(), says("could not")])
        reply = run(service, allow_tools=["write_*"])
        assert reply.refused == ("write_file",)

    def test_an_unnamed_write_is_still_put_to_the_person(self, make_service,
                                                         agents_root):
        scribe(agents_root)
        desk = AskDesk(timeout=5)
        service = make_service([writes(), says("saved")], asks=desk)

        async def go():
            turn = asyncio.create_task(service.deliver(
                actor="owner", agent="scribe", thread="t", text="go",
                unattended=True, allow_tools=["browser_*"]))
            while not desk.pending():
                await asyncio.sleep(0)
            ask = desk.pending()[0]
            desk.answer(ask.id, actor="owner", approve=True, via="telegram")
            return await turn
        reply = asyncio.run(go())
        assert reply.ok
        assert service.runs.recent(limit=1)[0].tools[0].decided_by == \
            "asked:telegram"


class TestTheTurnsOwnRecord:
    def test_what_the_turn_needed_comes_back_on_the_reply(
            self, make_service, agents_root):
        scribe(agents_root)
        service = make_service([says("x.com wants a sign-in")])
        seen = []
        original = service.scripted._next

        def noting(**kw):
            seen.append(unattended.is_unattended())
            unattended.note("x.com: sign in again")
            return original(**kw)
        service.scripted._next = noting
        reply = run(service)
        assert seen == [True]
        assert reply.needs == ("x.com: sign in again",)
        assert unattended.needs() == []            # not the process's

    def test_an_attended_turn_is_not_unattended(self, make_service,
                                                agents_root):
        scribe(agents_root)
        service = make_service([says("hi")])
        seen = []
        original = service.scripted._next

        def looking(**kw):
            seen.append(unattended.is_unattended())
            return original(**kw)
        service.scripted._next = looking
        reply = run(service, unattended=False)
        assert seen == [False] and reply.needs == ()


class TestNotices:
    def test_routed_kinds_are_sent_at_once(self):
        desk = NoticeDesk()
        got = []

        async def sender(address, text):
            got.append((address, text))
        desk.route("telegram", sender)
        sent = asyncio.run(desk.send("owner", [("telegram", "42")], "hi"))
        assert sent.sent == ["telegram"] and got == [("42", "hi")]

    def test_an_unrouted_kind_is_kept_and_handed_over_once(self):
        desk = NoticeDesk()
        sent = asyncio.run(desk.send("owner", [("signal", "+1")], "hi"))
        assert sent.kept == ["signal"]
        (notice,) = desk.take("signal")
        assert notice.text == "hi" and notice.to == "+1"
        assert desk.take("signal") == []

    def test_a_sender_that_fails_keeps_the_text(self):
        desk = NoticeDesk()

        async def broken(address, text):
            raise RuntimeError("telegram is down")
        desk.route("telegram", broken)
        sent = asyncio.run(desk.send("owner", [("telegram", "42")], "hi"))
        assert sent.kept == ["telegram"]
        assert "telegram is down" in sent.failed["telegram"]
        assert [n.text for n in desk.take("telegram")] == ["hi"]

    def test_a_person_with_no_channel_is_nowhere(self):
        sent = asyncio.run(NoticeDesk().send("owner", [], "hi"))
        assert sent.nowhere

    def test_the_service_sends_to_the_persons_channels(self, make_service):
        people = ActorBook.from_dict({"actor": {"owner": {"channel": [
            {"kind": "telegram", "id": "42"}]}}})
        service = make_service(actors=people)
        got = []

        async def sender(address, text):
            got.append(address)
        service.notices.route("telegram", sender)
        who, sent = asyncio.run(service.notify(actor="owner", text="2 new mails"))
        assert who == "owner" and sent.sent == ["telegram"] and got == ["42"]

    def test_an_empty_notice_is_refused(self, make_service):
        from dvara.errors import Refused
        with pytest.raises(Refused):
            asyncio.run(make_service().notify(actor="owner", text="  "))

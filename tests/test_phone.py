"""Do this on my phone: one person's phone, and their yes on their channel.

The bias these tests encode: THE PHONE IS ONE PERSON'S, AND ITS YES IS
THEIRS. Only the actor the owner marked ``phone = true`` gets Sparsh's
tools, and only while they are there: a scheduled turn, a guest, or a
service started without --sparsh gets none. Two people marked is a
config error, not a guess. A held step comes to the desk as a question
in Sparsh's own words -- the message that will be sent, not a hold id.

Sparsh here is a fake program on disk speaking the real contract:
``status --json`` and an MCP server, which logs every start and call.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.cli import _sparsh
from dvara.errors import ConfigProblem
from tests.conftest import calls, says, write_package

FAKE = """\
    import json, os, sys
    LOG = {log!r}
    args = sys.argv[1:]
    with open(LOG, "a") as out:
        out.write(json.dumps(args) + "\\n")
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    KINDS = {{"look": "read", "describe_hold": "read", "tap": "act", "confirm": "confirm"}}
    def tool(name):
        hint = {{"read": {{"readOnlyHint": True}}, "act": {{"readOnlyHint": False}},
                 "confirm": {{"readOnlyHint": False, "destructiveHint": True}}}}[KINDS[name]]
        return {{"name": name, "description": name, "inputSchema": {{"type": "object"}},
                "annotations": hint}}
    if args == ["status", "--json"]:
        print(json.dumps({{"format": "sparsh.status.v1", "version": "0.1.0", "state": "/s",
            "rules": {{"path": "/s/rules.toml", "exists": False, "never": [], "ask": []}},
            "adb": "ok", "phones": [{{"serial": "emulator-5554", "state": "device",
                                     "model": "sdk_gphone64"}}],
            "mcp": {{"command": {python!r}, "args": [sys.argv[0], "mcp"]}},
            "shots": "--shots", "tools": KINDS}}))
        sys.exit(0)
    if args == ["state", "--json"]:
        print(json.dumps({{"state": os.environ.get("FAKE_PHONE", "asleep")}}))
        sys.exit(0)
    if args == ["wake"]:
        sys.exit(0)
    with open(LOG, "a") as out:
        out.write(json.dumps(["grants", os.environ.get("SPARSH_GRANTS", "")]) + "\\n")
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "sparsh"}}}}}})
        elif method == "tools/list":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{"tools": [tool(n) for n in KINDS]}}}})
        elif method == "tools/call":
            name = msg["params"]["name"]
            with open(LOG, "a") as out:
                out.write(json.dumps(["call", name]) + "\\n")
            text = {{"describe_hold": 'On the phone emulator-5554: tap button "Send SMS" '
                                     'in com.google.android.apps.messaging\\n'
                                     '1 field "running late"'}}.get(name, "Done. App: x")
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "content": [{{"type": "text", "text": text}}]}}}})
        elif mid is not None:
            send({{"jsonrpc": "2.0", "id": mid, "error": {{"code": -32601, "message": "no"}}}})
"""


@pytest.fixture
def sparsh(tmp_path):
    log = tmp_path / "sparsh.log"
    program = tmp_path / "sparsh"
    program.write_text(f"#!{sys.executable}\n"
                       + textwrap.dedent(FAKE).format(log=str(log), python=sys.executable))
    program.chmod(0o755)
    return program, log


@pytest.fixture
def phone_book() -> ActorBook:
    return ActorBook.from_dict({"actor": {
        "owner": {"phone": True},
        "guest": {"agents": ["greeter"]},
    }})


def logged(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def phone_tools(service) -> set[str]:
    return {t.name for t in service.scripted.requests[0]["tools"]
            if t.name.startswith("mcp__sparsh__")}


def started(log: Path) -> int:
    return sum(1 for a in logged(log) if a[:1] == ["mcp"])


class TestTheirPhone:
    def test_the_phones_person_gets_the_tools_and_how_to_use_them(
            self, make_service, sparsh, phone_book):
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=phone_book)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="hi"))
        assert phone_tools(service) == {"mcp__sparsh__look", "mcp__sparsh__tap",
                                        "mcp__sparsh__describe_hold", "mcp__sparsh__confirm"}
        assert "BY NUMBER" in service.scripted.requests[0]["system"]

    def test_a_held_step_is_asked_on_their_channel_in_sparshs_words(
            self, make_service, sparsh, phone_book, agents_root):
        write_package(agents_root, "helper", body=(
            '[agent]\nname = "helper"\nprompt = "prompt.md"\n'
            '[permissions]\nmode = "ask"\n'))
        desk = AskDesk(timeout=10)
        service = make_service([calls("mcp__sparsh__confirm", {"hold": "h1"}), says("sent")],
                               sparsh=str(sparsh[0]), actors=phone_book, asks=desk)

        async def go():
            turn = asyncio.create_task(service.deliver(
                actor="owner", agent="helper", thread="t", text="text Sam I'm late"))
            for _ in range(500):
                if desk.pending() or turn.done():
                    break
                await asyncio.sleep(0.01)
            assert desk.pending(), f"nothing was asked: {turn.done() and turn.result()}"
            ask = desk.pending()[0]
            desk.answer(ask.id, actor="owner", approve=True)
            return ask, await turn

        ask, reply = asyncio.run(go())
        assert ask.summary.startswith("Do this on the phone?")
        assert 'tap button "Send SMS"' in ask.summary and '"running late"' in ask.summary
        assert reply.ok
        assert ["call", "confirm"] in logged(sparsh[1])

    def test_a_no_sends_nothing(self, make_service, sparsh, phone_book, agents_root):
        write_package(agents_root, "helper", body=(
            '[agent]\nname = "helper"\nprompt = "prompt.md"\n'
            '[permissions]\nmode = "ask"\n'))
        desk = AskDesk(timeout=10)
        service = make_service([calls("mcp__sparsh__confirm", {"hold": "h1"}),
                                says("not sent")],
                               sparsh=str(sparsh[0]), actors=phone_book, asks=desk)

        async def go():
            turn = asyncio.create_task(service.deliver(
                actor="owner", agent="helper", thread="t", text="text Sam"))
            for _ in range(500):
                if desk.pending() or turn.done():
                    break
                await asyncio.sleep(0.01)
            desk.answer(desk.pending()[0].id, actor="owner", approve=False)
            return await turn

        assert asyncio.run(go()).ok
        assert ["call", "confirm"] not in logged(sparsh[1])

    def test_no_server_outlives_its_turn(self, make_service, sparsh, phone_book):
        service = make_service([says("one"), says("two")], sparsh=str(sparsh[0]),
                               actors=phone_book)
        for text in ("a", "b"):
            asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text=text))
        assert started(sparsh[1]) == 2


class TestWhoGetsNone:
    def test_someone_else_on_the_door(self, make_service, sparsh, phone_book):
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=phone_book)
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t", text="hi"))
        assert phone_tools(service) == set() and started(sparsh[1]) == 0

    def test_a_scheduled_turn(self, make_service, sparsh, phone_book):
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=phone_book)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="go",
                                    unattended=True))
        assert phone_tools(service) == set() and started(sparsh[1]) == 0

    def test_a_service_started_without_it(self, make_service, sparsh, phone_book):
        service = make_service([says("ok")], actors=phone_book)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="hi"))
        assert phone_tools(service) == set() and logged(sparsh[1]) == []

    def test_a_sparsh_that_wont_start_costs_the_phone_not_the_turn(
            self, make_service, tmp_path, phone_book):
        service = make_service([says("still here")], sparsh=str(tmp_path / "gone"),
                               actors=phone_book)
        reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                            text="hi"))
        assert reply.ok and reply.text == "still here"


class TestTheOwnersFile:
    def test_two_people_on_one_phone_is_an_error_naming_both(self):
        with pytest.raises(ConfigProblem, match=r"\[actor.a\] and \[actor.b\]"):
            ActorBook.from_dict({"actor": {"a": {"phone": True}, "b": {"phone": True}}})

    def test_phone_is_true_or_false(self):
        with pytest.raises(ConfigProblem, match="phone must be true or false"):
            ActorBook.from_dict({"actor": {"a": {"phone": "yes"}}})

    def test_asked_for_and_missing_stops_the_start(self, tmp_path):
        with pytest.raises(ConfigProblem, match="--sparsh"):
            _sparsh(str(tmp_path / "nope"))

    def test_not_asked_for_is_off(self):
        assert _sparsh(None) is None and _sparsh("off") is None

    def test_found_is_announced_with_its_phone(self, sparsh, capsys):
        assert _sparsh(str(sparsh[0])) == str(sparsh[0])
        assert "phone: emulator-5554" in capsys.readouterr().err



# ---- a schedule that works the phone ---------------------------------------

STEP = "send in Messages when the screen shows 555-0123"
ON_TELEGRAM = ActorBook.from_dict({"actor": {"owner": {
    "phone": True, "channel": [{"kind": "telegram", "id": 42}]}}})


def scheduled(service, **kw):
    return asyncio.run(service.deliver(actor="owner", agent="greeter",
                                       thread="samay-s1-1", text="text Sam I'm late",
                                       unattended=True, **kw))


class TestAScheduleWithThePhone:
    def test_it_gets_the_phone_and_the_steps_its_person_let_it_do(
            self, make_service, sparsh, monkeypatch):
        monkeypatch.setenv("FAKE_PHONE", "asleep")
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=ON_TELEGRAM)
        reply = scheduled(service, phone=True, phone_steps=[STEP])
        assert reply.ok and "mcp__sparsh__confirm" in phone_tools(service)
        assert ["wake"] in logged(sparsh[1])                  # asleep: woken first
        assert ["grants", json.dumps([STEP])] in logged(sparsh[1])

    def test_without_its_schedule_saying_so_a_scheduled_turn_still_gets_none(
            self, make_service, sparsh):
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=ON_TELEGRAM)
        scheduled(service)
        assert phone_tools(service) == set() and started(sparsh[1]) == 0

    def test_someone_who_isnt_the_phones_person_is_refused(self, make_service, sparsh,
                                                           phone_book):
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=phone_book)
        reply = asyncio.run(service.deliver(actor="guest", agent="greeter", thread="s",
                                            text="go", unattended=True, phone=True))
        assert reply.stop_reason == "refused" and "phone = true" in reply.text

    def test_a_phone_in_use_is_left_alone_and_the_run_skipped(
            self, make_service, sparsh, monkeypatch):
        from dvara import ready

        monkeypatch.setenv("FAKE_PHONE", "in_use")
        monkeypatch.setattr(ready, "IN_USE_FOR", 0.2)
        monkeypatch.setattr(ready, "IN_USE_EVERY", 0.05)
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=ON_TELEGRAM)
        reply = scheduled(service, phone=True)
        assert reply.stop_reason == "skipped" and "in use" in reply.text
        assert started(sparsh[1]) == 0 and service.scripted.requests == []

    def test_a_locked_phone_asks_its_person_then_skips(self, make_service, sparsh,
                                                       monkeypatch):
        from dvara import ready

        monkeypatch.setenv("FAKE_PHONE", "locked")
        monkeypatch.setattr(ready, "LOCKED_EVERY", 0.05)
        service = make_service([says("ok")], sparsh=str(sparsh[0]), actors=ON_TELEGRAM)
        got = []

        async def telegram(address, text, file=None):
            got.append((address, text))
        service.notices.route("telegram", telegram)
        reply = scheduled(service, phone=True, wait=0.3)
        assert reply.stop_reason == "skipped" and "stayed locked" in reply.text
        assert len(got) == 1 and got[0][0] == "42"
        assert "Your phone is locked" in got[0][1] and "text Sam" in got[0][1]


class TestReady:
    """ready.py on its own, with a phone made of answers and a clock."""

    def run(self, states, *, wait=60.0):
        from dvara import ready

        now, said, woken = [0.0], [], []
        answers = iter(states)

        async def state():
            return next(answers)

        async def wake():
            woken.append(True)

        async def ask(line):
            said.append(line)

        async def sleep(seconds):
            now[0] += seconds
        why = asyncio.run(ready.ready(ready.Phone(state, wake), wait=wait, ask=ask,
                                      about="check", clock=lambda: now[0], sleep=sleep))
        return why, said, woken, now[0]

    def test_unlocked_after_being_asked_is_a_go(self):
        why, said, woken, _ = self.run(["locked", "locked", "in_use"])
        assert why is None and len(said) == 1 and woken == []

    def test_in_use_is_looked_at_each_minute_for_ten(self):
        why, said, _, waited = self.run(["in_use"] * 20)
        assert "in use for 10 minutes" in why and said == [] and waited == 600

    def test_put_down_while_waited_on_and_locked_then_asks(self):
        why, said, _, _ = self.run(["in_use", "locked", "in_use"])
        assert why is None and len(said) == 1

    def test_an_iphone_that_says_only_unlocked_goes(self):
        assert self.run(["unknown"])[0] is None

    def test_a_phone_that_cant_be_reached_is_a_skip_in_its_words(self):
        from dvara import ready

        async def state():
            raise RuntimeError("no phone attached")

        async def wake():
            pass

        async def ask(line):
            pass
        why = asyncio.run(ready.ready(ready.Phone(state, wake), wait=60, ask=ask, about="x"))
        assert why == "skipped: the phone couldn't be reached (no phone attached)"

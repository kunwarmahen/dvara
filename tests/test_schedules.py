"""A person's agent offers a schedule, and the person says yes on their channel.

The bias these tests encode: ONE PERSON'S SCHEDULES, MADE ONLY WITH
THAT PERSON'S YES. Each turn's Samay server is started for that turn's
actor and nobody else, on this road, and stopped when the turn ends.
Making a schedule is a question on the desk -- the card in words, not
JSON -- and a scheduled turn, which nobody is watching, gets no Samay at
all. Schedules stay off unless the owner turned them on.

Samay here is a fake program on disk speaking the real contract:
``status --json`` and an MCP server, which logs every start and every
call so the tests can read who it was started for.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from dvara.asks import AskDesk
from dvara.cli import _samay
from dvara.errors import ConfigProblem
from tests.conftest import calls, says, write_package

FAKE = """\
    import json, sys
    LOG = {log!r}
    args = sys.argv[1:]
    with open(LOG, "a") as out:
        out.write(json.dumps(args) + "\\n")
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    def tool(name, ro):
        return {{"name": name, "description": name, "inputSchema": {{"type": "object"}},
                "annotations": {{"readOnlyHint": ro}}}}
    if args == ["status", "--json"]:
        print(json.dumps({{"format": "samay.status.v1", "version": "0.1.0",
            "state": "/s", "serving": False, "url": None, "dvara": "http://d",
            "schedules": {{"active": 0, "paused": 0, "done": 0}},
            "mcp": {{"command": {python!r}, "args": [sys.argv[0], "--state", "/s", "mcp"]}}}}))
        sys.exit(0)
    TOOLS = [tool("preview_schedule", True), tool("list_schedules", True),
             tool("create_schedule", False)]
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "samay"}}}}}})
        elif method == "tools/list":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{"tools": TOOLS}}}})
        elif method == "tools/call":
            with open(LOG, "a") as out:
                out.write(json.dumps(["call", msg["params"]["name"]]) + "\\n")
            text = {{"preview_schedule": "every 2 hours -- next: 14:00, 16:00"}}.get(
                msg["params"]["name"], "saved s-1")
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "content": [{{"type": "text", "text": text}}]}}}})
        elif mid is not None:
            send({{"jsonrpc": "2.0", "id": mid, "error": {{"code": -32601, "message": "no"}}}})
"""


@pytest.fixture
def samay(tmp_path):
    log = tmp_path / "samay.log"
    program = tmp_path / "samay"
    program.write_text(f"#!{sys.executable}\n"
                       + textwrap.dedent(FAKE).format(log=str(log), python=sys.executable))
    program.chmod(0o755)
    return program, log


def logged(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def tools_sent(service) -> set[str]:
    return {t.name for t in service.scripted.requests[0]["tools"]}


CREATE = {"prompt": "check my mail", "when": {"every": "2h"}, "notify": "when_new"}


class TestAPersonsTurn:
    def test_the_server_is_for_this_person_and_this_agent_on_this_road(
            self, make_service, samay):
        service = make_service([says("ok")], samay=str(samay[0]))
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                    text="hi"))
        started = [a for a in logged(samay[1]) if "mcp" in a][0]
        assert started[-6:] == ["--for", "owner", "--agent", "greeter",
                                "--runner", "dvara"]
        assert "mcp__samay__create_schedule" in tools_sent(service)

    def test_the_model_is_told_to_ask_and_where_schedules_are_seen(
            self, make_service, samay):
        service = make_service([says("ok")], samay=str(samay[0]))
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                    text="hi"))
        system = service.scripted.requests[0]["system"]
        assert "preview_schedule" in system and "say yes" in system
        assert "sees their schedules by asking you" in system
        assert "Schedules panel" not in system
        assert "once the service's owner starts it" in system
        assert "samay serve" not in system

    def test_making_one_is_asked_on_the_desk_in_words(self, make_service, samay,
                                                       agents_root):
        write_package(agents_root, "mailer", body=(
            '[agent]\nname = "mailer"\nprompt = "prompt.md"\n'
            '[permissions]\nmode = "ask"\n'))
        desk = AskDesk(timeout=10)
        service = make_service([calls("mcp__samay__create_schedule", CREATE),
                                says("set up")], samay=str(samay[0]), asks=desk)

        async def go():
            turn = asyncio.create_task(service.deliver(
                actor="owner", agent="mailer", thread="t", text="every 2h, check"))
            for _ in range(500):
                if desk.pending() or turn.done():
                    break
                await asyncio.sleep(0.01)
            assert desk.pending(), f"nothing was asked: {turn.done() and turn.result()}"
            ask = desk.pending()[0]
            desk.answer(ask.id, actor="owner", approve=True)
            return ask, await turn

        ask, reply = asyncio.run(go())
        assert ask.summary.startswith("Save a schedule.")
        assert "every 2 hours -- next: 14:00, 16:00" in ask.summary
        assert '{"every"' not in ask.summary
        assert reply.ok
        assert ["call", "create_schedule"] in logged(samay[1])

    def test_no_server_outlives_its_turn(self, make_service, samay):
        service = make_service([says("one"), says("two")], samay=str(samay[0]))
        for text in ("a", "b"):
            asyncio.run(service.deliver(actor="owner", agent="greeter",
                                        thread="t", text=text))
        assert sum(1 for a in logged(samay[1]) if "mcp" in a) == 2


class TestWhoGetsNone:
    def test_a_scheduled_turn_gets_no_samay(self, make_service, samay):
        service = make_service([says("ok")], samay=str(samay[0]))
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                    text="go", unattended=True))
        assert not any("mcp" in a for a in logged(samay[1]))
        assert "mcp__samay__create_schedule" not in tools_sent(service)

    def test_off_unless_the_owner_turned_it_on(self, make_service, samay):
        service = make_service([says("ok")])
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                    text="hi"))
        assert logged(samay[1]) == []
        assert not any(n.startswith("mcp__samay__") for n in tools_sent(service))

    def test_a_samay_that_wont_start_costs_the_tools_not_the_turn(
            self, make_service, tmp_path):
        gone = tmp_path / "no-such-samay"
        service = make_service([says("still here")], samay=str(gone))
        reply = asyncio.run(service.deliver(actor="owner", agent="greeter",
                                            thread="t", text="hi"))
        assert reply.ok and reply.text == "still here"


class TestTheOwnersSwitch:
    def test_asked_for_and_missing_stops_the_start(self, tmp_path):
        with pytest.raises(ConfigProblem, match="--samay"):
            _samay(str(tmp_path / "nope"))

    def test_not_asked_for_is_off(self):
        assert _samay(None) is None and _samay("off") is None

    def test_found_is_announced_and_a_missing_url_is_warned(self, samay, capsys,
                                                           monkeypatch):
        monkeypatch.delenv("SAMAY_DVARA_URL", raising=False)
        assert _samay(str(samay[0])) == str(samay[0])
        err = capsys.readouterr().err
        assert "schedules through samay 0.1.0" in err
        assert "SAMAY_DVARA_URL is not set" in err

"""The owner's agent offers a watch, and the owner says yes on their channel.

The bias these tests encode: A WATCH LOOKS WITH THIS COMPUTER'S ACCOUNTS,
SO IT IS ONE PERSON'S. Prahari's tools reach only the turns of the
person named by ``--prahari-for``; anyone else on the same service gets
none, because a watch they made would read the owner's mail for them.
Like Samay's: each turn's server is started for that person on this
road and stopped when the turn ends, a scheduled turn gets none, and
watches stay off unless the owner turned them on -- and named whose.

Prahari here is a fake program on disk speaking the real contract.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from dvara.cli import _prahari
from dvara.errors import ConfigProblem
from tests.conftest import says

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
        print(json.dumps({{"format": "prahari.status.v1", "version": "0.1.0",
            "state": "/p", "serving": False, "url": None, "dvara": "http://d",
            "local_to": "", "inlet": None,
            "watches": {{"active": 0, "paused": 0, "listening": 0}},
            "mcp": {{"command": {python!r}, "args": [sys.argv[0], "--state", "/p", "mcp"]}}}}))
        sys.exit(0)
    TOOLS = [tool("preview_watch", True), tool("list_watches", True),
             tool("create_watch", False)]
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "prahari"}}}}}})
        elif method == "tools/list":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{"tools": TOOLS}}}})
        elif method == "tools/call":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "content": [{{"type": "text", "text": "ok"}}]}}}})
        elif mid is not None:
            send({{"jsonrpc": "2.0", "id": mid, "error": {{"code": -32601, "message": "no"}}}})
"""


@pytest.fixture
def prahari(tmp_path):
    log = tmp_path / "prahari.log"
    program = tmp_path / "prahari"
    program.write_text(f"#!{sys.executable}\n"
                       + textwrap.dedent(FAKE).format(log=str(log), python=sys.executable))
    program.chmod(0o755)
    return program, log


def logged(log: Path) -> list[list[str]]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def tools_sent(service) -> set[str]:
    return {t.name for t in service.scripted.requests[0]["tools"]}


class TestThePersonNamed:
    def test_their_turn_gets_the_tools_for_them_on_this_road(self, make_service, prahari):
        service = make_service([says("ok")], prahari=str(prahari[0]), prahari_for="owner")
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="hi"))
        started = [a for a in logged(prahari[1]) if "mcp" in a][0]
        assert started[-6:] == ["--for", "owner", "--agent", "greeter", "--runner", "dvara"]
        assert "mcp__prahari__create_watch" in tools_sent(service)
        system = service.scripted.requests[0]["system"]
        assert "preview_watch" in system and "sees their watches by asking you" in system
        assert "once the service's owner starts it" in system
        assert "prahari serve" not in system

    def test_anybody_else_gets_none(self, make_service, prahari):
        service = make_service([says("ok")], prahari=str(prahari[0]), prahari_for="owner")
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t", text="hi"))
        assert not any("mcp" in a for a in logged(prahari[1]))     # never started for them

    def test_a_scheduled_turn_gets_none(self, make_service, prahari):
        service = make_service([says("ok")], prahari=str(prahari[0]), prahari_for="owner")
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="go",
                                    unattended=True))
        assert not any("mcp" in a for a in logged(prahari[1]))

    def test_no_server_outlives_its_turn(self, make_service, prahari):
        service = make_service([says("one"), says("two")], prahari=str(prahari[0]),
                               prahari_for="owner")
        for text in ("a", "b"):
            asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                        text=text))
        assert sum(1 for a in logged(prahari[1]) if "mcp" in a) == 2

    def test_a_prahari_that_wont_start_costs_the_tools_not_the_turn(self, make_service,
                                                                    tmp_path):
        service = make_service([says("still here")], prahari=str(tmp_path / "gone"),
                               prahari_for="owner")
        reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                            text="hi"))
        assert reply.ok and reply.text == "still here"


class TestTheOwnersSwitch:
    def test_off_unless_asked_for(self):
        assert _prahari(None, "owner") == (None, "") and _prahari("off", None) == (None, "")

    def test_on_needs_whose(self, prahari):
        with pytest.raises(ConfigProblem, match="--prahari-for ACTOR"):
            _prahari(str(prahari[0]), None)

    def test_asked_for_and_missing_stops_the_start(self, tmp_path):
        with pytest.raises(ConfigProblem, match="--prahari"):
            _prahari(str(tmp_path / "nope"), "owner")

    def test_found_is_announced_and_a_missing_url_is_warned(self, prahari, capsys,
                                                           monkeypatch):
        monkeypatch.delenv("PRAHARI_DVARA_URL", raising=False)
        assert _prahari(str(prahari[0]), "owner") == (str(prahari[0]), "owner")
        err = capsys.readouterr().err
        assert "watches through prahari 0.1.0" in err and "for owner" in err
        assert "PRAHARI_DVARA_URL is not set" in err

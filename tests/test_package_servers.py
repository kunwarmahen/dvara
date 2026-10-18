"""A package's own MCP servers ([[mcp]] in agent.toml) start for each turn.

The bias: THE AGENT THAT SHIPS IS THE AGENT THAT ANSWERS. Yantra starts a
package's declared servers in every session; a turn here that left them
out answered with a smaller agent than its author wrote, and nobody was
told. And the other way: a declared server never gets past the package's
own [tools] allow, never displaces a server this turn already has by the
same name, and one that won't start costs its tools, not the turn.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap

from tests.conftest import says, write_package

SERVER = """\
    import json, sys
    with open({log!r}, "a") as out:
        out.write("started\\n")
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "docs"}}}}}})
        elif method == "tools/list":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{"tools": [
                {{"name": "lookup", "description": "look a word up",
                  "inputSchema": {{"type": "object"}},
                  "annotations": {{"readOnlyHint": True}}}}]}}}})
        elif mid is not None:
            send({{"jsonrpc": "2.0", "id": mid, "error": {{"code": -32601, "message": "no"}}}})
"""


def package(agents_root, tmp_path, *, allow: str | None = None, command: str | None = None):
    script = tmp_path / "docs_server.py"
    log = tmp_path / "docs.log"
    script.write_text(textwrap.dedent(SERVER).format(log=str(log)))
    tools = f"[tools]\nallow = {json.dumps([allow])}\n" if allow else ""
    write_package(agents_root, "librarian", body=(
        '[agent]\nname = "librarian"\nprompt = "prompt.md"\n' + tools +
        f'[[mcp]]\nname = "docs"\ncommand = {json.dumps(command or sys.executable)}\n'
        f'args = [{json.dumps(str(script))}]\n'))
    return log


def turn(service):
    return asyncio.run(service.deliver(actor="owner", agent="librarian", thread="t",
                                       text="what does 'setu' mean?"))


def tools_sent(service) -> set[str]:
    return {t.name for t in service.scripted.requests[0]["tools"]}


def test_a_declared_server_starts_for_the_turn(make_service, agents_root, tmp_path):
    log = package(agents_root, tmp_path)
    service = make_service([says("a bridge")])
    assert turn(service).text == "a bridge"
    assert "mcp__docs__lookup" in tools_sent(service)
    assert log.read_text().splitlines() == ["started"]


def test_the_packages_own_allow_still_decides(make_service, agents_root, tmp_path):
    package(agents_root, tmp_path, allow="read_file")
    service = make_service([says("ok")])
    turn(service)
    assert not any(name.startswith("mcp__docs__") for name in tools_sent(service))


def test_a_server_that_will_not_start_costs_its_tools_not_the_turn(make_service,
                                                                   agents_root, tmp_path,
                                                                   capsys):
    package(agents_root, tmp_path, command=str(tmp_path / "no-such-program"))
    service = make_service([says("still here")])
    assert turn(service).text == "still here"
    assert not any(name.startswith("mcp__docs__") for name in tools_sent(service))
    assert "mcp 'docs' (agent.toml) is off for this turn" in capsys.readouterr().err

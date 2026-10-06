"""Each person's agent reaches that person's own accounts, and no one else's.

The bias these tests encode: ONE PERSON'S MAIL NEVER REACHES ANOTHER
PERSON'S AGENT. Setu is read in the person's own folder and every
connector asks THERE for its pass; nobody gets accounts unless the owner
gave them a folder (``setu`` in actors.toml); a folder shared on purpose
can be narrowed to the accounts meant; and the package must have asked
(``[connections] needs``), at its level at most -- a sign-in is not a
reason for an agent that never asked to read somebody's mail.

Setu here is a fake program on PATH that reports whatever connections
the folder it is pointed at lists, and the Gmail connector is a fake MCP
server that says whose folder its pass came from.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from dvara.actors import ActorBook
from dvara.errors import ConfigProblem
from tests.conftest import calls, says, write_package

CONNECTOR = """\
    import json, os, sys
    HOME = os.environ.get("SETU_HOME", "-")
    ACCOUNT = sys.argv[1]
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    def tool(name):
        return {"name": name, "description": name, "inputSchema": {"type": "object"},
                "annotations": {"readOnlyHint": False}}
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {"tools": {}}, "serverInfo": {"name": "gmail"}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                tool("search_threads"), tool("send_message")]}})
        elif method == "tools/call":
            send({"jsonrpc": "2.0", "id": mid, "result": {"content": [
                {"type": "text", "text": f"mail of {ACCOUNT} from {HOME}"}]}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "no"}})
"""

SETU = """\
    import json, os, sys
    HOME = os.environ.get("SETU_HOME", "")
    assert sys.argv[1:] == ["status", "--json"], sys.argv
    try:
        accounts = json.load(open(os.path.join(HOME, "accounts.json")))
    except OSError:
        accounts = []
    def row(account):
        return {{"ref": "gmail:" + account, "connector": "gmail", "account": account,
                "email": account + "@example.com", "level": "send",
                "level_label": "Read, draft and send", "installed": True,
                "mcp": {{"name": "gmail-" + account, "command": {python!r},
                        "args": [{connector!r}, account]}}}}
    print(json.dumps({{"format": "setu.status.v1", "version": "0.1.0", "problems": [],
        "connections": [row(a) for a in accounts],
        "connectors": [{{"id": "gmail", "name": "Gmail", "connected": bool(accounts),
            "verbs": {{"search_threads": "read", "send_message": "write"}},
            "levels": []}}]}}))
"""


@pytest.fixture
def fake_setu(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    connector = tmp_path / "connector.py"
    connector.write_text(textwrap.dedent(CONNECTOR))
    program = bin_dir / "setu"
    program.write_text(f"#!{sys.executable}\n" + textwrap.dedent(SETU).format(
        python=sys.executable, connector=str(connector)))
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return program


def home_with(path: Path, *accounts: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "accounts.json").write_text(json.dumps(list(accounts)))
    return path


def mailer(agents_root, needs='["gmail:read"]'):
    write_package(agents_root, "mailer", body=(
        '[agent]\nname = "mailer"\nprompt = "prompt.md"\n'
        f'[connections]\nneeds = {needs}\n'))


def book(**people) -> ActorBook:
    return ActorBook.from_dict({"actor": {name: body for name, body in people.items()}})


def tools_sent(service) -> set[str]:
    return {t.name for t in service.scripted.requests[0]["tools"]}


def tool_text(service, index=1) -> str:
    """What the model was shown after its tool call: the last message's text."""
    message = service.scripted.requests[index]["messages"][-1]
    return " ".join(str(getattr(b, "content", "") or getattr(b, "text", ""))
                    for b in message.content)


def ask(service, actor, text="anything in my mail?", **kw):
    return asyncio.run(service.deliver(actor=actor, agent="mailer", thread="t",
                                       text=text, **kw))


SEARCH = calls("mcp__gmail-personal__search_threads", {})


class TestTheirOwnFolder:
    def test_a_persons_agent_reads_their_own_mail(self, make_service, fake_setu,
                                                  agents_root, tmp_path):
        mailer(agents_root)
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        service = make_service([SEARCH, says("ok")],
                               actors=book(priya={"setu": str(priya)}))
        assert ask(service, "priya").ok
        assert f"mail of personal from {priya}" in tool_text(service)

    def test_two_people_never_see_each_others(self, make_service, fake_setu,
                                              agents_root, tmp_path):
        mailer(agents_root)
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        raj = home_with(tmp_path / "homes" / "raj", "personal")
        service = make_service([SEARCH, says("p"), SEARCH, says("r")],
                               actors=book(priya={"setu": str(priya)},
                                           raj={"setu": str(raj)}))
        ask(service, "priya")
        ask(service, "raj")
        assert f"from {priya}" in tool_text(service, 1)
        assert f"from {raj}" in tool_text(service, 3)
        assert str(priya) not in tool_text(service, 3)

    def test_a_folder_of_their_own_is_made_theirs_alone(self, make_service, fake_setu,
                                                        agents_root):
        mailer(agents_root)
        service = make_service([says("ok")], actors=book(priya={"setu": True}))
        ask(service, "priya")
        home = service.state / "setu" / "priya"
        assert home.is_dir() and stat.S_IMODE(home.stat().st_mode) == 0o700


    def test_an_account_not_connected_yet_is_named_with_who_connects_it(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("ok")], actors=book(raj={"setu": True}))
        ask(service, "raj")
        system = service.scripted.requests[0]["system"]
        assert "Installed but not connected" in system and "Gmail" in system
        assert "/connect gmail" in system and "you cannot do it for them" in system
        assert "setu connect" not in system

    def test_a_folder_the_owner_pointed_them_at_is_connected_by_the_owner(
            self, make_service, fake_setu, agents_root, tmp_path):
        mailer(agents_root)
        shared = home_with(tmp_path / "homes" / "owner")
        service = make_service([says("ok")], actors=book(priya={"setu": str(shared)}))
        ask(service, "priya")
        system = service.scripted.requests[0]["system"]
        assert "the owner of this service connects it for them" in system


class TestWhoGetsNone:
    def test_no_folder_no_accounts(self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("ok")], actors=book(priya={}))
        ask(service, "priya")
        assert not any(n.startswith("mcp__gmail") for n in tools_sent(service))

    def test_a_package_that_never_asked_gets_none(self, make_service, fake_setu,
                                                  agents_root, tmp_path):
        mailer(agents_root, needs="[]")
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        service = make_service([says("ok")], actors=book(priya={"setu": str(priya)}))
        ask(service, "priya")
        assert not any(n.startswith("mcp__gmail") for n in tools_sent(service))

    def test_the_packages_level_is_a_ceiling(self, make_service, fake_setu,
                                             agents_root, tmp_path):
        mailer(agents_root)                               # gmail:read
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        service = make_service([says("ok")], actors=book(priya={"setu": str(priya)}))
        ask(service, "priya")
        sent = tools_sent(service)
        assert "mcp__gmail-personal__search_threads" in sent
        assert "mcp__gmail-personal__send_message" not in sent

    def test_a_shared_folder_narrows_to_the_accounts_meant(self, make_service, fake_setu,
                                                           agents_root, tmp_path):
        mailer(agents_root)
        owners = home_with(tmp_path / "homes" / "owner", "personal", "work")
        service = make_service([says("ok")], actors=book(
            partner={"setu": str(owners), "setu_accounts": ["gmail:personal"]}))
        ask(service, "partner")
        sent = tools_sent(service)
        assert "mcp__gmail-personal__search_threads" in sent
        assert not any(n.startswith("mcp__gmail-work") for n in sent)

    def test_a_scheduled_turn_reaches_the_same_accounts(self, make_service, fake_setu,
                                                        agents_root, tmp_path):
        mailer(agents_root)
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        service = make_service([SEARCH, says("ok")],
                               actors=book(priya={"setu": str(priya)}))
        ask(service, "priya", unattended=True)
        assert f"from {priya}" in tool_text(service)

    def test_no_setu_program_costs_the_accounts_not_the_turn(self, make_service,
                                                             agents_root, tmp_path,
                                                             monkeypatch):
        mailer(agents_root)
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        priya = home_with(tmp_path / "homes" / "priya", "personal")
        service = make_service([says("still here")],
                               actors=book(priya={"setu": str(priya)}))
        reply = ask(service, "priya")
        assert reply.ok and reply.text == "still here"


class TestTheActorsFile:
    def test_true_means_a_folder_of_their_own_and_a_string_a_path(self):
        people = book(a={"setu": True}, b={"setu": "~/x"}, c={})
        assert people.get("a").setu == "own"
        assert people.get("b").setu == str(Path("~/x").expanduser())
        assert people.get("c").setu is None

    @pytest.mark.parametrize("body", [{"setu": 1}, {"setu": ""},
                                      {"setu_accounts": ["gmail:personal"]},
                                      {"setu": True, "setu_accounts": ["gmail"]}])
    def test_a_typo_is_refused_not_read_as_yes(self, body):
        with pytest.raises(ConfigProblem):
            book(a=body)

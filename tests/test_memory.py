"""Each person's memory, behind the door.

The bias these tests encode: ONE PERSON'S MEMORIES NEVER REACH ANOTHER.
A turn's memories are filed under its person's name -- never the login
the service runs as, which would pour everybody's facts into the
owner's. With the owner's store named, each turn starts it with that
person's own key and name, and a person with no key gets no memory at
all rather than someone else's. A package that never asked for memory
gets none, whichever store the owner named.

The store here is a fake program on disk speaking MCP, which logs the
person it was started for and every call it was asked to make.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from pathlib import Path

import pytest

from dvara.actors import ActorBook
from dvara.cli import _memory
from dvara.errors import ConfigProblem
from dvara.memory import PEOPLE_FILE, MemoryProblem, Person, Store, people, write_people
from tests.conftest import says

FAKE = """\
    import json, os, sys
    LOG = {log!r}
    def log(row):
        with open(LOG, "a") as out:
            out.write(json.dumps(row) + "\\n")
    log(["start", os.environ.get("SMRITIKOSH_USER_ID"), os.environ.get("SMRITIKOSH_API_KEY")])
    def send(m): sys.stdout.write(json.dumps(m) + "\\n"); sys.stdout.flush()
    def tool(name):
        return {{"name": name, "description": name, "inputSchema": {{"type": "object"}}}}
    TOOLS = [tool(n) for n in ("remember", "recall", "forget", "list_memories")]
    for line in sys.stdin:
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "protocolVersion": msg["params"]["protocolVersion"],
                "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "store"}}}}}})
        elif method == "tools/list":
            send({{"jsonrpc": "2.0", "id": mid, "result": {{"tools": TOOLS}}}})
        elif method == "tools/call":
            p = msg["params"]
            log(["call", p["name"], p["arguments"].get("user_id")])
            text = json.dumps({{"id": "m-1"}}) if p["name"] == "remember" else "[]"
            send({{"jsonrpc": "2.0", "id": mid, "result": {{
                "content": [{{"type": "text", "text": text}}]}}}})
        elif mid is not None:
            send({{"jsonrpc": "2.0", "id": mid, "error": {{"code": -32601, "message": "no"}}}})
"""

REMEMBERING = ('[agent]\nname = "greeter"\nprompt = "prompt.md"\n'
               '[memory]\nvia = "local"\n')


@pytest.fixture
def store(tmp_path):
    log = tmp_path / "store.log"
    program = tmp_path / "store"
    program.write_text(f"#!{sys.executable}\n"
                       + textwrap.dedent(FAKE).format(log=str(log)))
    program.chmod(0o755)
    config = tmp_path / "memory-mcp.json"
    config.write_text(json.dumps({"servers": {"smritikosh": {
        "command": str(program),
        "env": {"SMRITIKOSH_USER_ID": "${DVARA_MEMORY_USER}",
                "SMRITIKOSH_API_KEY": "${DVARA_MEMORY_KEY}"}}}}))
    return Store.load(config), log


@pytest.fixture
def remembering(agents_root):
    """greeter, as a package that asks for memory."""
    (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
    return agents_root


#: Two people with no allowance to price: the tests are about whose
#: memories, not money.
PEOPLE = {"actor": {"owner": {}, "guest": {"agents": ["greeter"]}}}


@pytest.fixture
def make_service(make_service):
    def build(script=None, **kwargs):
        kwargs.setdefault("actors", ActorBook.from_dict(PEOPLE))
        return make_service(script, **kwargs)
    return build


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    """The built-in file under the test's folder, and a login name that
    is plainly the machine's, so a memory filed under it is caught."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("YANTRA_USER", "the-machine")


def logged(log: Path) -> list[list]:
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def keys(service, table: dict[str, Person]) -> None:
    write_people(service.state, table)


class TestWhoseMemories:
    def test_the_built_in_file_reads_the_persons_not_the_logins(
            self, make_service, remembering):
        from yantra.memory.local import LocalStore
        store = LocalStore()
        store.remember("guest", "Lives near RDU", {})
        store.remember("the-machine", "The owner's bank is First Federal", {})
        service = make_service([says("hi")])
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t",
                                    text="find me flights"))
        system = str(service.scripted.requests[0]["system"])
        assert "Lives near RDU" in system
        assert "First Federal" not in system

    def test_memory_json_can_name_the_owner_as_their_store_knows_them(
            self, make_service, remembering):
        service = make_service([says("hi")])
        keys(service, {"owner": Person(user="asha")})
        spec, who = service._memory_for(service.roster.spec("greeter"),
                                        service.actors.may("owner", "greeter"))
        assert who.user == "asha" and spec.memory == "local"


class TestTheOwnersStore:
    def test_each_turn_starts_it_with_that_persons_own_name_and_key(
            self, make_service, remembering, store):
        service = make_service([says("noted")], memory=store[0])
        keys(service, {"guest": Person(user="dvara-guest", key="sk-guest"),
                       "owner": Person(user="asha", key="sk-owner")})
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t",
                                    text="I prefer tea"))
        rows = logged(store[1])
        assert rows[0] == ["start", "dvara-guest", "sk-guest"]
        # every call the turn made, the look at what they said before included
        assert rows[1:] and all(row[2] == "dvara-guest" for row in rows[1:])
        assert "remember" in {t.name for t in service.scripted.requests[0]["tools"]}
        assert not any("sk-owner" in row or "asha" in row for row in rows)

    def test_a_person_with_no_key_gets_no_memory_not_someone_elses(
            self, make_service, remembering, store, capsys):
        service = make_service([says("hi")], memory=store[0])
        keys(service, {"owner": Person(user="asha", key="sk-owner")})
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t", text="hi"))
        assert logged(store[1]) == []
        assert "remember" not in {t.name for t in service.scripted.requests[0]["tools"]}
        assert "guest: no memory this turn -- no key of their own" in capsys.readouterr().err

    def test_a_package_that_never_asked_gets_none(self, make_service, store):
        service = make_service([says("hi")], memory=store[0])
        keys(service, {"guest": Person(user="dvara-guest", key="sk-guest")})
        asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t", text="hi"))
        assert logged(store[1]) == []

    def test_a_store_that_wont_start_costs_the_memory_not_the_turn(
            self, make_service, remembering, store, capsys):
        broken = Store(name="smritikosh", server={"command": "/nowhere/at-all"},
                       where="x")
        service = make_service([says("still here")], memory=broken)
        keys(service, {"guest": Person(user="dvara-guest", key="sk-guest")})
        reply = asyncio.run(service.deliver(actor="guest", agent="greeter", thread="t",
                                            text="hi"))
        assert reply.text == "still here"
        assert "guest: memory is off for this turn -- smritikosh" in capsys.readouterr().err


class TestTheFiles:
    def test_memory_json_is_the_owners_alone(self, tmp_path):
        path = write_people(tmp_path, {"guest": Person(user="g", key="sk")})
        assert path.name == PEOPLE_FILE and path.stat().st_mode & 0o777 == 0o600
        assert people(tmp_path) == {"guest": Person(user="g", key="sk")}

    def test_a_store_file_names_exactly_one_server(self, tmp_path):
        path = tmp_path / "m.json"
        path.write_text(json.dumps({"servers": {"a": {"command": "x"},
                                                "b": {"command": "y"}}}))
        with pytest.raises(MemoryProblem, match="exactly one server"):
            Store.load(path)

    def test_a_missing_store_file_stops_the_start(self, tmp_path):
        with pytest.raises(ConfigProblem, match="no such file"):
            _memory(str(tmp_path / "missing.json"))
        assert _memory(None) is None

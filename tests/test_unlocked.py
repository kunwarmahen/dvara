"""A person locks their accounts with a passphrase, and opens them for a while.

The bias: THE PASSPHRASE GOES TO SETU AND NOWHERE ELSE, AND THE KEY ONLY
AS FAR AS SETU. The message after /lock or /unlock is never an agent's
to read, never a run, never history; the key it buys is held in memory
for the days asked and handed to Setu for that person's turns; when the
time is up the folder is sealed again and they are told. And a person
pointed at the owner's folder cannot lock the owner out of it.

Setu is a fake on PATH: lock.json present means locked; the passphrase
it was set with opens it; `lock seal` is written down.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap

import pytest

from dvara import unlocked
from dvara.actors import ActorBook
from tests.conftest import says, write_package

SETU = """\
    import json, os, sys
    HOME = os.environ["SETU_HOME"]
    KEY = os.environ.get("SETU_VAULT_KEY")
    def at(name): return os.path.join(HOME, name)
    with open(at("calls.log"), "a") as log:
        log.write(json.dumps({"argv": sys.argv[1:], "key": KEY}) + "\\n")
    args = sys.argv[1:]
    locked = os.path.exists(at("lock.json"))
    if args[:2] == ["lock", "status"]:
        print(json.dumps({"locked": locked, "open": bool(KEY), "sealed_profiles": []}))
    elif args[:2] == ["lock", "set"]:
        phrase = sys.stdin.readline().strip()
        if len(phrase) < 8:
            print("error: a passphrase needs at least 8 characters", file=sys.stderr)
            sys.exit(2)
        open(at("lock.json"), "w").write(phrase)
        print("locked")
    elif args[:2] == ["lock", "unlock"]:
        phrase = sys.stdin.readline().strip()
        if not locked or open(at("lock.json")).read() != phrase:
            print(json.dumps({"error": "that is not this folder's passphrase"})); sys.exit(2)
        print(json.dumps({"key": "KEY-OF-" + os.path.basename(HOME), "profiles": []}))
    elif args[:2] == ["lock", "seal"]:
        print(json.dumps({"sealed": []}))
    elif args[:2] == ["status", "--json"]:
        print(json.dumps({"format": "setu.status.v1", "problems": [],
            "lock": {"locked": locked, "open": bool(KEY)},
            "connections": [{"ref": "gmail:personal", "connector": "gmail",
                             "account": "personal", "email": "r@example.com",
                             "level_label": "Read only", "installed": True,
                             "locked": locked and not KEY,
                             "mcp": {"name": "gmail-personal", "command": "/bin/false",
                                     "args": []}}],
            "connectors": [{"id": "gmail", "name": "Gmail", "connected": True,
                            "verbs": {}, "levels": []}]}))
"""

PHRASE = "a few words here"


@pytest.fixture
def fake_setu(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    program = bin_dir / "setu"
    program.write_text(f"#!{sys.executable}\n" + textwrap.dedent(SETU))
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return program


def mailer(agents_root):
    write_package(agents_root, "mailer", body=(
        '[agent]\nname = "mailer"\nprompt = "prompt.md"\n'
        '[connections]\nneeds = ["gmail:read"]\n'))


def book(**people) -> ActorBook:
    return ActorBook.from_dict({"actor": dict(people.items())})


def say(service, actor, text, **kw):
    return service.deliver(actor=actor, agent="mailer", thread="t", text=text, **kw)


def calls(service, actor="raj") -> list[dict]:
    path = service.state / "setu" / actor / "calls.log"
    return [json.loads(line) for line in path.read_text().splitlines()]


class TestLockingAndOpening:
    def test_lock_then_the_passphrase_locks_and_opens_and_no_agent_sees_it(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))

        async def go():
            first = await say(service, "raj", "/lock")
            second = await say(service, "raj", PHRASE)
            key = service.accounts.keys.key_for("raj")
            await service.accounts.aclose()
            return first, second, key
        first, second, key = asyncio.run(go())
        assert "next message" in first.text and "delete your message" in first.text
        assert second.text.startswith("Locked with your passphrase. Your accounts are open")
        assert key == "KEY-OF-raj"
        assert service.scripted.requests == [] and list(service.runs.recent()) == []
        assert PHRASE not in json.dumps(calls(service))       # stdin only, never argv

    def test_unlock_holds_the_key_for_the_turns_and_lock_drops_it(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("ok")], actors=book(raj={"setu": True}))
        home = service.setu_home(service.actors.get("raj"))
        (home / "lock.json").write_text(PHRASE)

        async def go():
            asked = await say(service, "raj", "/unlock 3")
            opened = await say(service, "raj", PHRASE)
            await say(service, "raj", "anything new?")
            closed = await say(service, "raj", "/lock")
            return asked, opened, closed
        asked, opened, closed = asyncio.run(go())
        assert "open for 3 days" in asked.text and "open until" in opened.text
        assert closed.text.startswith("Locked.")
        assert service.accounts.keys.key_for("raj") is None
        turn = [c for c in calls(service) if c["argv"] == ["status", "--json"]]
        assert turn and turn[-1]["key"] == "KEY-OF-raj"         # the turn's look, opened
        assert calls(service)[-1]["argv"] == ["lock", "seal"]   # sealed again on /lock

    def test_a_locked_folder_is_named_to_the_agent_with_how_it_opens(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("ok")], actors=book(raj={"setu": True}))
        (service.setu_home(service.actors.get("raj")) / "lock.json").write_text(PHRASE)
        asyncio.run(say(service, "raj", "any mail?"))
        system = service.scripted.requests[0]["system"]
        assert "Connected but locked right now" in system and "/unlock" in system
        assert "mcp__gmail-personal" not in json.dumps(
            [t.name for t in service.scripted.requests[0]["tools"]])

    def test_a_wrong_passphrase_opens_nothing_and_five_stop_the_asking(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))
        (service.setu_home(service.actors.get("raj")) / "lock.json").write_text(PHRASE)

        async def go():
            said = []
            for _ in range(5):
                await say(service, "raj", "/unlock")
                said.append((await say(service, "raj", "not it at all")).text)
            said.append((await say(service, "raj", "/unlock")).text)
            return said
        said = asyncio.run(go())
        assert "didn't open them" in said[0]
        assert said[-1] == "Too many wrong passphrases. Try again in an hour."
        assert service.accounts.keys.key_for("raj") is None

    def test_a_command_instead_of_the_passphrase_cancels_the_wait(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("an ordinary answer")],
                               actors=book(raj={"setu": True}))

        async def go():
            await say(service, "raj", "/lock")
            await say(service, "raj", "/accounts")
            return await say(service, "raj", "hello there")
        assert asyncio.run(go()).text == "an ordinary answer"

    def test_a_folder_the_owner_pointed_them_at_cannot_be_locked_from_the_chat(
            self, make_service, fake_setu, agents_root, tmp_path):
        mailer(agents_root)
        shared = tmp_path / "owners"
        shared.mkdir()
        service = make_service([], actors=book(priya={"setu": str(shared)}))
        reply = asyncio.run(say(service, "priya", "/lock"))
        assert "looked after by the owner" in reply.text
        assert not (shared / "lock.json").exists()


def test_when_the_days_are_up_it_seals_and_tells_them(make_service, fake_setu, agents_root,
                                                      monkeypatch):
    mailer(agents_root)
    service = make_service([], actors=book(raj={"setu": True}))
    told: list[tuple[str, str]] = []

    async def notify(actor, text):
        told.append((actor, text))
    service.accounts.keys.notify = notify
    monkeypatch.setattr(unlocked, "DAY", 0.05)
    home = service.setu_home(service.actors.get("raj"))

    async def go():
        await service.accounts.keys.hold("raj", home, "K", 1)
        await asyncio.sleep(0.2)
    asyncio.run(go())
    assert service.accounts.keys.key_for("raj") is None
    assert told and "locked again" in told[0][1]
    assert calls(service)[-1]["argv"] == ["lock", "seal"]


def test_at_start_up_a_locked_folders_open_sign_ins_are_sealed(make_service, fake_setu,
                                                                agents_root, tmp_path):
    mailer(agents_root)
    state = tmp_path / "state-before"
    home = state / "setu" / "raj"
    home.mkdir(parents=True)
    (home / "lock.json").write_text(PHRASE)
    (state / "setu" / "guest").mkdir()                  # not locked: left alone
    unlocked.seal_loose(str(fake_setu), state / "setu", log=lambda _: None)
    assert json.loads((home / "calls.log").read_text())["argv"] == ["lock", "seal", "--json"]
    assert not (state / "setu" / "guest" / "calls.log").exists()

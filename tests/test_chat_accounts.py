"""A person connects, lists and disconnects their own accounts from the chat.

The bias: A SIGN-IN NEVER PASSES THROUGH AN AGENT. ``/connect`` and the
address pasted back are answered before any turn -- no model is asked,
nothing lands in the conversation's history or the run log -- and the
pasted address goes to the waiting sign-in, the one belonging to that
person, and to nothing else. A chat must also never become a way to add
accounts to a folder that is not the person's own.

Setu is a fake program on PATH speaking ``setu connect --json --paste``:
it prints the link, then reads pasted lines -- the right state connects
(and writes the account into the folder), a wrong one is refused and it
keeps waiting.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap

import pytest

from dvara import accounts
from dvara.actors import ActorBook
from tests.conftest import says, write_package

SETU = """\
    import json, os, sys
    HOME = os.environ["SETU_HOME"]
    with open(os.path.join(HOME, "argv.log"), "a") as log:
        log.write(json.dumps(sys.argv[1:]) + "\\n")
    path = os.path.join(HOME, "accounts.json")
    have = json.load(open(path)) if os.path.exists(path) else []
    def emit(**e): print(json.dumps(e), flush=True)
    cmd = sys.argv[1]
    if cmd == "status":
        print(json.dumps({"format": "setu.status.v1", "problems": [],
            "setup": {"google_client_file": None},
            "connections": [{"ref": r, "connector": r.split(":")[0], "email": "me@example.com",
                             "level_label": "Read only", "installed": True} for r in have],
            "connectors": []}))
    elif cmd == "disconnect":
        ref = sys.argv[2]
        if ref not in have:
            print(f"error: no connection {ref!r}", file=sys.stderr); sys.exit(2)
        json.dump([r for r in have if r != ref], open(path, "w"))
        print("revoked at Google; forgotten here")
    elif cmd == "connect":
        args = sys.argv[2:]
        ref = args[0] + ":" + args[args.index("--as") + 1]
        if args[0] == "amazon":
            emit(event="error", message="Amazon is signed in to in a window"); sys.exit(2)
        emit(event="started", ref=ref, level="read", level_label="Read only")
        emit(event="url", url="https://accounts.google.com/o/oauth2/auth?state=GOOD", paste=True)
        for line in sys.stdin:
            if "state=GOOD" in line and "code=" in line:
                json.dump(have + [ref], open(path, "w"))
                emit(event="connected", ref=ref, email="me@example.com", level="read",
                     level_label="Read only", asked_level="read")
                break
            emit(event="paste_refused", message="that address belongs to a different sign-in")
"""

GOOD = "http://127.0.0.1:41234/?state=GOOD&code=4/0AbCd&scope=x"
BAD = "http://127.0.0.1:41234/?state=OLD&code=4/0Zzz"


@pytest.fixture
def fake_setu(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    program = bin_dir / "setu"
    program.write_text(f"#!{sys.executable}\n" + textwrap.dedent(SETU))
    program.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("SETU_GOOGLE_CLIENT_FILE", str(tmp_path / "owners-client.json"))
    return program


def mailer(agents_root):
    write_package(agents_root, "mailer", body=(
        '[agent]\nname = "mailer"\nprompt = "prompt.md"\n'
        '[connections]\nneeds = ["gmail:read"]\n'))


def book(**people) -> ActorBook:
    return ActorBook.from_dict({"actor": dict(people.items())})


def turn(service, actor, text):
    return service.deliver(actor=actor, agent="mailer", thread="t", text=text)


def run(coro):
    return asyncio.run(coro)


class TestSigningInFromTheChat:
    def test_connect_sends_the_link_and_the_paste_finishes_it(self, make_service,
                                                              fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))

        async def both():
            first = await turn(service, "raj", "/connect gmail")
            second = await turn(service, "raj", f"here it is {GOOD}")
            return first, second
        first, second = run(both())
        assert "https://accounts.google.com/" in first.text and "127.0.0.1" in first.text
        assert second.text.startswith("Connected gmail:personal (me@example.com)")
        assert first.stop_reason == second.stop_reason == "accounts"
        home = service.state / "setu" / "raj"
        assert json.loads((home / "accounts.json").read_text()) == ["gmail:personal"]
        # no model was asked, no run kept, no history written
        assert service.scripted.requests == []
        assert list(service.runs.recent()) == []

    def test_the_level_defaults_to_what_the_package_asks_and_the_owners_client_is_lent(
            self, make_service, fake_setu, agents_root, tmp_path):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))

        async def go():
            await turn(service, "raj", "/connect gmail as school")
            await service.accounts.aclose()
        run(go())
        argv = json.loads((service.state / "setu" / "raj" / "argv.log")
                          .read_text().splitlines()[-1])
        assert argv[:4] == ["connect", "gmail", "--as", "school"]
        assert "--paste" in argv and argv[argv.index("--level") + 1] == "read"
        assert argv[argv.index("--client-file") + 1] == str(tmp_path / "owners-client.json")

    def test_a_wrong_paste_says_so_and_the_right_one_still_works(self, make_service,
                                                                 fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))

        async def go():
            await turn(service, "raj", "/connect gmail")
            wrong = await turn(service, "raj", BAD)
            right = await turn(service, "raj", GOOD)
            return wrong, right
        wrong, right = run(go())
        assert "different sign-in" in wrong.text and "still waiting" in wrong.text
        assert right.text.startswith("Connected")

    def test_a_paste_with_nothing_waiting_is_dropped_not_given_to_the_agent(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("should not be asked")],
                               actors=book(raj={"setu": True}))
        reply = run(turn(service, "raj", GOOD))
        assert "no sign-in waiting" in reply.text
        assert service.scripted.requests == []

    def test_one_persons_paste_never_reaches_anothers_sign_in(self, make_service,
                                                              fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}, priya={"setu": True}))

        async def go():
            await turn(service, "raj", "/connect gmail")
            stolen = await turn(service, "priya", GOOD)
            await service.accounts.aclose()
            return stolen
        assert "no sign-in waiting" in run(go()).text
        assert not (service.state / "setu" / "raj" / "accounts.json").exists()

    def test_a_site_signed_in_through_a_window_says_why_not(self, make_service,
                                                            fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))
        reply = run(turn(service, "raj", "/connect amazon"))
        assert "couldn't start" in reply.text and "window" in reply.text


class TestListingAndDisconnecting:
    def test_accounts_lists_theirs_and_disconnect_forgets_one(self, make_service,
                                                              fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([], actors=book(raj={"setu": True}))
        home = service.setu_home(service.actors.get("raj"))
        (home / "accounts.json").write_text(json.dumps(["gmail:personal", "gmail:work"]))

        async def go():
            listed = await turn(service, "raj", "/accounts")
            gone = await turn(service, "raj", "/disconnect gmail:work")
            again = await turn(service, "raj", "/accounts")
            missing = await turn(service, "raj", "/disconnect gmail:nope")
            return listed, gone, again, missing
        listed, gone, again, missing = run(go())
        assert "gmail:personal" in listed.text and "gmail:work" in listed.text
        assert gone.text.startswith("Disconnected gmail:work")
        assert "gmail:work" not in again.text
        assert "no connection" in missing.text

    def test_a_folder_the_owner_pointed_them_at_is_listed_but_not_changed(
            self, make_service, fake_setu, agents_root, tmp_path):
        mailer(agents_root)
        shared = tmp_path / "owner-setu"
        shared.mkdir()
        (shared / "accounts.json").write_text(json.dumps(["gmail:personal", "gmail:mine"]))
        service = make_service([], actors=book(priya={
            "setu": str(shared), "setu_accounts": ["gmail:personal"]}))

        async def go():
            return (await turn(service, "priya", "/accounts"),
                    await turn(service, "priya", "/connect gmail as extra"),
                    await turn(service, "priya", "/disconnect gmail:personal"))
        listed, connect, disconnect = run(go())
        assert "gmail:personal" in listed.text and "gmail:mine" not in listed.text
        assert "looked after by the owner" in connect.text
        assert "looked after by the owner" in disconnect.text
        assert json.loads((shared / "accounts.json").read_text()) == [
            "gmail:personal", "gmail:mine"]

    def test_no_folder_no_accounts_and_a_scheduled_turn_types_no_commands(
            self, make_service, fake_setu, agents_root):
        mailer(agents_root)
        service = make_service([says("an ordinary answer")],
                               actors=book(guest={}, raj={"setu": True}))
        assert "No accounts are set up" in run(turn(service, "guest", "/accounts")).text
        reply = run(service.deliver(actor="raj", agent="mailer", thread="t",
                                    text="/connect gmail", unattended=True))
        assert reply.stop_reason != "accounts"


def test_what_counts_as_a_paste_and_what_is_kept_of_one():
    assert accounts.looks_pasted(GOOD) and accounts.looks_pasted(f"look: {GOOD} thanks")
    assert accounts.looks_pasted("http://localhost:8080/?error=access_denied&state=x")
    assert not accounts.looks_pasted("https://example.com/?code=1")
    assert not accounts.looks_pasted("my code is 1234")
    assert accounts.scrub(GOOD) == "(an address pasted back for a sign-in)"
    assert accounts.is_command("/connect gmail") and accounts.is_command("/accounts@my_bot")
    assert not accounts.is_command("connect my gmail")

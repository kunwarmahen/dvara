"""A watch's look, made here as its person: ``POST /call``.

The bias these tests encode: A LOOK IS THE PERSON'S, OR IT IS NOBODY'S.
Prahari repeats a watch's check with no model; for someone else in the
house it must read with their accounts, in their folder -- so a guest's
look sees the guest's files, a tool that changes something runs only as
the one call they granted word for word, and a person whose watches the
owner did not turn on is turned away. The second bias: A LOOK IS NOT A
TURN. The scripted provider has no answers at all, so any model call
fails the test, and nothing is written to the person's runs.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from dvara.errors import Refused

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.http import create_app  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"


@pytest.fixture
def looks(make_service):
    def build(**kwargs):
        kwargs.setdefault("prahari", "/usr/bin/true")
        return make_service([], **kwargs)
    return build


def folder(service, actor: str):
    where = service.state / "work" / actor / "greeter"
    where.mkdir(parents=True, exist_ok=True)
    return where


class TestAsThePerson:
    def test_a_guests_look_reads_the_guests_own_folder(self, looks):
        service = looks()
        (folder(service, "guest") / "note.txt").write_text("the guest's own words\n")
        (folder(service, "owner") / "note.txt").write_text("the owner's secret\n")
        said = asyncio.run(service.call(actor="guest", agent="greeter", tool="read_file",
                                        arguments={"path": "note.txt"}))
        assert said["format"] == "yantra.call.v1" and said["ok"]
        assert "the guest's own words" in said["text"]
        assert "secret" not in said["text"]

    def test_no_model_is_asked_and_no_run_is_written(self, looks):
        service = looks()
        (folder(service, "guest") / "note.txt").write_text("x\n")
        asyncio.run(service.call(actor="guest", agent="greeter", tool="read_file",
                                 arguments={"path": "note.txt"}))
        assert service.scripted.requests == []
        assert service.runs.turns_since("guest", datetime(2000, 1, 1, tzinfo=UTC)) == (0, 0)

    def test_a_tool_that_writes_needs_the_call_granted_word_for_word(self, looks):
        service = looks()
        folder(service, "guest")
        refused = asyncio.run(service.call(
            actor="guest", agent="greeter", tool="write_file",
            arguments={"path": "a.txt", "content": "hi"}, allow_tools=["write_file"]))
        assert not refused["ok"] and "not read-only" in refused["detail"]
        granted = asyncio.run(service.call(
            actor="guest", agent="greeter", tool="write_file",
            arguments={"path": "a.txt", "content": "hi"},
            allow_tools=["write_file(path=a.txt, content=hi)"]))
        assert granted["ok"], granted["detail"]
        assert (folder(service, "guest") / "a.txt").read_text() == "hi"

    def test_an_unknown_tool_is_an_answer_not_a_crash(self, looks):
        said = asyncio.run(looks().call(actor="guest", agent="greeter", tool="read_fil",
                                        arguments={}))
        assert not said["ok"] and "did you mean read_file" in said["detail"]


class TestWhoseWatchesAreOn:
    def test_everyone_when_the_owner_named_nobody(self, looks):
        service = looks()
        assert service.watches_for("guest") and service.watches_for("owner")

    def test_only_those_named_when_some_are(self, looks):
        service = looks(prahari_for="owner")
        assert service.watches_for("owner") and not service.watches_for("guest")
        with pytest.raises(Refused, match="watches are off for guest"):
            asyncio.run(service.call(actor="guest", agent="greeter", tool="read_file",
                                     arguments={"path": "x"}))

    def test_nobody_when_watches_are_off(self, make_service):
        service = make_service([])
        with pytest.raises(Refused, match="watches are off"):
            asyncio.run(service.call(actor="owner", agent="greeter", tool="read_file",
                                     arguments={"path": "x"}))

    def test_an_agent_the_person_may_not_use_is_refused(self, looks, agents_root):
        from tests.conftest import write_package
        write_package(agents_root, "banker")
        service = looks()
        with pytest.raises(Refused):
            asyncio.run(service.call(actor="guest", agent="banker", tool="read_file",
                                     arguments={"path": "x"}))


class TestTheDoor:
    def test_call_answers_in_yantras_shape(self, looks):
        service = looks()
        (folder(service, "guest") / "note.txt").write_text("hello\n")
        with TestClient(create_app(service, token=TOKEN)) as client:
            reply = client.post("/call", headers={"Authorization": f"Bearer {TOKEN}"},
                                json={"actor": "guest", "agent": "greeter",
                                      "tool": "read_file", "args": {"path": "note.txt"}})
        assert reply.status_code == 200
        assert reply.json()["ok"] and "hello" in reply.json()["text"]

    def test_a_person_watches_are_off_for_is_404(self, looks):
        service = looks(prahari_for="owner")
        with TestClient(create_app(service, token=TOKEN)) as client:
            reply = client.post("/call", headers={"Authorization": f"Bearer {TOKEN}"},
                                json={"actor": "guest", "agent": "greeter",
                                      "tool": "read_file", "args": {}})
        assert reply.status_code == 404 and "watches are off" in reply.json()["detail"]

    def test_no_token_no_call_and_missing_fields_are_named(self, looks):
        with TestClient(create_app(looks(), token=TOKEN)) as client:
            assert client.post("/call", json={}).status_code == 401
            reply = client.post("/call", headers={"Authorization": f"Bearer {TOKEN}"},
                                json={"actor": "guest"})
        assert reply.status_code == 400 and "agent, tool" in reply.json()["detail"]


class TestAMailboxLogin:
    """The mailbox Prahari keeps open for someone: its login comes from THEIR
    Setu folder, with the key they unlocked it with -- never this computer's."""

    def setu(self, tmp_path):
        program = tmp_path / "setu"
        log = tmp_path / "setu.calls"
        program.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            f"open({str(log)!r}, 'a').write(json.dumps({{'argv': sys.argv[1:], "
            "'home': os.environ.get('SETU_HOME'), 'key': os.environ.get('SETU_VAULT_KEY')})"
            " + '\\n')\n"
            "print(json.dumps({'server': 'imap.example.com', 'port': 993, "
            "'user': 'asha@example.com', 'password': 'p', 'folder': 'INBOX', 'tls': True}))\n")
        program.chmod(0o755)
        return program, log

    def house(self):
        from dvara.actors import ActorBook
        return ActorBook.from_dict({"actor": {"owner": {}, "asha": {"setu": True}}})

    def test_it_is_read_from_their_own_folder(self, make_service, tmp_path):
        import json as _json
        service = make_service([], prahari="/usr/bin/true", actors=self.house())
        program, log = self.setu(tmp_path)
        service.accounts.setu = str(program)
        said = asyncio.run(service.mail_login(actor="asha", ref="mail:home"))
        assert said["user"] == "asha@example.com"
        call = _json.loads(log.read_text())
        assert call["argv"] == ["login", "mail:home", "--json"]
        assert call["home"] == str(service.state / "setu" / "asha")

    def test_only_a_mail_account_and_only_with_a_folder_of_their_own(self, make_service,
                                                                     tmp_path):
        service = make_service([], prahari="/usr/bin/true", actors=self.house())
        service.accounts.setu = str(self.setu(tmp_path)[0])
        with pytest.raises(Refused, match="only a mail account"):
            asyncio.run(service.mail_login(actor="asha", ref="gmail:personal"))
        with pytest.raises(Refused, match="no Setu folder"):
            asyncio.run(service.mail_login(actor="owner", ref="mail:home"))

    def test_the_door_answers_and_refuses_a_person_watches_are_off_for(self, make_service,
                                                                       tmp_path):
        service = make_service([], prahari="/usr/bin/true", prahari_for="owner",
                               actors=self.house())
        with TestClient(create_app(service, token=TOKEN)) as client:
            reply = client.post("/mail-login",
                                headers={"Authorization": f"Bearer {TOKEN}"},
                                json={"actor": "asha", "ref": "mail:home"})
        assert reply.status_code == 404 and "watches are off" in reply.json()["detail"]


class TestAPageOnASparePhone:
    """A page this computer's browser is turned away from, read on a phone.
    With nobody there, ONLY ON A SPARE PHONE OF THEIRS: never one someone
    carries, never another person's."""

    PAGE = "mcp__sparsh__open_url"
    ARGS = {"url": "https://shop.example/p/1"}

    def test_no_spare_phone_is_an_answer_that_says_where_to_mark_one(
            self, looks, monkeypatch):
        monkeypatch.delenv("SPARSH_SPARE", raising=False)
        said = asyncio.run(looks().call(actor="owner", agent="greeter", tool=self.PAGE,
                                        arguments=self.ARGS))
        assert not said["ok"] and "none is marked spare" in said["detail"]
        assert "Settings -> Your phones -> Spare" in said["detail"]

    def test_only_the_persons_spare_phones_start(self, looks, monkeypatch):
        from dataclasses import replace

        monkeypatch.setenv("SPARSH_SPARE", "drawer,ashas-old")
        service = looks()
        started = []

        async def phone(agent, manager, *, who, grants=None, only=()):
            started.append(only)
        monkeypatch.setattr(service, "_phone", phone)
        who = replace(service.actors.get("owner"), phones=("nexus", "drawer"))
        monkeypatch.setattr(service.actors, "may", lambda actor, agent: who)
        asyncio.run(service.call(actor="owner", agent="greeter", tool=self.PAGE,
                                 arguments=self.ARGS))
        assert started == [("drawer",)]          # theirs AND spare, nothing else

    def test_spare_phones_are_mine_and_marked(self, looks, monkeypatch):
        from dataclasses import replace

        monkeypatch.setenv("SPARSH_SPARE", "drawer, tablet")
        service = looks()
        owner = service.actors.get("owner")
        assert service._spare_phones(replace(owner, phones=("nexus",))) == ()
        assert service._spare_phones(replace(owner, phones=("tablet",))) == ("tablet",)
        assert service._spare_phones(replace(owner, phone=True)) == ("drawer", "tablet")
        assert service._spare_phones(replace(owner, phone=False)) == ()

    def test_other_tools_start_no_phone(self, looks, monkeypatch):
        monkeypatch.setenv("SPARSH_SPARE", "drawer")
        service = looks()
        started = []

        async def phone(*a, **k):
            started.append(1)
        monkeypatch.setattr(service, "_phone", phone)
        (folder(service, "owner") / "n.txt").write_text("x\n")
        asyncio.run(service.call(actor="owner", agent="greeter", tool="read_file",
                                 arguments={"path": "n.txt"}))
        assert started == []

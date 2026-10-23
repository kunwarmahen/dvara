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

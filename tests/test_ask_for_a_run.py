"""A question for a run that is not Dvara's, and a yes fixed to one thing.

Samay's direct road starts Yantra with nobody at it. "Turn off the stairs
light at four" met the switch there, refused, while its person sat in
front of Telegram. ``POST /ask`` lets that run put the question here.

The bias these tests encode: A QUESTION FROM OUTSIDE IS STILL A QUESTION
FROM HERE. It goes through the owner's rules and the person's rung
exactly as a turn's question does -- a deny rule refuses without asking,
a read-only person is never put on the spot -- and silence is a refusal
that lapses, never a yes and never held for a run that cannot be resumed
from here.

And A YES FIXED TO ONE THING COVERS ONLY THAT THING: a schedule that
allowed ``call_service(entity_id=switch.lights_2)`` ahead of time has
not allowed the same tool on the front door's lock.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.gate import Policy
from dvara.rules import Rule, RuleBook
from tests.conftest import says, write_package
from yantra.types import Message, ModelResponse, ToolCall, Usage

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.http import create_app  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
HA = "write_file"


def ask(service, **kw):
    body = {"actor": "owner", "tool": "write_file", "summary": "write notes.txt?",
            "arguments": {"path": "notes.txt"}, "timeout": 5.0}
    return service.ask(**{**body, **kw})


def answered(service, desk, approve, via="telegram", **kw):
    async def go():
        question = asyncio.create_task(ask(service, **kw))
        while not desk.pending():
            await asyncio.sleep(0)
        put = desk.pending()[0]
        desk.answer(put.id, actor="owner", approve=approve, via=via)
        return await question, put
    return asyncio.run(go())


class TestAQuestionFromOutside:
    def test_a_yes_in_the_chat_comes_back_as_approved_with_where(self, make_service):
        desk = AskDesk(timeout=5)
        service = make_service(asks=desk)
        answer, put = answered(service, desk, approve=True)
        assert answer.approved and answer.via == "telegram"
        assert put.tool == "write_file" and put.summary == "write notes.txt?"

    def test_a_no_comes_back_refused_by_the_person(self, make_service):
        desk = AskDesk(timeout=5)
        service = make_service(asks=desk)
        answer, _ = answered(service, desk, approve=False)
        assert not answer.approved and answer.code == "user"

    def test_silence_lapses_in_the_runs_own_wait_and_is_never_held(self, make_service):
        desk = AskDesk(timeout=5, on_timeout="hold")
        service = make_service(asks=desk)
        answer = asyncio.run(ask(service, timeout=0.05))
        assert not answer.approved and answer.code == "timeout"
        assert "wait the person set for this schedule" in answer.reason

    def test_a_standing_deny_refuses_without_asking_anybody(self, make_service):
        desk = AskDesk(timeout=5)
        rules = RuleBook([Rule(tool="write_file", verdict="deny")])
        service = make_service(asks=desk, policy=Policy(rules=rules))
        answer = asyncio.run(ask(service))
        assert not answer.approved and answer.code == "policy"
        assert desk.pending() == []

    def test_a_read_only_person_is_never_put_on_the_spot(self, make_service):
        desk = AskDesk(timeout=5)
        people = ActorBook.from_dict({"actor": {"owner": {"permissions": "read_only"}}})
        service = make_service(asks=desk, actors=people)
        answer = asyncio.run(ask(service))
        assert not answer.approved and desk.pending() == []

    def test_with_no_desk_there_is_nobody_to_ask(self, make_service):
        answer = asyncio.run(ask(make_service()))
        assert not answer.approved and answer.code == "unattended"


@pytest.fixture
def client(make_service):
    service = make_service(asks=AskDesk(timeout=5))
    with TestClient(create_app(service, token=TOKEN)) as client:
        yield client


def auth() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


class TestTheDoorForIt:
    def test_no_token_no_question(self, client):
        assert client.post("/ask", json={}).status_code == 401

    @pytest.mark.parametrize("body,said", [
        ({"tool": "x", "summary": "x", "timeout": 5}, "actor"),
        ({"actor": "owner", "tool": "x", "summary": "x"}, "timeout"),
        ({"actor": "owner", "tool": "x", "summary": "x", "timeout": 5,
          "arguments": [1]}, "arguments"),
    ])
    def test_a_malformed_question_is_a_400(self, client, body, said):
        reply = client.post("/ask", json=body, headers=auth())
        assert reply.status_code == 400 and said in reply.json()["detail"]

    def test_somebody_not_on_the_roster_is_a_404(self, client):
        reply = client.post("/ask", json={"actor": "ghost", "tool": "x", "summary": "x?",
                                          "timeout": 1}, headers=auth())
        assert reply.status_code == 404

    def test_an_unanswered_question_is_an_answer_not_an_error(self, client):
        reply = client.post("/ask", json={"actor": "owner", "tool": "write_file",
                                          "summary": "write?", "timeout": 0.05},
                            headers=auth())
        assert reply.status_code == 200
        assert reply.json()["approved"] is False and reply.json()["code"] == "timeout"


def lights(agents_root):
    write_package(agents_root, "home", body=(
        '[agent]\nname = "home"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file", "read_file"]\n'
        '[permissions]\nmode = "ask"\n'))


def writes(path) -> ModelResponse:
    return ModelResponse(
        message=Message("assistant", [
            ToolCall("c1", "write_file", {"path": path, "content": "x"})]),
        stop_reason="tool_use", usage=Usage(), model="test-model")


class TestAYesFixedToOneThing:
    def test_the_named_target_runs_without_a_question(self, make_service, agents_root):
        lights(agents_root)
        desk = AskDesk(timeout=5)
        service = make_service([writes("stairs.txt"), says("done")], asks=desk)
        reply = asyncio.run(service.deliver(
            actor="owner", agent="home", thread="t", text="go", unattended=True,
            allow_tools=["write_file(path=stairs.txt)"]))
        assert reply.ok and reply.refused == () and desk.pending() == []

    def test_another_target_on_the_same_tool_is_put_to_the_person(
            self, make_service, agents_root):
        lights(agents_root)
        desk = AskDesk(timeout=5)
        service = make_service([writes("front-door.txt"), says("asked")], asks=desk)

        async def go():
            turn = asyncio.create_task(service.deliver(
                actor="owner", agent="home", thread="t", text="go", unattended=True,
                allow_tools=["write_file(path=stairs.txt)"], wait=5))
            while not desk.pending():
                await asyncio.sleep(0)
            asked = desk.pending()[0]
            desk.answer(asked.id, actor="owner", approve=False)
            return await turn, asked
        reply, asked = asyncio.run(go())
        assert "front-door.txt" in asked.summary
        assert reply.refused == ("write_file",)

    def test_a_grant_typed_wrong_is_refused_at_the_door(self, make_service):
        service = make_service([says("x")])
        with TestClient(create_app(service, token=TOKEN)) as client:
            reply = client.post("/message", headers=auth(), json={
                "actor": "owner", "agent": "home", "thread": "t", "text": "go",
                "unattended": True, "allow_tools": ["write_file(path=stairs.txt"]})
        assert reply.status_code == 400 and "bracket is not closed" in reply.json()["detail"]

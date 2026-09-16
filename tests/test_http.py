"""Bias: a port that serves whoever reaches it.

The transport decides nothing except who is allowed to ask, so that is
what these tests are about -- a missing token, a wrong one, a body that
claims to be someone. The one thing this layer must never do is let the
``actor`` field mean anything on its own: it is an assertion by a trusted
caller, and the token is what makes the caller trusted.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.errors import ConfigProblem  # noqa: E402
from dvara.http import create_app  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"


@pytest.fixture
def client(make_service):
    from tests.conftest import says
    service = make_service([says("Hello.")] * 4)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.service = service
        yield client


def auth() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_a_service_without_a_token_refuses_to_start(make_service):
    with pytest.raises(ConfigProblem):
        create_app(make_service(), token="")


def test_a_short_token_is_treated_as_no_token(make_service):
    with pytest.raises(ConfigProblem):
        create_app(make_service(), token="hunter2")


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN},
])
def test_nothing_is_served_without_the_right_token(client, headers):
    assert client.get("/agents", headers=headers).status_code == 401
    assert client.post("/message", json={}, headers=headers).status_code == 401


def test_the_roster_lists_agents_without_loading_their_code(client):
    body = client.get("/agents", headers=auth()).json()
    assert body["agents"] == ["greeter"]


def test_a_message_comes_back_answered(client):
    reply = client.post("/message", headers=auth(), json={
        "actor": "owner", "agent": "greeter", "thread": "t", "text": "hi",
    }).json()
    assert reply["text"] == "Hello."
    assert reply["ok"] and reply["run_id"]


def test_a_refusal_is_a_200_with_a_reason_not_a_500(client):
    # A channel adapter has to be able to deliver the refusal as a
    # message. An exception here is a reply that silently never arrives.
    reply = client.post("/message", headers=auth(), json={
        "actor": "stranger", "agent": "greeter", "thread": "t", "text": "hi",
    })
    assert reply.status_code == 200
    assert reply.json()["ok"] is False
    assert reply.json()["stop_reason"] == "refused"


@pytest.mark.parametrize("body", [
    {}, {"actor": "owner"}, {"actor": "owner", "agent": "greeter",
                             "thread": "t", "text": "  "},
    {"actor": 7, "agent": "greeter", "thread": "t", "text": "hi"},
])
def test_a_malformed_body_is_a_400(client, body):
    assert client.post("/message", headers=auth(), json=body).status_code == 400


def test_health_says_what_the_service_holds(client):
    body = client.get("/health", headers=auth()).json()
    assert body == {"ok": True, "agents": 1, "actors": 2}


# ---- questions waiting for a person -----------------------------------------

@pytest.fixture
def asking(make_service, agents_root):
    """A service that escalates, with one question already standing."""
    import asyncio
    import threading
    import time

    from dvara.asks import AskDesk
    from tests.conftest import calls, says, write_package

    write_package(agents_root, "scribe", body=(
        '[agent]\nname = "scribe"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file"]\n'
        '[permissions]\nmode = "ask"\n'))
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("written."),
    ], asks=desk)

    # The turn runs on its own loop in its own thread, exactly as it would
    # under uvicorn: the point of these endpoints is that the answer
    # arrives from somewhere else entirely while the turn is parked.
    done: list = []

    def run_turn():
        done.append(asyncio.run(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down")))

    turn = threading.Thread(target=run_turn)
    turn.start()
    while not desk.pending():
        time.sleep(0.001)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.service, client.desk, client.done = service, desk, done
        client.turn = turn
        yield client
        # Let the turn finish INSIDE the client's lifespan. Leaving the
        # block is what closes the service's connection pools, and a turn
        # still in flight when that happens dies on its next model call --
        # which is a fixture bug that would look exactly like a bug in the
        # code under test.
        for ask in desk.pending():
            desk.answer(ask.id, actor=ask.actor, approve=False)
        turn.join(timeout=5)


def test_a_waiting_question_is_visible_to_a_caller(asking):
    body = asking.get("/asks", headers=auth()).json()
    assert len(body["asks"]) == 1
    ask = body["asks"][0]
    assert ask["tool"] == "write_file"
    assert ask["actor"] == "owner"
    assert "notes.txt" in ask["summary"]


def test_answering_releases_the_turn(asking):
    ask = asking.get("/asks", headers=auth()).json()["asks"][0]
    reply = asking.post(f"/asks/{ask['id']}",
                        json={"actor": "owner", "approve": True},
                        headers=auth())
    assert reply.status_code == 200
    assert reply.json() == {"answered": True, "approved": True}
    # The answer came from the TestClient's thread; the turn is parked on
    # a different loop entirely. If the desk did not hand it across, this
    # waits out the whole deadline and comes back refused for silence.
    asking.turn.join(timeout=5)
    assert asking.done and asking.done[0].ok


def test_a_question_put_to_somebody_else_is_not_yours_to_answer(asking):
    ask = asking.get("/asks", headers=auth()).json()["asks"][0]
    reply = asking.post(f"/asks/{ask['id']}",
                        json={"actor": "guest", "approve": True},
                        headers=auth())
    assert reply.status_code == 403
    assert asking.desk.pending(), "and the question is still standing"


def test_an_answer_that_is_not_a_boolean_is_refused(asking):
    # "no" is truthy. A channel adapter forwarding a person's literal
    # words into this field must fail loudly rather than approve.
    ask = asking.get("/asks", headers=auth()).json()["asks"][0]
    reply = asking.post(f"/asks/{ask['id']}",
                        json={"actor": "owner", "approve": "no"},
                        headers=auth())
    assert reply.status_code == 400
    assert "true or false" in reply.json()["detail"]
    assert asking.desk.pending()


def test_an_expired_question_answers_nothing(asking):
    reply = asking.post("/asks/nothing-like-a-real-id",
                        json={"actor": "owner", "approve": True},
                        headers=auth())
    assert reply.status_code == 404


def test_the_ask_endpoints_need_the_token_like_everything_else(asking):
    assert asking.get("/asks").status_code == 401
    assert asking.post("/asks/x", json={"actor": "owner",
                                        "approve": True}).status_code == 401


def test_a_service_that_does_not_escalate_has_no_questions(client):
    assert client.get("/asks", headers=auth()).json() == {"asks": []}
    reply = client.post("/asks/anything", json={"actor": "owner",
                                                "approve": True},
                        headers=auth())
    assert reply.status_code == 404
    assert "does not escalate" in reply.json()["detail"]

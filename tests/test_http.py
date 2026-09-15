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

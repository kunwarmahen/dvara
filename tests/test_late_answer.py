"""Bias: an answer written to nobody.

A schedule's caller (Samay) waits its time limit, then stops listening;
the turn goes on here and finishes. Its answer used to go back down a
connection nobody held, and the person never saw what was written for
them. Now a caller says ahead what a late answer is for -- ``send`` it to
the person, or ``keep`` it -- and only a caller that really hung up
changes anything.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from dvara.http import create_app  # noqa: E402
from tests.conftest import says  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
TURN = {"actor": "owner", "agent": "greeter", "thread": "samay-x-1",
        "text": "Write my morning brief.", "unattended": True, "came_by": "samay"}


@pytest.fixture
def told(make_service, monkeypatch):
    service = make_service([says("**Mail** -- one bill.")])
    sent: list[tuple[str, str]] = []

    async def notify(*, text, actor, via):
        sent.append((actor, text))
        return actor, None

    monkeypatch.setattr(service, "notify", notify)
    return service, sent


def hung_up(monkeypatch, gone: bool) -> None:
    async def is_disconnected(self) -> bool:
        return gone
    monkeypatch.setattr(Request, "is_disconnected", is_disconnected)


def test_a_caller_that_hung_up_has_the_answer_sent_to_the_person(told, monkeypatch):
    service, sent = told
    hung_up(monkeypatch, True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/message", headers=AUTH, json={**TURN, "if_late": "send"})
    (whom, text), = sent
    assert whom == "owner"
    assert text == ("Finished after Samay had stopped waiting (greeter):\n\n"
                    "**Mail** -- one bill.")


def test_a_caller_still_there_gets_it_and_nobody_is_told_twice(told, monkeypatch):
    service, sent = told
    hung_up(monkeypatch, False)
    with TestClient(create_app(service, token=TOKEN)) as client:
        reply = client.post("/message", headers=AUTH, json={**TURN, "if_late": "send"})
    assert reply.json()["text"] == "**Mail** -- one bill." and sent == []


@pytest.mark.parametrize("extra", [{"if_late": "keep"}, {}])
def test_keep_or_nothing_said_sends_nothing(told, monkeypatch, extra):
    service, sent = told
    hung_up(monkeypatch, True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/message", headers=AUTH, json={**TURN, **extra})
    assert sent == []


@pytest.mark.parametrize(("extra", "said"), [
    ({"if_late": "maybe"}, "if_late is send or keep"),
    ({"if_late": "send", "unattended": False}, "if_late goes with unattended"),
])
def test_a_wrong_if_late_is_refused(told, extra, said):
    service, _ = told
    with TestClient(create_app(service, token=TOKEN)) as client:
        reply = client.post("/message", headers=AUTH, json={**TURN, **extra})
    assert reply.status_code == 400 and said in reply.json()["detail"]

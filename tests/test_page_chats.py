"""Each conversation on the page is its own chat (web.py).

The bias is ONE CONVERSATION KEEPING ANOTHER WAITING, OR ITS WORDS AND
ANSWERS LANDING IN THE OTHER. A page lists conversations; a person who
asks in one while another is still answering means both, now, as a chat
app does. So: a new chat gets its own conversation and its id on the
line; a second conversation answers while the first is still working;
every line, every live view and ``working`` say which conversation they
are; words with a conversation's id carry that one on in its own chat; a
conversation answering cannot be deleted from under itself, and one that
is not is deleted with its page chat; and a caller that names neither
(no list of its own) still has the one page chat it always had.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.http import create_app  # noqa: E402
from dvara.keys import session_key  # noqa: E402
from dvara.web import THREAD, page_thread  # noqa: E402
from tests.conftest import says  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def asked_last(messages) -> str:
    for m in reversed(messages):
        if m.role == "user":
            for block in m.content:
                if getattr(block, "text", None):
                    return block.text
    return ""


@pytest.fixture
def page(make_service):
    """A page whose model answers "answer to WORDS", and holds any
    question that starts "slow" until ``release`` is set."""
    service = make_service([], web=True)
    release = threading.Event()
    seen: list[list[str]] = []

    model = service.scripted
    plain_complete, plain_stream = type(model).acomplete, type(model).astream

    async def held(messages):
        said = asked_last(messages)
        seen.append([asked_last([m]) for m in messages if m.role == "user"])
        while said.startswith("slow") and not release.is_set():
            await asyncio.sleep(0.01)
        model.script.append(says(f"answer to {said}"))

    async def acomplete(**kwargs):
        await held(kwargs["messages"])
        return await plain_complete(model, **kwargs)

    async def astream(**kwargs):
        await held(kwargs["messages"])
        async for event in plain_stream(model, **kwargs):
            yield event

    model.acomplete, model.astream = acomplete, astream
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.release, client.seen, client.service = release, seen, service
        yield client
    release.set()


def say(client, text, **more):
    return client.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": text, **more}).json()["line"]


def look(client):
    return client.get("/web?actor=owner", headers=AUTH).json()


def until(client, test, *, within=5.0):
    end = time.monotonic() + within
    while time.monotonic() < end:
        seen = look(client)
        if test(seen):
            return seen
        time.sleep(0.02)
    raise AssertionError(f"never happened; last look: {seen}")


def answers(seen):
    return {ln["text"]: ln.get("conversation") for ln in seen["lines"] if ln["who"] == "agent"}


def test_a_new_chat_gets_its_own_conversation_and_its_id_on_the_line(page):
    line = say(page, "where should we go?", new=True)
    conv = line["conversation"]
    seen = until(page, lambda s: not s["busy"])
    assert answers(seen) == {"answer to where should we go?": conv}
    rows = page.service.past.listed("owner", "greeter")
    assert [(r.id, r.title) for r in rows] == [(conv, "where should we go?")]
    assert page.service.past.here(session_key("owner", "greeter", page_thread(conv))) == conv


def test_a_second_conversation_answers_while_the_first_is_still_working(page):
    slow = say(page, "slow: plan the whole trip", new=True)["conversation"]
    until(page, lambda s: s["working"] == [slow])
    quick = say(page, "what time is it?", new=True)["conversation"]
    seen = until(page, lambda s: "answer to what time is it?" in answers(s))
    assert seen["working"] == [slow]                    # still at it
    assert answers(seen) == {"answer to what time is it?": quick}
    page.release.set()
    seen = until(page, lambda s: not s["working"])
    assert answers(seen) == {"answer to what time is it?": quick,
                             "answer to slow: plan the whole trip": slow}


def test_each_live_view_says_its_conversation(page):
    slow = say(page, "slow: one", new=True)["conversation"]
    seen = until(page, lambda s: s["live"])
    assert [(lv["agent"], lv["conversation"]) for lv in seen["live"]] == [("greeter", slow)]
    page.release.set()


def test_words_with_its_id_carry_that_conversation_on_in_its_own_chat(page):
    first = say(page, "where should we go?", new=True)["conversation"]
    until(page, lambda s: not s["busy"])
    say(page, "what time is it?", new=True)
    until(page, lambda s: not s["busy"])
    line = say(page, "and then?", conversation=first)
    assert line["conversation"] == first
    until(page, lambda s: "answer to and then?" in answers(s))
    assert page.seen[-1] == ["where should we go?", "and then?"]


def test_words_for_a_conversation_still_answering_wait_in_its_chat(page):
    slow = say(page, "slow: one", new=True)["conversation"]
    until(page, lambda s: s["working"] == [slow])
    say(page, "and two", conversation=slow)
    time.sleep(0.1)
    assert "answer to and two" not in answers(look(page))   # its own chat, in turn
    page.release.set()
    seen = until(page, lambda s: "answer to and two" in answers(s))
    assert answers(seen)["answer to and two"] == slow
    assert page.seen[-1] == ["slow: one", "and two"]


def test_a_conversation_answering_is_not_deleted_from_under_itself(page):
    slow = say(page, "slow: one", new=True)["conversation"]
    until(page, lambda s: s["working"] == [slow])
    gone = page.request("DELETE", f"/web/chats/{slow}", headers=AUTH,
                        params={"actor": "owner"})
    assert gone.status_code == 409 and "answering now" in gone.json()["detail"]
    page.release.set()
    until(page, lambda s: not s["working"])
    assert page.request("DELETE", f"/web/chats/{slow}", headers=AUTH,
                        params={"actor": "owner"}).status_code == 200
    key = session_key("owner", "greeter", page_thread(slow))
    assert page.service.past.here(key) is None
    assert page.service.sessions.load_latest(key) is None


def test_new_in_a_conversation_clears_that_window_only(page):
    conv = say(page, "where should we go?", new=True)["conversation"]
    until(page, lambda s: not s["busy"])
    say(page, "/new", conversation=conv)
    seen = until(page, lambda s: any(ln.get("fresh") for ln in s["lines"]))
    fresh = next(ln for ln in seen["lines"] if ln.get("fresh"))
    assert fresh["conversation"] == conv


def test_a_caller_that_names_no_conversation_has_the_one_page_chat(page):
    say(page, "where should we go?")
    until(page, lambda s: not s["busy"])
    say(page, "and then?")
    until(page, lambda s: "answer to and then?" in answers(s))
    assert page.seen[-1] == ["where should we go?", "and then?"]
    key = session_key("owner", "greeter", THREAD)
    assert page.service.past.here(key) == page.service.past.listed("owner", "greeter")[0].id

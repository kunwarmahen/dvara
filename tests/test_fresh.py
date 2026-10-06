"""Starting over: ``/new``.

The bias these tests encode: STARTING OVER FORGETS THE CONVERSATION AND
NOTHING ELSE. The failure worth designing against is a word that reaches
too far -- into the ledger, the person's folder, or somebody else's
thread -- or one that does too little, leaving the old turns in front of
the model so the habit it was meant to break carries on. So each test
checks what the next turn's model is shown, and beside it what must
still be there.
"""

from __future__ import annotations

import asyncio

from dvara import fresh
from dvara.keys import session_key
from tests.conftest import says


def say(service, text, *, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter",
                                       thread=thread, text=text))


def shown(service, n=-1):
    """Every user text the model was shown on its n-th call."""
    return [block.text for m in service.scripted.requests[n]["messages"]
            if m.role == "user" for block in m.content
            if getattr(block, "text", None)]


def test_the_word_is_recognised_with_or_without_the_bots_name():
    assert fresh.is_new_word("/new")
    assert fresh.is_new_word("  /NEW  ")
    assert fresh.is_new_word("/new@SarathiAgentBot")
    assert not fresh.is_new_word("/newer")
    assert not fresh.is_new_word("tell me what's new")


def test_the_next_turn_is_shown_none_of_what_came_before(make_service):
    service = make_service([says("one"), says("two")])
    say(service, "fetch it with web_fetch")
    reply = say(service, "/new")
    assert reply.text == fresh.STARTED_OVER
    assert reply.run_id is None                    # not a turn
    say(service, "the latest post, please")
    assert shown(service) == ["the latest post, please"]


def test_starting_over_reaches_no_model_and_spends_nothing(make_service):
    # An empty script: a model call here would raise "script exhausted".
    service = make_service([])
    assert say(service, "/new").text == fresh.NOTHING_YET
    assert service.scripted.requests == []
    assert service.runs.recent() == []


def test_the_ledger_and_the_folder_stay(make_service):
    service = make_service([says("noted")])
    say(service, "keep a note")
    work = service.state / "work" / "owner" / "greeter"
    work.mkdir(parents=True, exist_ok=True)
    (work / "log.txt").write_text("kept\n")
    say(service, "/new")
    assert len(service.runs.recent()) == 1
    assert (work / "log.txt").read_text() == "kept\n"


def test_only_this_conversation_goes(make_service):
    service = make_service([says("a"), says("b")])
    say(service, "first chat", thread="chat")
    say(service, "another chat", thread="other")
    say(service, "/new", thread="chat")
    assert service.sessions.load_latest(session_key("owner", "greeter", "chat")) is None
    assert service.sessions.load_latest(session_key("owner", "greeter", "other"))


def test_a_turn_still_running_is_not_pulled_out_from_under_it(make_service):
    service = make_service([says("hi")])
    say(service, "hello")
    key = session_key("owner", "greeter", "chat")

    async def while_busy():
        async with service._locks.hold(key):
            return await service.deliver(actor="owner", agent="greeter",
                                         thread="chat", text="/new")

    assert asyncio.run(while_busy()).text == fresh.STILL_ANSWERING
    assert service.sessions.load_latest(key)

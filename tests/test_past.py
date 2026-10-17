"""Past conversations: kept by ``/new``, opened by ``/chats N`` (past.py).

The bias is A CONVERSATION THAT COMES BACK WRONG, OR NOT AT ALL, OR TO
SOMEBODY ELSE. What ``/new`` ends is kept whole and listed; going back
puts exactly it in front of the model and keeps the one it replaced; one
person never sees another's; and nothing here is a turn.
"""

from __future__ import annotations

import asyncio

from dvara import past
from dvara.keys import session_key
from tests.conftest import says


def say(service, text, *, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter",
                                       thread=thread, text=text))


def shown(service, n=-1):
    return [block.text for m in service.scripted.requests[n]["messages"]
            if m.role == "user" for block in m.content
            if getattr(block, "text", None)]


def test_new_keeps_what_it_ends_and_chats_lists_it(make_service):
    service = make_service([says("The trip is on Friday.")])
    say(service, "when is the school trip?")
    say(service, "/new")
    listed = say(service, "/chats")
    assert listed.run_id is None
    assert "1. when is the school trip? —" in listed.text and "1 message" in listed.text


def test_going_back_shows_the_model_that_conversation_and_keeps_this_one(make_service):
    service = make_service([says("Friday."), says("Hello."), says("Bring a packed lunch.")])
    say(service, "when is the school trip?")
    say(service, "/new")
    say(service, "hi")
    back = say(service, "/chats 1")
    assert back.text.startswith("Back in: when is the school trip?")
    assert "Where we left it: Friday." in back.text
    say(service, "what should he bring?")
    assert shown(service) == ["when is the school trip?", "what should he bring?"]
    assert [r.title for r in service.past.listed("owner", "greeter")] == ["hi"]


def test_a_number_that_is_not_there_is_said(make_service):
    service = make_service([says("x")])
    say(service, "a")
    say(service, "/new")
    assert "no conversation 7" in say(service, "/chats 7").text
    assert "no conversation two" in say(service, "/chats two").text


def test_one_persons_conversations_are_never_anothers(make_service):
    service = make_service([says("x")])
    say(service, "my secret plan")
    say(service, "/new")
    theirs = say(service, "/chats", actor="guest")
    assert "secret" not in theirs.text and "no earlier conversations" in theirs.text


def test_nothing_said_is_nothing_kept(make_service):
    service = make_service([])
    say(service, "/new")
    assert service.past.listed("owner", "greeter") == []


def test_the_book_keeps_only_the_newest(tmp_path):
    book = past.PastBook(tmp_path / "p.sqlite3", keep=2)
    for n in range(3):
        book.keep_one("o", "a", "web:chat", {"history": [
            {"role": "user", "content": [{"kind": "text", "text": f"chat {n}"}]}]})
    assert [r.title for r in book.listed("o", "a")] == ["chat 2", "chat 1"]
    assert book.listed("o", "a")[0].came == "the page"
    book.close()


def test_the_session_it_replaces_is_its_own_key(make_service):
    service = make_service([says("Friday.")])
    say(service, "trip?")
    say(service, "/new")
    say(service, "/chats 1")
    assert service.sessions.load_latest(session_key("owner", "greeter", "chat"))

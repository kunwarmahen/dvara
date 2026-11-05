"""Words carried on in the conversation they were written under (past.py).

The bias is WORDS ANSWERED IN THE WRONG CONVERSATION. A page showed an
old conversation and said "write below to carry it on"; it sent
``/chats open ID`` and then the words, and when the chat was still
answering in the newer conversation the first was turned away and the
second answered there, under a window that showed the old one. So: words
sent with a conversation are answered in it, in one go; a chat still
answering is waited out, never refused; a conversation that is gone is
said so and the words are answered nowhere; one person's id never opens
another's; and on Telegram a reply to an old answer carries that
conversation on, with ``/chats`` offering a button for each.
"""

from __future__ import annotations

import asyncio
import time

from dvara import past
from dvara.actors import ActorBook
from dvara.keys import session_key
from dvara.telegram import TelegramBot
from tests.conftest import says
from tests.test_telegram import KNOWN, TOKEN, FakeTelegram, message


def say(service, text, *, actor="owner", conversation=None):
    return asyncio.run(service.deliver(actor=actor, agent="greeter", thread="chat",
                                       text=text, conversation=conversation))


def shown(service, n=-1):
    return [block.text for m in service.scripted.requests[n]["messages"]
            if m.role == "user" for block in m.content
            if getattr(block, "text", None)]


def two_conversations(service):
    """The first about a trip, then /new and a second; the first's id."""
    say(service, "where should we go?")
    say(service, "/new")
    say(service, "hello")
    return next(r.id for r in service.past.listed("owner", "greeter")
                if r.title == "where should we go?")


def test_words_sent_with_a_conversation_are_answered_in_it(make_service):
    service = make_service([says("Lisbon."), says("Hi."), says("Book flights.")])
    old = two_conversations(service)
    reply = say(service, "and then?", conversation=old)
    assert reply.text == "Book flights."
    assert shown(service) == ["where should we go?", "and then?"]
    assert reply.moved == "Back in: where should we go?"
    assert reply.conversation == old
    rows = service.past.listed("owner", "greeter")
    assert [(r.title, r.turns) for r in rows] == [("where should we go?", 2), ("hello", 1)]


def test_the_conversation_it_is_in_already_is_no_move(make_service):
    service = make_service([says("Lisbon."), says("Porto too.")])
    say(service, "where should we go?")
    here = service.past.listed("owner", "greeter")[0].id
    reply = say(service, "anywhere else?", conversation=here)
    assert reply.moved == "" and reply.conversation == here
    assert shown(service) == ["where should we go?", "anywhere else?"]


def test_a_chat_still_answering_is_waited_out_not_refused(make_service):
    """The case that went wrong: the newer conversation still answering
    when words are written under the older one."""
    service = make_service([says("Lisbon."), says("Hi."), says("Book flights.")])
    old = two_conversations(service)
    key = session_key("owner", "greeter", "chat")

    async def busy_then_carried_on():
        async with service._locks.hold(key):        # a turn still answering
            carried = asyncio.ensure_future(service.deliver(
                actor="owner", agent="greeter", thread="chat", text="and then?",
                conversation=old))
            await asyncio.sleep(0.05)
            assert not carried.done()                # waiting, not refused
        return await carried

    reply = asyncio.run(busy_then_carried_on())
    assert reply.text == "Book flights."
    assert shown(service) == ["where should we go?", "and then?"]


def test_chats_n_typed_while_the_chat_answers_waits_too(make_service):
    service = make_service([says("Lisbon."), says("Hi."), says("Book flights.")])
    two_conversations(service)
    key = session_key("owner", "greeter", "chat")

    async def busy_then_back():
        async with service._locks.hold(key):
            back = asyncio.ensure_future(service.deliver(
                actor="owner", agent="greeter", thread="chat", text="/chats 2"))
            await asyncio.sleep(0.05)
            assert not back.done()
        return await back

    assert asyncio.run(busy_then_back()).text.startswith("Back in: where should we go?")


def test_a_conversation_that_is_gone_is_said_and_answered_nowhere(make_service):
    service = make_service([says("Lisbon.")])
    say(service, "where should we go?")
    asked = len(service.scripted.requests)
    reply = say(service, "and then?", conversation="not-a-conversation")
    assert reply.text == past.GONE and reply.stop_reason == "refused"
    assert len(service.scripted.requests) == asked          # no turn at all


def test_one_persons_conversation_is_gone_to_another(make_service):
    service = make_service([says("x")])
    say(service, "my secret plan")
    mine = service.past.listed("owner", "greeter")[0].id
    reply = say(service, "what was the plan?", actor="guest", conversation=mine)
    assert reply.text == past.GONE
    assert service.past.listed("guest") == []


def test_new_leaves_no_conversation_on_its_reply(make_service):
    service = make_service([says("Lisbon.")])
    say(service, "where should we go?")
    assert say(service, "/new").conversation is None


def test_chats_offers_a_button_for_each_but_the_one_open(make_service):
    service = make_service([says("Lisbon."), says("Hi.")])
    two_conversations(service)
    listed = say(service, "/chats")
    assert listed.choices == (("2. where should we go?", "/chats 2"),)


def test_a_long_title_is_cut_on_its_button():
    row = type("Row", (), {"id": "a", "title": "x" * 80})()
    (label, word), = past.choices([row], {"a": 3})
    assert len(label) == past.BUTTON_LABEL and label.endswith("…") and word == "/chats 3"


def test_a_message_id_finds_its_conversation_and_the_oldest_are_let_go(tmp_path,
                                                                       monkeypatch):
    book = past.PastBook(tmp_path)
    monkeypatch.setattr(past, "SAID_KEPT", 3)
    book.sent("telegram:greeter:1", [1, 2, None], "first")
    book.sent("telegram:greeter:1", [3, 4], "second")
    book.sent("telegram:greeter:2", [1], "elsewhere")
    assert book.sent_in("telegram:greeter:1", 1) is None          # let go
    assert [book.sent_in("telegram:greeter:1", m) for m in (2, 3, 4)] == [
        "first", "second", "second"]
    assert book.sent_in("telegram:greeter:2", 1) == "elsewhere"   # its own chat
    assert book.sent_in("telegram:greeter:1", None) is None
    book.close()


# ---- the page: one request carries it on ------------------------------------


def test_the_page_carries_one_on_in_one_request_while_the_other_answers(make_service):
    from fastapi.testclient import TestClient

    from dvara.http import create_app

    service = make_service([says("Lisbon."), says("hi"), says("Book flights.")], web=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        def finish(text, **more):
            client.post("/web/message", headers=auth, json={
                "actor": "owner", "agent": "greeter", "text": text, **more})
            for _ in range(200):
                seen = client.get("/web?actor=owner", headers=auth).json()
                if not seen["busy"]:
                    return seen
                time.sleep(0.02)
            return seen

        finish("where should we go?")
        finish("/new")
        finish("hello")
        old = client.get("/web/chats", headers=auth, params={
            "actor": "owner", "q": "where"}).json()["rows"][0]["id"]
        seen = finish("and then?", conversation=old)
    assert [ln["text"] for ln in seen["lines"][-2:]] == ["and then?", "Book flights."]
    rows = service.past.listed("owner", "greeter")
    assert [(r.title, r.turns) for r in rows] == [("where should we go?", 2), ("hello", 1)]


# ---- Telegram: a reply goes back --------------------------------------------


def bot_for(fake, service):
    bot = TelegramBot(service, token=TOKEN, agent="greeter", client=fake.client(),
                      send_gap=0.0, poll_seconds=0, catch_up=True)
    fake.bot = bot
    return bot


def sent_id(fake, text):
    """The message_id the fake gave the message that said ``text``."""
    return next(n for n, (m, p) in enumerate(fake.calls, 1)
                if m == "sendMessage" and p.get("text") == text)


ON_TELEGRAM = {"actor": {"mahen": {"channel": [{"kind": "telegram", "id": KNOWN}]}}}


def test_a_reply_to_an_old_answer_carries_that_conversation_on(make_service):
    service = make_service([says("Lisbon."), says("Hi."), says("Book flights.")],
                           actors=ActorBook.from_dict(ON_TELEGRAM))
    first = FakeTelegram([message("where should we go?", update_id=1)])
    asyncio.run(bot_for(first, service).run())
    answer = sent_id(first, "Lisbon.")
    then = FakeTelegram([message("/new", update_id=2)], [message("hello", update_id=3)])
    asyncio.run(bot_for(then, service).run())

    back = FakeTelegram([message("and then?", update_id=4,
                                 reply_to_message={"message_id": answer})])
    asyncio.run(bot_for(back, service).run())
    assert back.texts() == ["Back in: where should we go?", "Book flights."]
    assert shown(service) == ["where should we go?", "and then?"]


def test_a_reply_to_a_message_in_the_one_open_says_nothing_of_moving(make_service):
    service = make_service([says("Lisbon."), says("Porto too.")],
                           actors=ActorBook.from_dict(ON_TELEGRAM))
    first = FakeTelegram([message("where should we go?", update_id=1)])
    asyncio.run(bot_for(first, service).run())
    again = FakeTelegram([message("anywhere else?", update_id=2,
                                  reply_to_message={"message_id": sent_id(first, "Lisbon.")})])
    asyncio.run(bot_for(again, service).run())
    assert again.texts() == ["Porto too."]


def test_chats_on_telegram_has_a_button_that_goes_back(make_service):
    service = make_service([says("Lisbon."), says("Hi.")],
                           actors=ActorBook.from_dict(ON_TELEGRAM))
    for n, text in enumerate(("where should we go?", "/new", "hello", "/chats"), 1):
        fake = FakeTelegram([message(text, update_id=n)])     # one at a time
        asyncio.run(bot_for(fake, service).run())
    listing = fake.sent()[-1]
    assert listing["reply_markup"] == {"inline_keyboard": [[
        {"text": "2. where should we go?", "callback_data": "w:/chats 2"}]]}

    pressed = FakeTelegram([{"update_id": 5, "callback_query": {
        "id": "cb", "from": {"id": KNOWN}, "data": "w:/chats 2",
        "message": {"message_id": 9, "chat": {"id": KNOWN}}}}])
    asyncio.run(bot_for(pressed, service).run())
    assert pressed.texts()[-1].startswith("Back in: where should we go?")

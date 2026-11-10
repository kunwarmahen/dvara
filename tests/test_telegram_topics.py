"""Bias: a topic's conversation answered in, or mixed with, another.

A bot whose private chat has topics turned on (Bot API 9.3) gets each
message with the topic it was written in. The failures worth a test: an
answer that lands in the chat instead of the topic it was asked in; two
topics sharing one conversation, so one's words are the other's
history; a chat without topics changed at all; and a topic Telegram
refuses to send into (deleted, or a Bot API that won't), which must
still leave an answer rather than none.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from dvara.actors import ActorBook
from dvara.keys import session_key
from dvara.telegram import Chat, TelegramBot, _chat_in, _thread

from tests.conftest import says

BOT_TOKEN = "8675309:AAtest-token-not-a-real-one"
ME = 8675309


class Wire:
    """Enough of the Bot API to see where each message went; ``refuse``
    turns a topic down the way Telegram does."""

    def __init__(self, refuse: bool = False) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.refuse = refuse

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        if self.refuse and "message_thread_id" in payload:
            return httpx.Response(400, json={
                "ok": False, "description": "Bad Request: message thread not found"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.calls)}})

    def sent(self) -> list[dict]:
        return [p for m, p in self.calls if m == "sendMessage"]


def in_topic(text: str, topic: int | None, message_id: int = 1) -> dict:
    message = {"message_id": message_id, "from": {"id": ME}, "chat": {"id": ME},
               "text": text}
    if topic is not None:
        message.update(message_thread_id=topic, is_topic_message=True)
    return {"update_id": message_id, "message": message}


@pytest.fixture
def bot(make_service):
    def build(script, refuse=False):
        people = ActorBook.from_dict({"actor": {
            "owner": {"channel": [{"kind": "telegram", "id": ME}]}}})
        service = make_service(script, actors=people)
        wire = Wire(refuse)
        made = TelegramBot(service, token=BOT_TOKEN, agent="greeter",
                           client=wire.client(), send_gap=0.0, poll_seconds=0)
        made.wire = wire
        made.notes = []
        made._note = made.notes.append
        return made
    return build


def test_a_chat_and_its_topic_are_told_apart():
    plain = _chat_in({"chat": {"id": ME}})
    topic = _chat_in({"chat": {"id": ME}, "message_thread_id": 7, "is_topic_message": True})
    reply = _chat_in({"chat": {"id": ME}, "message_thread_id": 7})   # a reply thread, not a topic
    assert (plain, plain.topic, _thread(plain)) == (ME, None, str(ME))
    assert (topic, topic.topic, _thread(topic)) == (ME, 7, f"{ME}/7")
    assert reply.topic is None
    assert json.dumps({"chat_id": Chat(ME, 7)}) == f'{{"chat_id": {ME}}}'


def test_the_answer_goes_back_into_the_topic_it_was_asked_in(bot):
    made = bot([says("In topic seven.")])
    asyncio.run(made._handle(in_topic("hi", 7)))
    [answer] = made.wire.sent()
    assert answer["text"] == "In topic seven." and answer["message_thread_id"] == 7
    typing = [p for m, p in made.wire.calls if m == "sendChatAction"]
    assert typing and all(p.get("message_thread_id") == 7 for p in typing)


def test_each_topic_is_its_own_conversation(bot):
    made = bot([says("one"), says("two"), says("one again")])
    asyncio.run(made._handle(in_topic("plan the trip", 7, 1)))
    asyncio.run(made._handle(in_topic("fix the sink", 9, 2)))
    asyncio.run(made._handle(in_topic("and the hotel?", 7, 3)))
    past = made.service.past
    seven = past.here(session_key("owner", "greeter", f"telegram:{ME}/7"))
    nine = past.here(session_key("owner", "greeter", f"telegram:{ME}/9"))
    assert seven and nine and seven != nine
    # topic 7's third message was answered with its own history only
    last = made.service.scripted.requests[-1]
    words = json.dumps([str(m) for m in last["messages"]]) if isinstance(last, dict) \
        else str(last)
    assert "plan the trip" in words and "fix the sink" not in words


def test_a_chat_without_topics_is_unchanged(bot):
    made = bot([says("plain.")])
    asyncio.run(made._handle(in_topic("hi", None)))
    [answer] = made.wire.sent()
    assert "message_thread_id" not in answer
    assert made.service.past.here(session_key("owner", "greeter", f"telegram:{ME}"))


def test_a_topic_telegram_refuses_is_answered_in_the_chat_itself(bot):
    from dvara.telegram import TOPIC_REFUSED
    made = bot([says("Still answered."), says("And again.")], refuse=True)
    asyncio.run(made._handle(in_topic("hi", 7)))
    landed = [p for p in made.wire.sent() if "message_thread_id" not in p]
    # said once, before the answer, so it isn't silently somewhere else
    assert [p["text"] for p in landed] == [TOPIC_REFUSED, "Still answered."]
    assert any("topic 7 refused" in n for n in made.notes)
    # the same topic again: not tried, not told twice
    asyncio.run(made._handle(in_topic("more", 7, 2)))
    later = made.wire.sent()[len(made.wire.sent()) - 1:]
    assert [p["text"] for p in later] == ["And again."]
    assert sum(p["text"] == TOPIC_REFUSED for p in made.wire.sent()) == 1


def test_telegrams_own_topic_note_is_not_answered(bot):
    # a chat with topics on: typing outside one makes a topic, and Telegram
    # sends "topic created" as a message with no words
    made = bot([])
    note = {"update_id": 5, "message": {
        "message_id": 5, "from": {"id": ME}, "chat": {"id": ME},
        "message_thread_id": 5, "is_topic_message": True,
        "forum_topic_created": {"name": "/routines W2R7ZH blue door", "icon_color": 1}}}
    asyncio.run(made._handle(note))
    assert made.wire.sent() == []
    sticker = in_topic("x", 7)
    del sticker["message"]["text"]
    sticker["message"]["sticker"] = {"file_id": "s"}
    asyncio.run(made._handle(sticker))
    assert [p["text"] for p in made.wire.sent()] == [
        "I can read words, pictures and files, not this."]


def test_a_reply_to_a_routines_question_answers_it(bot, monkeypatch):
    made = bot([])
    heard = []

    async def answered(actor, text, **kw):
        heard.append(text)
        return 'Yes to "Send it?" — it carries on now.'

    made.service.vidhi = "vidhi"
    monkeypatch.setattr(made.service.routines, "answer", answered)
    update = in_topic("blue door", None, 8)
    update["message"]["reply_to_message"] = {
        "message_id": 3, "from": {"id": 1, "is_bot": True},
        "text": "Answer in a few words: /routines say W2R7ZH your words"}
    asyncio.run(made._handle(update))
    assert heard == ["/routines say W2R7ZH blue door"]

"""Bias: a channel that turns a held turn's answer into the wrong answer.

``test_holds.py`` is the queue; this is every door onto it (notes/16).
Each one has its own way to get a held turn wrong:

* HTTP: the string "yes" read as a yes, or "not yours" reported as "gone";
* Telegram: a held reply with no way to answer it from the chat, a press
  by somebody else that carries the turn on, or the rest of the answer
  landing in the wrong chat;
* the terminal: a call nobody named approved by default, or a held turn
  that the ledger cannot tell from a refused one.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from dvara.actors import ActorBook
from dvara.asks import Answer, AskDesk
from dvara.cli import main
from dvara.keys import session_key
from dvara.roster import Roster
from dvara.service import Service
from dvara.telegram import TelegramBot, ending
from yantra import HELD

from tests.conftest import ScriptedProvider, says
from tests.test_what_decided_it import scribe, two_calls


def holding() -> AskDesk:
    return AskDesk(timeout=0.05, on_timeout="hold")


# ---- HTTP -------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.http import create_app  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def web(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("wrote a.")], asks=holding())
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.service = service
        yield client


def held_over_http(web) -> dict:
    body = web.post("/message", headers=AUTH, json={
        "actor": "owner", "agent": "scribe", "thread": "t",
        "text": "write both"}).json()
    assert body["stop_reason"] == "held"
    return body["held"]


def test_a_held_message_says_what_is_waiting_and_how_to_answer(web):
    held = held_over_http(web)
    assert [c["id"] for c in held["calls"]] == ["call-a", "call-b"]
    assert held["id"] and "key" not in held
    listed = web.get("/holds?actor=owner", headers=AUTH).json()["holds"]
    assert [h["id"] for h in listed] == [held["id"]]


def test_posting_answers_carries_the_turn_on(web):
    held = held_over_http(web)
    reply = web.post(f"/holds/{held['id']}", headers=AUTH, json={
        "actor": "owner",
        "answers": {"call-a": True, "call-b": "not b"}}).json()
    assert reply["ok"] and reply["text"] == "wrote a."
    work = web.service._workspace(session_key("owner", "scribe", "t"))
    assert (work / "a.txt").exists() and not (work / "b.txt").exists()
    assert web.get("/holds", headers=AUTH).json()["holds"] == []


def test_the_string_yes_is_not_an_approval(web):
    held = held_over_http(web)
    web.post(f"/holds/{held['id']}", headers=AUTH, json={
        "actor": "owner", "answers": {"call-a": "yes", "call-b": "yes"}})
    work = web.service._workspace(session_key("owner", "scribe", "t"))
    assert not (work / "a.txt").exists()


def test_not_yours_and_gone_are_different_statuses(web):
    held = held_over_http(web)
    both = {"call-a": True, "call-b": True}
    assert web.post(f"/holds/{held['id']}", headers=AUTH, json={
        "actor": "guest", "answers": both}).status_code == 403
    assert web.post("/holds/nope", headers=AUTH, json={
        "actor": "owner", "answers": both}).status_code == 404
    assert web.post(f"/holds/{held['id']}", headers=AUTH, json={
        "actor": "owner", "answers": {"call-a": True}}).status_code == 400
    assert web.post(f"/holds/{held['id']}", headers=AUTH, json={
        "actor": "owner"}).status_code == 400
    # None of those used it up.
    assert len(web.get("/holds", headers=AUTH).json()["holds"]) == 1


def test_holds_need_the_token_too(web):
    assert web.get("/holds").status_code == 401
    assert web.post("/holds/x", json={}).status_code == 401


# ---- Telegram ---------------------------------------------------------------

BOT_TOKEN = "8675309:AAtest-token-not-a-real-one"
KNOWN, OTHER = 8675309, 4242


@pytest.fixture
def people() -> ActorBook:
    return ActorBook.from_dict({"actor": {
        "mahen": {"channel": [{"kind": "telegram", "id": KNOWN}]},
        "other": {"channel": [{"kind": "telegram", "id": OTHER}]},
    }})


class Wire:
    """Enough of the Bot API to watch what a held turn sends."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        return httpx.Response(200, json={
            "ok": True, "result": {"message_id": len(self.calls)}})

    def of(self, method: str) -> list[dict]:
        return [p for m, p in self.calls if m == method]


@pytest.fixture
def bot(make_service, agents_root, people):
    scribe(agents_root)
    service = make_service([two_calls(), says("both written.")],
                           asks=holding(), actors=people)
    wire = Wire()
    client = wire.client()
    made = TelegramBot(service, token=BOT_TOKEN, agent="scribe",
                       client=client, send_gap=0.0, poll_seconds=0)
    made.wire = wire
    yield made
    asyncio.run(client.aclose())


def said(text: str, *, user: int = KNOWN, chat: int | None = None) -> dict:
    return {"update_id": 1, "message": {
        "message_id": 1, "from": {"id": user},
        "chat": {"id": chat if chat is not None else user}, "text": text}}


def pressed(data: str, *, user: int = KNOWN, chat: int = KNOWN) -> dict:
    return {"update_id": 2, "callback_query": {
        "id": "cb", "from": {"id": user}, "data": data,
        "message": {"message_id": 9, "chat": {"id": chat},
                    "text": "Nobody answered in time..."}}}


def held_in_chat(bot, chat: int | None = None) -> str:
    asyncio.run(bot._handle(said("write both", chat=chat)))
    [last] = [p for p in bot.wire.of("sendMessage") if "reply_markup" in p]
    buttons = last["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["approve all", "refuse all"]
    return buttons[0]["callback_data"].partition(":")[2]


def test_a_held_reply_carries_buttons_to_answer_it(bot):
    hold_id = held_in_chat(bot)
    assert [h.id for h in bot.service.holds.pending()] == [hold_id]


def test_a_press_carries_the_turn_on_in_the_same_chat(bot):
    hold_id = held_in_chat(bot)
    asyncio.run(bot._handle(pressed(f"h:{hold_id}")))
    assert bot.wire.of("sendMessage")[-1]["text"] == "both written."
    assert bot.wire.of("answerCallbackQuery")[-1]["text"] == "approved"
    [edited] = bot.wire.of("editMessageText")
    assert edited["message_id"] == 9 and edited["text"].endswith("— approved")
    work = bot.service._workspace(session_key("mahen", "scribe",
                                              f"telegram:{KNOWN}"))
    assert (work / "a.txt").exists() and (work / "b.txt").exists()
    assert bot.outbox.owed("scribe") == []


def test_a_turn_held_in_a_group_is_answered_in_the_group(bot):
    group = -100123
    hold_id = held_in_chat(bot, chat=group)
    asyncio.run(bot._handle(pressed(f"h:{hold_id}", chat=KNOWN)))
    assert bot.wire.of("sendMessage")[-1]["chat_id"] == group


def test_somebody_elses_press_carries_nothing_on(bot):
    hold_id = held_in_chat(bot)
    asyncio.run(bot._handle(pressed(f"h:{hold_id}", user=OTHER)))
    assert "not yours" in bot.wire.of("answerCallbackQuery")[-1]["text"]
    assert [h.id for h in bot.service.holds.pending()] == [hold_id]
    assert bot.outbox.owed("scribe") == []


def test_refuse_all_refuses_every_call(bot):
    hold_id = held_in_chat(bot)
    asyncio.run(bot._handle(pressed(f"x:{hold_id}")))
    work = bot.service._workspace(session_key("mahen", "scribe",
                                              f"telegram:{KNOWN}"))
    assert not (work / "a.txt").exists()
    assert bot.wire.of("answerCallbackQuery")[-1]["text"] == "refused"


def test_a_stale_press_says_so(bot):
    asyncio.run(bot._handle(pressed("h:gone")))
    assert "no longer waiting" in bot.wire.of("answerCallbackQuery")[-1]["text"]


def test_a_question_taken_down_for_a_hold_is_not_called_refused():
    assert "waiting for you" in ending(Answer(False, None, HELD))
    assert "refused" not in ending(Answer(False, None, HELD))


# ---- the terminal -----------------------------------------------------------


@pytest.fixture
def owned(tmp_path, agents_root, monkeypatch):
    scribe(agents_root)
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"test-model": {"input": 0.0,
                                                 "output": 0.0}}))
    monkeypatch.setenv("YANTRA_PRICES", str(prices))
    return ["--root", str(agents_root), "--actors", str(actors),
            "--state", str(tmp_path / "state"), "--provider", "anthropic",
            "--model", "test-model"]


def hold_one(tmp_path, agents_root) -> str:
    service = Service(roster=Roster(agents_root),
                      actors=ActorBook.from_dict({"actor": {"owner": {}}}),
                      state=tmp_path / "state", asks=holding(),
                      provider_name="anthropic", model="test-model",
                      provider_factory=lambda n: ScriptedProvider(
                          [two_calls()]))
    try:
        reply = asyncio.run(service.deliver(actor="owner", agent="scribe",
                                            thread="cli", text="write both"))
        return reply.held.id
    finally:
        service.close()


def test_hold_without_ask_is_the_owners_mistake(owned, capsys):
    assert main([*owned, "--on-timeout", "hold", "agents"]) == 2
    assert "needs --ask" in capsys.readouterr().err


def test_held_lists_what_is_waiting(owned, tmp_path, agents_root, capsys):
    hold_id = hold_one(tmp_path, agents_root)
    assert main([*owned, "held"]) == 0
    out = capsys.readouterr().out
    assert hold_id in out
    assert "call-a  write_file" in out
    assert "as they are now" in out


def test_resume_approves_and_the_ledger_links_the_two(owned, tmp_path,
                                                      agents_root, capsys,
                                                      monkeypatch):
    hold_id = hold_one(tmp_path, agents_root)
    monkeypatch.setattr("dvara.service._default_provider",
                        lambda name: ScriptedProvider([says("both done.")]))
    assert main([*owned, "resume", hold_id, "--actor", "owner",
                 "--approve"]) == 0
    assert "both done." in capsys.readouterr().out
    assert main([*owned, "runs"]) == 0
    out = capsys.readouterr().out
    assert "write_file(held) -> write_file(held)" in out
    assert "resumes " in out
    assert "[answered from terminal]" in out


def test_a_call_nobody_named_is_not_approved(owned, tmp_path, agents_root,
                                             capsys, monkeypatch):
    hold_id = hold_one(tmp_path, agents_root)
    monkeypatch.setattr("dvara.service._default_provider",
                        lambda name: ScriptedProvider([says("x")]))
    assert main([*owned, "resume", hold_id, "--actor", "owner",
                 "--call", "call-a=yes"]) == 1
    assert "unanswered: call-b" in capsys.readouterr().err


def test_call_words_become_answers(owned, tmp_path, agents_root):
    from dvara.cli import _answers, _service, build_parser
    hold_id = hold_one(tmp_path, agents_root)
    args = build_parser().parse_args([
        *owned, "resume", hold_id, "--actor", "owner", "--approve",
        "--call", "call-b=leave it"])
    service = _service(args)
    try:
        assert _answers(service, args) == {"call-a": True,
                                           "call-b": "leave it"}
    finally:
        service.close()

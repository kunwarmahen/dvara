"""The channel adapter, and the four ways a chat app can lose a message.

The bias these tests encode is that EVERY FAILURE HERE IS SILENT. A
message that exceeds the cap is rejected whole, and what the person sees
is a bot that ignored them. A reply measured in Python characters instead
of UTF-16 units fits every test written in ASCII and fails the first time
somebody's answer has an emoji in it. A poll loop that awaits its own
turns deadlocks only when a tool call escalates, which is the path
nobody exercises by hand. An offset advanced at the wrong moment shows up
as a duplicate charge after a crash, days later.

So the transport is faked rather than mocked out: a real
``httpx.MockTransport`` standing in for the Bot API, real JSON on the
wire, real status codes, and an assertion on the actual payload Telegram
would have received. What a test asserts is what the bot SENT, not what
it meant to send.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from dvara.actors import ActorBook
from dvara.asks import Ask, AskDesk
from dvara.errors import ConfigProblem
from dvara.telegram import (
    MESSAGE_LIMIT,
    TelegramBot,
    TelegramError,
    elide,
    split_message,
    utf16_len,
)

from tests.conftest import says, write_package

TOKEN = "8675309:AAtest-token-not-a-real-one"

#: An id in the actors file, and one that is not. The second is the whole
#: of "assigned, never asserted" as a test fixture.
KNOWN, STRANGER = 8675309, 5551212


@pytest.fixture
def actors() -> ActorBook:
    """One person, reachable on Telegram; everybody else is nobody."""
    return ActorBook.from_dict({
        "actor": {
            "mahen": {"channel": [{"kind": "telegram", "id": KNOWN}]},
            "offline": {},
        }
    })


class FakeTelegram:
    """As much of the Bot API as this adapter ever touches.

    Positional arguments are batches that arrive WHILE the bot is
    running, one per ``getUpdates``; ``backlog`` is what Telegram was
    already holding when it started. The two are deliberately separate,
    because the whole of the startup decision is what happens to the
    second and not the first. When the batches run out the bot is asked
    to stop, which is what keeps a long poll against a transport that
    answers instantly from spinning forever.
    """

    def __init__(self, *batches: list[dict],
                 backlog: list[dict] | None = None) -> None:
        self.batches = list(batches)
        self.backlog = list(backlog or [])
        self.calls: list[tuple[str, dict]] = []
        self.status: dict[str, list[httpx.Response]] = {}
        self.bot: TelegramBot | None = None
        self.idle = 0

    # ---- the transport -----------------------------------------------------

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        scripted = self.status.get(method)
        if scripted:
            return scripted.pop(0)
        if method == "getMe":
            return _ok({"username": "testbot"})
        if method == "getUpdates":
            if payload.get("offset") == -1:
                return _ok(self.backlog_tip())
            # AN OFFSET IS AN ACKNOWLEDGEMENT. A fake that ignored it
            # would hand back the backlog the bot has just told Telegram
            # to forget, which is exactly the behaviour under test.
            low = payload.get("offset") or 0
            if self.backlog:
                held, self.backlog = self.backlog, []
                kept = [u for u in held if u["update_id"] >= low]
                if kept:
                    return _ok(kept)
            if self.batches:
                return _ok([u for u in self.batches.pop(0)
                            if u["update_id"] >= low])
            # NOTHING LEFT TO POLL IS NOT NOTHING LEFT TO DO. The loop
            # hands each update to a task and goes straight back to
            # polling -- which is the property under test -- so stopping
            # the instant the batches run out would cancel the very turn
            # the test is waiting for. `run` cancels what is in flight on
            # the way out, and that is correct for a Ctrl-C and wrong for
            # a harness.
            self.idle += 1
            if self.bot is not None and (not self.bot._turns
                                         or self.idle > 500):
                self.bot.stop()
            return _ok([])
        return _ok({"message_id": len(self.calls)})

    def backlog_tip(self) -> list[dict]:
        """What ``offset=-1`` returns: the last held update, or nothing."""
        return [self.backlog[-1]] if self.backlog else []

    # ---- what a test asks about --------------------------------------------

    def sent(self) -> list[dict]:
        return [p for method, p in self.calls if method == "sendMessage"]

    def texts(self) -> list[str]:
        return [p["text"] for p in self.sent()]

    def of(self, method: str) -> list[dict]:
        return [p for m, p in self.calls if m == method]


def _ok(result) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": result})


def message(text: str | None = "hello", *, user: int = KNOWN,
            chat: int | None = None, update_id: int = 1, **extra) -> dict:
    body = {"message_id": update_id, "from": {"id": user},
            "chat": {"id": chat if chat is not None else user}, **extra}
    if text is not None:
        body["text"] = text
    return {"update_id": update_id, "message": body}


def press(ask_id: str, *, approve: bool = True, user: int = KNOWN,
          update_id: int = 1) -> dict:
    return {"update_id": update_id, "callback_query": {
        "id": "cb1", "from": {"id": user},
        "data": f"{'y' if approve else 'n'}:{ask_id}",
        "message": {"message_id": 7, "chat": {"id": user},
                    "text": "greeter wants to run bash:\n\nls"}}}


@pytest.fixture
def make_bot(make_service, actors, agents_root):
    """A bot, its service and its fake Telegram, all closed afterwards."""
    clients: list[httpx.AsyncClient] = []

    def build(fake: FakeTelegram, *, script=None, agent="greeter",
              service=None, **kwargs) -> TelegramBot:
        service = service or make_service(script, actors=actors)
        client = fake.client()
        clients.append(client)
        # catch_up by default, so a test that scripts a message does not
        # have to think about the startup probe. The two tests that ARE
        # about the probe say so.
        kwargs.setdefault("catch_up", True)
        bot = TelegramBot(service, token=TOKEN, agent=agent,
                          client=client, send_gap=0.0, poll_seconds=0,
                          **kwargs)
        fake.bot = bot
        return bot

    yield build

    async def shut():
        for client in clients:
            await client.aclose()
    asyncio.run(shut())


# ---- the cap, which is measured in UTF-16 ----------------------------------


def test_a_short_reply_is_one_message():
    assert split_message("hello") == ["hello"]


def test_an_empty_reply_is_no_messages_at_all():
    assert split_message("   \n  ") == []


def test_the_length_telegram_measures_is_not_the_one_python_reports():
    # One Python character, two UTF-16 code units. The whole reason this
    # function exists: len() says this reply fits and Telegram does not.
    assert len("\U0001f600") == 1
    assert utf16_len("\U0001f600") == 2
    assert utf16_len("abc") == 3


def test_an_answer_of_emoji_is_split_by_units_not_characters():
    # 3000 characters -- comfortably under 4096 by len() -- and 6000
    # units, which Telegram rejects whole.
    reply = "\U0001f600" * 3000
    parts = split_message(reply)
    assert len(parts) > 1
    assert all(utf16_len(part) <= MESSAGE_LIMIT for part in parts)
    assert "".join(parts) == reply


def test_a_split_never_cuts_a_surrogate_pair_in_half():
    parts = split_message("\U0001f600" * 3000)
    for part in parts:
        # A half-pair does not survive a round trip through UTF-16.
        assert part.encode("utf-16", "strict").decode("utf-16") == part


def test_a_long_reply_prefers_to_break_at_a_blank_line():
    first, second = "a" * 3000, "b" * 3000
    parts = split_message(f"{first}\n\n{second}")
    assert parts == [first, second]


def test_it_falls_back_to_a_newline_then_to_a_space():
    on_newline = split_message(f"{'a' * 3000}\n{'b' * 3000}")
    assert on_newline == ["a" * 3000, "b" * 3000]
    on_space = split_message(f"{'a' * 3000} {'b' * 3000}")
    assert on_space == ["a" * 3000, "b" * 3000]


def test_a_boundary_near_the_front_is_ignored_so_the_split_makes_progress():
    # One space at character 5 of a 9000-character run. Cutting there
    # would send "aaaaa" and leave the same problem behind it.
    parts = split_message("aaaaa " + "b" * 9000)
    assert len(parts[0]) > MESSAGE_LIMIT // 2
    assert all(utf16_len(part) <= MESSAGE_LIMIT for part in parts)


def test_a_reply_with_no_boundary_at_all_is_still_split():
    parts = split_message("x" * 10_000)
    assert [len(part) for part in parts] == [4096, 4096, 1808]


def test_nothing_of_the_reply_is_dropped():
    """Whitespace at a cut is the splitter's; a word never is."""
    reply = "\n\n".join(f"paragraph {n} " + "w " * 400 for n in range(20))
    parts = split_message(reply)
    assert len(parts) > 1
    assert "".join("".join(reply.split()) for reply in [""]) == ""
    assert "".join("".join(part.split()) for part in parts) == \
        "".join(reply.split())


# ---- a question is elided, not split ---------------------------------------


def test_an_oversized_question_keeps_both_of_its_ends():
    summary = "rm -rf " + "middle/" * 2000 + " --no-preserve-root"
    short = elide(summary, 200)
    assert utf16_len(short) <= 200
    assert short.startswith("rm -rf")
    assert short.endswith("--no-preserve-root")
    assert "elided" in short


def test_a_question_that_fits_is_left_exactly_alone():
    assert elide("ls -la", 200) == "ls -la"


# ---- who is talking --------------------------------------------------------


def test_a_stranger_gets_silence_and_the_owner_gets_a_line(make_bot, capsys):
    fake = FakeTelegram([message("hello", user=STRANGER)])
    bot = make_bot(fake)
    asyncio.run(bot.run())
    assert fake.sent() == []
    assert str(STRANGER) in capsys.readouterr().err


def test_a_known_id_becomes_the_actor_the_roster_assigned(make_bot):
    fake = FakeTelegram([message("what changed today?")])
    bot = make_bot(fake, script=[says("nothing much")])
    asyncio.run(bot.run())
    assert fake.texts() == ["nothing much"]
    run = bot.service.runs.recent(limit=1)[0]
    assert run.actor == "mahen"
    # The channel qualifies the thread, which is note 05's collision fix
    # arriving here as the first caller that can actually trip it.
    assert run.thread == f"telegram:{KNOWN}"


def test_a_message_that_is_not_text_is_answered_rather_than_ignored(make_bot):
    fake = FakeTelegram([message(None, sticker={"file_id": "x"})])
    bot = make_bot(fake)
    asyncio.run(bot.run())
    assert fake.texts() == ["I can only read text."]


def test_start_is_answered_here_and_never_reaches_the_model(make_bot,
                                                           make_service,
                                                           actors, tmp_path):
    root = tmp_path / "described"
    root.mkdir()
    write_package(root, "greeter", body='[agent]\nname = "Greeter"\n'
                                        'description = "says hello"\n'
                                        'prompt = "prompt.md"\n')
    # An empty script: a model call here would raise "script exhausted".
    service = make_service([], actors=actors, root=root)
    fake = FakeTelegram([message("/start")])
    bot = make_bot(fake, service=service)
    asyncio.run(bot.run())
    assert fake.texts() == ["Greeter\n\nsays hello\n\n"
                            "Send me a message and I will answer it."]


# ---- the reply -------------------------------------------------------------


def test_a_long_answer_arrives_as_several_messages_in_order(make_bot):
    # Two, not three: what fits after the first cut is not cut again.
    reply = "\n\n".join(["a" * 3000, "b" * 3000, "c" * 100])
    fake = FakeTelegram([message("go")])
    bot = make_bot(fake, script=[says(reply)])
    asyncio.run(bot.run())
    assert fake.texts() == ["a" * 3000, f"{'b' * 3000}\n\n{'c' * 100}"]
    assert {p["chat_id"] for p in fake.sent()} == {KNOWN}


def test_nothing_is_ever_sent_with_a_parse_mode(make_bot):
    # An unmatched asterisk is a 400 under Markdown, and the whole answer
    # is lost for one character the model happened to type.
    fake = FakeTelegram([message("go")])
    bot = make_bot(fake, script=[says("a *star and an _underscore")])
    asyncio.run(bot.run())
    assert all("parse_mode" not in payload for payload in fake.sent())


def test_the_receipt_rides_on_the_last_message_not_the_first(make_bot,
                                                            make_service,
                                                            priced_model):
    book = ActorBook.from_dict({"actor": {"mahen": {
        "receipt": "cost",
        "channel": [{"kind": "telegram", "id": KNOWN}]}}})
    service = make_service([says("\n\n".join(["a" * 3000, "b" * 3000]))],
                           actors=book)
    fake = FakeTelegram([message("go")])
    asyncio.run(make_bot(fake, service=service).run())
    texts = fake.texts()
    assert len(texts) == 2
    assert texts[0] == "a" * 3000
    assert texts[1].startswith("b" * 3000)
    assert texts[1].endswith("$0.0000")


def test_a_refusal_is_delivered_like_any_other_answer(make_bot, make_service):
    """A person on the list, reaching for an agent that is not theirs."""
    book = ActorBook.from_dict({"actor": {"mahen": {
        "agents": ["something-else"],
        "channel": [{"kind": "telegram", "id": KNOWN}]}}})
    service = make_service([], actors=book)
    fake = FakeTelegram([message("go")])
    asyncio.run(make_bot(fake, service=service).run())
    assert fake.texts() == ["you do not have access to the agent 'greeter'"]


# ---- the loop --------------------------------------------------------------


def test_the_offset_moves_past_a_message_as_it_is_taken(make_bot):
    fake = FakeTelegram([message("one", update_id=41)])
    bot = make_bot(fake, script=[says("ok")])
    asyncio.run(bot.run())
    offsets = [p.get("offset") for p in fake.of("getUpdates")]
    # -1 is the backlog probe; then 0 for the first real poll; then past
    # the update that was taken -- whether or not its turn has finished.
    assert offsets[-1] == 42


def test_a_backlog_is_passed_over_by_default(make_bot, capsys):
    fake = FakeTelegram(backlog=[message("stale", update_id=99)])
    bot = make_bot(fake, catch_up=False)
    asyncio.run(bot.run())
    assert fake.sent() == []
    assert "--catch-up" in capsys.readouterr().err
    # -1 is the probe that learns the high-water mark; 100 is past it.
    assert [p.get("offset") for p in fake.of("getUpdates")][:2] == [-1, 100]


def test_catch_up_answers_what_was_held(make_bot):
    fake = FakeTelegram(backlog=[message("stale", update_id=99)])
    bot = make_bot(fake, script=[says("late but here")])
    asyncio.run(bot.run())
    assert fake.texts() == ["late but here"]
    # No probe at all: catching up means starting from the beginning.
    assert fake.of("getUpdates")[0].get("offset") == 0


def test_a_broken_update_does_not_take_the_bot_off_the_air(make_bot, capsys):
    fake = FakeTelegram([{"update_id": 1, "message": {"text": "hi"}},
                         message("hello", update_id=2)])
    bot = make_bot(fake, script=[says("still here")])
    asyncio.run(bot.run())
    assert fake.texts() == ["still here"]


def test_a_network_blip_is_retried_rather_than_fatal(make_bot, capsys):
    fake = FakeTelegram([message("hello", update_id=2)])
    fake.status["getUpdates"] = [httpx.Response(500, text="bad gateway")]
    bot = make_bot(fake, script=[says("still here")])
    asyncio.run(bot.run())
    assert fake.texts() == ["still here"]
    assert "retrying" in capsys.readouterr().err


def test_a_typing_indicator_runs_while_the_turn_does(make_bot):
    fake = FakeTelegram([message("go")])
    bot = make_bot(fake, script=[says("done")])
    asyncio.run(bot.run())
    assert fake.of("sendChatAction")[0]["action"] == "typing"


# ---- the question, and the button ------------------------------------------


def _ask(**over) -> Ask:
    body = {"id": "abc123", "actor": "mahen", "agent": "greeter",
            "thread": f"telegram:{KNOWN}", "tool": "bash",
            "summary": "rm -rf /tmp/x", "to": str(KNOWN)}
    return Ask(**{**body, **over})


def test_a_question_goes_to_the_person_with_two_buttons_on_it(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)

    asyncio.run(bot._deliver_ask(_ask()))

    sent = fake.sent()[0]
    assert sent["chat_id"] == KNOWN
    assert "rm -rf /tmp/x" in sent["text"]
    buttons = sent["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["approve", "refuse"]
    assert [b["callback_data"] for b in buttons] == ["y:abc123", "n:abc123"]


def test_a_question_is_delivered_to_the_person_not_to_the_thread(make_bot):
    # The turn is running in a group chat; the question still arrives in
    # the person's own chat, because the address rides on the Ask.
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_ask(_ask(thread="telegram:-100999")))
    assert fake.sent()[0]["chat_id"] == KNOWN


def test_a_callback_id_that_would_not_fit_is_a_failed_delivery(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)
    with pytest.raises(TelegramError):
        asyncio.run(bot._deliver_ask(_ask(id="x" * 100)))
    assert fake.sent() == []


def test_a_press_lands_on_the_desk_and_clears_the_buttons(make_bot,
                                                          make_service,
                                                          actors):
    desk = AskDesk(timeout=5)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)

    async def go():
        put = asyncio.ensure_future(desk.put(
            actor="mahen", agent="greeter", thread="t", tool="bash",
            summary="ls", reach=(("telegram", str(KNOWN)),)))
        await asyncio.sleep(0)
        ask_id = desk.pending("mahen")[0].id
        await bot._handle(press(ask_id, approve=True))
        return await put

    answer = asyncio.run(go())
    assert answer.approved is True
    assert fake.of("answerCallbackQuery")[0]["text"] == "approved"
    # The chat is where this decision is written down, and a button that
    # stays pressable invites a second press that can do nothing.
    edited = fake.of("editMessageText")[0]
    assert edited["text"].endswith("— approved")
    assert "reply_markup" not in edited


def test_a_refusal_is_carried_back_as_a_refusal(make_bot, make_service,
                                                actors):
    desk = AskDesk(timeout=5)
    service = make_service([says("ok")], actors=actors, asks=desk)
    bot = make_bot(FakeTelegram(), service=service)

    async def go():
        put = asyncio.ensure_future(desk.put(
            actor="mahen", agent="greeter", thread="t", tool="bash",
            summary="ls"))
        await asyncio.sleep(0)
        await bot._handle(press(desk.pending("mahen")[0].id, approve=False))
        return await put

    answer = asyncio.run(go())
    assert answer.approved is False
    assert "said no" in answer.reason


def test_somebody_elses_button_resolves_nothing(make_bot, make_service,
                                                actors):
    desk = AskDesk(timeout=5)
    book = ActorBook.from_dict({"actor": {
        "mahen": {"channel": [{"kind": "telegram", "id": KNOWN}]},
        "other": {"channel": [{"kind": "telegram", "id": STRANGER}]}}})
    service = make_service([says("ok")], actors=book, asks=desk)
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)

    async def go():
        put = asyncio.ensure_future(desk.put(
            actor="mahen", agent="greeter", thread="t", tool="bash",
            summary="ls"))
        await asyncio.sleep(0)
        ask_id = desk.pending("mahen")[0].id
        await bot._handle(press(ask_id, user=STRANGER))
        assert desk.pending("mahen"), "the question must still be standing"
        await bot._handle(press(ask_id, user=KNOWN))
        return await put

    answer = asyncio.run(go())
    assert answer.approved is True
    toasts = [p["text"] for p in fake.of("answerCallbackQuery")]
    assert "not put to you" in toasts[0]


def test_a_press_from_a_stranger_says_nothing_about_who_is_on_the_list(
        make_bot, make_service, actors):
    service = make_service([says("ok")], actors=actors, asks=AskDesk())
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)
    asyncio.run(bot._handle(press("whatever", user=STRANGER)))
    assert fake.of("answerCallbackQuery")[0]["text"] == \
        "you are not on this service's list of people"


def test_a_stale_button_says_so_rather_than_spinning(make_bot, make_service,
                                                     actors):
    service = make_service([says("ok")], actors=actors, asks=AskDesk())
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)
    asyncio.run(bot._handle(press("gone-long-ago")))
    assert "no longer waiting" in fake.of("answerCallbackQuery")[0]["text"]


# ---- rate limits -----------------------------------------------------------


def test_a_429_is_waited_out_and_the_message_still_arrives(make_bot):
    fake = FakeTelegram([message("go")])
    fake.status["sendMessage"] = [httpx.Response(
        429, json={"ok": False, "description": "Too Many Requests",
                   "parameters": {"retry_after": 0.01}})]
    bot = make_bot(fake, script=[says("patience")])
    asyncio.run(bot.run())
    assert fake.texts() == ["patience", "patience"]  # the retry is the send


def test_a_flood_wait_longer_than_a_deadline_is_a_failure_not_a_wait(make_bot):
    fake = FakeTelegram()
    fake.status["sendMessage"] = [httpx.Response(
        429, json={"ok": False, "parameters": {"retry_after": 600}})]
    bot = make_bot(fake)
    with pytest.raises(TelegramError, match="rate limited"):
        asyncio.run(bot._send(KNOWN, "hello"))


def test_an_undeliverable_question_is_a_denial_rather_than_a_deadline(
        make_bot, make_service, actors):
    """The desk's rule, exercised through the channel that made it real."""
    desk = AskDesk(timeout=30)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    fake.status["sendMessage"] = [httpx.Response(
        429, json={"ok": False, "parameters": {"retry_after": 600}})]
    bot = make_bot(fake, service=service)
    desk.route("telegram", bot._deliver_ask)

    started = time.monotonic()
    answer = asyncio.run(desk.put(
        actor="mahen", agent="greeter", thread="t", tool="bash",
        summary="ls", reach=(("telegram", str(KNOWN)),)))
    assert answer.approved is False
    assert "could not be delivered" in answer.reason
    assert time.monotonic() - started < 5  # not the 30-second deadline


def test_two_messages_into_one_chat_are_spaced_apart(make_bot):
    fake = FakeTelegram([message("go")])
    bot = make_bot(fake, script=[says("a" * 5000)])
    bot._pacer.gap = 0.05

    started = time.monotonic()
    asyncio.run(bot.run())
    assert len(fake.texts()) == 2
    assert time.monotonic() - started >= 0.05


# ---- the owner's own mistakes ----------------------------------------------


def test_a_token_that_is_not_a_token_is_refused_before_anything_runs(
        make_service, actors):
    service = make_service(actors=actors)
    with pytest.raises(ConfigProblem, match="TELEGRAM_TOKEN"):
        TelegramBot(service, token="hunter2", agent="greeter")


def test_an_agent_that_is_not_in_the_roster_fails_at_startup(make_service,
                                                            actors):
    from dvara.errors import Refused
    service = make_service(actors=actors)
    with pytest.raises(Refused):
        TelegramBot(service, token=TOKEN, agent="nosuchagent")


def test_a_rejected_token_names_the_variable_to_fix(make_bot):
    fake = FakeTelegram()
    fake.status["getMe"] = [httpx.Response(401, json={"ok": False})]
    bot = make_bot(fake)
    with pytest.raises(ConfigProblem, match="TELEGRAM_TOKEN"):
        asyncio.run(bot.run())


def test_a_second_poller_on_one_token_is_fatal_and_says_why(make_bot):
    fake = FakeTelegram()
    fake.status["getUpdates"] = [httpx.Response(409, json={"ok": False})]
    bot = make_bot(fake)
    with pytest.raises(ConfigProblem, match="split"):
        asyncio.run(bot.run())

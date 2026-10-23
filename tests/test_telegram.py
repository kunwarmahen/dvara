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
import contextlib
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
        if request.url.path.startswith("/file/bot"):
            # A file the bot downloads (getFile's path), as its bytes.
            self.calls.append(("download", {"path": request.url.path}))
            return httpx.Response(200, content=b"bytes of " + request.url.path.encode())
        method = request.url.path.rsplit("/", 1)[-1]
        if request.headers.get("content-type", "").startswith("multipart/"):
            # A file: kept whole, for a test to look for the name and bytes.
            payload = {"multipart": request.read().decode("latin-1")}
        else:
            payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        scripted = self.status.get(method)
        if scripted:
            outcome = scripted.pop(0)
            if isinstance(outcome, Exception):
                raise outcome             # the network, not Telegram
            return outcome
        if method == "getMe":
            return _ok({"username": "testbot"})
        if method == "getFile":
            return _ok({"file_path": f"files/{payload.get('file_id')}.bin"})
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
    assert fake.texts() == ["I can read words, pictures and files, not this."]


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
    # No allowlist means every tool, write_file among them -- so the
    # person is told their files can be asked for (files.py).
    assert fake.texts() == ["Greeter\n\nsays hello\n\n"
                            "Send me a message and I will answer it.\n\n"
                            "Send /files to see the files I keep for you, "
                            "and /file NAME to get one.\n\n"
                            "Send /tools to see what I can use.\n\n"
                            "Send /new to start our conversation over. Every "
                            "conversation is kept: /chats lists them, /chats and a "
                            "word finds one, /chats N goes back into it, /chats "
                            "export N sends it to you as a file to share. "
                            "/keep test keeps the one we're in as a test, with "
                            "the words my answer must say after it: /keep test "
                            "May 20, refund."]


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


def test_a_question_with_a_picture_shows_it_first_and_the_buttons_under_it(make_bot):
    # A tap by position is answered by looking where the ring is.
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_ask(_ask(tool="mcp__sparsh__confirm",
                                      picture=b"\x89PNG ringed")))
    assert [m for m, _ in fake.calls] == ["sendPhoto", "sendMessage"]
    photo = fake.of("sendPhoto")[0]["multipart"]
    assert "\x89PNG ringed" in photo and str(KNOWN) in photo
    assert "inline_keyboard" in fake.calls[1][1]["reply_markup"]


def test_a_question_in_words_sends_no_picture(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_ask(_ask()))
    assert fake.of("sendPhoto") == []


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
    desk.route("telegram", bot._deliver_ask)

    async def go():
        answer = await _ask_and(desk, fake, lambda ask_id: bot._handle(
            press(ask_id, approve=True)))
        await desk.withdrawn()
        return answer

    answer = asyncio.run(go())
    assert answer.approved is True
    assert fake.of("answerCallbackQuery")[0]["text"] == "approved"
    # The chat is where this decision is written down, and a button that
    # stays pressable invites a second press that can do nothing. The
    # edit lands on the message the question WENT OUT as, and only once.
    [edited] = fake.of("editMessageText")
    assert edited["message_id"] == _question_id(fake)
    assert edited["text"].endswith("— approved")
    assert "reply_markup" not in edited


async def _delivered(fake) -> None:
    """Until the question has actually gone out -- a real round trip."""
    while not any("reply_markup" in p for p in fake.sent()):
        await asyncio.sleep(0)
    await asyncio.sleep(0)                # and the notifier has returned


async def _ask_and(desk, fake, act):
    """Put a question, wait until it is delivered, do ``act``, return the answer."""
    put = asyncio.ensure_future(desk.put(
        actor="mahen", agent="greeter", thread="t", tool="bash",
        summary="ls", reach=(("telegram", str(KNOWN)),)))
    await _delivered(fake)
    outcome = act(desk.pending("mahen")[0].id)
    if asyncio.iscoroutine(outcome):
        await outcome
    return await put


def _question_id(fake) -> int:
    """The message_id the fake handed back for the question's sendMessage."""
    index = next(i for i, (m, p) in enumerate(fake.calls)
                 if m == "sendMessage" and "reply_markup" in p)
    return index + 1


def test_a_question_answered_at_the_keyboard_loses_its_buttons_here(
        make_bot, make_service, actors):
    # The phone must not go on offering a decision that was made at the
    # laptop -- and it must say it was made there, or it looks like
    # somebody else answered.
    desk = AskDesk(timeout=5)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)
    desk.route("telegram", bot._deliver_ask)

    async def go():
        answer = await _ask_and(desk, fake, lambda ask_id: desk.answer(
            ask_id, actor="mahen", approve=True, via="terminal"))
        await desk.withdrawn()
        return answer

    assert asyncio.run(go()).approved
    [edited] = fake.of("editMessageText")
    assert edited["message_id"] == _question_id(fake)
    assert edited["text"].endswith("— approved at the terminal")
    assert "reply_markup" not in edited


def test_a_question_nobody_answered_says_so_rather_than_waiting_forever(
        make_bot, make_service, actors):
    desk = AskDesk(timeout=0.2)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)
    desk.route("telegram", bot._deliver_ask)

    async def go():
        answer = await desk.put(actor="mahen", agent="greeter", thread="t",
                                tool="bash", summary="ls",
                                reach=(("telegram", str(KNOWN)),))
        await desk.withdrawn()
        return answer

    assert asyncio.run(go()).approved is False
    [edited] = fake.of("editMessageText")
    assert edited["text"].endswith("nobody answered in time, so it was refused")


def test_a_question_whose_turn_went_away_is_not_called_refused(
        make_bot, make_service, actors):
    desk = AskDesk(timeout=5)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    bot = make_bot(fake, service=service)
    desk.route("telegram", bot._deliver_ask)

    async def go():
        put = asyncio.ensure_future(desk.put(
            actor="mahen", agent="greeter", thread="t", tool="bash",
            summary="ls", reach=(("telegram", str(KNOWN)),)))
        await _delivered(fake)
        put.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await put
        await desk.withdrawn()

    asyncio.run(go())
    [edited] = fake.of("editMessageText")
    assert "no longer needed" in edited["text"]
    assert "refused" not in edited["text"].rsplit("—", 1)[-1]


def test_an_edit_telegram_rejects_does_not_touch_the_answer(
        make_bot, make_service, actors):
    desk = AskDesk(timeout=5)
    service = make_service([says("ok")], actors=actors, asks=desk)
    fake = FakeTelegram()
    fake.status["editMessageText"] = [httpx.Response(
        400, json={"ok": False, "description": "message can't be edited"})]
    bot = make_bot(fake, service=service)
    desk.route("telegram", bot._deliver_ask)

    async def go():
        answer = await _ask_and(desk, fake, lambda ask_id: bot._handle(
            press(ask_id, approve=True)))
        await desk.withdrawn()
        return answer

    assert asyncio.run(go()).approved


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


# ---- a notice nobody asked for (notices.py) --------------------------------


def test_a_notice_arrives_in_the_persons_own_chat(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_notice(str(KNOWN), "2 new mails from the bank"))
    assert fake.texts() == ["2 new mails from the bank"]
    assert fake.sent()[0]["chat_id"] == KNOWN
    assert "parse_mode" not in fake.sent()[0]


def test_a_long_notice_is_split_like_an_answer(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_notice(str(KNOWN), "a" * 3000 + "\n\n" + "b" * 3000))
    assert fake.texts() == ["a" * 3000, "b" * 3000]


def test_a_running_bot_is_where_the_service_sends_notices(make_bot):
    """Registered when the bot starts, the way questions are: a notice
    for somebody with a telegram entry needs no other wiring."""
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot.run())
    who, sent = asyncio.run(bot.service.notify(actor="mahen", text="news"))
    assert sent.sent == ["telegram"]
    assert fake.texts()[-1] == "news"


def _folder(service, actor="mahen", agent="greeter"):
    work = service.state / "work" / actor / agent
    work.mkdir(parents=True, exist_ok=True)
    return work


# ---- a file, sent as a document (files.py) -------------------------------------------


def test_telegram_sends_the_file_itself_with_its_name_as_caption(make_bot, make_service,
                                                                  actors):
    service = make_service([], actors=actors)
    (_folder(service) / "uptime-log.txt").write_text("2026-10-06 07:09 UP\n")
    fake = FakeTelegram([message("/file uptime-log.txt")])
    asyncio.run(make_bot(fake, service=service).run())
    [upload] = fake.of("sendDocument")
    body = upload["multipart"]
    assert 'filename="uptime-log.txt"' in body
    assert "2026-10-06 07:09 UP" in body and str(KNOWN) in body
    assert fake.texts() == []                     # the caption, not a message


def test_a_file_too_big_for_telegram_is_said_not_attempted(make_bot, make_service,
                                                           actors, monkeypatch):
    from dvara import telegram
    monkeypatch.setattr(telegram, "FILE_LIMIT", 4)
    service = make_service([], actors=actors)
    (_folder(service) / "big.txt").write_text("more than four")
    fake = FakeTelegram([message("/file big.txt")])
    asyncio.run(make_bot(fake, service=service).run())
    assert fake.of("sendDocument") == []
    assert "more than Telegram lets a bot send" in fake.texts()[0]


def test_start_mentions_files_only_to_an_agent_that_writes_them(make_bot, make_service,
                                                                 actors, agents_root):
    from tests.test_unattended_turns import scribe
    scribe(agents_root)
    service = make_service([], actors=actors)
    fake = FakeTelegram([message("/start")])
    asyncio.run(make_bot(fake, service=service, agent="scribe").run())
    assert "/files" in fake.texts()[0]


def test_a_file_the_agent_sent_follows_its_answer(make_bot, make_service, actors,
                                                  agents_root):
    from dvara.asks import AskDesk
    from dvara.gate import Policy
    from dvara.rules import Rule, RuleBook
    from tests.conftest import calls
    write_package(agents_root, "courier", body=(
        '[agent]\nname = "courier"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["send_file"]\n[permissions]\nmode = "ask"\n'))
    service = make_service(
        [calls("send_file", {"path": "report.md"}), says("Here's this week's report.")],
        actors=actors, asks=AskDesk(timeout=5),
        policy=Policy(rules=RuleBook([Rule(tool="send_file", verdict="allow")])))
    (_folder(service, agent="courier") / "report.md").write_text("# week 40\nall up\n")
    fake = FakeTelegram([message("send me the report")])
    asyncio.run(make_bot(fake, service=service, agent="courier").run())
    order = [m for m, _ in fake.calls if m in ("sendMessage", "sendDocument")]
    # the "Working…" message first, gone once the answer comes (Steps)
    assert order == ["sendMessage", "sendMessage", "sendDocument"]
    assert fake.texts() == ["Working…\n• send_file: send you the file report.md",
                            "Here's this week's report."]
    assert fake.of("deleteMessage")
    assert 'filename="report.md"' in fake.of("sendDocument")[0]["multipart"]


# ---- the / menu ------------------------------------------------------------


def menu_of(fake):
    return [c["command"] for m, p in fake.calls if m == "setMyCommands"
            for c in p["commands"]]


def test_the_menu_offers_new_and_files_to_an_agent_that_writes_them(make_bot):
    fake = FakeTelegram([])
    asyncio.run(make_bot(fake).run())
    assert menu_of(fake) == ["new", "chats", "files", "file", "tools"]


def test_the_account_words_are_offered_only_where_the_package_asks_for_accounts(
        make_bot, make_service, actors, agents_root):
    write_package(agents_root, "reader", body=(
        '[agent]\nname = "reader"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["web_fetch"]\n'
        '[connections]\nneeds = ["gmail:read"]\n'))
    fake = FakeTelegram([])
    asyncio.run(make_bot(fake, service=make_service([], actors=actors),
                         agent="reader").run())
    assert menu_of(fake) == ["new", "chats", "accounts", "connect", "disconnect",
                             "lock", "unlock", "tools"]


def test_the_memory_words_are_offered_only_where_the_package_remembers(
        make_bot, make_service, actors, agents_root):
    write_package(agents_root, "keeper", body=(
        '[agent]\nname = "keeper"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["web_fetch"]\n'
        '[memory]\nvia = "local"\n'))
    fake = FakeTelegram([])
    asyncio.run(make_bot(fake, service=make_service([], actors=actors),
                         agent="keeper").run())
    assert menu_of(fake) == ["new", "chats", "memory", "remember", "tools"]


def test_a_menu_telegram_refuses_costs_the_menu_never_the_bot(make_bot):
    fake = FakeTelegram([message("hi")])
    fake.status["setMyCommands"] = [httpx.Response(
        400, json={"ok": False, "description": "Bad Request"})]
    asyncio.run(make_bot(fake, script=[says("hello back")]).run())
    assert "hello back" in fake.texts()


# ---- skills offered, and the work while it happens ----------------------------------


def test_a_skill_offered_carries_keep_and_not_now(make_bot):
    fake = FakeTelegram([])
    bot = make_bot(fake)
    offer = {"offer": {"id": "a1b2", "agent": "greeter", "name": "greet-someone"}}
    asyncio.run(bot._deliver_notice(str(KNOWN), "I could keep this.", extra=offer))
    sent = fake.sent()[-1]
    buttons = sent["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["Keep", "Not now"]
    assert [b["callback_data"] for b in buttons] == ["k:greeter:a1b2", "d:greeter:a1b2"]


def test_pressing_one_is_the_word_typed(make_bot):
    pressed = {"update_id": 1, "callback_query": {
        "id": "cb1", "from": {"id": KNOWN}, "data": "d:greeter:a1b2",
        "message": {"message_id": 7, "chat": {"id": KNOWN}, "text": "I could keep this."}}}
    fake = FakeTelegram([pressed])
    asyncio.run(make_bot(fake, script=[]).run())
    assert fake.of("editMessageReplyMarkup")           # the buttons come off
    assert fake.texts() == ["greeter doesn't use skills, so there is nothing to keep here."]


def test_the_working_message_shows_the_last_steps_only():
    from dvara.telegram import STEPS_SHOWN, Steps

    steps = Steps(bot=None, chat=1)
    steps._job = object()                  # no task: only the words are tested
    for n in range(STEPS_SHOWN + 2):
        steps({"kind": "step", "said": f"bash: echo {n}", "ok": n != 7})
    steps({"kind": "text", "text": "never shown"})
    text = steps.text()
    assert text.startswith("Working… (2 earlier steps)")
    assert "bash: echo 0" not in text and "• bash: echo 7 — didn't work" in text
    assert "never shown" not in text


# ---- a sign-in word under the answer (accounts.taps) ----------------------------------


def test_an_answer_that_says_connect_carries_the_button(make_bot):
    fake = FakeTelegram([message("anything from the school?")])
    told = "Gmail isn't connected yet. Send /connect gmail and sign in, then ask again."
    asyncio.run(make_bot(fake, script=[says(told)]).run())
    sent = fake.sent()[-1]
    buttons = sent["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["Connect gmail"]
    assert [b["callback_data"] for b in buttons] == ["w:/connect gmail"]


def test_an_answer_that_says_nothing_of_signing_in_has_no_button(make_bot):
    fake = FakeTelegram([message("hello")])
    asyncio.run(make_bot(fake, script=[says("Hello! Connect with me any time.")]).run())
    assert "reply_markup" not in fake.sent()[-1]


def test_pressing_connect_is_the_word_typed_by_whoever_pressed(make_bot):
    pressed = {"update_id": 1, "callback_query": {
        "id": "cb1", "from": {"id": KNOWN}, "data": "w:/connect gmail",
        "message": {"message_id": 7, "chat": {"id": KNOWN}, "text": "Send /connect gmail"}}}
    fake = FakeTelegram([pressed])
    asyncio.run(make_bot(fake, script=[]).run())
    # answered by the account words, never by the model (the script is empty)
    assert fake.texts() and "/connect" not in fake.texts()[0].split()[0]


def test_a_pressed_word_that_is_not_a_sign_in_word_does_nothing(make_bot):
    pressed = {"update_id": 1, "callback_query": {
        "id": "cb1", "from": {"id": KNOWN}, "data": "w:delete everything",
        "message": {"message_id": 7, "chat": {"id": KNOWN}, "text": "x"}}}
    fake = FakeTelegram([pressed])
    asyncio.run(make_bot(fake, script=[]).run())
    assert fake.texts() == []


# ---- a picture or a file, sent to the agent (attached.py) -----------------------------


def test_a_document_is_kept_in_their_folder_and_named_in_the_message(make_bot):
    sent = message(None, document={"file_id": "doc1", "file_name": "school letter.pdf",
                                   "file_size": 1000}, caption="what does this say?")
    fake = FakeTelegram([sent])
    bot = make_bot(fake, script=[says("It's about the trip.")])
    asyncio.run(bot.run())
    assert fake.texts() == ["It's about the trip."]
    run = bot.service.runs.recent(limit=1)[0]
    assert run.message.startswith("what does this say?")
    assert "from-you/school letter.pdf" in run.message
    kept = list(bot.service.state.rglob("from-you/school letter.pdf"))
    assert len(kept) == 1 and kept[0].read_bytes() == b"bytes of /file/bot" + \
        TOKEN.encode() + b"/files/doc1.bin"


def test_a_photo_is_its_largest_size_and_needs_no_caption(make_bot):
    sent = message(None, photo=[{"file_id": "small", "file_size": 10},
                                {"file_id": "big", "file_size": 900}])
    fake = FakeTelegram([sent])
    bot = make_bot(fake, script=[says("A receipt.")])
    asyncio.run(bot.run())
    assert [p["file_id"] for m, p in fake.calls if m == "getFile"] == ["big"]
    run = bot.service.runs.recent(limit=1)[0]
    assert run.message.startswith("(They sent from-you/photo-") and "(a picture)" in run.message


def test_a_file_too_big_to_download_is_said_and_no_turn_runs(make_bot):
    sent = message(None, document={"file_id": "huge", "file_name": "film.mp4",
                                   "file_size": 900 * 1024 * 1024})
    fake = FakeTelegram([sent])
    bot = make_bot(fake, script=[])
    asyncio.run(bot.run())
    assert fake.texts()[0].startswith("I couldn't get that file: film.mp4 is over")
    assert not [m for m, _ in fake.calls if m == "getFile"]

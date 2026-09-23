"""Bias: a restart must never run a turn twice, and never go quiet about one.

Those pull in opposite directions, which is why both are tested. The easy
way to keep a person from being left unanswered is to replay their
message after a crash -- and that runs a tool twice and spends their
allowance twice. The easy way to never repeat a turn is note 07's, which
was right and left them staring at a chat that would never answer. The
tests here hold both lines at once: no turn is re-run, and nobody who
was owed a reply goes without being told.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from dvara.outbox import PREVIEW, Outbox
from tests.conftest import says
# The bot, its fake Telegram and its one-person roster are test_telegram's
# fixtures, imported so pytest finds them here by name. Ruff reads each
# test's parameter as shadowing the import, which is the mechanism.
# ruff: noqa: F811
from tests.test_telegram import (  # noqa: F401
    KNOWN,
    STRANGER,
    FakeTelegram,
    actors,
    make_bot,
    message,
)


def _owed_by(bot):
    """What is on DISK -- the bot has closed its own handle by now."""
    return Outbox(bot.outbox.path).owed(bot.agent)


# ---- the store -------------------------------------------------------------


def test_a_taken_message_is_owed_until_it_is_settled(tmp_path):
    box = Outbox(tmp_path / "outbox.sqlite3")
    row = box.took(agent="greeter", chat="1", sender="1", text="hello?")
    [debt] = box.owed("greeter")
    assert debt.id == row and not debt.answered

    box.answered(row, ["one", "two"])
    box.sent(row, 1)
    [debt] = box.owed("greeter")
    assert debt.unsent == ("two",)

    box.settled(row)
    assert box.owed("greeter") == []
    box.close()


def test_what_is_owed_survives_the_process(tmp_path):
    first = Outbox(tmp_path / "outbox.sqlite3")
    first.took(agent="greeter", chat="1", sender="1", text="hello?")
    first.close()
    assert len(Outbox(tmp_path / "outbox.sqlite3").owed("greeter")) == 1


def test_only_a_reminder_of_the_message_is_kept(tmp_path):
    box = Outbox(tmp_path / "outbox.sqlite3")
    box.took(agent="greeter", chat="1", sender="1", text="word " * 100)
    [debt] = box.owed("greeter")
    assert len(debt.asked) <= PREVIEW and debt.asked.endswith("…")


def test_one_agent_is_not_owed_another_agents_replies(tmp_path):
    box = Outbox(tmp_path / "outbox.sqlite3")
    box.took(agent="scribe", chat="1", sender="1", text="hi")
    assert box.owed("greeter") == []


# ---- a turn that finishes owes nothing -------------------------------------


def test_an_answered_message_leaves_nothing_owed(make_bot):
    fake = FakeTelegram([message("hello?")])
    bot = make_bot(fake, script=[says("Hello.")])
    asyncio.run(bot.run())
    assert fake.texts() == ["Hello."]
    assert _owed_by(bot) == []


def test_a_long_answer_is_owed_part_by_part(make_bot):
    fake = FakeTelegram([message("go")])
    bot = make_bot(fake, script=[says("a" * 5000)])
    seen = []
    original = bot.outbox.sent
    bot.outbox.sent = lambda row, count: (seen.append(count),
                                          original(row, count))
    asyncio.run(bot.run())
    assert seen == [1, 2]


# ---- the crash, and the boot after it --------------------------------------


def test_a_turn_cut_off_mid_answer_is_owned_up_to_not_run_again(make_bot,
                                                               make_service,
                                                               actors):
    service = make_service([says("never reached")], actors=actors)

    async def hangs(**_):
        await asyncio.Event().wait()      # the process "dies" in here

    real_deliver = service.deliver
    service.deliver = hangs
    first = FakeTelegram([message("what changed today?")])
    asyncio.run(make_bot(first, service=service).run())
    assert first.texts() == []

    # The next boot. Same state directory, a working service.
    service.deliver = real_deliver
    second = FakeTelegram()
    bot = make_bot(second, service=service)
    asyncio.run(bot.run())

    [told] = second.sent()
    assert told["chat_id"] == KNOWN
    assert "“what changed today?”" in told["text"]
    assert "will not be run again" in told["text"]
    # NOT RUN AGAIN: the model was never asked anything, on either boot.
    assert service.scripted.requests == []
    assert _owed_by(bot) == []


def test_an_answer_that_was_half_sent_is_finished_not_repeated(make_bot):
    fake = FakeTelegram()
    bot = make_bot(fake)
    row = bot.outbox.took(agent="greeter", chat=str(KNOWN),
                          sender=str(KNOWN), text="tell me everything")
    bot.outbox.answered(row, ["part one", "part two", "part three"])
    bot.outbox.sent(row, 1)

    asyncio.run(bot.run())
    texts = fake.texts()
    assert "the rest of my answer" in texts[0]
    assert texts[1:] == ["part two", "part three"]
    assert _owed_by(bot) == []


def test_somebody_taken_off_the_list_while_it_was_down_gets_silence(
        make_bot, capsys):
    fake = FakeTelegram()
    bot = make_bot(fake)
    bot.outbox.took(agent="greeter", chat=str(STRANGER),
                    sender=str(STRANGER), text="hello?")
    asyncio.run(bot.run())
    assert fake.sent() == []
    assert _owed_by(bot) == []
    assert "no longer in the actors file" in capsys.readouterr().err


def test_a_network_that_is_down_keeps_the_debt_for_next_time(make_bot):
    fake = FakeTelegram()
    fake.status["sendMessage"] = [httpx.ConnectError("no route to host")]
    bot = make_bot(fake)
    bot.outbox.took(agent="greeter", chat=str(KNOWN), sender=str(KNOWN),
                    text="hello?")
    asyncio.run(bot.run())
    assert len(_owed_by(bot)) == 1


def test_a_chat_that_refuses_is_not_retried_at_every_start(make_bot):
    fake = FakeTelegram()
    fake.status["sendMessage"] = [httpx.Response(
        403, json={"ok": False,
                   "description": "Forbidden: bot was blocked by the user"})]
    bot = make_bot(fake)
    bot.outbox.took(agent="greeter", chat=str(KNOWN), sender=str(KNOWN),
                    text="hello?")
    asyncio.run(bot.run())
    assert _owed_by(bot) == []


@pytest.mark.parametrize("backlog", [False, True])
def test_what_is_owed_is_paid_whether_or_not_the_backlog_is(make_bot,
                                                            backlog):
    # --catch-up decides what happens to messages that ARRIVED while the
    # bot was down. A reply owed from before it went down is a different
    # thing, and is paid either way.
    fake = FakeTelegram()
    bot = make_bot(fake, catch_up=backlog)
    bot.outbox.took(agent="greeter", chat=str(KNOWN), sender=str(KNOWN),
                    text="hello?")
    asyncio.run(bot.run())
    assert len(fake.sent()) == 1

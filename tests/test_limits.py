"""Bias: a limit for a child that a schedule, a refusal or a hold slips past.

Hours, a day's messages and an approver are three short rules. The ways
they go wrong are all around the edges:

* a window past midnight read as "never open";
* a schedule made in the evening that runs at 2 am anyway;
* a refused message counted as one of the day's, so a child at the limit
  can never get back under it;
* a question meant for the parent put to the child, or held for a child
  who cannot answer it;
* an owner's typo (an approver nobody here is called) meaning "nobody is
  asked", which is a refusal of every change nobody chose.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from dvara.actors import ActorBook
from dvara.asks import AskDesk, NotYours
from dvara.errors import ConfigProblem
from dvara.limits import ForApproval, Hours, turns_spent
from dvara.runs import Run

from tests.conftest import calls, says
from tests.test_what_decided_it import scribe


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 23, hour, minute).astimezone()


# ---- the hours --------------------------------------------------------------

def test_a_day_window_is_open_inside_and_closed_outside():
    hours = Hours.parse("07:00-21:00")
    assert hours.open_at(at(7)) and hours.open_at(at(20, 59))
    assert not hours.open_at(at(21)) and not hours.open_at(at(6, 59))


def test_a_window_past_midnight_is_open_late_and_early():
    hours = Hours.parse("22:00-06:00")
    assert hours.open_at(at(23)) and hours.open_at(at(1))
    assert not hours.open_at(at(12))


def test_outside_the_hours_the_sentence_says_when_to_come_back():
    said = Hours.parse("07:00-21:00").closed(at(22))
    assert "07:00-21:00" in said and "after 07:00" in said
    assert Hours.parse("07:00-21:00").closed(at(9)) is None


@pytest.mark.parametrize("bad", ["7-21", "07:00", "25:00-26:00", "08:00-08:00", 7])
def test_hours_that_dont_read_as_a_window_are_an_error(bad):
    with pytest.raises(ConfigProblem, match="hours"):
        ActorBook.from_dict({"actor": {"kid": {"hours": bad}}})


# ---- the day's messages -------------------------------------------------------

@pytest.mark.parametrize("value", [0, -1, 2.5, "40", True])
def test_a_turn_limit_is_a_whole_number_above_zero(value):
    with pytest.raises(ConfigProblem, match="max_turns_per_day"):
        ActorBook.from_dict({"actor": {"kid": {"max_turns_per_day": value}}})


def test_the_limit_speaks_only_once_it_is_reached():
    assert turns_spent(3, 2) is None and turns_spent(None, 99) is None
    assert "all 3 messages" in turns_spent(3, 3)


KIDS = ActorBook.from_dict({"actor": {
    "owner": {"permissions": "ask"},
    "kid": {"max_turns_per_day": 2, "permissions": "ask", "approver": "owner"},
}})


def deliver(service, **kw):
    kw.setdefault("actor", "kid")
    kw.setdefault("agent", "greeter")
    kw.setdefault("thread", "t")
    kw.setdefault("text", "hi")
    return asyncio.run(service.deliver(**kw))


def test_the_third_message_of_a_two_message_day_is_refused(make_service):
    service = make_service([says("one"), says("two")], actors=KIDS)
    assert deliver(service).ok and deliver(service).ok
    third = deliver(service)
    assert third.stop_reason == "refused" and "all 2 messages" in third.text


def test_refusals_and_schedules_are_not_counted(make_service):
    service = make_service([says("ok")], actors=KIDS)
    now = datetime.now(UTC)
    for stop, unattended in (("refused", False), ("looked_back", False),
                             ("end_turn", True)):
        service.runs.record(Run(actor="kid", agent="greeter", thread="t", message="m",
                                started_at=now, stop_reason=stop, unattended=unattended))
    assert service.runs.asked_since("kid", now - timedelta(minutes=1)) == 0
    assert deliver(service).ok


def test_outside_the_hours_a_turn_is_refused_before_any_model(make_service):
    now = datetime.now().astimezone()
    later = now + timedelta(hours=2)
    window = f"{later:%H:%M}-{later + timedelta(hours=1):%H:%M}"
    book = ActorBook.from_dict({"actor": {"owner": {}, "kid": {"hours": window}}})
    service = make_service([], actors=book)       # nothing may be called
    reply = deliver(service)
    assert reply.stop_reason == "refused" and window in reply.text


# ---- the approver -------------------------------------------------------------

def test_an_approver_must_be_somebody_in_the_file():
    with pytest.raises(ConfigProblem, match="nobody in this file"):
        ActorBook.from_dict({"actor": {"kid": {"approver": "mum"}}})
    with pytest.raises(ConfigProblem, match="themselves"):
        ActorBook.from_dict({"actor": {"kid": {"approver": "kid"}}})


def test_the_question_goes_to_the_approver_and_says_whose_agent(make_service,
                                                               agents_root):
    scribe(agents_root)
    desk = AskDesk(timeout=5, on_timeout="hold")
    service = make_service([calls("write_file", {"path": "a.txt", "content": "x"}),
                            says("written.")], actors=KIDS, asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(actor="kid", agent="scribe",
                                                   thread="t", text="write it"))
        while not desk.pending():
            await asyncio.sleep(0)
        ask = desk.pending()[0]
        assert ask.actor == "owner" and ask.summary.startswith("For kid:")
        assert desk.pending("kid") == []
        with pytest.raises(NotYours):          # not the child's to answer
            desk.answer(ask.id, actor="kid", approve=True)
        desk.answer(ask.id, actor="owner", approve=True)
        return await turn

    assert asyncio.run(go()).ok


def test_silence_from_the_approver_refuses_rather_than_holds():
    assert ForApproval(AskDesk(timeout=5, on_timeout="hold"), approver="owner",
                       reach=(), person="kid").on_timeout == "deny"

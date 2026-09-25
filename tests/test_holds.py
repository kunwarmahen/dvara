"""Bias: a held turn that is lost, doubled, or answered by the wrong person.

``--on-timeout hold`` keeps an unanswered question for the person to come
back to, instead of refusing the call (notes/16). The ways that goes
wrong are all worse than the refusal it replaces:

* a call runs that nobody approved -- a held call treated as allowed, or
  a batch-mate asked about and approved by a person who was not there;
* a hold that cannot be found after a restart, which is the one moment
  it exists for;
* a hold answered twice, so an approved write runs twice;
* a hold answered by somebody the turn was not running as;
* a bad answer that uses the hold up, so the person cannot try again;
* a newer message that leaves the old hold answerable, so an approval
  lands on a conversation that has moved on;
* a batch that waits out the full deadline once per call before it can
  stop.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest
from yantra import HELD

from dvara.asks import AskDesk
from dvara.holds import HoldBook, NoSuchHold, NotYourHold, Waiting
from dvara.errors import Refused
from dvara.keys import session_key
from dvara.runs import Run, ToolStep

from tests.conftest import says
from tests.test_what_decided_it import scribe, two_calls


def holding(timeout: float = 0.05) -> AskDesk:
    return AskDesk(timeout=timeout, on_timeout="hold")


def held_turn(service):
    return asyncio.run(service.deliver(actor="owner", agent="scribe",
                                       thread="t", text="write both"))


def work(service):
    return service._workspace(session_key("owner", "scribe", "t"))


# ---- silence holds ----------------------------------------------------------


def test_an_unanswered_question_stops_the_turn_and_nothing_runs(
        make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls()], asks=holding())
    reply = held_turn(service)
    assert reply.stop_reason == "held"
    assert reply.held is not None
    assert [c.call_id for c in reply.held.calls] == ["call-a", "call-b"]
    assert "waiting for your approval" in reply.text
    assert "write_file" in reply.text
    assert not (work(service) / "a.txt").exists()
    assert not (work(service) / "b.txt").exists()
    assert service.scripted.script == []      # no second model call


def test_a_batch_stops_after_one_deadline_not_one_per_call(make_service,
                                                           agents_root):
    """The second call is held WITHOUT being put: the person is away."""
    scribe(agents_root)
    put = []
    desk = holding(timeout=0.4)

    async def notify(ask):
        put.append(ask.id)

    desk.notify = notify
    service = make_service([two_calls()], asks=desk)
    started = time.monotonic()
    held_turn(service)
    assert len(put) == 1
    assert time.monotonic() - started < 0.8


def test_the_held_turn_is_recorded_with_its_waiting_calls(make_service,
                                                          agents_root):
    scribe(agents_root)
    service = make_service([two_calls()], asks=holding())
    reply = held_turn(service)
    run = service.runs.get(reply.run_id)
    assert run.stop_reason == "held"
    assert [(s.name, s.refusal) for s in run.tools] == [
        ("write_file", HELD), ("write_file", HELD)]
    # Waiting is not refused: `dvara case` must not suggest forbidding it.
    assert run.refused_tools == []
    assert run.waited_seconds > 0


def test_deny_is_still_the_default(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("nobody answered.")],
                           asks=AskDesk(timeout=0.05))
    reply = held_turn(service)
    assert reply.stop_reason == "end_turn"
    assert reply.held is None
    assert service.holds.pending() == []


def test_silence_may_never_approve():
    with pytest.raises(ValueError, match="never approves"):
        AskDesk(timeout=5, on_timeout="allow")


def test_a_spent_day_holds_instead_of_refusing(make_service, agents_root):
    """Under deny a used-up day is a refusal; under hold it is a question
    kept for when they are back -- and still not put to them now."""
    from dvara.actors import ActorBook
    scribe(agents_root)
    put = []
    desk = holding(timeout=5)

    async def notify(ask):
        put.append(ask.id)

    desk.notify = notify
    book = ActorBook.from_dict({"actor": {"owner": {"max_wait_per_day": 1}}})
    service = make_service([two_calls()], asks=desk, actors=book)
    service.runs.record(Run(actor="owner", agent="scribe", thread="old",
                            message="m", started_at=datetime.now(UTC),
                            waited_seconds=5.0))
    reply = held_turn(service)
    assert reply.stop_reason == "held"
    assert put == []


# ---- answering it -----------------------------------------------------------


def test_an_answer_carries_the_turn_on(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("wrote a, left b.")],
                           asks=holding())
    held = held_turn(service).held
    reply = asyncio.run(service.resume(
        held.id, actor="owner", door="http",
        answers={"call-a": True, "call-b": "leave b alone"}))
    assert reply.ok and reply.text == "wrote a, left b."
    assert (work(service) / "a.txt").read_text() == "one"
    assert not (work(service) / "b.txt").exists()
    # The person's own words reached the model.
    last = service.scripted.requests[-1]["messages"][-1]
    assert "leave b alone" in str(last.content)
    assert service.holds.pending() == []


def test_the_answer_is_its_own_run_linked_to_the_held_one(make_service,
                                                          agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("done.")], asks=holding())
    held = held_turn(service).held
    reply = asyncio.run(service.resume(held.id, actor="owner",
                                       door="telegram",
                                       answers={"call-a": True,
                                                "call-b": False}))
    run = service.runs.get(reply.run_id)
    assert run.resumes == held.run_id
    assert run.message == "write both"
    assert [(s.name, s.refusal, s.decided_by) for s in run.tools] == [
        ("write_file", None, "asked:telegram"),
        ("write_file", "user", "asked:telegram")]


def test_a_hold_survives_a_restart(make_service, agents_root, tmp_path):
    scribe(agents_root)
    first = make_service([two_calls()], asks=holding())
    held = held_turn(first).held
    first.close()

    # A new process over the same state, and with no hold policy at all:
    # whether silence holds is about new questions, not stranding old ones.
    second = make_service([says("done after the restart.")])
    assert [h.id for h in second.holds.pending()] == [held.id]
    reply = asyncio.run(second.resume(held.id, actor="owner",
                                      answers={"call-a": True,
                                               "call-b": True}))
    assert reply.text == "done after the restart."
    assert (work(second) / "b.txt").read_text() == "two"


def test_a_hold_cannot_be_answered_twice(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("done.")], asks=holding())
    held = held_turn(service).held
    answers = {"call-a": True, "call-b": True}
    asyncio.run(service.resume(held.id, actor="owner", answers=answers))
    with pytest.raises(NoSuchHold):
        asyncio.run(service.resume(held.id, actor="owner", answers=answers))


def test_two_answers_racing_run_the_calls_once(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("done.")], asks=holding())
    held = held_turn(service).held
    answers = {"call-a": True, "call-b": True}

    async def race():
        return await asyncio.gather(
            service.resume(held.id, actor="owner", answers=answers),
            service.resume(held.id, actor="owner", answers=answers),
            return_exceptions=True)

    results = asyncio.run(race())
    assert sum(isinstance(r, NoSuchHold) for r in results) == 1
    assert sum(getattr(r, "ok", False) for r in results) == 1


def test_only_the_person_it_ran_as_may_answer(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("done.")], asks=holding())
    held = held_turn(service).held
    with pytest.raises(NotYourHold):
        asyncio.run(service.resume(held.id, actor="guest",
                                   answers={"call-a": True, "call-b": True}))
    assert [h.id for h in service.holds.pending()] == [held.id]


def test_a_wrong_answer_costs_nothing(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("done.")], asks=holding())
    held = held_turn(service).held
    with pytest.raises(Refused, match="unanswered: call-b"):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True}))
    with pytest.raises(Refused, match="true, false"):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True,
                                            "call-b": {"path": "x"}}))
    assert not (work(service) / "a.txt").exists()
    reply = asyncio.run(service.resume(held.id, actor="owner",
                                       answers={"call-a": True,
                                                "call-b": True}))
    assert reply.ok


def test_a_spent_allowance_keeps_the_hold_for_tomorrow(make_service,
                                                       agents_root,
                                                       priced_model):
    from dvara.actors import ActorBook
    scribe(agents_root)
    book = ActorBook.from_dict({"actor": {"owner": {"max_usd_per_day": 1.0}}})
    service = make_service([two_calls(), says("done.")], asks=holding(),
                           actors=book)
    held = held_turn(service).held
    service.runs.record(Run(actor="owner", agent="scribe", thread="x",
                            message="m", started_at=datetime.now(UTC),
                            cost_usd=5.0))
    with pytest.raises(Refused, match="allowance is spent"):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True, "call-b": True}))
    assert [h.id for h in service.holds.pending()] == [held.id]


# ---- setting it aside -------------------------------------------------------


def test_a_new_message_sets_the_hold_aside(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("ok, something else.")],
                           asks=holding())
    held = held_turn(service).held
    reply = asyncio.run(service.deliver(actor="owner", agent="scribe",
                                        thread="t", text="never mind"))
    assert reply.ok
    assert service.holds.pending() == []
    sent = service.scripted.requests[-1]["messages"]
    assert "set aside" in str(sent[-2].content)
    with pytest.raises(NoSuchHold):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True, "call-b": True}))


def test_a_message_in_another_conversation_leaves_it_alone(make_service,
                                                           agents_root):
    scribe(agents_root)
    service = make_service([two_calls(), says("hi.")], asks=holding())
    held = held_turn(service).held
    asyncio.run(service.deliver(actor="owner", agent="scribe",
                                thread="elsewhere", text="hello"))
    assert [h.id for h in service.holds.pending()] == [held.id]


def test_a_row_the_session_no_longer_backs_is_dropped_when_used(
        make_service, agents_root):
    """The checkpoint is the truth; the table is its index."""
    scribe(agents_root)
    service = make_service([says("hello")])
    stale = service.holds.keep(
        key=session_key("owner", "scribe", "t"), actor="owner",
        agent="scribe", thread="t", run_id="r1",
        held_at=datetime.now(UTC), calls=[Waiting("c9", "write_file", "s")])
    with pytest.raises(NoSuchHold, match="moved on"):
        asyncio.run(service.resume(stale.id, actor="owner",
                                   answers={"c9": True}))
    assert service.holds.pending() == []


# ---- expiry and the book ----------------------------------------------------


def test_an_old_hold_expires(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls()], asks=holding(), hold_for=60)
    held = held_turn(service).held
    later = datetime.now(UTC) + timedelta(minutes=5)
    assert service.holds.pending(now=later) == []
    with pytest.raises(NoSuchHold):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True, "call-b": True}))


def test_expiry_is_said_in_the_refusal(make_service, agents_root):
    scribe(agents_root)
    service = make_service([two_calls()], asks=holding(), hold_for=0.01)
    held = held_turn(service).held
    time.sleep(0.05)
    with pytest.raises(NoSuchHold, match="can no longer be answered"):
        asyncio.run(service.resume(held.id, actor="owner",
                                   answers={"call-a": True, "call-b": True}))


def test_one_conversation_holds_one_turn(tmp_path):
    book = HoldBook(tmp_path / "h.sqlite3")
    now = datetime.now(UTC)
    first = book.keep(key="k", actor="a", agent="g", thread="t", run_id="1",
                      held_at=now, calls=[])
    second = book.keep(key="k", actor="a", agent="g", thread="t", run_id="2",
                       held_at=now, calls=[])
    assert book.get(first.id) is None
    assert [h.id for h in book.pending()] == [second.id]
    book.close()


def test_a_hold_of_no_time_is_refused(tmp_path):
    with pytest.raises(ValueError, match="expires before anyone"):
        HoldBook(tmp_path / "h.sqlite3", keep_for=0)


def test_a_held_step_is_not_a_refused_one():
    run = Run(actor="o", agent="a", thread="t", message="m",
              started_at=datetime.now(UTC),
              tools=[ToolStep("write_file", HELD), ToolStep("bash", "user")])
    assert run.refused_tools == ["bash"]


"""Bias: the four ways a question to a human goes wrong.

A gate that waits is a gate that can wait forever, wait for the wrong
person, wait for somebody who was never told, or still be waiting after
the turn behind it has gone. Every test here is one of those, and the one
that matters most is the last section: a turn that waits must not stop
anybody else's.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara.asks import AskDesk, NotYours


def run(coro):
    return asyncio.run(coro)


async def answered(desk: AskDesk, *, approve: bool, actor: str = "owner"):
    """Wait for the question to appear, then answer it."""
    while not desk.pending():
        await asyncio.sleep(0)
    ask = desk.pending()[0]
    desk.answer(ask.id, actor=actor, approve=approve)
    return ask


def put(desk: AskDesk, *, actor: str = "owner", tool: str = "bash"):
    return desk.put(actor=actor, agent="ops", thread="t1", tool=tool,
                    summary="rm -rf /tmp/x")


# ---- a decision comes back either way --------------------------------------

def test_a_yes_approves_the_call():
    desk = AskDesk(timeout=5)

    async def go():
        asking = asyncio.create_task(put(desk))
        await answered(desk, approve=True)
        return await asking

    answer = run(go())
    assert answer.approved
    assert answer.reason is None


def test_a_no_denies_it_and_says_who_said_so():
    desk = AskDesk(timeout=5)

    async def go():
        asking = asyncio.create_task(put(desk))
        await answered(desk, approve=False)
        return await asking

    answer = run(go())
    assert not answer.approved
    # The sentence goes to the MODEL. It has to be able to tell being
    # refused by a reachable person from the other two denials.
    assert "owner was asked and said no" in answer.reason
    assert "do not re-run this call" in answer.reason


def test_silence_denies_and_says_it_was_silence():
    desk = AskDesk(timeout=0.05)
    answer = run(put(desk))
    assert not answer.approved
    assert "nobody answered within 0.05 seconds" in answer.reason
    assert "This is silence, not a refusal" in answer.reason


def test_a_question_that_cannot_be_delivered_denies_without_waiting():
    # The bot is down. Waiting out the deadline would be two minutes of
    # nothing, and the model would be told the wrong thing at the end of
    # it: nobody could be reached is not the same fact as nobody answered.
    async def broken(ask):
        raise RuntimeError("telegram: 401")

    desk = AskDesk(timeout=30, notify=broken)
    answer = run(put(desk))
    assert not answer.approved
    assert "could not be delivered" in answer.reason
    assert "RuntimeError" in answer.reason
    assert "asking again will not help" in answer.reason


def test_the_notifier_is_what_carries_the_question_out():
    seen = []

    async def notify(ask):
        seen.append(ask)
        desk.answer(ask.id, actor=ask.actor, approve=True)

    desk = AskDesk(timeout=5, notify=notify)
    assert run(put(desk, tool="write_file")).approved
    assert [ask.tool for ask in seen] == ["write_file"]
    assert seen[0].summary == "rm -rf /tmp/x"
    assert seen[0].agent == "ops"


# ---- only the person it was put to ------------------------------------------

def test_somebody_else_cannot_answer_your_question():
    desk = AskDesk(timeout=0.2)

    async def go():
        asking = asyncio.create_task(put(desk, actor="owner"))
        while not desk.pending():
            await asyncio.sleep(0)
        ask = desk.pending()[0]
        with pytest.raises(NotYours):
            desk.answer(ask.id, actor="guest", approve=True)
        # ...and the question is still standing, for the person it was
        # actually put to. A wrong answer must not consume it.
        assert desk.get(ask.id) is not None
        return await asking

    answer = run(go())
    assert not answer.approved          # it timed out instead
    assert "nobody answered" in answer.reason


def test_an_unknown_id_answers_nothing():
    desk = AskDesk(timeout=5)
    assert desk.answer("not-a-real-id", actor="owner", approve=True) is False


def test_a_question_is_over_once_it_is_answered():
    desk = AskDesk(timeout=5)

    async def go():
        asking = asyncio.create_task(put(desk))
        ask = await answered(desk, approve=True)
        await asking
        # Second answer lands on nothing: the turn is long past caring.
        assert desk.answer(ask.id, actor="owner", approve=False) is False
        assert desk.pending() == []

    run(go())


def test_a_timed_out_question_is_not_left_lying_around():
    desk = AskDesk(timeout=0.05)
    run(put(desk))
    assert desk.pending() == []


def test_a_desk_with_no_deadline_is_refused_at_construction():
    # A timeout of zero denies before it asks, which is a legible thing to
    # want and an illegible way to say it.
    with pytest.raises(ValueError, match="denies before it asks"):
        AskDesk(timeout=0)


# ---- the turn behind the question -------------------------------------------

def test_a_cancelled_turn_takes_its_question_with_it():
    # A dropped connection is not a person saying no. The ask goes away
    # because nothing is waiting on the answer any more, and the
    # cancellation carries on up.
    desk = AskDesk(timeout=30)

    async def go():
        asking = asyncio.create_task(put(desk))
        while not desk.pending():
            await asyncio.sleep(0)
        asking.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asking
        assert desk.pending() == []

    run(go())


def test_one_persons_wait_does_not_stop_anybody_else():
    # THE WHOLE POINT. The gate suspends; it does not block. If it
    # blocked, the second question could not even be asked until the
    # first one's deadline had passed -- and in a real service that is
    # every other conversation in the process, not just this one.
    desk = AskDesk(timeout=5)

    async def go():
        slow = asyncio.create_task(put(desk, actor="owner"))
        quick = asyncio.create_task(put(desk, actor="guest"))
        while len(desk.pending()) < 2:
            await asyncio.sleep(0)

        # Answer the guest's, while the owner's is still standing.
        guest_ask = desk.pending("guest")[0]
        desk.answer(guest_ask.id, actor="guest", approve=True)
        assert (await quick).approved
        assert desk.pending("owner")

        owner_ask = desk.pending("owner")[0]
        desk.answer(owner_ask.id, actor="owner", approve=False)
        assert not (await slow).approved

    run(go())


def test_pending_lists_one_persons_questions_oldest_first():
    desk = AskDesk(timeout=5)

    async def go():
        tasks = [asyncio.create_task(put(desk, actor=who, tool=tool))
                 for who, tool in (("owner", "bash"), ("guest", "write_file"),
                                   ("owner", "edit_file"))]
        while len(desk.pending()) < 3:
            await asyncio.sleep(0)
        assert [a.tool for a in desk.pending("owner")] == ["bash", "edit_file"]
        assert [a.tool for a in desk.pending("guest")] == ["write_file"]
        assert len(desk.pending()) == 3
        for ask in desk.pending():
            desk.answer(ask.id, actor=ask.actor, approve=False)
        await asyncio.gather(*tasks)

    run(go())


def test_the_wire_shape_carries_what_a_channel_needs_to_render_it():
    desk = AskDesk(timeout=5)

    async def go():
        asking = asyncio.create_task(put(desk, tool="bash"))
        while not desk.pending():
            await asyncio.sleep(0)
        shape = desk.pending()[0].as_dict()
        assert shape["tool"] == "bash"
        assert shape["summary"] == "rm -rf /tmp/x"
        assert shape["actor"] == "owner"
        assert shape["agent"] == "ops"
        assert shape["thread"] == "t1"
        assert shape["asked_at"].endswith("+00:00")
        desk.answer(shape["id"], actor="owner", approve=False)
        await asking

    run(go())


def test_an_answer_from_another_thread_still_wakes_the_turn():
    # A channel adapter is under no obligation to be asyncio. Resolving a
    # future from the wrong thread does not raise -- it just never wakes
    # the loop -- so this would fail as a TIMEOUT, which is the worst
    # possible symptom: an approval that reads as silence.
    import threading

    desk = AskDesk(timeout=5)

    async def go():
        asking = asyncio.create_task(put(desk))
        while not desk.pending():
            await asyncio.sleep(0)
        ask = desk.pending()[0]

        elsewhere = threading.Thread(
            target=lambda: desk.answer(ask.id, actor="owner", approve=True))
        elsewhere.start()
        elsewhere.join()
        return await asking

    answer = run(go())
    assert answer.approved, "an answer from another thread was lost"


def test_a_notifier_that_waits_for_the_answer_still_has_a_deadline():
    # The terminal prompt both asks and collects: it does not return until
    # somebody types. If delivery were awaited BEFORE the wait, the clock
    # would not start until the answer had already arrived, and the one
    # front end that most needs a deadline would be the one without one.
    async def prompt_that_nobody_answers(ask):
        await asyncio.sleep(3600)

    desk = AskDesk(timeout=0.05, notify=prompt_that_nobody_answers)
    answer = run(put(desk))
    assert not answer.approved
    assert "nobody answered within" in answer.reason


def test_a_slow_delivery_that_arrives_still_gets_its_answer():
    # The other side of the same change: delivery finishing is not the
    # same event as the question being answered, and the wait must carry
    # on afterwards rather than falling out of the loop.
    desk = AskDesk(timeout=5)

    async def slow_notify(ask):
        await asyncio.sleep(0.01)
        desk.answer(ask.id, actor=ask.actor, approve=True)

    desk.notify = slow_notify
    assert run(put(desk)).approved

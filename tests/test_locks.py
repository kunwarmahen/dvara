"""Bias: a lock that is thrown away too early is worse than one kept forever.

A table that never evicts costs memory, slowly and visibly. A table that
evicts at the wrong moment costs a conversation: two turns run at once
against one checkpoint, both save, and one of them is simply not in the
history afterwards. Nothing raises. So most of the tests here are about
the moment an entry must NOT go -- while somebody is queued on it, and
while a cancelled waiter is on its way out -- and only then about the
table actually emptying.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara.locks import KeyedLocks
from dvara.telegram import _Pacer
from tests.conftest import says


async def _enter_and_leave(locks, key, log, name, *, pause=0):
    async with locks.hold(key):
        log.append(f"{name} in")
        for _ in range(pause):
            await asyncio.sleep(0)
        log.append(f"{name} out")


# ---- the table empties -----------------------------------------------------


def test_a_key_is_gone_once_its_only_holder_leaves():
    locks = KeyedLocks()

    async def once():
        async with locks.hold("t1"):
            assert "t1" in locks
        assert "t1" not in locks

    asyncio.run(once())
    assert len(locks) == 0


def test_a_thousand_conversations_leave_nothing_behind():
    locks = KeyedLocks()

    async def many():
        await asyncio.gather(*(
            _enter_and_leave(locks, f"t{i}", [], "x") for i in range(1000)))

    asyncio.run(many())
    assert len(locks) == 0


# ---- ...but never while somebody still needs it ----------------------------


def test_a_key_somebody_is_queued_on_outlives_its_holder():
    locks = KeyedLocks()
    log: list[str] = []

    async def scene():
        first = locks.hold("t")
        await first.__aenter__()
        queued = asyncio.create_task(_enter_and_leave(locks, "t", log, "B"))
        await asyncio.sleep(0)              # B is now waiting on the lock
        await first.__aexit__(None, None, None)

        # The moment that matters: the holder has left, B has not run
        # yet. Evicting here would hand the next arrival a fresh lock.
        assert "t" in locks
        late = asyncio.create_task(
            _enter_and_leave(locks, "t", log, "C", pause=3))
        await asyncio.gather(queued, late)

    asyncio.run(scene())
    assert log == ["B in", "B out", "C in", "C out"]
    assert len(locks) == 0


def test_fifty_turns_on_one_key_never_overlap():
    locks = KeyedLocks()
    inside = peak = 0

    async def turn():
        nonlocal inside, peak
        async with locks.hold("t"):
            inside += 1
            peak = max(peak, inside)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            inside -= 1

    async def crowd():
        await asyncio.gather(*(turn() for _ in range(50)))

    asyncio.run(crowd())
    assert peak == 1
    assert len(locks) == 0


def test_a_cancelled_waiter_gives_its_place_back():
    locks = KeyedLocks()

    async def scene():
        held = locks.hold("t")
        await held.__aenter__()
        waiter = asyncio.create_task(_enter_and_leave(locks, "t", [], "B"))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        await held.__aexit__(None, None, None)

    asyncio.run(scene())
    # Without the count coming back, this key would be pinned for the
    # life of the process -- the original leak, one entry at a time.
    assert len(locks) == 0


def test_a_holder_that_raises_still_lets_the_key_go():
    locks = KeyedLocks()

    async def boom():
        async with locks.hold("t"):
            raise RuntimeError("the turn broke")

    with pytest.raises(RuntimeError):
        asyncio.run(boom())
    assert len(locks) == 0


def test_two_keys_do_not_wait_for_each_other():
    locks = KeyedLocks()
    log: list[str] = []

    async def scene():
        async with locks.hold("a"):
            await _enter_and_leave(locks, "b", log, "b")

    asyncio.run(asyncio.wait_for(scene(), timeout=1))
    assert log == ["b in", "b out"]


# ---- the two tables that use it --------------------------------------------


def test_the_service_keeps_no_lock_for_a_finished_conversation(make_service):
    service = make_service([says("one"), says("two"), says("three")])

    async def three_threads():
        await asyncio.gather(*(
            service.deliver(actor="owner", agent="greeter", thread=t,
                            text="hi")
            for t in ("t1", "t2", "t3")))

    asyncio.run(three_threads())
    assert len(service._locks) == 0


def test_the_pacer_forgets_a_chat_once_its_gap_has_passed():
    pacer = _Pacer(gap=0.01)

    async def scene():
        for chat in range(100):
            async with pacer.lock(chat):
                await pacer.wait(chat)
                pacer.sent(chat)
        await asyncio.sleep(0.02)
        async with pacer.lock(999):
            pacer.sent(999)

    asyncio.run(scene())
    assert len(pacer._locks) == 0
    assert list(pacer._next) == [999]


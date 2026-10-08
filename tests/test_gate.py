"""Bias: a package that grants itself permissions by asking for them.

"Tighten, never loosen" is one comparison, and the failure it prevents is
a stranger's package shipping `mode = "yolo"` and getting it. Then two
halves of what "ask" means: what the MODEL is told when there is nobody to
ask -- which used to be a sentence about a user who did not exist -- and
what happens when there IS somebody, which is a gate that suspends.
"""

from __future__ import annotations

import asyncio
import base64

from yantra import (
    DENIED,
    PermissionRequest,
    adecide,
    allow_read_only,
    denial_text,
    yolo,
)

from yantra.types import ImageBlock

from dvara.asks import AskDesk
from dvara.gate import Policy, stricter


def request(*, read_only: bool, tool: str = "bash") -> PermissionRequest:
    return PermissionRequest(tool_name=tool, arguments={}, summary="rm -rf /",
                             read_only=read_only)


# ---- the ladder -------------------------------------------------------------

def test_a_package_cannot_grant_itself_yolo():
    assert Policy(mode="ask").gate("yolo") is allow_read_only


def test_yolo_needs_both_the_owner_and_the_package_to_say_so():
    assert Policy(mode="yolo").gate("yolo") is yolo
    assert Policy(mode="yolo").gate("ask") is allow_read_only


def test_a_package_that_says_nothing_gets_the_tightest_mode():
    # The one silence that is read as a decision: an author who ships code
    # and no [permissions] table has not asked to be escalated for.
    assert Policy(mode="yolo").gate(None) is allow_read_only
    assert stricter() == "read_only"


def test_an_actor_who_says_nothing_changes_nothing():
    # The other silence. An absent `permissions` key composes like an
    # absent `max_usd_per_turn`: by not being a ceiling.
    assert Policy(mode="yolo").gate("yolo", actor_mode=None) is yolo
    assert stricter("yolo", None) == "yolo"


def test_an_actor_may_tighten_and_never_loosen():
    assert Policy(mode="yolo").gate("yolo", actor_mode="read_only") is allow_read_only
    # ...and the other direction is simply ignored, by arithmetic.
    assert Policy(mode="ask").gate("ask", actor_mode="yolo") is allow_read_only
    assert stricter("read_only", "yolo") == "read_only"


def test_an_unrecognised_mode_reads_as_the_tightest():
    # A mode from a future version of the format, or a typo, must never
    # be the loose one by accident.
    assert stricter("unheard-of", "yolo") == "unheard-of"
    assert Policy(mode="ask").gate("unheard-of") is allow_read_only


# ---- with nobody to ask -----------------------------------------------------

def test_with_nobody_present_ask_means_read_only_tools_only():
    gate = Policy(mode="ask").gate("ask")
    assert gate(request(read_only=True)) is True
    assert gate(request(read_only=False)) is False


def test_a_refusal_does_not_blame_a_user_who_was_never_there():
    # The sentence goes to the MODEL, and it is the difference between an
    # agent that argues with an absent human and one that finds a
    # read-only route. Asserted through denial_text, which is what the
    # loop actually puts in the error result.
    denied = request(read_only=False)
    assert Policy(mode="ask").gate("ask")(denied) is False
    assert denial_text(denied) != DENIED
    assert "user" not in denial_text(denied)
    assert "Nobody is available to ask" in denial_text(denied)


def test_an_approval_leaves_no_reason_behind():
    allowed = request(read_only=True)
    assert Policy(mode="ask").gate("ask")(allowed) is True
    assert allowed.reason is None


# ---- with somebody to ask ---------------------------------------------------

def gate_with_desk(desk, *, package="ask", owner="ask", actor_mode=None):
    return Policy(mode=owner).gate(package, actor_mode=actor_mode, desk=desk,
                                   actor="owner", agent="ops", thread="t1")


def test_a_desk_is_what_turns_ask_into_a_question():
    desk = AskDesk(timeout=5)
    gate = gate_with_desk(desk)
    # Not one of Yantra's two functions any more: this one waits.
    assert gate is not allow_read_only
    assert gate is not yolo

    async def go():
        wanted = request(read_only=False)
        deciding = asyncio.create_task(adecide(gate, wanted))
        while not desk.pending():
            await asyncio.sleep(0)
        desk.answer(desk.pending()[0].id, actor="owner", approve=True)
        assert await deciding is True
        assert wanted.reason is None

    asyncio.run(go())


def test_a_cards_picture_rides_on_the_question_to_the_person_only():
    desk = AskDesk(timeout=5)
    gate = gate_with_desk(desk)

    async def go():
        wanted = request(read_only=False, tool="mcp__sparsh__confirm")
        wanted.picture = ImageBlock(media_type="image/png",
                                    data=base64.b64encode(b"\x89PNG ringed").decode())
        deciding = asyncio.create_task(adecide(gate, wanted))
        while not desk.pending():
            await asyncio.sleep(0)
        ask = desk.pending()[0]
        assert ask.picture == b"\x89PNG ringed"
        assert ask.as_dict()["picture"] == wanted.picture.data
        desk.answer(ask.id, actor="owner", approve=False)
        assert await deciding is False

    asyncio.run(go())


def test_a_question_in_words_carries_no_picture():
    desk = AskDesk(timeout=5)
    gate = gate_with_desk(desk)

    async def go():
        deciding = asyncio.create_task(adecide(gate, request(read_only=False)))
        while not desk.pending():
            await asyncio.sleep(0)
        assert desk.pending()[0].picture is None
        assert "picture" not in desk.pending()[0].as_dict()
        desk.answer(desk.pending()[0].id, actor="owner", approve=False)
        await deciding

    asyncio.run(go())


def test_a_refused_question_becomes_a_reason_the_model_can_read():
    desk = AskDesk(timeout=5)
    gate = gate_with_desk(desk)

    async def go():
        wanted = request(read_only=False)
        deciding = asyncio.create_task(adecide(gate, wanted))
        while not desk.pending():
            await asyncio.sleep(0)
        desk.answer(desk.pending()[0].id, actor="owner", approve=False)
        assert await deciding is False
        assert "owner was asked and said no" in denial_text(wanted)

    asyncio.run(go())


def test_a_read_only_call_is_never_put_to_a_person():
    # Waking somebody up to confirm a directory listing is how a service
    # gets turned off. The answer is a plain True, not even a coroutine.
    desk = AskDesk(timeout=5)
    assert gate_with_desk(desk)(request(read_only=True)) is True
    assert desk.pending() == []


def test_a_desk_does_not_make_a_read_only_service_start_asking():
    # The owner said read_only. Having somewhere to send a question is not
    # a reason to send one.
    desk = AskDesk(timeout=5)
    assert gate_with_desk(desk, owner="read_only") is allow_read_only
    assert gate_with_desk(desk, actor_mode="read_only") is allow_read_only


def test_no_desk_is_the_old_behaviour_exactly():
    # The property that keeps every service built before escalation
    # existed working the way it did: nothing waits on somebody who was
    # never wired up.
    assert Policy(mode="ask").gate("ask", desk=None) is allow_read_only



# ---- a scheduled run's own wait --------------------------------------------


def test_a_schedules_wait_may_be_longer_than_the_desks_and_is_answered_in_it():
    from dvara.gate import put
    from dvara.patience import Patience

    desk = AskDesk(timeout=0.05)   # the door's own deadline: far too short

    async def go():
        wait = Patience(scheduled=5.0)
        deciding = asyncio.create_task(put(desk, request(read_only=False), actor="owner",
                                           agent="ops", thread="t", patience=wait))
        while not desk.pending():
            await asyncio.sleep(0)
        await asyncio.sleep(0.2)                       # past the desk's deadline
        desk.answer(desk.pending()[0].id, actor="owner", approve=True)
        return await deciding, wait

    approved, wait = asyncio.run(go())
    assert approved and wait.lapsed == [] and 0 < wait.scheduled < 5


def test_a_question_that_outwaits_its_schedule_lapses_never_held_and_is_named():
    from dvara.gate import put
    from dvara.patience import Patience

    desk = AskDesk(timeout=10, on_timeout="hold")   # the owner holds silences...
    wanted = PermissionRequest(
        tool_name="mcp__sparsh__confirm", arguments={"hold": "h1"}, read_only=False,
        summary="Do this on the phone?\nOn the phone emulator-5554: tap button "
                '"Send SMS" in com.google.android.apps.messaging')
    wait = Patience(scheduled=0.1)
    approved = asyncio.run(put(desk, wanted, actor="owner", agent="ops", thread="t",
                               patience=wait))
    assert approved is False                         # ...but a schedule's lapses
    assert "within the wait the person set for this schedule" in wanted.reason
    assert wait.lapsed == ['mcp__sparsh__confirm: On the phone emulator-5554: tap button '
                           '"Send SMS" in com.google.android.apps.messaging']
    again = request(read_only=False)                 # nothing left: not even asked
    assert asyncio.run(put(desk, again, actor="owner", agent="ops", thread="t",
                           patience=wait)) is False
    assert desk.pending() == [] and len(wait.lapsed) == 2

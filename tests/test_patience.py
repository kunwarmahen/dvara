"""Bias: a day's limit on waiting that punishes more than the waiting.

A person who has been kept on the hook long enough today should stop
being asked. That is the whole feature, and there are three ways to get
it wrong that are worse than not having it:

* stop the calls nobody was going to ask about -- the read-only ones,
  the ones a standing rule allows -- so an agent cannot even read a file
  until midnight because its person was slow;
* let the last question of the day wait the desk's full deadline anyway,
  and refuse it with a sentence about silence when it was the day that
  ran out;
* keep a figure the next turn cannot see, so the limit resets every turn.

Plus the ordinary one: an owner's typo meaning "no limit".
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime

import pytest
from yantra import (REFUSED_OUT_OF_TIME, REFUSED_TIMEOUT, PermissionRequest,
                    adecide, denial_text)

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.errors import ConfigProblem
from dvara.gate import Policy
from dvara.patience import Patience, remaining_today
from dvara.rules import Rule, RuleBook
from dvara.runs import SCHEMA, Run, RunStore

from tests.conftest import says
from tests.test_what_decided_it import answer_each, scribe, two_calls


def request(*, read_only: bool = False, tool: str = "write_file"):
    return PermissionRequest(tool_name=tool, arguments={"path": "a.txt"},
                             summary="write a.txt", read_only=read_only)


def gate(desk, patience, *, rules=None):
    policy = Policy(mode="ask", rules=rules or RuleBook())
    return policy.gate("ask", actor_mode="ask", desk=desk, actor="owner",
                       agent="scribe", thread="t", patience=patience)


# ---- the roster -------------------------------------------------------------

def test_an_actor_may_carry_a_days_waiting():
    book = ActorBook.from_dict({"actor": {"guest": {"max_wait_per_day": 300}}})
    assert book.get("guest").max_wait_per_day == 300.0


@pytest.mark.parametrize("value", [0, -5, "300", True])
def test_a_limit_that_is_not_a_positive_number_is_an_error(value):
    with pytest.raises(ConfigProblem, match="max_wait_per_day"):
        ActorBook.from_dict({"actor": {"guest": {"max_wait_per_day": value}}})


# ---- only what would have been asked ----------------------------------------

def test_a_spent_day_refuses_a_question_without_putting_it():
    desk = AskDesk(timeout=5)
    wanted = request()
    verdict = asyncio.run(adecide(gate(desk, Patience(left=0.0)), wanted))
    assert verdict is False
    assert wanted.code == REFUSED_OUT_OF_TIME
    assert "nobody was asked" in denial_text(wanted)
    assert "comes back at 00:00 UTC" in denial_text(wanted)
    assert desk.pending() == []


def test_a_spent_day_still_lets_the_agent_read():
    """The failure this is built around: Yantra's per-turn wrapper refuses
    everything once its allowance is gone; a DAY must not."""
    verdict = asyncio.run(adecide(gate(AskDesk(timeout=5), Patience(0.0)),
                                  request(read_only=True, tool="read_file")))
    assert verdict is True


def test_a_spent_day_still_honours_a_standing_yes():
    rules = RuleBook([Rule(tool="write_file", verdict="allow")])
    verdict = asyncio.run(adecide(
        gate(AskDesk(timeout=5), Patience(0.0), rules=rules), request()))
    assert verdict is True


# ---- what is left is the deadline --------------------------------------------

def test_what_is_left_of_the_day_shortens_the_question():
    desk = AskDesk(timeout=30)
    wanted = request()
    patience = Patience(left=0.05)
    started = asyncio.run(_timed(adecide(gate(desk, patience), wanted)))
    assert started < 5                       # not the desk's thirty seconds
    assert wanted.code == REFUSED_TIMEOUT
    assert "left of today's allowance" in denial_text(wanted)
    assert patience.spent_out


def test_the_desk_deadline_is_never_lengthened():
    desk = AskDesk(timeout=0.05)
    answer = asyncio.run(desk.put(actor="owner", agent="a", thread="t",
                                  tool="bash", summary="s", timeout=999))
    assert "0.05 seconds" in answer.reason


def test_an_answered_question_costs_what_it_waited():
    desk = AskDesk(timeout=5)
    patience = Patience(left=100.0)

    async def go():
        deciding = asyncio.create_task(adecide(gate(desk, patience),
                                               request()))
        await answer_each(desk, [(True, "terminal")])
        return await deciding

    assert asyncio.run(go()) is True
    assert 0 < patience.waited < 5
    assert patience.left == pytest.approx(100.0 - patience.waited)


async def _timed(coro):
    loop = asyncio.get_running_loop()
    start = loop.time()
    await coro
    return loop.time() - start


# ---- the ledger ----------------------------------------------------------------

def test_the_day_is_summed_from_the_runs(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    now = datetime.now(UTC)
    for waited in (40.0, 2.5, None):
        store.record(Run(actor="guest", agent="a", thread="t", message="m",
                         started_at=now, waited_seconds=waited))
    assert store.waited_since("guest", now.replace(hour=0, minute=0)) == 42.5
    assert remaining_today(60.0, 42.5) == 17.5
    assert remaining_today(None, 42.5) is None
    store.close()


def test_an_older_store_gains_the_column_and_keeps_its_rows(tmp_path):
    path = tmp_path / "runs.sqlite3"
    older = SCHEMA.replace("agent_version TEXT,", "agent_version TEXT").replace(
        "\n    waited_seconds REAL           -- how long it waited on a person",
        "")
    assert older != SCHEMA
    db = sqlite3.connect(path)
    db.executescript(older)
    db.close()
    store = RunStore(path)                   # migrates
    store.record(Run(actor="g", agent="a", thread="t", message="m",
                     started_at=datetime.now(UTC), waited_seconds=3.0))
    assert store.recent()[0].waited_seconds == 3.0
    store.close()


def test_a_turn_writes_what_it_waited_and_the_next_turn_sees_it(
        make_service, agents_root):
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    actors = ActorBook.from_dict({"actor": {"owner": {
        "permissions": "ask", "max_wait_per_day": 0.2}}})
    service = make_service([two_calls(), says("done."), two_calls(),
                            says("done.")], asks=desk, actors=actors)

    async def first():
        # Nobody answers: the first question uses the whole day, and the
        # second is refused without being put.
        return await service.deliver(actor="owner", agent="scribe",
                                     thread="t", text="write both")

    asyncio.run(first())
    run = service.runs.recent(limit=1)[0]
    assert run.waited_seconds == pytest.approx(0.2, abs=0.1)
    assert [step.refusal for step in run.tools] == [REFUSED_TIMEOUT,
                                                    REFUSED_OUT_OF_TIME]

    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="again"))
    second = service.runs.recent(limit=1)[0]
    assert [step.refusal for step in second.tools] == [REFUSED_OUT_OF_TIME] * 2
    assert second.waited_seconds == 0.0
    assert second.stop_reason == "end_turn"  # the turn ran; only asks stopped

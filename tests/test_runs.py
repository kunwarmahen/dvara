"""Bias: a store that only remembers the turns that went well.

The rows that matter most are the ones nobody wanted, and the query that
runs before every single turn is the daily spend. So: failures are
recorded, unpriced runs are not quietly worth $0.00, and the day window
does not accidentally include yesterday.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from yantra import Usage

from dvara.money import day_start
from dvara.runs import Run, RunStore


@pytest.fixture
def store(tmp_path) -> RunStore:
    store = RunStore(tmp_path / "runs.sqlite3")
    yield store
    store.close()


def run(actor="mahen", *, cost=0.01, when=None, reason="end_turn",
        agent="greeter") -> Run:
    return Run(actor=actor, agent=agent, thread="t", message="hi",
               started_at=when or datetime.now(UTC), reply="hello",
               model="test-model", usage=Usage(10, 5, 0, 0),
               cost_usd=cost, stop_reason=reason)


def test_a_recorded_run_comes_back_whole(store):
    store.record(run())
    got = store.recent()[0]
    assert (got.actor, got.agent, got.message, got.reply) == \
        ("mahen", "greeter", "hi", "hello")
    assert got.usage.input_tokens == 10
    assert got.ok


def test_a_failed_turn_is_recorded_too(store):
    store.record(run(reason="over_budget", cost=0.02))
    got = store.recent()[0]
    assert not got.ok
    assert got.stop_reason == "over_budget"


def test_todays_spend_excludes_yesterdays(store):
    yesterday = datetime.now(UTC) - timedelta(days=1)
    store.record(run(when=yesterday, cost=5.00))
    store.record(run(cost=0.25))
    assert store.spent_since("mahen", day_start()) == pytest.approx(0.25)


def test_one_actors_spend_is_not_anothers(store):
    store.record(run("mahen", cost=1.00))
    store.record(run("guest", cost=0.10))
    assert store.spent_since("guest", day_start()) == pytest.approx(0.10)


def test_an_unpriced_run_contributes_tokens_but_no_dollars(store):
    # Rendering an unknown price as $0.00 teaches an owner the wrong
    # instinct about what their service costs.
    store.record(run(cost=None))
    assert store.recent()[0].cost_usd is None
    assert store.spent_since("mahen", day_start()) == 0.0


def test_recent_is_newest_first_and_filterable(store):
    store.record(run(agent="greeter", when=datetime.now(UTC) - timedelta(minutes=5)))
    store.record(run(agent="researcher"))
    assert [r.agent for r in store.recent()] == ["researcher", "greeter"]
    assert [r.agent for r in store.recent(agent="greeter")] == ["greeter"]


def test_history_survives_the_process_that_wrote_it(tmp_path):
    path = tmp_path / "runs.sqlite3"
    first = RunStore(path)
    first.record(run())
    first.close()
    second = RunStore(path)
    try:
        assert len(second.recent()) == 1
    finally:
        second.close()

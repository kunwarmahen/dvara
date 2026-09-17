"""Bias: "over budget" with no idea whose budget.

Composition is three lines of arithmetic; the failure worth testing is
everything around it -- a minimum that forgets its owner, an allowance
that goes negative, a day boundary computed in the local timezone of
whichever machine happened to be running.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dvara.money import (
    Ceiling,
    compose,
    day_start,
    next_reset,
    receipt,
    remaining_today,
)


def test_no_ceilings_anywhere_means_no_ceiling():
    assert compose(package=None, actor_turn=None,
                   remaining_today=None) == Ceiling(None, None)


def test_the_lowest_ceiling_wins_and_remembers_whose_it_was():
    got = compose(package=0.50, actor_turn=0.02, remaining_today=1.00)
    assert (got.amount, got.whose) == (0.02, "actor")


def test_an_exhausted_allowance_beats_a_generous_package():
    got = compose(package=0.50, actor_turn=None, remaining_today=0.0)
    assert (got.amount, got.whose) == (0.0, "today")


def test_a_tie_names_the_ceiling_a_person_can_do_something_about():
    # All three at $0.25: "your allowance resets at midnight" is a fact
    # someone can act on; "the package says 0.25" is trivia about
    # somebody else's file.
    got = compose(package=0.25, actor_turn=0.25, remaining_today=0.25)
    assert got.whose == "today"


def test_an_allowance_never_goes_negative():
    assert remaining_today(1.00, spent=1.75) == 0.0


def test_an_unset_allowance_is_not_a_ceiling_of_zero():
    assert remaining_today(None, spent=99.0) is None


@pytest.mark.parametrize("hour", [0, 5, 23])
def test_the_day_starts_at_midnight_utc_wherever_the_service_runs(hour):
    now = datetime(2026, 9, 15, hour, 30, tzinfo=UTC)
    assert day_start(now) == datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
    assert next_reset(now) == day_start(now) + timedelta(days=1)


def test_a_naive_local_datetime_still_lands_in_a_utc_day():
    aware = datetime(2026, 9, 15, 3, 0, tzinfo=UTC)
    assert day_start(aware).tzinfo == UTC


# ---- one line under an answer ----------------------------------------------

def test_no_receipt_asked_for_is_no_line():
    assert receipt(None, cost_usd=0.0031, free=False) is None


def test_the_owner_gets_what_it_cost():
    assert receipt("cost", cost_usd=0.0031, free=False) == "$0.0031"


def test_a_person_on_an_allowance_gets_what_is_left():
    """The figure somebody acts on, not the one they would do sums on."""
    assert receipt("remaining", cost_usd=0.02, free=False,
                   remaining=0.08) == "$0.0800 left today"


@pytest.mark.parametrize("kind", ["cost", "remaining"])
def test_a_service_that_bills_nothing_says_nothing_about_money(kind):
    # Under a local model every turn is $0.0000 and no allowance can
    # move. A footer under every answer forever, metering nothing.
    assert receipt(kind, cost_usd=0.0, free=True, remaining=0.10) is None


def test_an_unpriced_turn_says_so_rather_than_rounding_to_zero():
    # The one case where silence is dangerous: an owner asking for a
    # receipt is asking to watch a bill, and $0.00 is a guess wearing a
    # number's clothes.
    assert receipt("cost", cost_usd=None, free=False) == "unpriced"


def test_a_spent_allowance_still_renders_a_number():
    assert receipt("remaining", cost_usd=0.1, free=False,
                   remaining=0.0) == "$0.0000 left today"

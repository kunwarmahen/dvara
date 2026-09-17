"""Two ceilings, one meter.

The handoff contract said: package ceiling ∧ actor ceiling, lower wins,
and the reply says which one stopped it. Made concrete there are three
numbers, and one of them is not a ceiling at all:

    package   spec.max_usd_per_turn     what the author thinks a task costs
    actor     actor.max_usd_per_turn    what the owner lets this person spend
    today     max_usd_per_day - spent   what is LEFT of an allowance

THE DECISION THAT SHAPES THIS MODULE IS A REFUSAL: dvara does not build a
second meter. It takes the minimum of whichever ceilings are set, hands
that one number to Yantra's existing ``Budget``, and gets the entire
apparatus that already exists for free -- the mid-turn stop, the warning
at 80%, and the shared meter that stops a sub-agent clearing its parent's
spend. A daily allowance is therefore enforced by a per-turn ceiling that
shrinks as the day is spent, which is a strange sentence and a correct
design: every extra meter is another place the arithmetic can disagree
with itself, and the first place it would disagree is sub-agents.

The other half of the job is remembering WHOSE number won. "Over budget"
tells a person nothing they wanted to know; "your daily allowance had
$0.12 left" tells them what happened and when it comes back.

``receipt`` at the end is the same instinct applied to the turns that did
NOT stop: one short line under an answer, for the people whose roster
entry asked for one. Two things decide what it says.

**A SERVICE THAT BILLS NOTHING SAYS NOTHING ABOUT MONEY.** Under a local
model every turn costs $0.0000 and no allowance can ever move, so a
receipt would be a meter that is not metering -- a line under every
answer, forever, teaching its reader something they already know. Yantra
draws that state as an empty bar labelled "free" (its note 43) and this
does not, which is a real divergence and not an oversight: a bar is
ambient and costs nothing to keep on screen, where a chat footer is a
line appended to every message anybody ever receives.

**UNPRICED IS SAID, NOT ROUNDED.** A hosted model with no list price is
the one case where silence would be dangerous, because an owner asking
for a receipt is asking to watch a bill. $0.00 would be a guess wearing a
number's clothes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

#: Tie-break order when two ceilings are equal. The most INFORMATIVE owner
#: wins, not the smallest or the first: "your allowance resets at midnight"
#: is a fact a person can act on, where "the package says $0.25" is trivia
#: about somebody else's file.
PRECEDENCE = ("today", "actor", "package")


@dataclass(frozen=True)
class Ceiling:
    """The one number a turn runs under, and whose it was."""

    amount: float | None
    whose: str | None

    @property
    def unlimited(self) -> bool:
        return self.amount is None

    def describe(self) -> str:
        if self.amount is None:
            return "no ceiling"
        return f"${self.amount:.2f} ({self.whose})"


def compose(*, package: float | None, actor_turn: float | None,
            remaining_today: float | None) -> Ceiling:
    """The lowest ceiling in force, and its owner. All-None means no ceiling."""
    candidates = {"package": package, "actor": actor_turn, "today": remaining_today}
    live = {k: v for k, v in candidates.items() if v is not None}
    if not live:
        return Ceiling(None, None)
    lowest = min(live.values())
    for owner in PRECEDENCE:
        if owner in live and live[owner] == lowest:
            return Ceiling(lowest, owner)
    raise AssertionError("unreachable: a minimum that belongs to nobody")


def day_start(now: datetime | None = None) -> datetime:
    """Midnight UTC of the current day.

    A UTC calendar day rather than a rolling 24 hours, because the person
    this cuts off needs a time they can plan around. "It comes back at
    midnight UTC" is an answer; "it comes back as your oldest spend from
    yesterday rolls off" is a shrug with arithmetic in it.
    """
    now = now or datetime.now(UTC)
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def next_reset(now: datetime | None = None) -> datetime:
    """When the allowance comes back. Said out loud in every refusal."""
    return day_start(now) + timedelta(days=1)


def remaining_today(limit: float | None, spent: float) -> float | None:
    """What is left of a daily allowance, floored at zero. None when unset."""
    if limit is None:
        return None
    return max(0.0, limit - spent)


# ---- one line under an answer ----------------------------------------------


def receipt(kind: str | None, *, cost_usd: float | None, free: bool,
            remaining: float | None = None) -> str | None:
    """The line that follows one answer, or None for no line at all.

    ``kind`` is the actor's own ``receipt`` key; None is the default and
    the quiet one. ``free`` is whether this turn's provider bills at all
    -- see the module docstring on why that silences both kinds rather
    than only the first.

    ``remaining`` is what is left of the allowance AFTER this turn, which
    is deliberately not the number ``compose`` was given at the start of
    it. The figure a person acts on is what they have now, and it is
    worth one more query to have it be the same figure the NEXT turn will
    be judged against -- a receipt that could disagree with the gate is
    worse than no receipt.
    """
    if kind is None or free:
        return None
    if kind == "cost":
        if cost_usd is None:
            return "unpriced"
        return f"${cost_usd:.4f}"
    if kind == "remaining":
        if remaining is None:
            return None
        return f"${remaining:.4f} left today"
    return None

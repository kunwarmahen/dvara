"""A day's worth of being asked.

``money.py`` answers "how much may this person spend today". This is the
other allowance a service owes somebody it puts questions to: how long
may it keep them on the hook today. Yantra drew the line at a turn --
``with_wait_budget`` spends down a turn's allowance of waiting, and "this
person may be asked for five minutes a day" was left as a service's job,
because it needs a store and an identity (Yantra's note 51). This service
has both.

    [actor.guest]
    max_wait_per_day = 300    # seconds of waiting on this person, a day

WHAT IS COUNTED IS TIME A TURN SPENT WAITING, not questions. An answer
that comes back in two seconds cost the person two seconds; a question
they never saw cost the full deadline -- and that second case is the one
this exists for. A person who has gone to bed stops being asked once
their silence has used the day up, instead of collecting a question
every few minutes until morning. A count of questions would treat the
two-second yes and the unanswered ping as the same thing.

NO SECOND GATE, THE SAME AS MONEY. Every question is put in one place
(``gate.put``), after the rung and the rules have already decided that a
person is needed. So the allowance is checked THERE and nowhere else: a
read-only call, a call a standing rule allowed, and a call ``yolo`` runs
are never touched by it. Yantra's per-turn wrapper refuses everything
once its allowance is gone, which is right for a turn and wrong for a
day -- an agent that cannot read a file until midnight because its
person was slow to answer is a punishment, not a limit.

WHAT IS LEFT BECOMES THE QUESTION'S DEADLINE, capped by the desk's own.
Ten seconds left today and a thirty-second ask timeout: this question
waits ten, and its refusal says the day ran out rather than that the
person was silent for thirty.

The ledger is the runs table: each turn records how long it waited
(``Run.waited_seconds``), and what is left is the limit minus the day's
sum -- read before every turn, midnight UTC to midnight UTC, exactly as
``money.py`` reads dollars. Two turns for one person running at once can
both start with the same figure; the dollar allowance has the same
window, and closing it for either needs a reservation this service does
not keep.
"""

from __future__ import annotations

from datetime import datetime

from dvara import money


class Patience:
    """One turn's share of a person's waiting, and the tally of what it
    actually waited. One per turn; the gate writes, the Run reads."""

    def __init__(self, left: float | None = None) -> None:
        #: Seconds of waiting this person has left today, or None when
        #: their roster entry sets no daily limit.
        self.left = left
        #: What this turn has waited so far -- recorded for every turn,
        #: limited or not, so a limit added tomorrow has a history.
        self.waited = 0.0

    @property
    def spent_out(self) -> bool:
        return self.left is not None and self.left <= 0

    def deadline(self, desk_timeout: float) -> float:
        """How long the next question may wait: the desk's own deadline,
        or what is left of today, whichever is shorter."""
        if self.left is None:
            return desk_timeout
        return min(desk_timeout, self.left)

    def spend(self, seconds: float) -> None:
        self.waited += seconds
        if self.left is not None:
            self.left = max(0.0, self.left - seconds)


def remaining_today(limit: float | None, waited: float) -> float | None:
    """Seconds of waiting left today, floored at zero. None when unset."""
    if limit is None:
        return None
    return max(0.0, limit - waited)


def spent_out(tool: str, now: datetime | None = None) -> str:
    """The refusal when nobody is asked because the day is used up.

    Says NOBODY WAS ASKED, because the model's right move is different
    from after a silence: waiting and retrying will not help until the
    reset, and the sentence names when that is.
    """
    return (f"{tool} was denied: nobody was asked. The person this "
            f"conversation would ask has been kept waiting on questions for "
            f"as long as this service allows in one day; that comes back at "
            f"{money.next_reset(now):%H:%M UTC}. Carry on with what you can "
            f"reach, and say what you would have needed approved.")


def ran_out(tool: str, seconds: float, now: datetime | None = None) -> str:
    """The refusal when a question was asked and the day ran out under it."""
    return (f"{tool} was denied: nobody answered in the "
            f"{seconds:.0f} second(s) left of today's allowance for waiting "
            f"on this person, which comes back at "
            f"{money.next_reset(now):%H:%M UTC}. This is silence, not a "
            f"refusal.")

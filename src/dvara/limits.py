"""A person's limits that are not money: hours, turns, and who says yes.

Money and waiting already had a ceiling each (money.py, patience.py).
A household with children in it needs three more, and none of them is a
number of dollars:

    [actor.kid]
    hours             = "07:00-21:00"   # when their agents answer
    max_turns_per_day = 40              # messages a day, not dollars
    approver          = "owner"         # who is asked before a change

HOURS BOUND EVERYTHING DONE FOR THEM, SCHEDULES TOO. A schedule is the
easiest way round a bedtime there is: "every night at 2" made at 8 pm.
So the hours are checked at the start of every turn that is theirs, typed
or scheduled, on this machine's own clock (the local time zone, which
Sarathi sets for its containers). A window may run past midnight
("22:00-06:00", a night worker's), which is the one subtle line here.

TURNS COUNT WHAT THEY SENT. A turn they started that reached the agent
-- not a refusal, not a look back at /new, not a schedule's run -- is one
of the day's. Schedules are left out because nobody typed them: a minder
that checks a page every hour would otherwise use up a child's day by
lunchtime and then refuse the child. The day is money.py's day (UTC), so
the two allowances reset together.

THE QUESTION GOES TO THE APPROVER, NOT TO THEM. Their rung (gate.py)
still decides whether a call is a question at all; ``approver`` decides
whom it is put to. ``ForApproval`` is the desk with that one difference:
the question is put to the approver, on the approver's channels, says
whose agent is asking, and silence refuses rather than holds (a held turn
can be taken up only by the person it belongs to, and the person who
could answer it is somebody else). A spend, or a change after the turn
read outside text, asks on every call (Yantra's always_ask), so those
always reach the approver too -- which is the point of naming one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

#: ``"07:00-21:00"``: two 24-hour clock times, start then end.
_HOURS = re.compile(r"^\s*([01]?\d|2[0-3]):([0-5]\d)\s*-\s*([01]?\d|2[0-3]):([0-5]\d)\s*$")


@dataclass(frozen=True)
class Hours:
    """When a person's agents answer, in minutes after local midnight."""

    start: int
    end: int

    @classmethod
    def parse(cls, text: str) -> Hours:
        """``"07:00-21:00"``, or ValueError with the words to fix it."""
        match = _HOURS.match(text or "") if isinstance(text, str) else None
        if match is None:
            raise ValueError(f'hours must look like "07:00-21:00" (got {text!r})')
        h1, m1, h2, m2 = (int(g) for g in match.groups())
        start, end = h1 * 60 + m1, h2 * 60 + m2
        if start == end:
            raise ValueError(f"hours start and end at the same time ({text!r}); "
                             "leave hours out for every hour of the day")
        return cls(start, end)

    def __str__(self) -> str:
        return f"{_clock(self.start)}-{_clock(self.end)}"

    def open_at(self, now: datetime) -> bool:
        minute = now.hour * 60 + now.minute
        if self.start < self.end:
            return self.start <= minute < self.end
        return minute >= self.start or minute < self.end    # past midnight

    def closed(self, now: datetime | None = None) -> str | None:
        """The sentence for a turn outside the hours; None inside them."""
        now = now or datetime.now().astimezone()
        if self.open_at(now):
            return None
        return (f"I'm not answering now -- your hours here are {self}. "
                f"Ask again after {_clock(self.start)}.")


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def turns_spent(limit: int | None, used: int) -> str | None:
    """The sentence for a day's turns used up; None while some are left."""
    if limit is None or used < limit:
        return None
    return (f"That's all {limit} messages for today. They come back at midnight "
            "UTC; ask whoever looks after this for more if it can't wait.")


class ForApproval:
    """The ask desk, with questions put to somebody other than the person.

    Everything but ``put`` is the desk's own (``on_timeout`` aside): the
    deadline, the routes, the answering. ``put`` changes three things and
    nothing else -- who is asked, where, and a summary that says for whom.
    """

    def __init__(self, desk, *, approver: str, reach, person: str) -> None:
        self._desk = desk
        self.approver = approver
        self.reach = tuple(reach)
        self.person = person
        #: never "hold": the person can't take up a hold the approver owes
        self.on_timeout = "deny"

    def __getattr__(self, name: str):
        return getattr(self._desk, name)

    async def put(self, *, actor: str, summary: str, reach=(), **rest):
        return await self._desk.put(actor=self.approver, reach=self.reach,
                                    summary=f"For {self.person}: {summary}", **rest)

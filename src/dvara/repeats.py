"""The same ask, day after day: offered as a schedule, never pushed.

People ask their agent the same thing at the same time of day -- the
guest room's temperature every evening, the portfolio every morning --
and type it each time, because nothing noticed. Making a schedule was
always possible (``/schedules``, or asking the agent), but only for
someone who thought of it.

    /repeats             what I noticed you ask again and again
    /repeats yes 1       make it a schedule, at the time you usually ask
    /repeats no 1        not that one, and never offered again

THREE DIFFERENT DAYS, NOT THREE TIMES. Asking twice in a minute is a
retry, not a habit. A request counts when it was typed (never a
schedule's or a watch's run) and answered, and the habit is the same
ask on ``DAYS`` different days within ``WITHIN``.

THE SAME ASK IN DIFFERENT WORDS. "what's the guest room temp" and
"guest room temperature?" are one ask. Words are compared after the
small ones are dropped and endings trimmed, and two asks are the same
when most of their words are (``SAME``). No model judges it: a model
asked whether two sentences match says yes to far too much, and the
cost of a missed habit is only an offer not made.

AN OFFER IS A LINE, NOT A QUESTION. When the habit is found, one line
goes under that answer, and the offer waits in ``<state>/repeats.json``
until ``/repeats yes`` or ``no``. Nothing is held open waiting for it
(the house's rule: offers wait in a tray, never a dialog). It is offered
once; turned down, it never comes back for that ask.

AT THE TIME THEY ASK. The schedule's time is the middle of the times
they asked, rounded to five minutes, on their clock; on weekdays only
when every ask was on a weekday. The words are their latest. The
schedule is Samay's, sent to them through this door as them, so it
answers exactly as their typed ask did.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from dvara.runs import Run

WORDS = ("/repeats",)
FILE = "repeats.json"
#: Different days the same ask must come on to be a habit.
DAYS = 3
#: How far back a habit is looked for.
WITHIN = timedelta(days=30)
#: The share of words two asks must have in common to be the same ask.
SAME = 0.6
#: Asks waiting for an answer, per person; the oldest go first.
WAITING = 10
#: Asks turned down, per person.
DECLINED = 100

_STOP = frozenset("""a an the and or but if of to in on at for from by with about as is
are was were be been am do does did can could would should will shall may might
me my mine you your i we our us it its this that these those what whats which who
whom how when where why please tell show give get find let lets now today just
again any some there here""".split())
_TOKEN = re.compile(r"[a-z0-9]+")


def word_of(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in WORDS


def marks(text: str) -> frozenset[str]:
    """The words that make an ask what it is: small ones out, endings off."""
    out = set()
    for token in _TOKEN.findall((text or "").lower()):
        if token in _STOP or len(token) < 3:
            continue
        for end in ("ing", "ed", "es", "s"):
            if token.endswith(end) and len(token) - len(end) >= 3:
                token = token[: -len(end)]
                break
        out.add(token[:4])          # "temperature", "temp": one word
    return frozenset(out)


def same(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= SAME


@dataclass
class Repeat:
    """One habit found: the ask in their latest words, when they ask it."""

    words: str
    agent: str
    at: str                       # "HH:MM", their clock
    weekdays: bool                # every ask was Mon-Fri
    days: int                     # different days it was asked on
    marks: list[str] = field(default_factory=list)

    def when(self) -> str:
        return f"at {self.at}" + (" on weekdays" if self.weekdays else "")

    def said(self) -> str:
        return (f"\"{self.words}\" — asked on {self.days} days, around {self.at}"
                + (" on weekdays" if self.weekdays else ""))


def _typed(run: Run) -> bool:
    return (not run.unattended and run.stop_reason == "end_turn"
            and not (run.message or "").lstrip().startswith("/"))


def habit(message: str, agent: str, runs: list[Run], now: datetime) -> Repeat | None:
    """The habit this message is the latest of, or None.

    ``runs`` are the person's, newest first, NOT including this message's
    own turn; ``now`` is on their clock."""
    mine = marks(message)
    if len(mine) < 2:                  # "thanks", "hi": no habit to find
        return None
    since = now - WITHIN
    asks = [(now, message)]
    for run in runs:
        when = run.started_at.astimezone(now.tzinfo)
        if when < since or run.agent != agent or not _typed(run):
            continue
        if same(mine, marks(run.message)):
            asks.append((when, run.message))
    days = {when.date() for when, _ in asks}
    if len(days) < DAYS:
        return None
    # one ask per day (the first): a retry later the same day isn't the habit's time
    first = {}
    for when, _ in sorted(asks, key=lambda pair: pair[0]):
        first.setdefault(when.date(), when)
    minutes = sorted(w.hour * 60 + w.minute for w in first.values())
    middle = minutes[len(minutes) // 2]
    middle = min(23 * 60 + 55, int(round(middle / 5.0)) * 5)
    return Repeat(words=" ".join(message.split())[:200], agent=agent,
                  at=f"{middle // 60:02d}:{middle % 60:02d}",
                  weekdays=all(w.weekday() < 5 for w in first.values()),
                  days=len(days), marks=sorted(mine))


class Offers:
    """What's waiting for each person's yes, and what they turned down."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def waiting(self, actor: str) -> list[Repeat]:
        rows = (self._load().get(actor) or {}).get("waiting") or []
        return [Repeat(**row) for row in rows if isinstance(row, dict)]

    def known(self, actor: str, found: Repeat) -> bool:
        """Offered already, or turned down: either way, not offered again."""
        theirs = self._load().get(actor) or {}
        seen = [frozenset(r.get("marks") or []) for r in theirs.get("waiting") or []]
        seen += [frozenset(m) for m in theirs.get("declined") or []]
        mine = frozenset(found.marks)
        return any(same(mine, other) for other in seen)

    def offer(self, actor: str, found: Repeat) -> int:
        """Put it on their list; returns its number there."""
        data = self._load()
        theirs = data.setdefault(actor, {"waiting": [], "declined": []})
        theirs["waiting"] = (theirs.get("waiting") or [])[-(WAITING - 1):] + [asdict(found)]
        self._save(data)
        return len(theirs["waiting"])

    def take(self, actor: str, n: int, *, decline: bool) -> Repeat | None:
        data = self._load()
        theirs = data.get(actor) or {}
        waiting = theirs.get("waiting") or []
        if not 1 <= n <= len(waiting):
            return None
        row = waiting.pop(n - 1)
        if decline:
            theirs["declined"] = ((theirs.get("declined") or []) + [row.get("marks") or []]
                                  )[-DECLINED:]
        data[actor] = theirs
        self._save(data)
        return Repeat(**row)


def hint(found: Repeat, number: int) -> str:
    """The one line under the answer."""
    return (f"_You've asked this on {found.days} days, around {found.at}"
            f"{' on weekdays' if found.weekdays else ''}. /repeats yes {number} makes it "
            f"a schedule; /repeats no {number} and I won't offer it again._")


def listing(waiting: list[Repeat]) -> str:
    if not waiting:
        return ("Nothing I've noticed you ask again and again. When a question comes "
                f"on {DAYS} different days, I'll offer to schedule it.")
    lines = ["What you ask again and again:"]
    lines += [f"{n}. {r.said()}" for n, r in enumerate(waiting, 1)]
    lines.append("/repeats yes N makes one a schedule at that time; /repeats no N, "
                 "never offered again.")
    return "\n".join(lines)


def pick(text: str) -> tuple[str, int] | str | None:
    """("yes"|"no", N) for ``/repeats yes 2``; None for ``/repeats``; words otherwise."""
    rest = text.strip().split()[1:]
    if not rest:
        return None
    if len(rest) == 2 and rest[0].lower() in ("yes", "no") and rest[1].isdigit():
        return rest[0].lower(), int(rest[1])
    return "Send /repeats to see them, /repeats yes N to schedule one, /repeats no N."

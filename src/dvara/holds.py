"""Turns that stopped for an answer nobody gave, kept until somebody does.

Note 01 said "ask" with nobody present is a hang, and ``asks.py`` built
the version with somebody present: a question, a deadline, and silence
that denies. What that left was the person who comes back an hour later
to find the model saying nobody approved it, and has to ask again -- so
the model plans again, reads again, and asks for the same write a second
time. Yantra's note 88 built the half only an agent loop can build: a
turn that STOPS without an answer and CARRIES ON with one. This module is
the half it said belongs to a service: the queue.

**A HELD TURN IS A RECORD, WHERE A QUESTION WAS A PROMISE.** ``asks.py``
keeps pending questions in memory on purpose: a question is a coroutine
standing there waiting, no coroutine survives a restart, and a persisted
ask would outlive the only thing that could act on it. A held turn is the
opposite case. Nothing is standing there -- the turn has ENDED, and what
can act on it is the session checkpoint, which Yantra writes with the
hold inside it. So this is a table, and a restart is a non-event.

**THE CHECKPOINT IS THE TRUTH; THIS IS ITS INDEX.** What is waiting, and
what already ran beside it, lives in the session, and Yantra restores it
with the conversation. A row here says only who may answer, what to show
them, and where to find the turn. When the two disagree -- a newer
message set the hold aside, a conversation was cleared -- the session
wins, and the row is dropped the moment anybody tries to use it.

**THE SAME TWO CHECKS AS A QUESTION.** An id is unguessable, and
answering still requires naming the actor the turn ran as. A held turn is
a question that lasts a day instead of two minutes, which is more time
for an id to be forwarded, not less.

**AN ANSWER USES THE ROW UP BEFORE ANYTHING RUNS.** Resuming deletes the
row and then runs the calls. A crash in between loses the hold -- the
person is told nothing ran after it, and asks again -- where the other
order could run a shell command twice. The outbox made the same choice
for the same reason (``outbox.py``): AN AGENT TURN IS NOT IDEMPOTENT.

**IT EXPIRES.** A write approved a week late writes over whatever is at
that path now, and Yantra cannot check whether the world moved. The age
of a hold is shown with it; past ``keep_for`` it can no longer be
answered, and the next message in that conversation sets it aside.
Expiry is lazy -- a row is dropped when it is listed or used, not by a
timer -- because nothing is waiting on it to go.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dvara import patience
from dvara.errors import Refused

#: How long a held turn may wait for its answer. A day: long enough to
#: sleep on, short enough that an approval does not land on a world that
#: has moved on entirely. The owner sets it with ``--hold-for``.
DEFAULT_KEEP = 24 * 3600.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS holds (
    id        TEXT PRIMARY KEY,
    key       TEXT NOT NULL UNIQUE,   -- one held turn per conversation
    actor     TEXT NOT NULL,
    agent     TEXT NOT NULL,
    thread    TEXT NOT NULL,
    run_id    TEXT NOT NULL,          -- the Run that stopped
    held_at   TEXT NOT NULL,
    calls     TEXT NOT NULL           -- [[call_id, tool, summary], ...]
);
CREATE INDEX IF NOT EXISTS holds_actor ON holds (actor, held_at);
"""


@dataclass(frozen=True)
class Waiting:
    """One call a held turn is waiting on, as the person will see it."""

    call_id: str
    tool: str
    summary: str


@dataclass(frozen=True)
class Hold:
    """A turn that stopped for approval, and who may answer it."""

    id: str
    key: str
    actor: str
    agent: str
    thread: str
    run_id: str
    held_at: datetime
    calls: tuple[Waiting, ...]

    def age(self, now: datetime | None = None) -> float:
        return ((now or datetime.now(UTC)) - self.held_at).total_seconds()

    def as_dict(self, now: datetime | None = None) -> dict:
        """The wire shape, for ``GET /holds`` and a held ``/message``.

        The session key is left out: it is where the turn is filed, and
        nobody answering it needs to know that.
        """
        return {"id": self.id, "actor": self.actor, "agent": self.agent,
                "thread": self.thread, "run_id": self.run_id,
                "held_at": self.held_at.isoformat(timespec="seconds"),
                "age": round(self.age(now)),
                "calls": [{"id": c.call_id, "tool": c.tool,
                           "summary": c.summary} for c in self.calls]}


class NoSuchHold(Refused):
    """Nothing is waiting under that id -- answered, set aside, or expired."""


class NotYourHold(Refused):
    """Somebody tried to answer a turn that ran as somebody else."""

    def __init__(self, hold_id: str) -> None:
        super().__init__(f"held turn {hold_id} is not yours to answer")


class HoldBook:
    """Every held turn this service is keeping, one per conversation."""

    def __init__(self, path: Path, *, keep_for: float = DEFAULT_KEEP) -> None:
        if keep_for <= 0:
            raise ValueError(
                "a hold kept for zero seconds or less expires before anyone "
                "could answer it; to refuse on silence instead, leave "
                "on_timeout at deny")
        self.keep_for = float(keep_for)
        self.path = Path(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def keep(self, *, key: str, actor: str, agent: str, thread: str,
             run_id: str, held_at: datetime,
             calls: list[Waiting]) -> Hold:
        """File a held turn, replacing any older one for the conversation.

        REPLACING, NOT REFUSING. A conversation has one history, so it can
        hold one turn at a time; a second hold means the first was already
        set aside by the message that led to the second.
        """
        hold = Hold(id=secrets.token_urlsafe(16), key=key, actor=actor,
                    agent=agent, thread=thread, run_id=run_id,
                    held_at=held_at, calls=tuple(calls))
        with self._lock:
            self._db.execute("DELETE FROM holds WHERE key = ?", (key,))
            self._db.execute(
                "INSERT INTO holds (id, key, actor, agent, thread, run_id, "
                "held_at, calls) VALUES (?,?,?,?,?,?,?,?)",
                (hold.id, key, actor, agent, thread, run_id,
                 _stamp(held_at),
                 json.dumps([[c.call_id, c.tool, c.summary] for c in calls])))
            self._db.commit()
        return hold

    def get(self, hold_id: str) -> Hold | None:
        """One hold by id, expired or not -- the caller says which it was."""
        with self._lock:
            row = self._db.execute(f"SELECT {COLUMNS} FROM holds WHERE id = ?",
                                   (hold_id,)).fetchone()
        return _row_to_hold(row) if row else None

    def expired(self, hold: Hold, now: datetime | None = None) -> bool:
        return hold.age(now) > self.keep_for

    def pending(self, actor: str | None = None,
                now: datetime | None = None) -> list[Hold]:
        """Held turns that can still be answered, oldest first.

        The expired ones are dropped on the way past. Nothing was waiting
        on them to go, and a listing that showed a hold nobody may answer
        would be a button that can only fail.
        """
        where, params = ("WHERE actor = ?", (actor,)) if actor else ("", ())
        with self._lock:
            rows = self._db.execute(
                f"SELECT {COLUMNS} FROM holds {where} ORDER BY held_at",
                params).fetchall()
        holds = [_row_to_hold(row) for row in rows]
        for hold in holds:
            if self.expired(hold, now):
                self.drop(hold.id)
        return [hold for hold in holds if not self.expired(hold, now)]

    def drop(self, hold_id: str) -> bool:
        with self._lock:
            gone = self._db.execute("DELETE FROM holds WHERE id = ?",
                                    (hold_id,)).rowcount
            self._db.commit()
        return bool(gone)

    def drop_key(self, key: str) -> bool:
        """The conversation moved on; whatever it was holding is gone."""
        with self._lock:
            gone = self._db.execute("DELETE FROM holds WHERE key = ?",
                                    (key,)).rowcount
            self._db.commit()
        return bool(gone)


COLUMNS = "id, key, actor, agent, thread, run_id, held_at, calls"


def waiting_text(hold: Hold) -> str:
    """What a person reads when their turn stops: what is waiting, and
    that nothing past it has happened yet.

    How to answer is left to the channel. A chat has buttons, a terminal
    has a command, an HTTP caller has the id in the body; one sentence
    that tried to name all three would be wrong in two of them.
    """
    lines = [f"  {c.tool}: {c.summary}" for c in hold.calls]
    return ("Nobody answered in time, so this is waiting for your approval "
            "and nothing past it has run:\n" + "\n".join(lines) + "\n"
            "Answer it when you are back and the turn carries on from here.")


def age_text(hold: Hold, now: datetime | None = None) -> str:
    """"held 4m ago", and the warning that goes with a late approval."""
    return (f"held {patience.duration(hold.age(now))} ago. What you approve "
            f"runs against things as they are now, not as they were then.")


def _stamp(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).isoformat(timespec="seconds")


def _row_to_hold(row: tuple) -> Hold:
    try:
        calls = [Waiting(*map(str, c[:3])) for c in json.loads(row[7])
                 if isinstance(c, list) and len(c) >= 3]
    except ValueError:
        calls = []
    return Hold(id=row[0], key=row[1], actor=row[2], agent=row[3],
                thread=row[4], run_id=row[5],
                held_at=datetime.fromisoformat(row[6]), calls=tuple(calls))

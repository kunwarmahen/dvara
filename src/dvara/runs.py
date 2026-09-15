"""The Run record: every turn this service ran, including the ones it lost.

A script forgets. A service that forgets cannot answer the owner's first
question -- "what has this thing been doing?" -- and cannot answer the
three that come after it either. Three later features are all queries
over this one table, which is why it exists in the first slice rather
than the fourth:

* **Money over time.** A daily allowance is ``SUM(cost_usd)`` over a
  window, not a second meter (see ``money.py``).
* **The failure loop.** A red Run is a trace, and Yantra's
  ``case_from_trace`` turns a trace into an eval case in the package that
  produced it. The failure in production becomes the gate that stops it
  coming back.
* **An audit.** Who asked what, of which agent, and what it cost.

A RUN IS RECORDED EVEN WHEN THE TURN RAISED. The rows that matter most
are the ones nobody wanted, and a store that only remembers successes is
a store that is silent exactly when it is needed.

Cost is nullable and it means something specific. A model with no list
price contributes TOKENS but no DOLLARS -- Yantra's rule, kept here
rather than softened into a zero, because rendering an unknown as $0.00
quietly teaches an owner the wrong instinct about what their service
costs. ``spent_since`` sums what is priced and says so.

Its own SQLite file, next to the session store rather than inside it.
``SessionStore`` owns its schema and its connection; sharing a file to
save a dependency edge would make dvara's migrations Yantra's problem.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from yantra import Usage

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    actor        TEXT NOT NULL,
    agent        TEXT NOT NULL,
    thread       TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    ended_at     TEXT NOT NULL,
    message      TEXT NOT NULL,
    reply        TEXT NOT NULL,
    model        TEXT NOT NULL,
    input_tokens        INTEGER NOT NULL DEFAULT 0,
    output_tokens       INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
    cost_usd     REAL,            -- NULL: real tokens, no list price
    stop_reason  TEXT NOT NULL,
    detail       TEXT
);
-- The daily-allowance query, which runs before EVERY turn: one actor,
-- one time window. Without this index it is a table scan that grows for
-- as long as the service stays up.
CREATE INDEX IF NOT EXISTS runs_actor_started
    ON runs (actor, started_at);
"""


@dataclass
class Run:
    """One turn, from a person's message to the agent's last word."""

    actor: str
    agent: str
    thread: str
    message: str
    started_at: datetime
    ended_at: datetime | None = None
    reply: str = ""
    model: str = ""
    usage: Usage = field(default_factory=Usage)
    cost_usd: float | None = None
    stop_reason: str = "error"
    detail: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"


class RunStore:
    """Append-only history of what the service did."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False plus one lock, for the same reason
        # Yantra's SessionStore does it: the store is built on the main
        # thread and written from whatever thread the event loop is on.
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def record(self, run: Run) -> str:
        """Write one Run. Returns its id."""
        ended = run.ended_at or datetime.now(UTC)
        with self._lock:
            self._db.execute(
                "INSERT INTO runs (id, actor, agent, thread, started_at, "
                "ended_at, message, reply, model, input_tokens, "
                "output_tokens, cache_read_tokens, cache_write_tokens, "
                "cost_usd, stop_reason, detail) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run.id, run.actor, run.agent, run.thread,
                 _stamp(run.started_at), _stamp(ended),
                 run.message, run.reply, run.model,
                 run.usage.input_tokens, run.usage.output_tokens,
                 run.usage.cache_read_tokens, run.usage.cache_write_tokens,
                 run.cost_usd, run.stop_reason, run.detail),
            )
            self._db.commit()
        return run.id

    def spent_since(self, actor: str, since: datetime) -> float:
        """Dollars this actor has spent since ``since``, priced runs only."""
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM runs "
                "WHERE actor = ? AND started_at >= ?",
                (actor, _stamp(since)),
            ).fetchone()
        return float(row[0])

    def recent(self, *, actor: str | None = None, agent: str | None = None,
               limit: int = 20) -> list[Run]:
        """The last ``limit`` runs, newest first."""
        where, params = [], []
        if actor is not None:
            where.append("actor = ?")
            params.append(actor)
        if agent is not None:
            where.append("agent = ?")
            params.append(agent)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._lock:
            rows = self._db.execute(
                f"SELECT id, actor, agent, thread, started_at, ended_at, "
                f"message, reply, model, input_tokens, output_tokens, "
                f"cache_read_tokens, cache_write_tokens, cost_usd, "
                f"stop_reason, detail FROM runs {clause} "
                f"ORDER BY started_at DESC, rowid DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [_row_to_run(row) for row in rows]


def _stamp(when: datetime) -> str:
    """ISO-8601 in UTC, to the second.

    Stored as TEXT and compared as TEXT, which works only because every
    stamp is written in the same zone and the same width -- so the
    conversion happens HERE, once, rather than at each call site where
    somebody's naive local datetime would sort into the wrong day.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).isoformat(timespec="seconds")


def _row_to_run(row: tuple) -> Run:
    return Run(
        id=row[0], actor=row[1], agent=row[2], thread=row[3],
        started_at=datetime.fromisoformat(row[4]),
        ended_at=datetime.fromisoformat(row[5]),
        message=row[6], reply=row[7], model=row[8],
        usage=Usage(input_tokens=row[9], output_tokens=row[10],
                    cache_read_tokens=row[11], cache_write_tokens=row[12]),
        cost_usd=row[13], stop_reason=row[14], detail=row[15],
    )

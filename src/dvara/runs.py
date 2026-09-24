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

A row also remembers HOW the turn went, not only that it ended: the tools
it called, in order, and which of them the gate turned away. That is the
half note 04 was missing -- a case generated from a Run could assert that
a turn COMPLETES and nothing else, which is the weakest assertion in the
format and not the one anybody wanted.

NAMES, NOT ARGUMENTS. A tool name is a fact about the shape of a turn; a
tool's arguments are the turn's content, and the difference decides three
things at once. The case assertions take names (``required_tools``,
``forbidden_tools``), so arguments buy the feature that motivated this
exactly nothing. A row that grows with an argument is a row that can hold
a file, a key, or the contents of somebody's afternoon. And ``dvara
case`` prints a Run into a file an owner commits -- note 04 already
worried about the MESSAGE being somebody's own words, and arguments would
put a second and much larger body of text in the same place that nobody
typed. Whoever wants arguments wants a transcript, which is a different
feature with a different retention story.

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

import json
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
    detail       TEXT,
    -- How the turn went, as JSON, and both are nullable because every row
    -- written before this column existed has neither.
    tools        TEXT,            -- [["bash", "policy", "rule:58fbf4ad"], …]
    answered_from TEXT,           -- ["telegram"]; a summary of tools
    agent_version TEXT,           -- the package's own version, that turn
    waited_seconds REAL           -- how long it waited on a person
);
-- The daily-allowance query, which runs before EVERY turn: one actor,
-- one time window. Without this index it is a table scan that grows for
-- as long as the service stays up.
CREATE INDEX IF NOT EXISTS runs_actor_started
    ON runs (actor, started_at);
"""


#: Every column, in the order ``_row_to_run`` unpacks them. Written once
#: because two queries read rows and a third is coming: a SELECT that
#: drifted from that unpacking would not raise, it would quietly put the
#: reply in the model column.
COLUMNS = ("id, actor, agent, thread, started_at, ended_at, message, reply, "
           "model, input_tokens, output_tokens, cache_read_tokens, "
           "cache_write_tokens, cost_usd, stop_reason, detail, tools, "
           "answered_from, agent_version, waited_seconds")

#: Columns added after the first row was ever written, and the type each
#: one gets. ADDED, NEVER REBUILT: there is a runs.sqlite3 in somebody's
#: ~/dvara/state already, and a migration that drops and recreates a table
#: to add a column is a migration that loses the audit it exists to keep.
#: ``ALTER TABLE ADD COLUMN`` with no default is cheap and leaves the old
#: rows honest -- they have no trajectory, and NULL is what that means.
ADDED = (("tools", "TEXT"), ("answered_from", "TEXT"),
         ("agent_version", "TEXT"), ("waited_seconds", "REAL"))


@dataclass(frozen=True)
class ToolStep:
    """One tool call the loop reported, and whether it got to happen.

    ``refusal`` is the gate's own code (``policy``, ``user``, ``timeout``,
    ``unattended``) or None when the call ran -- Yantra's token rather
    than the sentence beside it, because a sentence written for a model is
    going to be reworded and a column that has to be grepped for English
    is a column nobody queries twice.

    A REFUSED CALL IS STILL A STEP. It is usually the most interesting one
    in the row: it is the moment the service did its job, and it is what
    an owner is looking for when they ask what an agent has been trying to
    do.
    """

    name: str
    refusal: str | None = None
    #: What settled this call: ``rule:<id>``, ``asked:<channel>``, or None
    #: for the ordinary case where the RUNG allowed it and nobody was
    #: consulted. Absent is most of them, and a field that said "nothing
    #: in particular" ninety times a day would be a field nobody reads.
    decided_by: str | None = None

    @property
    def ran(self) -> bool:
        return self.refusal is None

    @property
    def rule(self) -> str | None:
        """The id of the standing rule that settled this, if one did."""
        if self.decided_by and self.decided_by.startswith("rule:"):
            return self.decided_by[len("rule:"):]
        return None


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
    #: Every tool call the loop reported, in the order it reported them.
    #: Empty means a turn that called nothing; a row written before this
    #: column existed is empty too, and the two are not distinguishable
    #: on purpose -- inventing a third state for "we were not recording
    #: yet" would put a fact about this software into a row about an
    #: agent.
    tools: list[ToolStep] = field(default_factory=list)
    #: The doors this turn's questions were answered through. Empty when
    #: nothing was escalated, which is almost every turn. A SUMMARY of
    #: ``tools``, written from it rather than beside it, so the two
    #: cannot come to disagree.
    answered_from: list[str] = field(default_factory=list)
    #: The version the package declared when this turn built it -- or None
    #: for a package that declares none, and for every row written before
    #: this column existed. A package edited on disk takes effect on a
    #: live conversation's NEXT turn (which is desirable when you are
    #: fixing a prompt and alarming when you are not), and this is the
    #: only thing that makes it legible afterwards.
    agent_version: str | None = None
    #: Seconds this turn spent waiting on a person's answers (patience.py)
    #: -- the ledger a daily allowance of waiting is summed from. 0.0 for
    #: a turn that asked nothing; None on a row written before this was
    #: kept, which SUMs as nothing waited, and nothing was counted.
    waited_seconds: float | None = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"

    @property
    def ran_tools(self) -> list[str]:
        """Distinct names of the calls that actually happened, in order.

        What a regression case requires of the fixed agent (cases.py), and
        distinct because ``required_tools`` is a set question -- "did it
        use this?" -- and three identical entries would say nothing the
        first one did not.
        """
        return _distinct(step.name for step in self.tools if step.ran)

    @property
    def refused_tools(self) -> list[str]:
        """Distinct names of the calls the gate turned away, in order."""
        return _distinct(step.name for step in self.tools if not step.ran)

    @property
    def rules_used(self) -> list[str]:
        """Ids of the standing rules that settled a call in this turn."""
        return _distinct(step.rule for step in self.tools
                         if step.rule is not None)


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
        self._migrate()
        self._db.commit()

    def _migrate(self) -> None:
        """Bring a store written by an older version up to this schema.

        ``CREATE TABLE IF NOT EXISTS`` does nothing to a table that
        already exists, so a column added today is missing from every
        store created yesterday -- and the first INSERT would fail with
        "table runs has no column named tools", on somebody's running
        service, with no obvious cause. Adding what is absent is three
        lines and it runs once per process.

        ADD, NEVER REBUILD. The alternative -- create the new shape, copy,
        drop, rename -- is how an audit trail gets lost to a power cut
        halfway through. A column with no default costs nothing and leaves
        the existing rows saying exactly what is true of them: nothing was
        recorded, because nothing was recording.
        """
        have = {row[1] for row in
                self._db.execute("PRAGMA table_info(runs)").fetchall()}
        for column, kind in ADDED:
            if column not in have:
                self._db.execute(
                    f"ALTER TABLE runs ADD COLUMN {column} {kind}")

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
                "cost_usd, stop_reason, detail, tools, answered_from, "
                "agent_version, waited_seconds) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run.id, run.actor, run.agent, run.thread,
                 _stamp(run.started_at), _stamp(ended),
                 run.message, run.reply, run.model,
                 run.usage.input_tokens, run.usage.output_tokens,
                 run.usage.cache_read_tokens, run.usage.cache_write_tokens,
                 run.cost_usd, run.stop_reason, run.detail,
                 _dump([[step.name, step.refusal, step.decided_by]
                        for step in run.tools]),
                 _dump(list(run.answered_from)), run.agent_version,
                 run.waited_seconds),
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

    def waited_since(self, actor: str, since: datetime) -> float:
        """Seconds this actor has been kept waiting on questions since
        ``since`` (patience.py) -- the same query as ``spent_since``, on
        the other allowance."""
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(SUM(waited_seconds), 0.0) FROM runs "
                "WHERE actor = ? AND started_at >= ?",
                (actor, _stamp(since)),
            ).fetchone()
        return float(row[0])

    def get(self, run_id: str) -> Run | None:
        """One run by id, or None. A PREFIX is enough, as long as it picks
        out exactly one: the id a person has is the one printed at the end
        of a reply, and asking them to retype twelve hex characters to
        write a failure down is friction on the one path that most needs
        none. An ambiguous prefix matches nothing rather than guessing.
        """
        with self._lock:
            rows = self._db.execute(
                f"SELECT {COLUMNS} FROM runs WHERE id = ? OR id LIKE ? "
                f"LIMIT 2",
                (run_id, f"{run_id}%"),
            ).fetchall()
        if len(rows) != 1:
            return None
        return _row_to_run(rows[0])

    def rule_counts(self, since: datetime | None = None) -> dict[str, int]:
        """How many CALLS each standing rule has settled, by rule id.

        Counted over calls rather than over turns, because a rule that
        saved one question in a turn and a rule that saved nine did not do
        the same amount of work -- and "which standing yes is earning its
        place" is the question this exists for.

        Done in Python over the rows rather than in SQL, and that is a
        deliberate limit rather than an oversight: the trajectory is JSON
        in a TEXT column, so there is no index to use and a LIKE would
        match a rule id inside any other field. An owner with a year of
        runs and a slow answer wants a real schema for this, at which
        point the column is the thing to change.
        """
        counts: dict[str, int] = {}
        where, params = "", []
        if since is not None:
            where, params = "WHERE started_at >= ?", [_stamp(since)]
        with self._lock:
            rows = self._db.execute(
                f"SELECT tools FROM runs {where}", params).fetchall()
        for (raw,) in rows:
            for step in _load(raw):
                if isinstance(step, list) and len(step) > 2 and step[2]:
                    kind, _, name = str(step[2]).partition(":")
                    if kind == "rule" and name:
                        counts[name] = counts.get(name, 0) + 1
        return counts

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
                f"SELECT {COLUMNS} FROM runs {clause} "
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
        tools=[ToolStep(*step[:3]) for step in _load(row[16])
               if isinstance(step, list) and step],
        answered_from=list(_load(row[17])),
        agent_version=row[18],
        waited_seconds=row[19],
    )


def _distinct(names) -> list[str]:
    """Names in first-seen order, which is what a reader expects of a path."""
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen


def _dump(value: list) -> str | None:
    """JSON, or NULL for nothing at all.

    An empty list and a missing column both mean "no tools here", and
    writing ``"[]"`` for the first would spend a byte per row to record a
    distinction nothing downstream can use. NULL for both.
    """
    return json.dumps(value) if value else None


def _load(raw: str | None) -> list:
    """The list back, and never an exception into a query.

    A row written by hand, a file half-restored from a backup, a column
    somebody edited in a SQLite browser: all of those are reasons this can
    hold something that is not JSON, and none of them is a reason for
    ``dvara runs`` to stop working. A trajectory nobody can parse is a
    trajectory that is not there, which is a state every caller already
    handles.

    A row written before a step grew its third element unpacks as two,
    which is why the reader slices rather than destructures: an OLD row is
    a row with less to say, not a broken one.
    """
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except ValueError:
        return []
    return loaded if isinstance(loaded, list) else []

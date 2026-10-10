"""The web channel: a chat on a page, and a place answers wait.

Telegram was the one channel a person could talk on, and the one a
scheduled answer could reach them on. Without it, a schedule's answer
went nowhere (``Sent.nowhere``), and the only way to talk to an agent
behind this service was ``curl`` with the token. This is the channel a
page needs, and it is a channel like Telegram is one -- nothing in
``service.py`` decides anything differently because of it.

TWO JOBS, ONE RECORD. Each person has a list of lines: what they said
on the page, what their agent answered, and every notice sent to them
(a schedule's answer, a file a scheduled run sent). The page draws the
list; a notice "waits until they open the page" because it is a line
they have not scrolled to yet. Telegram's notices go out at once and are
gone; these are kept, so a person away for a week finds the week.

THE CHAT IS THE PAGE'S OWN CONVERSATION. Turns from here run under the
thread ``web:chat``, beside Telegram's ``telegram:<chat>`` -- a chat on
Telegram does not continue on the page, and the reverse. The person is
the same person on both: same allowance, rules, folder, sign-ins, and
one queue of questions. A question a page turn raises still goes to
their Telegram if they have one, and the page lists it too; the first
answer anywhere settles it, as it always did.

A TURN RUNS BEHIND THE REQUEST. A message is written down and its turn
started, and the request answers at once: a turn can take minutes, and
a page reloaded mid-turn must not lose the answer. The answer is a line
like any other, found by the next look. While a turn runs, ``busy``
says which agent is working.

KEPT ON DISK, AND CAPPED. One SQLite file next to ``runs.sqlite3``. The
newest ``KEEP_PER_PERSON`` lines a person has are kept; older ones go.

ON WHEN ASKED FOR. ``dvara serve --web`` turns it on, and then every
person on the roster has it, with no line in ``actors.toml``: the page
in front of it says who they are (a trusted caller naming an actor, as
every HTTP caller does). Without ``--web`` nothing is kept, and a person
with no channel is told about nowhere, as before.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from dvara.errors import Refused
from dvara.holds import NoSuchHold, NotYourHold

if TYPE_CHECKING:
    from dvara.service import Reply, Service

#: The channel's kind, in notices and in the thread a page turn runs in.
KIND = "web"
#: The page's one conversation per agent, as Telegram's is one per chat.
THREAD = f"{KIND}:chat"
#: Lines kept per person; the oldest go first.
KEEP_PER_PERSON = 2000
#: Lines one look hands over, at most.
PAGE = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS lines (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    actor   TEXT NOT NULL,
    at      TEXT NOT NULL,
    who     TEXT NOT NULL,     -- you | agent | notice
    agent   TEXT NOT NULL DEFAULT '',
    text    TEXT NOT NULL,
    extra   TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS lines_actor ON lines (actor, id);
"""


@dataclass(frozen=True)
class Line:
    id: int
    actor: str
    at: datetime
    who: str
    agent: str
    text: str
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        out = {"id": self.id, "at": self.at.isoformat(timespec="seconds"),
               "who": self.who, "agent": self.agent, "text": self.text}
        # file paths stay here: the page asks for a file by line and
        # number, never by a path on this machine
        files = self.extra.get("files") or []
        out["files"] = [Path(f).name for f in files]
        for name in ("receipt", "held", "stop_reason"):
            if self.extra.get(name):
                out[name] = self.extra[name]
        return out


class WebBook:
    """Every person's lines, on disk."""

    def __init__(self, path: Path, *, keep: int = KEEP_PER_PERSON) -> None:
        self.keep = keep
        self._lock = threading.Lock()
        self._db = sqlite3.connect(Path(path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def add(self, actor: str, who: str, text: str, *, agent: str = "",
            extra: dict | None = None) -> Line:
        at = datetime.now(UTC)
        extra = {k: v for k, v in (extra or {}).items() if v}
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO lines (actor, at, who, agent, text, extra) "
                "VALUES (?,?,?,?,?,?)",
                (actor, at.isoformat(timespec="seconds"), who, agent, text,
                 json.dumps(extra)))
            self._db.execute(
                "DELETE FROM lines WHERE actor = ? AND id <= ("
                "SELECT id FROM lines WHERE actor = ? ORDER BY id DESC "
                "LIMIT 1 OFFSET ?)", (actor, actor, self.keep))
            self._db.commit()
        return Line(id=int(cur.lastrowid), actor=actor, at=at, who=who,
                    agent=agent, text=text, extra=extra)

    def after(self, actor: str, after: int = 0, limit: int = PAGE) -> list[Line]:
        """A person's lines after ``after``, oldest first. ``after=0`` is
        the newest ``limit`` of them: a page opened fresh shows the end."""
        with self._lock:
            if after > 0:
                rows = self._db.execute(
                    "SELECT id, actor, at, who, agent, text, extra FROM lines "
                    "WHERE actor = ? AND id > ? ORDER BY id LIMIT ?",
                    (actor, after, limit)).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT id, actor, at, who, agent, text, extra FROM lines "
                    "WHERE actor = ? ORDER BY id DESC LIMIT ?",
                    (actor, limit)).fetchall()[::-1]
        return [_line(row) for row in rows]

    def get(self, actor: str, line_id: int) -> Line | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, actor, at, who, agent, text, extra FROM lines "
                "WHERE actor = ? AND id = ?", (actor, line_id)).fetchone()
        return _line(row) if row else None


def _line(row: tuple) -> Line:
    try:
        extra = json.loads(row[6])
    except ValueError:
        extra = {}
    return Line(id=row[0], actor=row[1], at=datetime.fromisoformat(row[2]),
                who=row[3], agent=row[4], text=row[5],
                extra=extra if isinstance(extra, dict) else {})


class WebChannel:
    """The page's side of a person's chat: say, look, answer."""

    def __init__(self, service: Service, book: WebBook) -> None:
        self.service = service
        self.book = book
        #: (actor, agent) with a turn running now.
        self._busy: set[tuple[str, str]] = set()
        self._jobs: set[asyncio.Task] = set()

    async def notice(self, address: str, text: str, file: Path | None = None) -> None:
        """A notice for ``address`` (the actor id): a line, kept."""
        self.book.add(address, "notice", text,
                      extra={"files": [str(file)] if file else []})

    # -- the person, on the page ---------------------------------------------

    def look(self, actor: str, after: int = 0) -> dict:
        """Everything the page shows, in one answer."""
        who = self.service.actors.get(actor)
        agents = [a for a in self.service.roster.names() if who.may_use(a)]
        asks = (self.service.asks.pending(actor)
                if self.service.asks is not None else [])
        return {"actor": actor, "agents": agents,
                "lines": [line.as_dict() for line in self.book.after(actor, after)],
                "busy": sorted(agent for (a, agent) in self._busy if a == actor),
                "asks": [ask.as_dict() for ask in asks],
                "holds": [hold.as_dict()
                          for hold in self.service.holds.pending(actor)]}

    def say(self, actor: str, agent: str, text: str) -> Line:
        """Write down what they said and start the turn behind it."""
        who = self.service.actors.get(actor)
        if not who.may_use(agent):
            raise Refused(f"you have no agent called {agent!r} here")
        if not text.strip():
            raise Refused("say something and I will answer it")
        line = self.book.add(actor, "you", text, agent=agent)
        self._start(actor, agent, self.service.deliver(
            actor=actor, agent=agent, thread=THREAD, text=text))
        return line

    def carry_on(self, hold_id: str, actor: str, answers: dict) -> None:
        """Answer a held turn from the page; what it comes to is a line.

        The two refusals that need no turn are raised here, before
        anything starts, so the page hears them as the request's answer.
        """
        hold = self.service.holds.get(hold_id)
        if hold is None or self.service.holds.expired(hold):
            raise NoSuchHold("nothing is waiting under that id any more")
        if hold.actor != actor:
            raise NotYourHold(hold_id)
        self._start(actor, hold.agent, self.service.resume(
            hold_id, answers=answers, actor=actor, door=KIND))

    def _start(self, actor: str, agent: str, turn) -> None:
        self._busy.add((actor, agent))

        async def run() -> None:
            try:
                reply = await turn
            except Refused as exc:
                self.book.add(actor, "agent", str(exc), agent=agent,
                              extra={"stop_reason": "refused"})
            except Exception as exc:     # never a turn that silently vanished
                self.book.add(actor, "agent", f"That went wrong: {exc}",
                              agent=agent, extra={"stop_reason": "error"})
            else:
                self.answered(actor, agent, reply)
            finally:
                self._busy.discard((actor, agent))

        job = asyncio.ensure_future(run())
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    def answered(self, actor: str, agent: str, reply: Reply) -> Line:
        return self.book.add(actor, "agent", reply.text, agent=agent, extra={
            "receipt": reply.receipt,
            "files": [str(f) for f in reply.files],
            "held": reply.held.id if reply.held else None,
            "stop_reason": reply.stop_reason if not reply.ok else None})

    def file(self, actor: str, line_id: int, n: int) -> Path | None:
        """A file a line carried, by line and number -- the path never
        leaves this process."""
        line = self.book.get(actor, line_id)
        files = (line.extra.get("files") or []) if line else []
        if not 0 <= n < len(files):
            return None
        path = Path(files[n])
        return path if path.is_file() else None

    async def aclose(self) -> None:
        for job in list(self._jobs):
            job.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await job
        self.book.close()

"""Replies that are owed, written down before anything can lose them.

Note 07 chose what a crash does to a message in flight, and chose right:
the Telegram offset is spent when a message is TAKEN, so a process that
dies mid-turn never runs that turn a second time. An agent turn is not
idempotent -- it spends somebody's allowance, and it may have run a tool
-- and the one participant who can safely repeat it is the person, by
sending the message again.

What that left was the person not knowing they should. A message that
was taken and never answered looks exactly like a turn that is slow, and
the only way to tell them apart was to wait. This module is the half of
the promise that survives a restart: not the turn, but the fact that
somebody is owed a reply.

**A TURN IS NEVER RUN AGAIN. TEXT MAY BE SENT AGAIN.** Those are the two
halves of a row. A row with no reply yet is a message the process took
and never answered; after a restart it becomes one plain sentence --
this was not answered, and it was not run again, so send it again if
you still want it. A row WITH a reply is an answer that was finished
and not fully delivered; after a restart the parts that had not gone
out are sent. Resending text is safe in a way re-running a turn is not.

**AT-LEAST-ONCE FOR TEXT, AND IT IS SAID OUT LOUD.** A part is marked
sent after Telegram accepts it, so a crash between the two sends that
part twice on the next boot. The other order loses a part instead, in
the middle of an answer, which is the truncation note 07 split replies
to avoid. A duplicated paragraph is visible and harmless. A missing one
is neither.

**THE ROW IS THE CHANNEL'S, NOT THE SERVICE'S.** It is keyed by the
agent a bot serves and the chat it answers in, both in the channel's own
terms, and nothing in ``service.py`` knows it exists. That is the same
line ``asks.py`` draws with a message id. A turn that arrives over HTTP
already has a caller holding the connection who sees it drop, so the
gap this closes is a chat app's.

Deliberately not durable across a lost disk, a second machine, or a
state directory somebody deleted. It is one small SQLite file next to
``runs.sqlite3``, and ``claim.py`` has already made sure that only one
process writes to it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS owed (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent     TEXT NOT NULL,
    chat      TEXT NOT NULL,
    sender    TEXT NOT NULL,
    taken_at  TEXT NOT NULL,
    asked     TEXT NOT NULL,
    parts     TEXT,
    sent      INTEGER NOT NULL DEFAULT 0
);
"""

#: How much of the person's own message is kept to remind them which one
#: went unanswered. Enough to recognise, not enough to be a second copy
#: of the conversation.
PREVIEW = 60


@dataclass(frozen=True)
class Owed:
    """One reply this process promised and had not finished delivering."""

    id: int
    agent: str
    chat: str
    #: Who sent the message, in the channel's own terms. Kept so a restart
    #: can ask the roster again before saying anything: a person taken off
    #: the list while the process was down gets silence, like any stranger.
    sender: str
    taken_at: datetime
    asked: str
    #: The reply, split exactly as it was going to be sent, or None when
    #: the turn never finished.
    parts: tuple[str, ...] | None
    #: How many of ``parts`` Telegram had accepted.
    sent: int

    @property
    def answered(self) -> bool:
        return self.parts is not None

    @property
    def unsent(self) -> tuple[str, ...]:
        return (self.parts or ())[self.sent:]


class Outbox:
    """What is owed to whom, per agent and chat."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # The same arrangement as RunStore: built on one thread, written
        # from whichever thread the event loop runs on.
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def took(self, *, agent: str, chat: str, sender: str, text: str) -> int:
        """A message was taken; its reply is now owed. Returns the row id."""
        asked = " ".join(text.split())
        if len(asked) > PREVIEW:
            asked = asked[:PREVIEW - 1].rstrip() + "…"
        return self._write(
            "INSERT INTO owed (agent, chat, sender, taken_at, asked) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent, str(chat), str(sender), _stamp(), asked))

    def answered(self, row: int, parts: list[str]) -> None:
        """The turn finished; this is what it said, split for sending."""
        self._write("UPDATE owed SET parts = ?, sent = 0 WHERE id = ?",
                    (json.dumps(parts), row))

    def sent(self, row: int, count: int) -> None:
        """The first ``count`` parts are delivered."""
        self._write("UPDATE owed SET sent = ? WHERE id = ?", (count, row))

    def settled(self, row: int) -> None:
        """Nothing more is owed on this row."""
        self._write("DELETE FROM owed WHERE id = ?", (row,))

    def owed(self, agent: str) -> list[Owed]:
        """What a previous run of this agent's channel left unfinished."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, agent, chat, sender, taken_at, asked, parts, "
                "sent FROM owed WHERE agent = ? ORDER BY id",
                (agent,)).fetchall()
        return [Owed(id=r[0], agent=r[1], chat=r[2], sender=r[3],
                     taken_at=datetime.fromisoformat(r[4]), asked=r[5],
                     parts=tuple(json.loads(r[6])) if r[6] is not None
                     else None,
                     sent=r[7]) for r in rows]

    def _write(self, sql: str, params: tuple) -> int:
        with self._lock:
            cursor = self._db.execute(sql, params)
            self._db.commit()
            return cursor.lastrowid or 0


def _stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

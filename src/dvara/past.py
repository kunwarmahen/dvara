"""Past conversations: kept when ``/new`` ends one, opened again by a word.

``/new`` let a conversation go for good (fresh.py), which was right for
the habit it was meant to break and wrong for everything else: "what did
we work out about the trip last week?" had nowhere to go but the
person's memory. Yantra's page has saved sessions; nothing here did.

    /chats          the conversations you've finished with this agent
    /chats 2        go back into that one

KEPT, NOT FORGOTTEN. ``/new`` now hands the conversation it ends to this
book first: its saved form exactly as Yantra wrote it, a title (its
first words), where it was (Telegram, the page) and when it ended. The
newest ``KEEP`` per person per agent are kept.

OPENING ONE SWAPS. The conversation you are in is kept the same way, and
the one you named becomes it, on the channel you asked from -- one begun
on Telegram can be carried on on the page. Nothing else moves: the
folder, the files, the schedules and the ledger never belonged to a
conversation. Like ``/new``, never under a turn still working on it.

WHAT YOU SEE IS THE CONVERSATION. The answer to ``/chats N`` ends with
its last few exchanges, so a phone shows where it was; a page gets the
whole of it (``transcript``: the person's words and the agent's answers,
never a tool's output) to draw in place.

THE PERSON'S WORDS, NOT THE MODEL'S, like ``/new`` and ``/files``:
answered here, never a turn, nothing spent.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

WORD = "/chats"
#: Conversations kept per person per agent; the oldest go first.
KEEP = 30
#: A title's length, at most.
TITLE = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS past (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    actor    TEXT NOT NULL,
    agent    TEXT NOT NULL,
    came     TEXT NOT NULL,
    title    TEXT NOT NULL,
    turns    INTEGER NOT NULL,
    ended    TEXT NOT NULL,
    payload  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS past_who ON past (actor, agent, id);
"""

CAME = {"telegram": "Telegram", "web": "the page", "http": "HTTP"}


def is_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() == WORD


def picked(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@dataclass(frozen=True)
class Past:
    id: int
    came: str
    title: str
    turns: int
    ended: datetime


def _texts(message: dict) -> str:
    return " ".join(b.get("text", "") for b in message.get("content") or []
                    if isinstance(b, dict) and b.get("kind") == "text")


def title_of(payload: dict) -> str:
    """Its first words: what the person first asked."""
    for message in payload.get("history") or []:
        if message.get("role") == "user":
            words = " ".join(_texts(message).split())
            if words:
                return words if len(words) <= TITLE else words[:TITLE - 1] + "…"
    return "(no words)"


def turns_of(payload: dict) -> int:
    """How many times the person wrote in it (not tool results)."""
    return sum(1 for m in payload.get("history") or []
               if m.get("role") == "user" and _texts(m).strip())


def last_answer(payload: dict) -> str:
    for message in reversed(payload.get("history") or []):
        if message.get("role") == "assistant" and _texts(message).strip():
            return " ".join(_texts(message).split())
    return ""


def came_of(thread: str) -> str:
    kind = thread.split(":", 1)[0] if ":" in thread else ""
    return CAME.get(kind, kind or "here")


class PastBook:
    def __init__(self, path: Path, *, keep: int = KEEP) -> None:
        self.keep = keep
        self._lock = threading.Lock()
        self._db = sqlite3.connect(Path(path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def keep_one(self, actor: str, agent: str, thread: str, payload: dict) -> None:
        """A finished conversation, kept; the oldest beyond ``keep`` go."""
        if not turns_of(payload):
            return               # nothing the person said: nothing to go back to
        with self._lock:
            self._db.execute(
                "INSERT INTO past (actor, agent, came, title, turns, ended, payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (actor, agent, came_of(thread), title_of(payload), turns_of(payload),
                 datetime.now(UTC).isoformat(timespec="seconds"), json.dumps(payload)))
            self._db.execute(
                "DELETE FROM past WHERE actor = ? AND agent = ? AND id NOT IN ("
                "SELECT id FROM past WHERE actor = ? AND agent = ? ORDER BY id DESC "
                "LIMIT ?)", (actor, agent, actor, agent, self.keep))
            self._db.commit()

    def listed(self, actor: str, agent: str) -> list[Past]:
        """Newest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, came, title, turns, ended FROM past WHERE actor = ? AND "
                "agent = ? ORDER BY id DESC", (actor, agent)).fetchall()
        return [Past(r[0], r[1], r[2], r[3], datetime.fromisoformat(r[4])) for r in rows]

    def take(self, actor: str, agent: str, past_id: int) -> dict | None:
        """The conversation, out of the book (it is about to be current)."""
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM past WHERE actor = ? AND agent = ? AND id = ?",
                (actor, agent, past_id)).fetchone()
            if row is None:
                return None
            self._db.execute("DELETE FROM past WHERE id = ?", (past_id,))
            self._db.commit()
        return json.loads(row[0])

    def forget_all(self, actor: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM past WHERE actor = ?", (actor,))
            self._db.commit()


def listing(agent: str, rows: list[Past]) -> str:
    if not rows:
        return (f"You have no earlier conversations with {agent}. When you send /new, "
                f"the one you end is kept here.")
    out = [f"Your earlier conversations with {agent}, newest first:"]
    for n, row in enumerate(rows, start=1):
        when = row.ended.astimezone().strftime("%a %-d %b %H:%M")
        out.append(f"{n}. {row.title} — {when}, on {row.came}, {row.turns} "
                   f"message{'s' if row.turns != 1 else ''}")
    out += ["", "Send /chats N to go back into one; this one is kept in its place."]
    return "\n".join(out)


#: Exchanges shown in the answer itself, and how long each line may be.
SHOWN = 4
LINE = 300


def transcript(payload: dict) -> list[dict]:
    """The person's words and the agent's answers, in order: what a page
    draws. A tool's output, and a turn's in-between text, never shows."""
    out: list[dict] = []
    for message in payload.get("history") or []:
        role = message.get("role")
        words = " ".join(_texts(message).split())
        if not words:
            continue                  # a tool's result, or a call with no words
        who = "you" if role == "user" else "agent" if role == "assistant" else None
        if who is None:
            continue
        if who == "agent" and out and out[-1]["who"] == "agent":
            out[-1] = {"who": "agent", "text": words}   # its last words, not its asides
        else:
            out.append({"who": who, "text": words})
    return out


def reopened(payload: dict, agent: str = "") -> str:
    lines = [f"Back in: {title_of(payload)}"]
    said = transcript(payload)[-SHOWN:]
    if said:
        lines += ["", "Where we left it:"]
        for row in said:
            text = row["text"] if len(row["text"]) <= LINE else row["text"][:LINE - 1] + "…"
            lines.append(f"{'You' if row['who'] == 'you' else agent or 'Agent'}: {text}")
    return "\n".join(lines)

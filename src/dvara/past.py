"""Past conversations: every one kept, found by its words, opened again.

``/new`` used to let a conversation go for good (fresh.py), which was
right for the habit it was meant to break and wrong for everything else:
"what did we work out about the trip last week?" had nowhere to go but
the person's memory. Then ``/new`` kept the conversation it ended, the
newest thirty -- and the one that was never ended with ``/new``, or the
thirty-first, was still gone.

    /chats                  every conversation with this agent, newest first
    /chats trip             only the ones that say "trip"
    /chats 2                go back into that one
    /chats delete 2         ask to delete it for good
    /chats export 2         that one as a file, to share
    /chats export 2 pdf     that one as a PDF (printed.py)
    /chats delete 2 sure    delete it for good

EVERY CONVERSATION, AS IT GOES. Each turn writes its conversation to the
person's own log (Yantra's ``history.ConversationLog``, the same one
its terminal and page keep) under the conversation's id -- when the
question comes in, at each step, and at its end, so a long job (a
flight search waiting on a yes at a kitchen puck) is in the list from
the moment it was asked. ``/new``
only starts a new id; there is nothing left to copy. A conversation cut
off by a restart is there, and so is the one nobody ended. A run a
schedule started is not a conversation and is not kept here; Samay's
logbook has it.

ONE FILE PER PERSON. ``past/<person>.sqlite`` holds a person's
conversations with every agent (each row's folder is the agent's name),
so one person's never shows to another by construction, not by a WHERE
clause, and a person who leaves can be removed by removing a file.

OPENING ONE JOINS THE CONVERSATION, NOT A COPY. The one you named
becomes the conversation here, on the channel you asked from -- one
begun on Telegram can be carried on on the page -- and its next turn
grows its own row. The one you were in is already kept. Nothing else
moves: the folder, the files, the schedules and the ledger never
belonged to a conversation. Like ``/new``, never under a turn still
working on it.

ONE CONVERSATION, SEVERAL CHATS. One still open on Telegram stays open
there too: both carry it on, and the next message on Telegram follows
what was said on the page. Each chat saves its own copy of where it is
(Yantra's sessions), so ``latest`` says which chat's copy is the row as
the log has it. Before a turn, a chat that is behind takes the row
again (``behind``, then ``caught_up``), and the turn holds the
conversation as well as its chat, so two chats never write it at once:
the second waits, as a second message on one chat does. A question one
chat was waiting on is set aside when another chat says something, the
rule a new message already follows on one chat. ``/new`` leaves only
the chat it was sent on.

SHARED AS A FILE. ``/chats export N`` writes that conversation as a
Markdown file (Yantra's ``export_markdown``: words, answers, the tools'
names, never their output) into the person's folder with that agent,
under ``shared/``, and it goes out with the answer: a document on
Telegram, a file on the page. ``/chats export N pdf`` makes it a PDF
instead, printed here by the browser already on this machine
(printed.py), for a phone that opens a PDF and not a Markdown file. A
page that wants it without a chat line asks ``GET /web/chats/ID/export``
(``?as=pdf`` for the PDF).

DELETED MEANS GONE, ASKED ONCE. A chat has no dialog, so ``/chats delete
N`` says which conversation that is and what to send to delete it; only
``/chats delete N sure`` does. The log deletes for good (Yantra's note
130). Not the conversation open here: its next turn would write it
again.

WHAT YOU SEE IS THE CONVERSATION. The answer to ``/chats N`` ends with
its last few exchanges, so a phone shows where it was; a page gets the
whole of it (``transcript``: the person's words and the agent's answers,
never a tool's output) to draw in place.

KEPT AS A TEST. ``/keep test [WORDS, ...]`` keeps the conversation open
here, and ``/chats test N [turn K] [WORDS, ...]`` one from the list (its
last turn, or turn K), as a test of
this agent (Yantra's kept_tests.py, its note 141): its last turn,
replayed by the night run with the tools answering from what they said
then -- nothing real runs -- and the words, comma-separated, what the
answer must say. Each person's tests are their own, in Yantra's tests
folder under ``people/<person>/<agent>/``, which the night run reads
with everyone else's. ``/tests`` lists them with how each did last time,
and ``/tests delete N`` takes one back.

THE PERSON'S WORDS, NOT THE MODEL'S, like ``/new`` and ``/files``:
answered here, never a turn, nothing spent.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

from yantra.history import (END, HIT, ConversationLog, Kept, export_markdown, export_name,
                            new_id, title_of)

WORD = "/chats"
#: Where a shared conversation's file is written, in the person's folder
#: with that agent (so ``/files`` lists it too).
SHARED = "shared"
#: Rows shown in a chat's list; a page asks for as many as it wants.
SHOWN_ROWS = 30

CURRENT = """
CREATE TABLE IF NOT EXISTS current (
    key           TEXT PRIMARY KEY,
    conversation  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS latest (
    conversation  TEXT PRIMARY KEY,
    key           TEXT NOT NULL
);
"""

CAME = {"telegram": "Telegram", "web": "the page", "http": "HTTP"}
#: A puck's thread (``vaani:kitchen``) is named by its puck. A row kept
#: before that says only "vaani", and is listed as "a puck".
PUCK = "vaani"


def is_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() == WORD


KEEP = "/keep"


def keep_test_words(text: str) -> str | None:
    """The words after ``/keep test``, or None when that isn't what was said."""
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 2 or parts[0].split("@")[0].lower() != KEEP or parts[1].lower() != "test":
        return None
    return parts[2] if len(parts) > 2 else ""


def test_pick(text: str) -> tuple[int, str] | None:
    """``/chats test N [WORDS]`` -> (N, words), or None."""
    if not is_word(text):
        return None
    parts = picked(text).split(maxsplit=2)
    if len(parts) >= 2 and parts[0].lower() == "test" and parts[1].isdigit():
        return int(parts[1]), parts[2] if len(parts) > 2 else ""
    return None


def turn_of(words: str) -> tuple[int | None, str]:
    """``turn K rest`` -> (K, rest); anything else is all words."""
    parts = words.split(maxsplit=2)
    if len(parts) >= 2 and parts[0].lower() == "turn" and parts[1].isdigit():
        return int(parts[1]), parts[2] if len(parts) > 2 else ""
    return None, words


TESTS = "/tests"


def is_tests(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() == TESTS


def tests_listing(agent: str, kept: list) -> str:
    """``/tests``: the person's kept tests of this agent, each with how it
    did on its last run."""
    if not kept:
        return (f"You haven't kept any conversation with {agent} as a test yet. "
                f"Right after an answer you checked, send /keep test and the words "
                f"it must say.")
    out = [f"Your kept tests of {agent}:"]
    for n, k in enumerate(kept, start=1):
        mark = {True: "passed", False: "failed", None: "not run yet"}[k.passed]
        out.append(f"{n}. {k.question[:80]} — {mark}"
                   + (f" (must say {', '.join(k.words)})" if k.words else ""))
        if k.passed is False and k.why:
            out.append(f"    {k.why[0][:200]}")
    out += ["", "Send /tests delete N to take one back (the conversation stays)."]
    return "\n".join(out)


def tested(case_id: str, title: str, used: list[str], words: list[str]) -> str:
    """What a chat says once one is kept as a test."""
    checks = []
    if used:
        checks.append(f"use {', '.join(used)} again")
    if words:
        checks.append(f"say {', '.join(words)}")
    checks.append("give the same facts as last time")
    return (f"Kept “{title}” as a test ({case_id}). Each time the tests run, I'm "
            f"asked it again with the tools answering from what they said then "
            f"(nothing real runs), and I must {', and '.join(checks)}.")


#: What ``/chats export N`` may be asked for as, after the number.
EXPORT_AS = {"pdf": "pdf", "md": "md", "markdown": "md"}


def export_pick(text: str) -> int | None:
    """The N of ``/chats export N [pdf]``, or None when that isn't what was said."""
    if not is_word(text):
        return None
    parts = picked(text).split()
    if (len(parts) in (2, 3) and parts[0].lower() == "export" and parts[1].isdigit()
            and (len(parts) == 2 or parts[2].lower() in EXPORT_AS)):
        return int(parts[1])
    return None


def export_as(text: str) -> str:
    """``pdf`` for ``/chats export N pdf`` (printed.py), else ``md``."""
    parts = picked(text).split()
    return EXPORT_AS.get(parts[2].lower(), "md") if len(parts) == 3 else "md"


def export_to(folder: Path, kept: dict, agent: str) -> Path:
    """``kept`` (``PastBook.read``) as a Markdown file in ``folder``; the
    same conversation shared again writes over its own earlier file."""
    folder.mkdir(parents=True, exist_ok=True)
    made = folder / export_name(kept)
    made.write_text(export_markdown(kept, agent=agent), encoding="utf-8")
    return made


def picked(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _texts(message: dict) -> str:
    return " ".join(b.get("text", "") for b in message.get("content") or []
                    if isinstance(b, dict) and b.get("kind") == "text")


def came_of_key(key: str) -> str:
    """Where a chat is, from its session key (``actor/agent/thread``)."""
    return came_of(unquote(key.rsplit("/", 1)[-1]))


def came_of(thread: str) -> str:
    kind, _, rest = thread.partition(":") if ":" in thread else ("", "", "")
    if kind == PUCK and rest:
        return f"the {rest} puck"
    return CAME.get(kind, kind or "here")


class PastBook:
    """Each person's log, and which conversation each chat is in now."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._logs: dict[str, ConversationLog] = {}
        self._db = sqlite3.connect(self.folder / "current.sqlite3",
                                   check_same_thread=False)
        self._db.executescript(CURRENT)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            for log in self._logs.values():
                log.close()
            self._logs.clear()
            self._db.close()

    def log(self, actor: str) -> ConversationLog:
        with self._lock:
            if actor not in self._logs:
                self._logs[actor] = ConversationLog(self._path(actor))
            return self._logs[actor]

    def _path(self, actor: str) -> Path:
        # quote leaves "." alone; a leading one is escaped too, so no
        # person's file is a dot-file or a step up (keys.py's reason).
        name = quote(actor, safe="")
        return self.folder / f"{'%2E' + name[1:] if name.startswith('.') else name}.sqlite"

    # ---- which conversation a chat is in --------------------------------------

    def current(self, key: str) -> str:
        """The id this chat's turns are written to; a new one if none."""
        with self._lock:
            row = self._db.execute("SELECT conversation FROM current WHERE key = ?",
                                   (key,)).fetchone()
            if row:
                return row[0]
            made = new_id()
            self._db.execute("INSERT INTO current (key, conversation) VALUES (?, ?)",
                             (key, made))
            self._db.commit()
            return made

    def _open_here(self, key: str) -> str | None:
        """The id this chat is in, without starting one."""
        with self._lock:
            row = self._db.execute("SELECT conversation FROM current WHERE key = ?",
                                   (key,)).fetchone()
        return row[0] if row else None

    def _mark_latest(self, key: str, conversation_id: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO latest (conversation, key) VALUES (?, ?) "
                "ON CONFLICT(conversation) DO UPDATE SET key = excluded.key",
                (conversation_id, key))
            self._db.commit()

    def behind(self, key: str) -> str | None:
        """The conversation this chat is in, when another chat wrote it
        since this one did: its copy must be taken again before a turn."""
        conversation = self._open_here(key)
        if conversation is None:
            return None
        with self._lock:
            row = self._db.execute("SELECT key FROM latest WHERE conversation = ?",
                                   (conversation,)).fetchone()
        return conversation if row is not None and row[0] != key else None

    def caught_up(self, key: str) -> None:
        """This chat's copy is the row again."""
        conversation = self._open_here(key)
        if conversation is not None:
            self._mark_latest(key, conversation)

    def _set_current(self, key: str, conversation_id: str | None) -> None:
        with self._lock:
            if conversation_id is None:
                self._db.execute("DELETE FROM current WHERE key = ?", (key,))
            else:
                self._db.execute(
                    "INSERT INTO current (key, conversation) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET conversation = excluded.conversation",
                    (key, conversation_id))
            self._db.commit()

    def open_on(self, actor: str, conversation_id: str) -> list[str]:
        """Where it is open right now: the chats (keys) of this person's
        whose turns are writing it."""
        prefix = quote(actor, safe="") + "/"
        with self._lock:
            return [r[0] for r in self._db.execute(
                "SELECT key FROM current WHERE conversation = ? AND substr(key, 1, ?) = ?",
                (conversation_id, len(prefix), prefix)).fetchall()]

    def open_ids(self, actor: str) -> set[str]:
        """Every conversation open in one of this person's chats now."""
        prefix = quote(actor, safe="") + "/"
        with self._lock:
            return {r[0] for r in self._db.execute(
                "SELECT conversation FROM current WHERE substr(key, 1, ?) = ?",
                (len(prefix), prefix)).fetchall()}

    def page_rows(self, actor: str, words: str = "") -> list[dict]:
        """The page's list: every agent's, each row saying which agent,
        whether it is open in a chat now (a page offers no delete there),
        and whether that chat is the page's own (``here``)."""
        prefix = quote(actor, safe="") + "/"
        with self._lock:
            keys = self._db.execute(
                "SELECT key, conversation FROM current WHERE substr(key, 1, ?) = ?",
                (len(prefix), prefix)).fetchall()
        open_now = {c for _, c in keys}
        here = {c for k, c in keys if came_of_key(k) == CAME["web"]}
        return [{**r.as_dict(), "agent": r.folder, "open": r.id in open_now,
                 "here": r.id in here}
                for r in self.listed(actor, None, words)]

    # ---- writing ---------------------------------------------------------------

    def kept(self, actor: str, agent: str, key: str, thread: str, payload: dict) -> None:
        """A turn's conversation, as it is now, into the person's log."""
        conversation = self.current(key)
        self.log(actor).keep(conversation, payload, road=came_of(thread), folder=agent)
        self._mark_latest(key, conversation)

    def ended(self, key: str) -> None:
        """``/new``: the next turn here starts a new conversation."""
        self._set_current(key, None)

    def opened(self, key: str, conversation_id: str) -> None:
        """``/chats N``: this chat's next turn grows that conversation,
        from the row just taken (so it is not behind)."""
        self._set_current(key, conversation_id)
        self._mark_latest(key, conversation_id)

    def delete(self, actor: str, conversation_id: str) -> bool:
        if not self.log(actor).delete(conversation_id):
            return False
        with self._lock:
            self._db.execute("DELETE FROM latest WHERE conversation = ?", (conversation_id,))
            self._db.commit()
        return True

    def rename(self, actor: str, conversation_id: str, title: str) -> bool:
        """The person's own title for it (an empty one: its first words)."""
        return self._path(actor).exists() and self.log(actor).rename(conversation_id, title)

    def pin(self, actor: str, conversation_id: str, pinned: bool = True) -> bool:
        return self._path(actor).exists() and self.log(actor).pin(conversation_id, pinned)

    def forget_all(self, actor: str) -> None:
        """A person removed: their file goes."""
        prefix = quote(actor, safe="") + "/"
        with self._lock:
            log = self._logs.pop(actor, None)
            self._db.execute("DELETE FROM latest WHERE substr(key, 1, ?) = ?",
                             (len(prefix), prefix))
            self._db.commit()
        if log is not None:
            log.close()
        with suppress(FileNotFoundError):
            self._path(actor).unlink()

    # ---- reading ---------------------------------------------------------------

    def listed(self, actor: str, agent: str | None = None, words: str = "",
               *, limit: int = 200) -> list[Kept]:
        """Newest first; ``agent`` None is every agent's."""
        if not self._path(actor).exists():
            return []
        return self.log(actor).listed(words, folder=agent, limit=limit)

    def payload(self, actor: str, conversation_id: str) -> dict | None:
        if not self._path(actor).exists():
            return None
        return self.log(actor).payload(conversation_id)

    def read(self, actor: str, conversation_id: str) -> dict | None:
        """One conversation for a page: its row, its entries (tools and
        all, as Yantra's reading view draws them) and its transcript."""
        if not self._path(actor).exists():
            return None
        log = self.log(actor)
        kept = log.read(conversation_id)
        if kept is None:
            return None
        payload = log.payload(conversation_id) or {}
        return {**kept, "transcript": transcript(payload)}

    # ---- what was kept before every conversation was -------------------------

    def bring_in(self, old: Path) -> int:
        """The book ``/new`` kept (past.sqlite3), moved into each person's
        log once, with when each one ended; the old file then goes.
        Returns how many came over."""
        if not old.exists():
            return 0
        db = sqlite3.connect(old)
        try:
            rows = db.execute("SELECT actor, agent, came, ended, payload FROM past "
                              "ORDER BY id").fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            db.close()
        for actor, agent, came, ended, payload in rows:
            self.log(actor).keep(new_id(), json.loads(payload), road=came,
                                 folder=agent, at=ended)
        old.unlink()
        return len(rows)


def listing(agent: str, rows: list[Kept], words: str = "", *,
            open_id: str | None = None, numbers: dict[str, int] | None = None) -> str:
    """The list a chat shows. ``numbers`` is each row's place in the
    whole list, when ``rows`` is a search's: ``/chats N`` counts that."""
    if not rows:
        if words:
            return (f"None of your conversations with {agent} say “{words}”. "
                    f"Send /chats to see them all.")
        return (f"You have no conversations with {agent} kept yet. Each one is "
                f"kept by itself as you talk.")
    head = (f"Your conversations with {agent} that say “{words}”, newest first:"
            if words else f"Your conversations with {agent}, newest first:")
    out = [head]
    for place, row in enumerate(rows[:SHOWN_ROWS], start=1):
        n = (numbers or {}).get(row.id, place)
        when = datetime.fromisoformat(row.updated_at).astimezone().strftime("%a %-d %b %H:%M")
        here = " (this one)" if row.id == open_id else ""
        pin = " (pinned)" if row.pinned else ""
        roads = " and ".join("a puck" if r == PUCK else r for r in row.roads or (row.road,))
        out.append(f"{n}. {row.title}{here}{pin} — {when}, on {roads}, {row.turns} "
                   f"message{'s' if row.turns != 1 else ''}")
        if row.snippet:
            snip = " ".join(row.snippet.replace(HIT, "*").replace(END, "*").split())
            out.append(f"    {snip}")
    if len(rows) > SHOWN_ROWS:
        out.append(f"… and {len(rows) - SHOWN_ROWS} older. Add a word to find one: "
                   f"/chats trip")
    out += ["", "Send /chats N to go back into one, /chats WORDS to find one, "
                "/chats test N to keep one as a test, /chats delete N to delete "
                "one for good."]
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
    lines = [f"Back in: {title_of(payload) or '(no words)'}"]
    said = transcript(payload)[-SHOWN:]
    if said:
        lines += ["", "Where we left it:"]
        for row in said:
            text = row["text"] if len(row["text"]) <= LINE else row["text"][:LINE - 1] + "…"
            lines.append(f"{'You' if row['who'] == 'you' else agent or 'Agent'}: {text}")
    return "\n".join(lines)

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
says which agent is working, and ``live`` shows it working (watch.py):
the answer so far and each step as a line. Live is kept in memory only
-- the answer line is the record; a restart mid-turn loses the view of
a turn that is lost anyway.

KEPT ON DISK, AND CAPPED. One SQLite file next to ``runs.sqlite3``. The
newest ``KEEP_PER_PERSON`` lines a person has are kept; older ones go.

AN ANSWER'S STEPS, BY ITS LINE. Each answer's line keeps its run's id,
and the page asks for what that turn did by the line, as it asks for a
file: the run id stays here, and a line opens only for its own person
(``steps``). Pictures are said as a count; the bytes stay in the run.

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

from dvara import spoken
from dvara.accounts import tap_label, taps
from dvara.attached import Attachment, safe_name
from dvara.errors import Refused
from dvara.holds import NoSuchHold, NotYourHold
from dvara.watch import Live

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
#: Answers read aloud for the page, under the state folder (spoken.py).
VOICE_CACHE = "voice-cache"

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
        for name in ("receipt", "held", "stop_reason", "offer", "taps", "sent",
                     "transcript", "heard", "speak"):
            if self.extra.get(name):
                out[name] = self.extra[name]
        # its turn can be read step by step (``steps``); asked for by line,
        # like a file, so the run's id stays here
        if self.extra.get("run"):
            out["steps"] = True
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
        #: What each of those turns has written and done so far.
        self._live: dict[tuple[str, str], Live] = {}
        self._jobs: set[asyncio.Task] = set()

    async def notice(self, address: str, text: str, file: Path | None = None,
                     extra: dict | None = None) -> None:
        """A notice for ``address`` (the actor id): a line, kept. A skill
        offered rides on it (``offer``), for the page's buttons."""
        self.book.add(address, "notice", text,
                      extra={"files": [str(file)] if file else [],
                             "offer": (extra or {}).get("offer"),
                             # "always": it plays by itself on the page too
                             "speak": (extra or {}).get("speak")})

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
                "live": [{"agent": agent, **live.as_dict()}
                         for (a, agent), live in sorted(self._live.items()) if a == actor],
                "asks": [ask.as_dict() for ask in asks],
                "holds": [hold.as_dict()
                          for hold in self.service.holds.pending(actor)],
                # A lesson open with an agent (learning.py): what it's for
                # and how far it got, for the page's lesson bar.
                "lessons": self._lessons(actor, agents),
                # whether an answer can be read aloud here (spoken.py): the
                # page's play button, and why not when it can't
                "voice": spoken.can_speak() is None}

    def _lessons(self, actor: str, agents: list[str]) -> list[dict]:
        learning = getattr(self.service, "learning", None)
        if learning is None:
            return []
        out = []
        for agent in agents:
            lesson = learning.lesson(actor, agent)
            if lesson is not None:
                out.append({"agent": agent, **lesson.describe()})
        return out

    def say(self, actor: str, agent: str, text: str,
            attachments: list[Attachment] | None = None) -> Line:
        """Write down what they said and start the turn behind it. Files
        sent with it are named on their line (kept in their folder by
        the turn: attached.py)."""
        who = self.service.actors.get(actor)
        if not who.may_use(agent):
            raise Refused(f"you have no agent called {agent!r} here")
        if not text.strip() and not attachments:
            raise Refused("say something and I will answer it")
        sent = [safe_name(a.name) for a in attachments or []]
        line = self.book.add(actor, "you", text, agent=agent,
                             extra={"sent": sent})
        live = Live()
        self._start(actor, agent, self.service.deliver(
            actor=actor, agent=agent, thread=THREAD, text=text, came_by=KIND,
            watch=live, attachments=attachments or ()), live)
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
        live = Live()
        self._start(actor, hold.agent, self.service.resume(
            hold_id, answers=answers, actor=actor, door=KIND, watch=live), live)

    def _start(self, actor: str, agent: str, turn, live: Live | None = None) -> None:
        self._busy.add((actor, agent))
        if live is not None:
            self._live[(actor, agent)] = live

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
                self._live.pop((actor, agent), None)

        job = asyncio.ensure_future(run())
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    def answered(self, actor: str, agent: str, reply: Reply) -> Line:
        return self.book.add(actor, "agent", reply.text, agent=agent, extra={
            # the run, for its steps (``steps``); a word's answer has none
            "run": reply.run_id,
            "receipt": reply.receipt,
            "files": [str(f) for f in reply.files],
            "held": reply.held.id if reply.held else None,
            "stop_reason": reply.stop_reason if not reply.ok else None,
            "transcript": list(reply.transcript),
            "heard": reply.heard,
            # read aloud by itself when it arrives (spoken.py)
            "speak": reply.speak,
            # sign-in words it told them to send, as buttons (accounts.taps)
            "taps": None if reply.held else [{"word": w, "label": tap_label(w)}
                                             for w in taps(reply.text)]})

    def steps(self, actor: str, line_id: int) -> dict | None:
        """What an answer's own turn did, step by step (runsteps.py), by
        its line: the person's own run, whole, as on the owner's page for
        the owner's own. Pictures are said as a count -- the page shows
        them nowhere, and their bytes would be most of the answer. None
        when the line has no run, or the run isn't theirs."""
        from dvara import runsteps

        line = self.book.get(actor, line_id)
        run_id = (line.extra.get("run") or "") if line else ""
        run = self.service.runs.get(run_id) if run_id else None
        if run is None or run.actor != actor:
            return None
        view = runsteps.timeline(self.service.sessions, run)
        for step in view.get("steps") or []:
            step["pictures"] = [{"media_type": p.get("media_type")}
                                for p in step.get("pictures") or []]
        return view

    def file(self, actor: str, line_id: int, n: int) -> Path | None:
        """A file a line carried, by line and number -- the path never
        leaves this process."""
        line = self.book.get(actor, line_id)
        files = (line.extra.get("files") or []) if line else []
        if not 0 <= n < len(files):
            return None
        path = Path(files[n])
        return path if path.is_file() else None

    async def spoken(self, actor: str, line_id: int) -> Path | None:
        """An answer's line read aloud, made the first time it's asked
        for and kept beside the service's state (WAV: every browser plays
        it; made again if it's gone, so a backup leaves it out). None for
        a line that isn't an agent's answer."""
        line = self.book.get(actor, line_id)
        if line is None or line.who not in ("agent", "notice") or not line.text.strip():
            return None
        who = self.service.actors.get(actor)
        # in their voice, or one for the answer's language; named in the
        # file, so a voice changed since is made again
        voice = await asyncio.to_thread(
            spoken.pick, spoken.aloud(line.text),
            self.service.voices.voice(actor, who.voice))
        made = (Path(self.service.state) / VOICE_CACHE / actor
                / f"{line_id}-{voice.name}.wav")
        if made.is_file():
            return made
        return await asyncio.to_thread(spoken.make, line.text, made, voice=voice)

    async def aclose(self) -> None:
        for job in list(self._jobs):
            job.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await job
        self.book.close()

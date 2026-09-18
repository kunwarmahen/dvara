"""One process at a time in a state directory, and why that is the rule.

``dvara serve`` and ``dvara telegram`` over one ``--state`` used to be
"unsupported and unprevented", which is the worst of the three available
states. This module makes it prevented, and the argument for refusing
rather than for making it work is the whole of the module.

**THE SQLITE ERROR WAS THE SYMPTOM, NOT THE DISEASE.** Two writers
against one ``runs.sqlite3`` stall for five seconds and then fail with
"database is locked", which is visible, loud and easy to reach for a fix:
switch the journal to WAL, raise the busy timeout, and both processes
carry on. That fix would have been the worst possible outcome, because it
silences the one signal that something is wrong while leaving three
things broken that SQLite was never going to notice.

A SERVICE IS A PROCESS. Three of the four things that make this service
correct live in memory and cannot be shared by a directory:

* **The per-session lock.** ``Service`` holds one ``asyncio.Lock`` per
  ``(actor, agent, thread)`` so that two messages in one conversation
  serialize. Two processes have two sets of locks and neither knows about
  the other's -- so both rehydrate the same checkpoint, both run a turn
  against it, and both save. ``SessionStore`` appends versions, so
  nothing raises: one of those turns simply is not in the history any
  more. Silent, and found weeks later by a person wondering why their
  agent forgot something.
* **The ask desk.** Questions live in memory and die with the process
  (``asks.py``), so a question raised in the bot's process is invisible to
  ``GET /asks`` in the served one. A person would be asked on Telegram and
  find nothing to answer over HTTP -- which is precisely the split
  [note 05] refused to let an actor have.
* **The provider pool**, harmlessly: two pools to the same endpoint.

None of those is a locking problem, and none of them has a fix that is
three lines long. So the directory is claimed, and a second process says
so and stops.

## How, and what that does not cover

``fcntl.flock`` on a file in the state directory, held for the life of
the process. THE KERNEL RELEASES IT, which is the entire reason to prefer
this over a pid file: a service killed with SIGKILL, or one that panicked,
leaves no stale lock to reason about and no "is pid 4032 still the same
process?" heuristic to get wrong. The pid is written into the file
anyway, because it is what the error message needs.

What it does not cover, said plainly rather than implied:

* **Two machines over one network filesystem.** ``flock`` on NFS is
  advisory at best and a lie at worst. A state directory on a share is a
  thing this cannot protect, and clustering was never in this service.
* **Two different state directories.** Nothing here is stopped, and
  nothing should be: two dvaras with separate state are two services, and
  the only thing they contend for is the agent packages, which are read.
* **An embedder.** ``Service`` does not claim anything. A host that has
  composed this into their own process is not a second dvara, and a
  library that took a lock on import would be a library nobody can
  compose. The claim belongs to the COMMAND, which is the thing that
  knows it is a whole service.

A COMMAND THAT RUNS A TURN CLAIMS THE DIRECTORY; ONE THAT ONLY READS IT
DOES NOT. ``say``, ``serve`` and ``telegram`` take it. ``runs``, ``case``
and ``agents`` do not, because reading a ledger while the bot is
answering somebody is the most ordinary thing an owner does and a service
that blocked it would be a service whose own history you cannot look at.
"""

from __future__ import annotations

import fcntl
import os
from datetime import UTC, datetime
from pathlib import Path

from dvara.errors import ConfigProblem

#: The file whose lock IS the claim. In the state directory rather than a
#: run directory, because the thing being protected is this directory and
#: an owner who moves their state somewhere else has moved the claim with
#: it -- a lock in /var/run keyed by a path is a second thing to keep in
#: step.
LOCKFILE = "dvara.lock"


class Claim:
    """One process's hold on one state directory.

    Not a context manager by default, because the two callers that need
    it hold it for the life of the process and releasing it in a
    ``finally`` would be ceremony around something the kernel does anyway.
    ``release`` exists for tests and for a caller that wants to be tidy.
    """

    def __init__(self, state: Path) -> None:
        self.state = Path(state).expanduser()
        self.path = self.state / LOCKFILE
        self._handle = None

    def take(self, what: str) -> None:
        """Claim the directory, or refuse with who is already in it.

        ``what`` is the command doing the claiming, written into the file
        so the refusal can say "a telegram bot" rather than "another
        process" -- an owner with one terminal window and a systemd unit
        needs to know which of the two they are about to fight with.

        The file is opened and locked BEFORE anything is written to it,
        and truncated only once the lock is held. Writing first would let
        a second process blank the first one's pid on its way to being
        refused, which would leave the error message that comes after it
        describing nobody.
        """
        self.state.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+", encoding="utf-8")  # noqa: SIM115
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = _read(handle)
            handle.close()
            raise ConfigProblem(
                f"another dvara is already using {self.state}"
                f"{holder}. A service is a PROCESS, not a directory: the "
                f"lock that serializes two messages in one conversation, "
                f"and the questions waiting for you to answer them, both "
                f"live in memory and cannot be shared. Stop that one, give "
                f"this one its own --state, or run both jobs in one "
                f"process (dvara serve --telegram AGENT)."
            ) from None
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid {os.getpid()}\n{what}\n"
                     f"since {datetime.now(UTC).isoformat(timespec='seconds')}\n")
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        """Let go. The kernel would have, but a test should not have to die."""
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


def _read(handle) -> str:
    """Whatever the holder wrote about itself, as a clause or as nothing.

    Never raises, and never blocks. A lock file that is empty, truncated
    or full of something else is a lock that is still held -- the refusal
    above is decided by ``flock`` and this only decorates it.
    """
    try:
        handle.seek(0)
        lines = [line.strip() for line in handle.read().splitlines()
                 if line.strip()]
    except OSError:
        return ""
    if not lines:
        return ""
    pid = lines[0]
    what = f" running {lines[1]}" if len(lines) > 1 else ""
    return f" ({pid}{what})"

"""Folders a person locked, and the keys they opened them with, for a while.

A person with a folder of their own (note 19) may lock it with a
passphrase (Setu's ``setu lock``): every key in it sealed, their browser
sign-ins packed and sealed, nothing usable on the owner's disk without
the passphrase. This module is the door's half: it holds the key for a
person who unlocked, for as long as they said, and no longer.

    /lock              the first time: choose a passphrase (next message);
                       after that: lock now
    /unlock [days]     open it (next message is the passphrase); 7 days
                       unless they say, 30 at most

THE PASSPHRASE IS A MESSAGE THAT GOES NOWHERE. After ``/lock`` or
``/unlock`` the person's next message is the passphrase. It is handed to
``setu lock`` on its stdin and dropped: no agent sees it, no history,
no run, no outbox preview, and on Telegram the message itself is deleted
from the chat. A command sent instead cancels the wait.

THE KEY LIVES IN MEMORY, NOWHERE ELSE. What ``setu lock unlock`` prints
is held here, in this process, until the time they chose -- then the
folder's browser sign-ins are packed and sealed again, the key is
dropped, and they are told. It is never written down, so a restart locks
every folder: at start-up, any browser sign-in left unpacked by a crash
is sealed again (sealing needs no key), and a person finds out at their
next turn, where the agent says their accounts are locked and how they
open.

TOO MANY WRONG PASSPHRASES, AND IT STOPS ASKING. Five in an hour and
``/unlock`` is refused for the rest of that hour: someone holding
somebody's phone gets five guesses, not a script.

The honest limit (Setu's seal.py says it too): while a folder is open,
its key is in this process's memory, and the owner of the machine could
take it. Locked protects the folder at rest.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: How long an unlock lasts unless the person says, and at most.
DEFAULT_DAYS, MOST_DAYS = 7, 30
#: How long after /lock or /unlock the next message counts as the passphrase.
PASSPHRASE_WITHIN = 300.0
#: Wrong passphrases allowed in an hour before /unlock is refused.
TRIES, TRIES_WINDOW = 5, 3600.0
DAY = 86400.0


@dataclass
class _Open:
    key: str
    until: float
    home: Path
    timer: asyncio.TimerHandle | None = None


@dataclass
class _Expecting:
    what: str            # "set" | "unlock"
    days: int
    before: float


@dataclass
class KeyHolder:
    notify: Callable[[str, str], Awaitable[Any]]
    #: The setu program, asked when it is needed (``AccountDesk._program``).
    program: Callable[[], str | None] = lambda: None
    log: Callable[[str], None] = print
    _open: dict[str, _Open] = field(default_factory=dict)
    _expecting: dict[str, _Expecting] = field(default_factory=dict)
    _wrong: dict[str, list[float]] = field(default_factory=dict)

    # ---- what the rest of the door asks -------------------------------------

    def key_for(self, actor: str) -> str | None:
        held = self._open.get(actor)
        if held is None or time.time() >= held.until:
            return None
        return held.key

    def expects_passphrase(self, actor: str) -> bool:
        wait = self._expecting.get(actor)
        return wait is not None and time.monotonic() < wait.before

    # ---- the two words ----------------------------------------------------------

    async def lock(self, actor: str, program: str, home: Path) -> str:
        if not _is_locked(program, home):
            self._expecting[actor] = _Expecting("set", DEFAULT_DAYS,
                                                time.monotonic() + PASSPHRASE_WITHIN)
            return ("Send the passphrase you want as your next message: at least 8 "
                    "characters, a few words is easiest to remember. It goes to Setu "
                    "only, never to an agent, and I'll delete your message. Nobody can "
                    "get it back for you: if you forget it, your accounts have to be "
                    "connected again.")
        if self._open.get(actor) is None:
            return "Your accounts are locked already. /unlock opens them."
        await self.close(actor, why=None)
        return "Locked. /unlock opens them again."

    def unlock(self, actor: str, program: str, home: Path, rest: list[str]) -> str:
        if not _is_locked(program, home):
            return "Your accounts aren't locked. /lock locks them with a passphrase."
        if self._too_many(actor):
            return "Too many wrong passphrases. Try again in an hour."
        try:
            days = int(rest[0].rstrip("dD")) if rest else DEFAULT_DAYS
        except ValueError:
            return "Say it as /unlock or /unlock 3 (days, 30 at most)."
        days = max(1, min(days, MOST_DAYS))
        self._expecting[actor] = _Expecting("unlock", days,
                                            time.monotonic() + PASSPHRASE_WITHIN)
        return (f"Send your passphrase as your next message, and your accounts open for "
                f"{days} day{'s' if days != 1 else ''}. It goes to Setu only, and I'll "
                "delete your message.")

    def cancel(self, actor: str) -> None:
        self._expecting.pop(actor, None)

    async def passphrase(self, actor: str, program: str, home: Path, text: str) -> str:
        """The message after /lock or /unlock: to Setu, and then forgotten."""
        wait = self._expecting.pop(actor)
        phrase = text.strip()
        if wait.what == "set":
            code, out = await _setu(program, home, ["lock", "set", "--passphrase-stdin"],
                                    phrase)
            if code != 0:
                return f"Not locked: {out}. Send /lock to try again."
            self.log(f"dvara: {actor} locked their accounts with a passphrase")
        code, out = await _setu(program, home,
                                ["lock", "unlock", "--passphrase-stdin", "--json"], phrase)
        try:
            answer = json.loads(out)
        except ValueError:
            answer = {"error": out}
        if "key" not in answer:
            if wait.what == "unlock":
                self._wrong.setdefault(actor, []).append(time.monotonic())
            return f"That didn't open them: {answer.get('error')}. Send /unlock to try again."
        self._wrong.pop(actor, None)
        until = await self.hold(actor, home, answer["key"], wait.days)
        when = datetime.fromtimestamp(until, UTC).astimezone().strftime("%a %d %b, %H:%M")
        first = ("Locked with your passphrase. " if wait.what == "set" else "")
        return (f"{first}Your accounts are open until {when}, so your agents and "
                "schedules can use them; then they lock again by themselves. /lock locks "
                "them sooner.")

    # ---- holding and letting go ------------------------------------------------

    async def hold(self, actor: str, home: Path, key: str, days: int) -> float:
        await self.close(actor, why=None, seal=False)
        until = time.time() + days * DAY
        held = _Open(key=key, until=until, home=home)
        loop = asyncio.get_running_loop()
        held.timer = loop.call_later(
            days * DAY, lambda: asyncio.ensure_future(self.close(
                actor, why=f"Your accounts locked again: the {days} day"
                           f"{'s' if days != 1 else ''} you opened them for are up. "
                           "Send /unlock when you want them back.")))
        self._open[actor] = held
        return until

    async def close(self, actor: str, *, why: str | None, seal: bool = True) -> None:
        held = self._open.pop(actor, None)
        if held is None:
            return
        if held.timer is not None:
            held.timer.cancel()
        if seal:
            program = self.program()
            if program:
                code, out = await _setu(program, held.home, ["lock", "seal"], "")
                if code != 0:
                    self.log(f"dvara: could not seal {actor}'s browser sign-ins: {out}")
        if why:
            with contextlib.suppress(Exception):
                await self.notify(actor, why)

    async def aclose(self) -> None:
        for actor in list(self._open):
            await self.close(actor, why=None)

    def _too_many(self, actor: str) -> bool:
        recent = [t for t in self._wrong.get(actor, []) if time.monotonic() - t < TRIES_WINDOW]
        self._wrong[actor] = recent
        return len(recent) >= TRIES


def seal_loose(program: str | None, homes: Path, log: Callable[[str], None] = print) -> None:
    """At start-up: every locked folder's browser sign-ins sealed again --
    a crash while one was open must not leave them on disk."""
    if program is None or not homes.is_dir():
        return
    for home in sorted(p for p in homes.iterdir() if (p / "lock.json").exists()):
        done = subprocess.run([program, "lock", "seal", "--json"], capture_output=True,
                              text=True, env={**os.environ, "SETU_HOME": str(home)})
        try:
            sealed = json.loads(done.stdout).get("sealed") or []
        except ValueError:
            sealed = []
        if sealed:
            log(f"dvara: sealed {home.name}'s browser sign-ins left open: "
                f"{', '.join(sealed)}")


def _is_locked(program: str, home: Path) -> bool:
    done = subprocess.run([program, "lock", "status", "--json"], capture_output=True,
                          text=True, env={**os.environ, "SETU_HOME": str(home)})
    try:
        return bool(json.loads(done.stdout).get("locked"))
    except ValueError:
        return False


async def _setu(program: str, home: Path, args: list[str], stdin: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        program, *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env={**os.environ, "SETU_HOME": str(home)})
    out, err = await proc.communicate((stdin + "\n").encode() if stdin else b"")
    said = (out.decode() or err.decode()).strip()
    return proc.returncode or 0, said.removeprefix("error: ")

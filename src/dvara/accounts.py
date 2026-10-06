"""Accounts from the chat: a person connects, lists and disconnects their own.

Note 19 gave each person a Setu folder of their own and signed them in
at the machine, because Google's sign-in comes back to ``127.0.0.1`` on
the computer running Setu -- which a phone somewhere else cannot reach.
This module lets the person do it from where they are.

THREE WORDS, AND THEY ARE THE PERSON'S, NOT THE MODEL'S.

    /connect gmail                 sign in (the level the agent asks for)
    /connect gmail send as work    a level, and a name for the account
    /connect homeassistant http://ha.local:8123
    /accounts                      what is connected here, for you
    /disconnect gmail:work         revoke it and forget it
    /lock, /unlock [days]          a passphrase only they know (unlocked.py)

dvara invents no command language for talking to agents, and this is
not one: an agent never sees these messages, never starts a sign-in and
never reads an answer to one. A sign-in is a decision about a person's
key, like an approval is a decision about a call, and neither is a
sentence for a model to read (``service.py``). A prompt injected into
somebody's mail can ask an agent for anything; it cannot type a slash
command into their chat.

THE PASTED ADDRESS GOES TO THE SIGN-IN AND NOWHERE ELSE. ``/connect``
starts ``setu connect --json --paste`` in the person's folder and sends
them Google's link. They sign in on their phone; the browser then fails
to load ``http://127.0.0.1:<port>/?state=...&code=...``. They copy that
address and send it here. It is handed to the waiting sign-in's stdin --
not to an agent, not to the conversation's history, not to the run log
-- and Setu checks its ``state`` and redeems the code with the PKCE
verifier only it holds. A code read off the chat by someone else is
worth nothing without that verifier, and it works once.

ONLY INTO A FOLDER OF THEIR OWN. A person with ``setu = true`` signs in
to their own folder. A person pointed at somebody else's folder (the
owner's, narrowed by ``setu_accounts``) is told that the owner looks
after those, at the machine: a chat must never be a way to add accounts
to the owner's own folder. Unless the owner said so for that person
(``setu_manage``, never with ``setu_accounts``): the owner's own phone on
the owner's own folder. Even then /lock is the computer's, since a
folder shared with a desktop and a page would lock them all out.

ONE SIGN-IN AT A TIME PER PERSON, for ten minutes. A new ``/connect``
replaces one that is waiting. The outcome comes back as the reply to the
paste, or -- when it ends some other way (timed out, refused at Google)
-- as a notice.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dvara.unlocked import KeyHolder

#: The three words, and nothing else, are the person's to type.
COMMANDS = ("/connect", "/accounts", "/disconnect", "/lock", "/unlock")
#: How long a sign-in waits for its address to come back.
SIGN_IN_FOR = 600.0
#: How long a reply waits on Setu (the link; the outcome of a paste).
ANSWER_WITHIN = 45.0
#: An address the sign-in ended on: on this computer, carrying a code.
PASTED = re.compile(r"https?://(127\.0\.0\.1|localhost)(:\d+)?/?\S*[?&](code|error)=",
                    re.IGNORECASE)


def is_command(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in COMMANDS


def looks_pasted(text: str) -> bool:
    return PASTED.search(text) is not None


def scrub(text: str) -> str:
    """What may be kept of a message that may be a pasted address."""
    return "(an address pasted back for a sign-in)" if looks_pasted(text) else text


@dataclass
class _Waiting:
    """One sign-in, waiting for the address to come back."""

    ref: str
    proc: asyncio.subprocess.Process
    events: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    #: A paste in flight waits on this for its outcome.
    waiter: asyncio.Future[dict[str, Any]] | None = None
    done: bool = False
    reader: asyncio.Task[None] | None = None


Notify = Callable[[str, str], Awaitable[Any]]


class AccountDesk:
    """The sign-ins waiting for people, and the three words that start them.

    ``notify(actor, text)`` reaches a person outside a reply, for a
    sign-in that ended while nobody was pasting. ``setu`` is the program
    (default: ``setu`` on PATH). ``client_file`` names the Google client
    a person's fresh folder signs in with when it has none of its own --
    the owner's, found once in the owner's own Setu."""

    def __init__(self, *, notify: Notify, setu: str | None = None,
                 sign_in_for: float = SIGN_IN_FOR, log: Callable[[str], None] = print,
                 client_file: Callable[[], str | None] | None = None) -> None:
        self.notify, self.setu, self.sign_in_for, self.log = notify, setu, sign_in_for, log
        self._client_file = client_file
        self._waiting: dict[str, _Waiting] = {}
        #: Folders their people locked, and the keys they opened them with.
        self.keys = KeyHolder(notify=notify, program=self._program, log=log)

    def _program(self) -> str | None:
        return self.setu or shutil.which("setu")

    # ---- the one entry point -------------------------------------------------

    async def handle(self, *, actor: str, text: str, home: Path | None, own: bool,
                     narrowed: tuple[str, ...] | None, needs: dict[str, str],
                     may_lock: bool | None = None) -> str | None:
        """The reply to a message that is the person's to act on, or None
        when it is a message for the agent. ``home`` is their Setu folder
        (None: no accounts here); ``own`` is whether its accounts are
        theirs to change from here; ``may_lock`` whether its passphrase is
        (default: ``own``) -- a shared folder the owner lets them manage
        is not theirs to lock, since everything else using it would be
        locked out; ``needs`` is the package's connectors and levels, for
        a default."""
        command = is_command(text)
        if self.keys.expects_passphrase(actor):
            if not command:
                program = self._program()
                if program is None or home is None:
                    self.keys.cancel(actor)
                    return "Accounts aren't available here right now."
                return await self.keys.passphrase(actor, program, home, text)
            self.keys.cancel(actor)              # a command instead: never mind
        if looks_pasted(text):
            return await self._pasted(actor, text)
        if not command:
            return None
        word, *rest = text.strip().split()
        word = word.split("@")[0].lower()
        if home is None:
            return ("No accounts are set up for you on this service. The owner can "
                    "give you a place for them.")
        program = self._program()
        if program is None:
            return "Accounts aren't available here right now (no Setu on this computer)."
        if word == "/accounts":
            return await self._list(program, home, narrowed, self.keys.key_for(actor))
        if not own:
            return ("Your accounts here are looked after by the owner of this service, "
                    "at their computer -- ask them to connect, disconnect or lock one.")
        if word in ("/lock", "/unlock") and not (own if may_lock is None else may_lock):
            return ("These accounts are shared with this computer, so their passphrase "
                    "is set at the computer: `setu lock` there.")
        if word == "/lock":
            return await self.keys.lock(actor, program, home)
        if word == "/unlock":
            return self.keys.unlock(actor, program, home, rest)
        if word == "/disconnect":
            return await self._disconnect(program, home, rest)
        return await self._connect(actor, program, home, rest, narrowed, needs)

    # ---- /accounts ------------------------------------------------------------

    async def _status(self, program: str, home: Path, key: str | None = None
                      ) -> dict[str, Any]:
        done = await _run([program, "status", "--json"], home, key)
        if done[0] != 0:
            raise RuntimeError(done[2].strip().splitlines()[-1:] or "setu status failed")
        return json.loads(done[1])

    async def _list(self, program: str, home: Path,
                    narrowed: tuple[str, ...] | None, key: str | None = None) -> str:
        try:
            data = await self._status(program, home, key)
        except (RuntimeError, ValueError) as exc:
            self.log(f"dvara: accounts: {exc}")
            return "I couldn't read your accounts just now."
        rows = [r for r in data.get("connections") or []
                if narrowed is None or r.get("ref") in narrowed]
        if not rows:
            return ("You have no accounts connected here. Send /connect gmail to "
                    "connect one.")
        lines = [f"{r['ref']} -- {r.get('email') or ''} -- {r.get('level_label') or ''}"
                 for r in rows]
        lock = data.get("lock") or {}
        state = ("" if not lock.get("locked") else
                 "\nLocked with your passphrase" + (", and open now (/lock closes it)."
                                                     if lock.get("open")
                                                     else ": send /unlock to open it."))
        return "Connected for you here:\n" + "\n".join(lines) + state

    # ---- /disconnect ------------------------------------------------------------

    async def _disconnect(self, program: str, home: Path, rest: list[str]) -> str:
        if len(rest) != 1:
            return "Say which one, as /accounts lists it: /disconnect gmail:personal"
        ref = rest[0] if ":" in rest[0] else f"{rest[0]}:personal"
        code, out, err = await _run([program, "disconnect", ref], home)
        if code != 0:
            return (err or out).strip().splitlines()[-1].removeprefix("error: ") \
                if (err or out).strip() else f"{ref} could not be disconnected."
        return f"Disconnected {ref}. " + (out.strip().splitlines() or [""])[-1]

    # ---- /connect ----------------------------------------------------------------

    async def _connect(self, actor: str, program: str, home: Path, rest: list[str],
                       narrowed: tuple[str, ...] | None, needs: dict[str, str]) -> str:
        if not rest:
            return ("Say which: /connect gmail (or /connect gmail send as work, or "
                    "/connect homeassistant http://your-home-assistant:8123)")
        connector, account, level, url = rest[0].lower(), "personal", None, None
        words = rest[1:]
        while words:
            word = words.pop(0)
            if word.lower() == "as" and words:
                account = words.pop(0)
            elif word.lower().startswith(("http://", "https://")):
                url = word
            elif level is None:
                level = word.lower()
            else:
                return f"I didn't follow {word!r}: /connect gmail [level] [as NAME]"
        ref = f"{connector}:{account}"
        if narrowed is not None and ref not in narrowed:
            return (f"The owner set your accounts here to {', '.join(narrowed) or 'none'}; "
                    f"{ref} isn't one of them.")
        level = level or needs.get(connector)
        try:
            status = await self._status(program, home)
        except (RuntimeError, ValueError):
            status = {}
        card = next((c for c in status.get("connectors") or [] if c.get("id") == connector),
                    {})
        in_a_window = card.get("auth") == "browser"
        if in_a_window and not window_set():
            return (f"{card.get('name') or connector} is signed in to in a browser window on "
                    "the owner's computer. They can sign you in there, or give this service a "
                    "window address (SETU_WINDOW_HOST) so it can be streamed to your phone.")
        road = "--remote" if in_a_window else "--paste"
        argv = [program, "connect", connector, "--as", account, "--json", road,
                "--timeout", str(int(self.sign_in_for))]
        if level:
            argv += ["--level", level]
        if url:
            argv += ["--url", url]
        client = self._client_file() if self._client_file else None
        if not in_a_window and client and not \
                (status.get("setup") or {}).get("google_client_file"):
            argv += ["--client-file", client]
        await self._forget(actor)                  # a new sign-in replaces a waiting one
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            # an unlocked folder stays unlocked: the new sign-in is not sealed
            # away under them (Setu seals it when nobody holds the key)
            env=_env(home, self.keys.key_for(actor)))
        waiting = _Waiting(ref=ref, proc=proc)
        self._waiting[actor] = waiting
        waiting.reader = asyncio.create_task(self._read(actor, waiting))
        started: dict[str, Any] = {}
        while True:
            try:
                event = await asyncio.wait_for(waiting.events.get(), ANSWER_WITHIN)
            except TimeoutError:
                await self._forget(actor)
                return "Setu didn't answer in time; nothing was started."
            if event.get("event") == "started":
                started = event
            elif event.get("event") in ("url", "link"):
                break
            elif event.get("event") == "error":
                await _settle(waiting)
                return f"I couldn't start that sign-in: {event.get('message')}"
        minutes = int(self.sign_in_for // 60)
        what = started.get("level_label") or level or "the least access"
        if event.get("event") == "link":
            return (f"To connect {ref} ({what}), open this on your phone:\n\n{event['url']}"
                    f"\n\nYou'll see {card.get('name') or connector}'s sign-in page, running "
                    "in a browser on this service's computer: tap and type as you would on "
                    "the page. It opens on the first device only and works for "
                    f"{minutes} minutes. Your sign-in stays in your own folder; I'll tell you "
                    "when it's done.")
        return (f"To connect {ref} ({what}), open this and sign in:\n\n{event['url']}\n\n"
                "After you allow it, your browser will try to open a page starting with "
                "http://127.0.0.1 and fail to load it. That's expected. Copy that page's "
                f"whole address and send it to me here. It works once, within {minutes} "
                "minutes, and it goes to the sign-in, not to any agent.")

    # ---- the address, pasted back ------------------------------------------------

    async def _pasted(self, actor: str, text: str) -> str:
        waiting = self._waiting.get(actor)
        if waiting is None or waiting.done or waiting.proc.stdin is None:
            return ("There's no sign-in waiting for you, so I've dropped that address. "
                    "Send /connect gmail to start one.")
        address = PASTED.search(text)
        line = text[address.start():].split()[0] if address else text.strip()
        loop = asyncio.get_running_loop()
        waiting.waiter = loop.create_future()
        waiting.proc.stdin.write(line.encode() + b"\n")
        await waiting.proc.stdin.drain()
        try:
            event = await asyncio.wait_for(asyncio.shield(waiting.waiter), ANSWER_WITHIN)
        except TimeoutError:
            return "Still checking that sign-in; I'll tell you when it's done."
        finally:
            waiting.waiter = None
        if event.get("event") != "paste_refused":
            await _settle(waiting)               # its process gone before the reply goes
        return _outcome(waiting.ref, event)

    async def _read(self, actor: str, waiting: _Waiting) -> None:
        """Setu's events, for as long as the sign-in runs.

        Before the link: ``started``, ``url`` or ``error`` go to the
        ``/connect`` reply. After it: ``paste_refused`` answers the paste
        in flight; ``connected`` or ``error`` ends the sign-in -- as the
        paste's answer if one is waiting, otherwise as a notice."""
        assert waiting.proc.stdout is not None
        deadline = time.monotonic() + self.sign_in_for + 30
        linked = False
        last: dict[str, Any] | None = None
        try:
            while (left := deadline - time.monotonic()) > 0:
                try:
                    raw = await asyncio.wait_for(waiting.proc.stdout.readline(), left)
                except TimeoutError:
                    break
                if not raw:
                    break
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                kind = event.get("event")
                if not linked:
                    await waiting.events.put(event)
                    linked = kind in ("url", "link")
                    if kind == "error":
                        return
                    continue
                if kind == "paste_refused":
                    self._answer(waiting, event)
                elif kind in ("connected", "error"):
                    last = event
                    if not self._answer(waiting, event):
                        await self._tell(actor, _outcome(waiting.ref, event))
                    return
        finally:
            replaced = waiting.done           # set by _forget: a new /connect, or closing
            waiting.done = True
            if self._waiting.get(actor) is waiting:
                del self._waiting[actor]
            with contextlib.suppress(ProcessLookupError):
                waiting.proc.kill()
            with contextlib.suppress(Exception):
                await waiting.proc.wait()
            if linked and last is None and not replaced:
                ended = {"event": "error", "message": "it ran out of time"}
                if not self._answer(waiting, ended):
                    await self._tell(actor, f"The sign-in for {waiting.ref} ran out of "
                                     "time. Send /connect again to start a new one.")
            if last is not None and last.get("event") == "connected":
                self.log(f"dvara: {actor} connected {waiting.ref} from the chat")

    @staticmethod
    def _answer(waiting: _Waiting, event: dict[str, Any]) -> bool:
        """Give ``event`` to the paste waiting for it; False if none is."""
        if waiting.waiter is not None and not waiting.waiter.done():
            waiting.waiter.set_result(event)
            return True
        return False

    async def _tell(self, actor: str, text: str) -> None:
        try:
            await self.notify(actor, text)
        except Exception as exc:                  # a notice that fails never stops one
            self.log(f"dvara: could not tell {actor} about a sign-in: {exc}")

    async def _forget(self, actor: str) -> None:
        waiting = self._waiting.pop(actor, None)
        if waiting is None:
            return
        waiting.done = True
        with contextlib.suppress(ProcessLookupError):
            waiting.proc.kill()
        if waiting.reader is not None:
            waiting.reader.cancel()
        await _settle(waiting)

    async def aclose(self) -> None:
        for actor in list(self._waiting):
            await self._forget(actor)
        await self.keys.aclose()


async def _settle(waiting: _Waiting) -> None:
    """Wait until a sign-in's reader and process are both gone."""
    if waiting.reader is not None:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await waiting.reader
    with contextlib.suppress(Exception):
        await waiting.proc.wait()


def _outcome(ref: str, event: dict[str, Any]) -> str:
    kind = event.get("event")
    if kind == "connected":
        who = f" ({event['email']})" if event.get("email") else ""
        lower = (f" You allowed less than was asked, so it holds {event.get('level_label')}."
                 if event.get("asked_level") and event.get("asked_level") != event.get("level")
                 else "")
        return (f"Connected {ref}{who} at {event.get('level_label') or event.get('level')}."
                f"{lower} Your agents that need it can use it from your next message.")
    if kind == "paste_refused":
        return f"That didn't work: {event.get('message')}. The sign-in is still waiting."
    return f"The sign-in for {ref} didn't finish: {event.get('message')}"


def window_set() -> bool:
    """Whether the owner said where a streamed sign-in window listens
    (Setu's SETU_WINDOW_HOST or SETU_WINDOW_URL, in this service's own
    environment)."""
    return bool(os.environ.get("SETU_WINDOW_HOST") or os.environ.get("SETU_WINDOW_URL"))


def _env(home: Path, key: str | None = None) -> dict[str, str]:
    env = {**os.environ, "SETU_HOME": str(home)}
    if key:
        env["SETU_VAULT_KEY"] = key
    return env


def owners_client_file(program: str | None = None) -> str | None:
    """The Google client the owner's own Setu signs in with -- what a
    person's fresh folder borrows, since it is the owner's app either way
    (``SETU_GOOGLE_CLIENT_FILE``, else the owner's own Setu's setting)."""
    import subprocess

    if os.environ.get("SETU_GOOGLE_CLIENT_FILE"):
        return os.environ["SETU_GOOGLE_CLIENT_FILE"]
    program = program or shutil.which("setu")
    if program is None:
        return None
    env = {k: v for k, v in os.environ.items() if k != "SETU_HOME"}
    try:
        done = subprocess.run([program, "status", "--json"], capture_output=True,
                              text=True, timeout=30, env=env)
        return json.loads(done.stdout).get("setup", {}).get("google_client_file")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


async def _run(argv: list[str], home: Path, key: str | None = None
               ) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL, env=_env(home, key))
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode(), err.decode()

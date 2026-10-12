"""A sign-in that ran out, found the day it did and told to its person.

Setu marks a sign-in the site refused, and a person's agent stops
offering that account and says how to sign in again (note 19). But a
sign-in is refused only when it is next used: a Gmail nobody asked about
for a week showed nothing wrong until the morning somebody needed it,
and then the person heard about it in the middle of what they wanted.

ONCE A DAY, EVERY FOLDER. ``setu check --json`` refreshes every sign-in
that can run out, now, in each Setu folder this service reads: a
person's own, and a folder the owner pointed people at. A refusal is
marked by Setu, where every other reader already looks.

TOLD ONCE, TO WHOEVER CAN FIX IT. A person with a folder of their own is
told about their own accounts, with the words that fix it from the
chat (``/connect gmail as work``). A shared folder is the owner's: it is
told to whoever may manage it from the chat (``setu_manage``), and when
nobody may, it is a line for the owner (``Service._note``) -- never a
message to a person who can do nothing about it. What was told is kept
in ``<state>/signins.json`` by the mark's own time, so the same refusal
is not told twice, and a sign-in that came back and ran out again is.

NOTHING ELSE IS TOUCHED. A browser profile, an app on the phone, a
locked folder and a token that cannot be refreshed are skipped by Setu
(it cannot try those without using them); a site that did not answer is
not a refusal. A check that fails is a line for the owner and waits for
tomorrow.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

FILE = "signins.json"
#: How often every folder is checked, by default.
EVERY = 24 * 3600.0
#: How long one folder's check may take.
WITHIN = 120.0


@dataclass(frozen=True, slots=True)
class Expired:
    ref: str
    connector: str
    account: str
    email: str
    since: str
    why: str


async def check(program: str, home: Path) -> list[Expired]:
    """``setu check --json`` in ``home``: the sign-ins found refused.
    Raises ``RuntimeError`` with Setu's words when it could not check."""
    env = {**os.environ, "SETU_HOME": str(home)}
    try:
        proc = await asyncio.create_subprocess_exec(
            program, "check", "--json", stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL, env=env)
        out, err = await asyncio.wait_for(proc.communicate(), WITHIN)
    except (OSError, TimeoutError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from None
    try:
        rows = json.loads(out.decode())["checked"]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError(err.decode().strip() or f"setu check exited {proc.returncode}") \
            from None
    return [Expired(ref=r.get("ref", ""), connector=r.get("connector", ""),
                    account=r.get("account", ""), email=r.get("email", ""),
                    since=str(r.get("since", "")), why=str(r.get("why", "")))
            for r in rows if r.get("state") == "expired"]


def message(gone: Expired, *, from_chat: bool) -> str:
    """What the person reads: which account, since when, and the fix."""
    name = gone.email or gone.ref
    since = gone.since[:10]
    fix = (f"Send /connect {gone.connector} as {gone.account} to sign in again."
           if from_chat else
           f"It needs signing in again at the computer: setu connect "
           f"{gone.connector} --as {gone.account}")
    return (f"Your {gone.connector} sign-in ({name}) stopped working"
            f"{' on ' + since if since else ''}: the site refused it. {fix}")


class Told:
    """``<state>/signins.json``: ``{folder: {ref: since}}`` -- each
    refusal told, by the time Setu marked it. Owner-only, rewritten whole."""

    def __init__(self, state: Path) -> None:
        self.path = state / FILE

    def read(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def news(self, folder: Path, found: list[Expired]) -> list[Expired]:
        """The refusals in ``found`` not told yet; the record for this
        folder becomes exactly ``found`` (a sign-in back again is let go,
        so its next refusal is news)."""
        data = self.read()
        before = data.get(str(folder), {})
        new = [g for g in found if before.get(g.ref) != g.since]
        data[str(folder)] = {g.ref: g.since for g in found}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)
        return new

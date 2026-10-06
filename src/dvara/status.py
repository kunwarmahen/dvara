"""What this service can tell a program that starts it: is it serving?

Sarathi starts dvara and then has to say whether the door is open. "The
program was found" is not that answer, and neither is "a process with
that pid exists". ``dvara status --json`` answers it from the one thing
that cannot be stale: the claim on the state directory (claim.py). A
``dvara serve`` or ``dvara telegram`` holds it for as long as it runs,
and the kernel lets it go however that process ends.

The shape is the family's: Setu's and Samay's ``status --json`` set it.
A ``format`` field names the version, and a reader refuses one it does
not know rather than guess.

READ, NEVER STARTED. Building a ``Service`` would open the ledger and
make the state directory, which is not what asking should do. So this
reads the lock, lists the agent folder and counts the actors file, and
says what it could not read as a problem in words instead of exiting:
"the actors file does not parse" is something the owner wants to see
from ``status``, not a reason for ``status`` to fail.

NO SECRET IS IN IT. Not the token, not the bot's token, not a name of a
person -- a count of them.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dvara.actors import ActorBook
from dvara.claim import holder
from dvara.errors import ConfigProblem
from dvara.roster import Roster

FORMAT = "dvara.status.v1"

#: The commands that serve people, as opposed to one turn at a keyboard
#: (``say``, ``resume``), which also hold the claim while they run.
SERVING = ("dvara serve", "dvara telegram")


def _version() -> str:
    try:
        return version("dvara")
    except PackageNotFoundError:
        return "unknown"


def report(*, root: Path, actors: Path, state: Path) -> dict:
    root, actors, state = (Path(p).expanduser().absolute()
                           for p in (root, actors, state))
    problems: list[str] = []
    try:
        agents = Roster(root).names()
    except ConfigProblem as exc:
        agents = []
        problems.append(str(exc))
    try:
        people = len(ActorBook.from_toml(actors))
    except (ConfigProblem, ValueError) as exc:
        people = 0
        problems.append(str(exc))
    held = holder(state)
    serving = held is not None and held.get("command") in SERVING
    return {
        "format": FORMAT,
        "version": _version(),
        "root": str(root),
        "actors": str(actors),
        "state": str(state),
        "serving": serving,
        "url": held.get("at") if serving and held else None,
        "running": held,
        "agents": agents,
        "people": people,
        "problems": problems,
    }


def lines(data: dict) -> list[str]:
    """``dvara status`` without ``--json``: the same answer, for a person."""
    out = [f"dvara {data['version']} · state {data['state']}"]
    running = data["running"]
    if running is None:
        out.append("not running (start it: dvara serve)")
    else:
        what = running.get("command") or "a dvara"
        where = f" at {data['url']}" if data["url"] else ""
        since = f", since {running['since']}" if running.get("since") else ""
        verb = "serving" if data["serving"] else "busy"
        out.append(f"{verb}{where} ({what}{since})")
    names = ", ".join(data["agents"]) or "none"
    out.append(f"agents: {names}  ·  people: {data['people']}")
    out += [f"problem: {p}" for p in data["problems"]]
    return out

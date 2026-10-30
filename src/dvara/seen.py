"""What a person's agent can use, and what they have scheduled -- by asking.

Yantra's page shows its tools and schedules in panels beside the chat. A
person behind this service had no way to see either: "what can you do?"
got the model's own guess, and a schedule made last month was found only
by asking the agent to list it, in words it chose.

``/tools``, ``/schedules`` and ``/watches`` answer from the record
instead, on every channel, and none is a turn: no model, no allowance
spent.

TOOLS AS THEY WERE ON YOUR LAST TURN. What an agent may use depends on
the package, the owner's rules, the person's accounts, the phone, and
which servers started -- all settled while a turn is built, and starting
every server again just to list them would cost seconds and sign-ins. So
each turn writes down the tools it was given (``state/tools/<person>/
<agent>.json``), and ``/tools`` reads that. Before a first turn there is
nothing to read, and it says so.

SEEING, NOT CHANGING. What a package may use is the owner's, in its
files (and on Sarathi's settings); a chat word that widened it would be
a way around them. A schedule is paused or removed by asking the agent,
which asks the person on their channel first (Samay's tools), so there
is one way to change one.

HOW OFTEN IS THE ONE CHANGE. ``/watches every 2 6h`` changes how often
their second watch looks, through ``prahari edit``, the same change
Prahari's page and Yantra's panel make with their Every box. It is the
person's own watch and only its pace: what it checks, and what the agent
may do when it fires, still go through the agent, which asks. A watch is
found among THEIR OWN first (Prahari files them under the person's name,
and the owner's made at the computer under ``local``), so a number or an
id from somebody else's list finds nothing.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

TOOLS = "/tools"
SCHEDULES = "/schedules"
WATCHES = "/watches"
#: What the owner made at the computer is filed under this (checkup.py).
LOCAL = "local"
#: Longest description line shown for a tool.
SAID_AT_MOST = 110


def word_of(text: str) -> str | None:
    first = text.strip().split(maxsplit=1)[:1]
    word = first[0].lower().split("@")[0] if first else ""
    return word if word in (TOOLS, SCHEDULES, WATCHES) else None


class Seen:
    def __init__(self, state: Path) -> None:
        self.state = Path(state) / "tools"

    def _file(self, actor: str, agent: str) -> Path:
        return self.state / actor / f"{agent}.json"

    def tools_were(self, actor: str, agent: str, built: Any) -> None:
        """Write down the tools this turn's agent was given. Never costs
        the turn: a record that can't be written is a stale list."""
        registry = getattr(built, "registry", None)
        if registry is None:
            return
        rows = [_row(tool) for tool in registry if not registry.is_disabled(tool.name)]
        # And what the package turned away: the settings page offers those
        # to the owner by what they do (toolbox.py), never to the person.
        away = getattr(registry, "turned_away", None)
        could = [_row(tool) for tool in (away() if callable(away) else [])]
        target = self._file(actor, agent)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, staged = tempfile.mkstemp(dir=target.parent, prefix=".tools-")
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump({"at": datetime.now().astimezone().isoformat(timespec="minutes"),
                           "tools": rows, "could": could}, out)
            os.replace(staged, target)
        except OSError:
            pass

    def tools(self, actor: str, agent: str) -> str:
        try:
            data = json.loads(self._file(actor, agent).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return (f"I'll know which tools {agent} has once you've sent it a message: "
                    f"they're settled when it starts working for you.")
        groups: dict[str, list[dict]] = {}
        for row in data.get("tools") or []:
            groups.setdefault(row.get("group") or "built in", []).append(row)
        out = [f"What {agent} could use on your last message:"]
        for group in sorted(groups, key=lambda g: (g != "built in", g)):
            out.append("")
            out.append(f"{group}:")
            for row in sorted(groups[group], key=lambda r: r["name"]):
                said = f" — {row['said']}" if row.get("said") else ""
                out.append(f"• {_short(row['name'])}{said}")
        out.append("")
        out.append("What it may use is set by whoever runs this for you.")
        return "\n".join(out)

    async def schedules(self, actor: str, samay: str | None, *, enabled: bool) -> str:
        """Their schedules, as Samay says them."""
        if not enabled:
            return "Schedules aren't switched on here."
        program = samay or shutil.which("samay")
        if not program:
            return "I can't find Samay on this computer just now."
        try:
            listed = await asyncio.to_thread(
                subprocess.run, [program, "list", "--json"], capture_output=True,
                text=True, timeout=30)
            cards = json.loads(listed.stdout) if listed.returncode == 0 else None
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return f"Samay didn't answer ({type(exc).__name__}). Try again soon."
        if not isinstance(cards, list):
            return "Samay didn't list its schedules. Try again soon."
        mine = [c for c in cards if isinstance(c, dict) and c.get("owner") == actor]
        if not mine:
            return ("You have no schedules. Ask me to do something at a time — "
                    "\"every morning at 8, tell me the weather\" — and I'll set one up.")
        out = ["Your schedules:"]
        for card in mine:
            state = card.get("state") or ""
            paused = (f" — paused: {card.get('paused_because')}" if state != "active"
                      and card.get("paused_because") else
                      " — paused" if state != "active" else "")
            last = card.get("last_run") or {}
            how = (f" Last time: {last.get('outcome')}"
                   f"{_when(last.get('ended_at') or last.get('due_at'))}."
                   if last.get("outcome") else "")
            agent = Path(str(card.get("agent") or "")).name
            out.append(f"• {card.get('prompt') or '(no words)'} ({agent}, id {card.get('id')})")
            out.append(f"  {card.get('sentence') or ''}{paused}.{how}")
        out.append("")
        out.append("To pause, change or remove one, just ask me.")
        return "\n".join(out)

    async def watches(self, actor: str, text: str, prahari: str | None, *,
                      enabled: bool, is_owner: bool = False) -> str:
        """Their watches, as Prahari says them; ``/watches every N 6h``
        changes how often one looks."""
        if not enabled:
            return "Watches aren't switched on here."
        program = prahari or shutil.which("prahari")
        if not program:
            return "I can't find Prahari on this computer just now."
        cards, trouble = await ask_json([program, "list", "--json"])
        if trouble or not isinstance(cards, list):
            return trouble or "Prahari didn't list its watches. Try again soon."
        names = {actor} | ({LOCAL} if is_owner else set())
        mine = [c for c in cards if isinstance(c, dict) and c.get("owner") in names]
        rest = text.strip().split()[1:]
        if rest and rest[0].lower() == "every":
            return await self._every(program, mine, rest[1:])
        if rest:
            return (f"I don't know \"/watches {' '.join(rest)}\". "
                    + EVERY_HOW)
        if not mine:
            return ("You have no watches. Ask me to tell you when something happens — "
                    "\"tell me when ALAB drops below $50\" — and I'll set one up.")
        out = ["Your watches:"]
        for n, card in enumerate(mine, 1):
            state = card.get("state") or ""
            paused = (f" — paused: {card.get('paused_because')}" if state != "active"
                      and card.get("paused_because") else
                      " — paused" if state != "active" else "")
            last = card.get("last_look") or {}
            at = last.get("ended_at") or last.get("started_at")
            how = (f" Last look: {last.get('outcome')}{_when(at)}."
                   if last.get("outcome") else "")
            out.append(f"{n}. {card.get('name') or '(no name)'} (id {card.get('id')})")
            out.append(f"  {card.get('sentence') or ''}{paused}.{how}")
        out.append("")
        out.append(EVERY_HOW + " To pause, mend or remove one, just ask me.")
        return "\n".join(out)

    async def _every(self, program: str, mine: list[dict], words: list[str]) -> str:
        if len(words) == 1 and len(mine) == 1:
            words = ["1", *words]         # the one watch they have
        if len(words) != 2:
            return EVERY_HOW
        which, every = words
        card = _which(mine, which)
        if card is None:
            return (f"You have no watch {which}. Send /watches to see their numbers."
                    if mine else "You have no watches.")
        if not card.get("every"):
            return (f"\"{card.get('name')}\" doesn't look on a clock: it hears when "
                    f"something is sent to it, so there's no how often to change.")
        changed, trouble = await ask_json([program, "edit", str(card["id"]),
                                            "--every", every, "--json"])
        if trouble or not isinstance(changed, dict):
            return trouble or "Prahari didn't change it. Try again soon."
        return f"Done. \"{changed.get('name')}\": {changed.get('sentence') or ''}."


#: How to change how often, said wherever it helps.
EVERY_HOW = "To change how often one looks: /watches every NUMBER 6h (30m, 3h, 1d)."


async def ask_json(argv: list[str], env: dict[str, str] | None = None) -> tuple[Any, str]:
    """A program's ``--json`` answer, or what went wrong in words a person
    can read (its own ``error:`` line when it said one). ``env``: added to
    this process's own."""
    name = Path(argv[0]).name.capitalize()
    try:
        done = await asyncio.to_thread(subprocess.run, argv, capture_output=True,
                                       text=True, timeout=30,
                                       env={**os.environ, **env} if env else None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{name} didn't answer ({type(exc).__name__}). Try again soon."
    if done.returncode != 0:
        said = " ".join(done.stderr.split()).removeprefix("error: ")
        return None, (f"{name} said: {said}" if said else
                      f"{name} didn't answer. Try again soon.")
    try:
        return json.loads(done.stdout), ""
    except ValueError:
        return None, f"{name} said something I couldn't read. Try again soon."


def _which(mine: list[dict], which: str) -> dict | None:
    """Their watch by its number in ``/watches``, or by the start of its id."""
    if which.isdigit() and 1 <= int(which) <= len(mine):
        return mine[int(which) - 1]
    found = [c for c in mine if str(c.get("id") or "").startswith(which)]
    return found[0] if len(found) == 1 and which else None


def _row(tool: Any) -> dict:
    line = " ".join((getattr(tool, "description", "") or "").split())
    line = line.split(". ")[0]
    if len(line) > SAID_AT_MOST:
        line = line[:SAID_AT_MOST - 1] + "…"
    return {"name": tool.name, "said": line, "group": _group(tool.name),
            "asks": not getattr(tool, "read_only", False)}


def _group(name: str) -> str:
    if name.startswith("mcp__"):
        return name.split("__")[1] or "connected"
    return "built in"


def _short(name: str) -> str:
    """``mcp__gmail-mine__search`` reads as ``search`` under its group."""
    return name.split("__", 2)[2] if name.startswith("mcp__") and name.count("__") >= 2 else name


def _when(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        at = datetime.fromisoformat(iso).astimezone()
    except ValueError:
        return ""
    return f" ({at:%a %-d %b %H:%M})"

"""What a person's agent can use, and what they have scheduled -- by asking.

Yantra's page shows its tools and schedules in panels beside the chat. A
person behind this service had no way to see either: "what can you do?"
got the model's own guess, and a schedule made last month was found only
by asking the agent to list it, in words it chose.

``/tools`` and ``/schedules`` answer from the record instead, on every
channel, and neither is a turn: no model, no allowance spent.

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
#: Longest description line shown for a tool.
SAID_AT_MOST = 110


def word_of(text: str) -> str | None:
    first = text.strip().split(maxsplit=1)[:1]
    word = first[0].lower().split("@")[0] if first else ""
    return word if word in (TOOLS, SCHEDULES) else None


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

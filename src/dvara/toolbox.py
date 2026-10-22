"""Every tool an agent here could be given, for the settings page's boxes.

``[tools] allow`` was a text box on Sarathi's settings: "one per line,
e.g. web_fetch, mcp__gmail*". The owner had to know every name, and a
name spelled wrong was a tool silently missing. This module is what the
page draws checkboxes from instead.

THREE KINDS, ONE LIST. Yantra's own tools (its tools/catalog.py, read off
the classes, nothing started); this service's own (``send_file``); and
the families a server brings -- Samay's schedules, Sparsh's phone -- whose
members are only known once a server has listed them. A family is one
box, its pattern (``mcp__samay__*``), because the allow list matches
patterns and a new tool in Samay should not need a new tick.

WHAT A TURN SAW FILLS THE FAMILIES IN. Starting Samay and Sparsh just to
list their tools would cost seconds on every page load, so each turn
writes down the tools it was given AND the ones the package turned away
(seen.py). A family's members are read from there: every person's last
turn with every agent, so a tool one package refused still shows for the
owner deciding whether to let it in. Before any turn, a family shows its
sentence alone.

ACCOUNTS ARE NOT HERE. A Setu account comes with its need
(``[connections] needs``, "*:read"), and a need brings its own tools past
the allow list (Yantra's setu_link); ticking them here as well would be a
second way to say the same thing, and the two could disagree.

ASKS IS THE GATE'S BIT. Each row says whether using it is a question
under "ask" (the tool's ``read_only``), so a tick reads as what it does.
A standing rule on the Rules tab may still answer that question for you.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

#: This service's own tools, worded for the person choosing.
OWN = (
    {"name": "send_file", "said": "Send you a file from its folder (on Telegram, the file "
     "itself)", "asks": True, "group": "Talking and skills"},
)

#: Families a server brings: one box, a pattern, a sentence.
FAMILIES = (
    {"name": "mcp__samay__*", "group": "Schedules (Samay)",
     "said": "See your schedules, and make, pause or remove them (each change asks first)",
     "asks": True, "prefix": "mcp__samay__"},
    {"name": "mcp__prahari__*", "group": "Watches (Prahari)",
     "said": "See what you're watching for, and make, mend, pause or remove a watch "
             "(each change asks first)",
     "asks": True, "prefix": "mcp__prahari__"},
    {"name": "mcp__sparsh__*", "group": "Your phone (Sparsh)",
     "said": "Work the phone on this computer (Send, Pay, Delete and passwords ask first)",
     "asks": False, "prefix": "mcp__sparsh__"},
)


def _seen(state: Path | None) -> dict[str, dict[str, dict]]:
    """agent -> tool name -> row, from every person's last turn."""
    out: dict[str, dict[str, dict]] = {}
    if state is None:
        return out
    for record in sorted((Path(state) / "tools").glob("*/*.json")):
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = out.setdefault(record.stem, {})
        for row in (data.get("tools") or []) + (data.get("could") or []):
            if isinstance(row, dict) and row.get("name"):
                rows.setdefault(row["name"], row)
    return out


def toolbox(state: Path | None = None) -> dict:
    """``tools``: rows for the boxes; ``seen``: per agent, the names its
    turns met (given or turned away), for a family's members."""
    from yantra.tools.catalog import builtin_catalog

    seen = _seen(state)
    met: dict[str, dict] = {}
    for rows in seen.values():
        for name, row in rows.items():
            met.setdefault(name, row)
    families = []
    for family in FAMILIES:
        members = sorted(
            ({"name": n, "said": r.get("said", ""), "asks": r.get("asks")}
             for n, r in met.items() if n.startswith(family["prefix"])),
            key=lambda r: r["name"])
        families.append({**{k: v for k, v in family.items() if k != "prefix"},
                         "family": True, "members": members})
    return {"tools": builtin_catalog() + [dict(r) for r in OWN] + families,
            "seen": {agent: sorted(rows) for agent, rows in seen.items()}}


def covered(allow: list[str] | None, rows: list[dict]) -> list[str]:
    """The allow entries no box stands for -- kept as written under
    Advanced (``amazon_*``, an old ``mcp__homeassistant*``), so a save
    from the boxes never drops what the owner typed."""
    names = {r["name"] for r in rows}
    return [a for a in (allow or []) if a not in names]


def ticked(allow: list[str] | None, name: str) -> bool:
    """Whether a box starts ticked: named exactly, or let in by a pattern
    the owner wrote (``browser_*`` ticks every browser box)."""
    if allow is None:
        return True        # no allow list: everything not denied
    return any(a == name or fnmatch.fnmatch(name, a) for a in allow)

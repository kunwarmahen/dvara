"""When someone moves: their schedules move with them.

A person's ``zone`` (actors.py) is where their clock is: "at 8" in a
chat is 8 on it, and a schedule made then is kept in that zone by Samay.
When they move and the owner changes the zone (Settings → People, or the
file), the schedules stayed behind: "every morning at 8" kept firing at 8
in the place they left, 3 am where they are now.

NOTICED, NOT ASKED. The actors file is reread while the service runs
(``Service.refresh``), so a chore compares each person's zone with the
last one it saw (``<state>/zones.json``) about once a minute. A change is
``samay zone WHO --from OLD --to NEW``: Samay moves the schedules that
were in the zone they left and leaves one they put elsewhere on purpose
(samay's schedules.py). The person is told what moved, on their
channels, so nothing changes about their day without a line saying so.

THE FIRST LOOK ONLY WRITES DOWN. A service started for the first time,
or a person just added, has no zone it saw before; that is not a move.
A move that fails (Samay not answering) is not written down either, so
the next tick tries it again.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

FILE = "zones.json"


class Zones:
    """The zone each person was last seen in; "" for this machine's."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def keep(self, seen: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)


async def move(program: str, actor: str, was: str, now: str) -> list[dict]:
    """``samay zone``: the schedules it moved, as Samay's cards."""
    done = await asyncio.to_thread(
        subprocess.run, [program, "zone", actor, "--from", was, "--to", now, "--json"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    if done.returncode != 0:
        raise RuntimeError(" ".join((done.stderr or done.stdout).split())[-300:]
                           or f"samay zone exited {done.returncode}")
    return list(json.loads(done.stdout).get("moved") or [])


def message(moved: list[dict], now: str) -> str:
    """What the person is told, in words."""
    where = now or "this computer's time zone"
    out = [f"Your time zone is now {where}, so your schedules moved with you:"]
    for card in moved:
        out.append(f"• {card.get('prompt') or '(no words)'}: {card.get('sentence') or ''}")
    out.append("Any schedule you set in another time zone on purpose stays where it is.")
    return "\n".join(out)

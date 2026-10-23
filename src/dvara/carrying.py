"""A job a restart stopped part way, offered back to its person (``/carry``).

Every step of every turn is checkpointed (Yantra's carry.py), so when the
service comes back after ``sarathi down && up`` or a crash, a turn that
was in the middle of a phone or site job is in the session store as far
as it got. Nobody would know: the person asked, saw "Working…", and then
nothing. So as the service starts, each person with a job stopped part
way is told what it was and how far it got, and ``/carry`` carries it on
from the last step -- the agent is told it stopped, looks at the screen
again, and stops to ask if things moved.

THEIRS TO DECIDE. A person's job is never carried on by itself: an hour
later the bus may have gone, the basket emptied. Anything else they send
leaves it. A schedule's run (``samay-…``) or a watch's (``prahari-…``)
is not offered here: Samay and Prahari own those, and Samay asks for a
carry-on itself (``carry_on: true`` on ``POST /message``).

TOLD ONCE. A job is told about once (``carry-told.json``, by session and
when it was saved), so a service restarted three times in an evening
does not say the same thing three times.
"""

from __future__ import annotations

import json
from pathlib import Path

from yantra import carry

WORD = "/carry"
#: Threads that are a scheduler's or a watch's, not a person's chat.
NOT_PEOPLES = ("samay-", "prahari-")

NOTHING = ("Nothing stopped part way here. (/carry carries on a job a "
           "restart stopped in the middle.)")


def is_word(text: str) -> bool:
    return text.strip().lower() == WORD


def stopped_words(agent: str, info: dict) -> str:
    return (f"I stopped part way through {carry.describe(info)} when I was "
            f"restarted ({agent}). Send {WORD} to carry on from there -- I'll look "
            "again before I do anything. Anything else leaves it.")


def is_peoples(thread: str) -> bool:
    return not thread.startswith(NOT_PEOPLES)


class Told:
    """Which stopped jobs were told about, by session key and save time."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def already(self, key: str, info: dict) -> bool:
        return self._read().get(key) == info.get("saved")

    def mark(self, key: str, info: dict) -> None:
        data = self._read()
        data[key] = info.get("saved")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=1))
        self.path.chmod(0o600)

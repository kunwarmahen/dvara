"""Telling a person something nobody asked about -- yet.

Everything else this service sends is an ANSWER: somebody wrote, a turn
ran, a reply went back where the message came from. A scheduled check
breaks that. At 08:00 a scheduler runs a turn for a person who is
asleep, and if it finds something, the finding has to go TO them, on
their channel, unprompted -- the one direction a chat adapter never had
to support.

``POST /notify`` is that direction, and nothing more: a person (by actor
id, or by a channel identity the roster maps) and a text. It knows
nothing about schedules. The scheduler decides WHETHER something is
worth sending; this module only sends.

THE PERSON'S CHANNELS, NOT A THREAD. A notice goes to every channel the
actors file lists for that person, at the address it names -- the same
place a question for them would go (``AskDesk.route``). There is no
conversation to reply into: nothing started one.

ROUTED IF IT CAN BE, KEPT IF IT CANNOT. An adapter running in this
process registers a sender for its kind (the Telegram bot does), and a
notice for that kind is sent at once. A kind with no sender here --
an adapter in another process -- finds its notices waiting at ``GET
/notices?channel=KIND``, which hands each one over exactly once. A
sender that raises falls back to the same queue rather than losing the
text.

KEPT IN MEMORY, AND SAID SO. Unlike the outbox (outbox.py), which owes
a reply to somebody who wrote, a notice is owed to nobody yet: a
restart drops the queue, and the cap on it (the newest
``KEEP_PER_KIND`` per kind) drops the oldest. A scheduler that must
know keeps its own record -- that is what its run log is.
"""

from __future__ import annotations

import secrets
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

#: Sends one text to one address on one channel kind.
Sender = Callable[[str, str], Awaitable[None]]

#: Notices kept per channel kind for an adapter that has not collected
#: them. A person away for a week of hourly checks is not owed all 168.
KEEP_PER_KIND = 100


@dataclass(frozen=True)
class Notice:
    id: str
    actor: str
    kind: str
    to: str
    text: str
    at: datetime

    def as_dict(self) -> dict:
        return {"id": self.id, "actor": self.actor, "channel": self.kind,
                "to": self.to, "text": self.text,
                "at": self.at.isoformat(timespec="seconds")}


@dataclass
class Sent:
    """Where one notice went: delivered now, kept for collection, or
    nowhere (a person with no channel)."""

    sent: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def nowhere(self) -> bool:
        return not self.sent and not self.kept


class NoticeDesk:
    def __init__(self) -> None:
        self._routes: dict[str, Sender] = {}
        self._kept: dict[str, deque[Notice]] = {}

    def route(self, kind: str, sender: Sender) -> None:
        """Send notices for ``kind`` through ``sender``; re-registering
        replaces, as ``AskDesk.route`` does."""
        self._routes[kind] = sender

    async def send(self, actor: str, reach: Sequence[tuple[str, str]],
                   text: str) -> Sent:
        result = Sent()
        for kind, address in reach:
            notice = Notice(id=secrets.token_hex(4), actor=actor, kind=kind,
                            to=address, text=text, at=datetime.now(UTC))
            sender = self._routes.get(kind)
            if sender is not None:
                try:
                    await sender(address, text)
                    result.sent.append(kind)
                    continue
                except Exception as exc:     # a channel down is not a crash
                    result.failed[kind] = f"{type(exc).__name__}: {exc}"
            self._kept.setdefault(kind, deque(maxlen=KEEP_PER_KIND)).append(notice)
            result.kept.append(kind)
        return result

    def take(self, kind: str) -> list[Notice]:
        """Everything kept for ``kind``, handed over once, oldest first."""
        kept = self._kept.pop(kind, None)
        return list(kept) if kept else []

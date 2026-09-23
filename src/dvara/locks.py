"""One lock per key, kept exactly as long as somebody needs it.

Two tables in this package hold an ``asyncio.Lock`` per key: the service,
one per conversation, so two messages in one thread serialize; and the
Telegram bot, one per chat, so the parts of a split reply go out in
order. Both used to keep every lock they had ever made. That is a few
hundred bytes per conversation the process has ever served, and a
process that stays up for months serves a lot of conversations.

**AN ENTRY LIVES WHILE ANYBODY HOLDS IT OR WAITS FOR IT.** The count is
taken BEFORE the wait, not after the acquire, and that ordering is the
whole of the correctness argument. Evict on "nobody holds it" and the
failure is two turns in one conversation at once: task A holds the lock,
task B is queued on it, A releases and the entry goes, and task C --
arriving before B is scheduled -- finds no entry, makes a fresh lock,
and walks straight in. B then wakes holding the OLD lock. Nothing
raises; one of the two turns simply is not in the history afterwards,
which is ``claim.py``'s silent lost turn arriving by a different door.
Counting waiters closes it: while B is queued the count is not zero, so
C finds the same lock B is waiting on.

**THE EVENT LOOP IS THE MUTEX FOR THE TABLE.** Nothing between reading
the count and deleting the entry awaits, so no other task can run in
between. That is why this is a counter and not a second lock, and why
this class is not safe to share across threads -- nothing in this
package does.

**A CANCELLED WAITER GIVES ITS COUNT BACK.** A turn cancelled while
queued (a shutdown, a caller that gave up) leaves through the same
``finally`` as one that finished. Without that, one cancellation would
pin its conversation's lock for the life of the process, which is the
original leak back again, one entry at a time.

Evicting has a side effect worth having: a lock is made fresh for each
burst of use, so none outlives the event loop it was first used on.
Tests that drive the service with one ``asyncio.run`` per message stop
depending on the lock never having been contended.

Deliberately not here: a time-to-live. Eviction on the last release is
exact, and a timer would only be a slower, approximate version of it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Hashable
from contextlib import asynccontextmanager


class _Entry:
    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        # Holders plus waiters. Zero means nobody is inside and nobody is
        # queued, which is the only moment the entry can go.
        self.users = 0


class KeyedLocks[K: Hashable]:
    """``async with locks.hold(key):`` -- one holder per key at a time."""

    def __init__(self) -> None:
        self._entries: dict[K, _Entry] = {}

    @asynccontextmanager
    async def hold(self, key: K) -> AsyncIterator[None]:
        entry = self._entries.get(key)
        if entry is None:
            entry = self._entries[key] = _Entry()
        entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.users -= 1
            if entry.users == 0 and self._entries.get(key) is entry:
                del self._entries[key]

    def __len__(self) -> int:
        """How many keys are in use right now -- held or waited on."""
        return len(self._entries)

    def __contains__(self, key: object) -> bool:
        return key in self._entries

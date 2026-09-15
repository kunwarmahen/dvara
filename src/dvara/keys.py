"""The session key: three nouns, one string.

Yantra's ``SessionStore`` is keyed by one opaque ``session_id``. A service
has three coordinates -- WHO is talking, WHICH agent they are talking to,
and in WHICH conversation -- and the whole arc depends on all three being
in the key. ``(actor, thread)`` alone would give one person talking to the
researcher and to the ops agent in the same chat a single shared history,
and the fix for that after the fact is a migration.

PERCENT-ESCAPE EVERY COMPONENT. Joining raw strings with "/" is not
injective: actor ``a/b`` + thread ``c`` and actor ``a`` + thread ``b/c``
produce the same key, which is one person reading another's conversation
because of a naming coincidence. ``quote(x, safe="")`` escapes the
separator itself, so the mapping is one-to-one and reversible.

Readable on purpose. ``select distinct session_id from checkpoints``
should answer an owner's question without a decoder ring, which is why
this is not a hash.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

from dvara.errors import Refused


def session_key(actor: str, agent: str, thread: str) -> str:
    """``actor/agent/thread``, each component escaped. One-to-one."""
    parts = {"actor": actor, "agent": agent, "thread": thread}
    for name, value in parts.items():
        if not value or not value.strip():
            raise Refused(f"a {name} is required")
    return "/".join(quote(v, safe="") for v in parts.values())


def parse_key(key: str) -> tuple[str, str, str]:
    """The inverse. Exists so the encoding is provably reversible -- a
    round-trip test is the only thing that keeps an escaping rule true."""
    parts = key.split("/")
    if len(parts) != 3:
        raise ValueError(f"not a session key: {key!r}")
    actor, agent, thread = (unquote(p) for p in parts)
    return actor, agent, thread


#: Path segments that mean something to a filesystem rather than naming
#: anything in it.
DOT_SEGMENTS = frozenset({"", ".", ".."})


def workspace_parts(key: str) -> tuple[str, str, str]:
    """The key's components as path segments that are only ever names.

    A conversation's scratch directory nests as ``work/actor/agent/thread``,
    so these segments are chosen by whoever is talking and have to be
    inert. Escaping gets most of the way: the separator, NUL and every
    control character are gone.

    IT DOES NOT GET ALL THE WAY. ``quote`` leaves ``.`` alone, because a
    dot is legal in a URL path, so a thread named ``..`` survives
    escaping intact and a scratch directory becomes its own parent. The
    dot segments are neutralised here explicitly -- the one case where
    percent-escaping is not enough, and the reason this function exists
    instead of the caller splitting the key itself.
    """
    parts = key.split("/")
    if len(parts) != 3:
        raise ValueError(f"not a session key: {key!r}")
    safe = tuple(p.replace(".", "%2E") if p in DOT_SEGMENTS else p
                 for p in parts)
    return safe[0], safe[1], safe[2]

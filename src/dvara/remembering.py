"""What the agent remembers about a person: looked back for, kept on their
word, listed and forgotten from the chat.

Note 37 gave each person their own memories, but only through the agent:
a fact was kept when the model called ``remember`` mid-answer and the
person said yes. What people say in passing ("flights from RDU again")
was never kept, because nothing looked back over a conversation here.
And a person could not see what was kept about them, or take one back,
without the owner opening the store.

    /memory              what is kept about you, with each one's id
    /memory forget ID    that one, gone
    /remember 1 3        keep what I noticed (the numbers I listed)
    /remember all        keep all of it

THE LOOK BACK IS YANTRA'S, AND SO IS WHAT IT NOTICES MID-TURN. Yantra's
own look back (its memory/reflect.py) asks the agent's model once what
the conversation showed about the person. Here a conversation ends when
they send ``/new``, and Dvara asks before it lets the conversation go.
Yantra also notices facts inside a turn: before it shortens a
conversation grown too long, and in the write-up of a task it learns
from (its skills/learn.py). Those wait on ``memory.pending`` for a host
to offer, and Dvara never did, so they were lost when the turn ended.
Now they join the waiting list, and the answer gets one line saying so.

NOTHING IS KEPT WITHOUT THEIR WORD. Candidates wait, numbered, and are
kept when the person sends ``/remember`` with the numbers, and not
otherwise. ``/new`` lists them all under its answer; ``/remember`` alone
lists them again. The look back at ``/new`` read the whole conversation,
so ITS LIST REPLACES what the turns noticed on the way: those were the
same conversation seen in parts, and a model says "Lives in Pune" three
ways in three turns. A turn's own finds are a ONE-LINE HINT, not a list:
a model offers much the same facts turn after turn, and a numbered list
under every answer is a chat nobody reads. This is not a yes/no button
that waits either: a question that waited on a turn would hold the store
open for as long as it waited, and a fact is no less true tomorrow.

THEIR WORDS, NOT A TURN. Like ``/files`` and ``/new`` these are answered
here, never by the model, and cost nothing. The store is opened for the
person exactly as a turn opens it (their name, their own key, note 37)
and closed again. A package that keeps no memories has none of this:
``/memory`` says so, and ``/new`` looks back at nothing.

KEPT HERE ONLY UNTIL THEY ANSWER. The candidates wait in
``<state>/offered.json``, readable by the owner alone, one list per
person, never the same fact twice (by its head: "Works night shifts as
a nurse" is one fact whatever follows the comma), the newest ``WAITING``
at most.
What is kept goes to the store.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

WORDS = ("/memory", "/remember")
FILE = "offered.json"
#: The most memories ``/memory`` lists in one message.
LISTED = 30
#: The most candidates waiting for one person; the oldest go first.
WAITING = 12

NOTHING_HERE = "{agent} doesn't keep memories about the people it talks to."
NO_STORE = ("Your memories aren't open for you here yet. The owner can give "
            "you a place for them.")


def word_of(text: str) -> str | None:
    """``/memory`` or ``/remember`` (Telegram's ``@bot`` dropped), else None."""
    first = text.strip().split(maxsplit=1)[:1]
    if not first:
        return None
    word = first[0].split("@")[0].lower()
    return word if word in WORDS else None


def rest_of(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


@dataclass(frozen=True)
class Offer:
    """One sentence the look back proposed, waiting for the person's word."""

    statement: str
    kind: str = "fact"


class Offered:
    """Each person's latest list of candidates, by number."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            return {}           # a broken list costs the offer, never the chat
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        spare = self.path.with_suffix(".tmp")
        fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=1)
        os.replace(spare, self.path)

    def add(self, actor: str, agent: str, offers: list[Offer], *,
            replace: bool = False) -> int:
        """``offers`` join what this person has waiting (or, ``replace``,
        take its place); how many were new. A fact already waiting is
        not added again (``same``)."""
        data = self._read()
        waiting = [] if replace else self.get(actor)
        fresh: list[Offer] = []
        for o in offers:
            if not any(same(o.statement, w.statement) for w in waiting + fresh):
                fresh.append(o)
        if not fresh and not replace:
            return 0
        kept = (waiting + fresh)[-WAITING:]
        if kept:
            data[actor] = {"agent": agent,
                           "at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "items": [{"statement": o.statement, "kind": o.kind}
                                     for o in kept]}
        else:
            data.pop(actor, None)
        self._write(data)
        return len(fresh)

    def get(self, actor: str) -> list[Offer]:
        entry = self._read().get(actor) or {}
        return [Offer(i["statement"], i.get("kind") or "fact")
                for i in entry.get("items", []) if i.get("statement")]

    def take(self, actor: str, chosen: list[int]) -> list[Offer]:
        """The chosen ones (1-based), removed from the list; the rest stay."""
        data = self._read()
        offers = self.get(actor)
        taken = [offers[n - 1] for n in chosen]
        left = [o for i, o in enumerate(offers, 1) if i not in chosen]
        if left:
            data[actor]["items"] = [{"statement": o.statement, "kind": o.kind} for o in left]
        else:
            data.pop(actor, None)
        self._write(data)
        return taken


_NUMBER = re.compile(r"\d+")


_WORD = re.compile(r"[a-z0-9]+")
_HEAD_END = re.compile(r"[,;(:\u2014\u2013]| - ")


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 1}


def _head(text: str) -> set[str]:
    """The words of a fact before its first comma, semicolon, bracket or
    dash: what it is about, without what a model said around it."""
    return _words(_HEAD_END.split(text, maxsplit=1)[0])


def same(a: str, b: str) -> bool:
    """Whether two candidates are one fact: one's head inside the other's
    head ("Lives in Pune" and "Lives in Pune, India"), or the same words."""
    ha, hb = _head(a), _head(b)
    if ha and hb and (ha <= hb or hb <= ha):
        return True
    return _words(a) == _words(b)


def chosen(rest: str, count: int) -> list[int] | str:
    """The numbers asked for, or the words saying why not."""
    if not count:
        return "There's nothing waiting to be kept. I list what I noticed when you send /new."
    if rest.lower() in ("all", "everything", "*"):
        return list(range(1, count + 1))
    numbers = sorted({int(n) for n in _NUMBER.findall(rest)})
    if not numbers:
        return "Which ones? Send /remember with their numbers (/remember 1 3), or /remember all."
    wrong = [n for n in numbers if not 1 <= n <= count]
    if wrong:
        return (f"I listed {count} thing{'s' if count != 1 else ''}; there's no "
                f"{', '.join(map(str, wrong))}. Send /remember to see them again.")
    return numbers


def listing(offers: list[Offer], *, head: str) -> str:
    """The numbered list a person answers with ``/remember``."""
    lines = [head]
    lines += [f"{n}. {o.statement}" for n, o in enumerate(offers, 1)]
    lines.append("Send /remember with the numbers to keep them (/remember 1 2), or "
                 "/remember all. Nothing is kept unless you do.")
    return "\n".join(lines)


def looked_back(offers: list[Offer], *, quiet: bool = False) -> str:
    return listing(offers, head=("Looking back over our conversation, I noticed this "
                                 "about you:" if quiet else
                                 "Before we started over, I noticed this about you:"))


def noticed(new: int) -> str:
    """The one line under an answer when the turn noticed something."""
    things = "a thing" if new == 1 else f"{new} things"
    return (f"(I noticed {things} about you worth remembering. "
            "Send /remember to see what's waiting.)")


def kept_words(statements: list[str]) -> str:
    if not statements:
        return "Nothing was kept."
    return "Kept:\n" + "\n".join(f"- {s}" for s in statements)


def memory_list(items, short) -> str:
    """``/memory``: what is kept, each with the id to forget it by."""
    if not items:
        return ("I don't remember anything about you yet. When something is worth "
                "keeping, I'll ask you first.")
    shown = items[:LISTED]
    lines = [f"What I remember about you ({len(items)}):"]
    lines += [f"#{short(i.id)}  {i.statement}" for i in shown]
    if len(items) > LISTED:
        lines.append(f"…and {len(items) - LISTED} more.")
    lines.append("Send /memory forget ID to remove one (/memory forget "
                 f"{short(shown[0].id)}).")
    return "\n".join(lines)

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
    /remember not 2      not that one, and never offered again
    /remember none       none of it, never offered again

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

WHAT THEY TURNED DOWN STAYS TURNED DOWN. A list nobody answers is
replaced at the next ``/new``, and the look back reads the same person
the same way, so a fact they never wanted came back every time they
started over. ``/remember not 1 2`` drops those and keeps their words in
the same file as declined (``DECLINED`` at most, the oldest go first);
a candidate that is ``same`` as one declined is never offered again.
Declining opens no store and asks no model. A fact reworded past
``same`` can still come back once; declining it again covers that
wording too.
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
#: The most declined facts remembered for one person; the oldest go first.
DECLINED = 200
#: The words that turn the numbers down instead of keeping them.
NOT = ("not", "no", "skip", "ignore", "drop", "never", "forget")
#: The words that turn down everything waiting.
NONE = ("none", "neither", "nothing")

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
        declined = self.declined(actor)
        fresh: list[Offer] = []
        for o in offers:
            if any(same(o.statement, d) for d in declined):
                continue
            if not any(same(o.statement, w.statement) for w in waiting + fresh):
                fresh.append(o)
        if not fresh and not replace:
            return 0
        kept = (waiting + fresh)[-WAITING:]
        self._put(data, actor, kept, declined, agent=agent)
        self._write(data)
        return len(fresh)

    def _put(self, data: dict, actor: str, items: list[Offer], declined: list[str],
             *, agent: str | None = None) -> None:
        """This person's entry, or none when nothing waits or was declined."""
        if not items and not declined:
            data.pop(actor, None)
            return
        entry = data.get(actor) or {}
        if agent is not None:
            entry["agent"] = agent
            entry["at"] = datetime.now(UTC).isoformat(timespec="seconds")
        entry["items"] = [{"statement": o.statement, "kind": o.kind} for o in items]
        if declined:
            entry["declined"] = declined[-DECLINED:]
        else:
            entry.pop("declined", None)
        data[actor] = entry

    def get(self, actor: str) -> list[Offer]:
        entry = self._read().get(actor) or {}
        return [Offer(i["statement"], i.get("kind") or "fact")
                for i in entry.get("items", []) if i.get("statement")]

    def declined(self, actor: str) -> list[str]:
        """What this person turned down, never to be offered again."""
        entry = self._read().get(actor) or {}
        return [d for d in entry.get("declined", []) if isinstance(d, str) and d]

    def take(self, actor: str, chosen: list[int], *,
             decline: bool = False) -> list[Offer]:
        """The chosen ones (1-based), removed from the list; the rest stay.
        ``decline``: their words are kept as turned down instead."""
        data = self._read()
        offers = self.get(actor)
        taken = [offers[n - 1] for n in chosen]
        left = [o for i, o in enumerate(offers, 1) if i not in chosen]
        declined = self.declined(actor)
        if decline:
            declined += [o.statement for o in taken]
        self._put(data, actor, left, declined)
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


def declining(rest: str) -> tuple[bool, str]:
    """Whether ``/remember …`` turns the numbers down (``not 1 2``,
    ``none``), and what is left to read the numbers from."""
    words = rest.split(maxsplit=1)
    first = words[0].lower() if words else ""
    if first in NONE:
        return True, "all"
    if first in NOT:
        return True, words[1] if len(words) > 1 else ""
    return False, rest


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
                 "/remember all. Nothing is kept unless you do. /remember not 1 2 "
                 "(or /remember none) and I won't offer those again.")
    return "\n".join(lines)


def looked_back(offers: list[Offer], *, quiet: bool = False,
                ended: bool = False) -> str:
    """``quiet``: the chat went quiet. ``ended``: the one /new just ended,
    looked back over after the fresh start was already answered."""
    head = ("Looking back over our conversation, I noticed this about you:" if quiet
            else "Looking back over the conversation we just ended, I noticed this "
                 "about you:" if ended
            else "Before we started over, I noticed this about you:")
    return listing(offers, head=head)


def noticed(new: int) -> str:
    """The one line under an answer when the turn noticed something."""
    things = "a thing" if new == 1 else f"{new} things"
    return (f"(I noticed {things} about you worth remembering. "
            "Send /remember to see what's waiting.)")


def declined_words(statements: list[str]) -> str:
    return "I won't offer these again:\n" + "\n".join(f"- {s}" for s in statements)


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

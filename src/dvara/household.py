"""What everyone in the house may know, beside what each person's own is.

Note 37 made every memory one person's: their name in the store, their
own key, and nobody else's facts one model mistake away. That is right
for "Priya flies from RDU", and wrong for "the wifi password is on the
fridge" or "bins go out Tuesday night", which the owner would otherwise
have to tell every person's agent separately, and keep in step by hand.

    /remember for everyone the bins go out Tuesday night
    /household              what everyone's agents know, numbered
    /household forget 2     that one, gone          (the owner)
    /household yes 1        keep what was offered   (the owner)
    /household no 1         and not that            (the owner)

THE OWNER WRITES IT; ANYONE MAY OFFER. A fact every agent in the house
reads is a fact every person in the house is told, so it is the owner's
word that puts it there (``--owner``, which Sarathi passes). Anybody else
who says ``/remember for everyone`` offers it: the owner is sent the
offer with its number, and it is kept on their yes. With no owner named
an offer has nobody to go to, and is refused with the reason.

A FILE BESIDE THE PEOPLE, NOT A STORE. Each person's memories live in
the store the owner chose (memory.py), searched by meaning because a
person's facts pile up. The household's are few, written on purpose and
true for everybody, so they are shown WHOLE in every turn of every agent
(Yantra's ``household`` prompt layer), the way a note on the fridge is
seen without being searched for. A search could miss one, and a missed
"bins go out Tuesday" is the whole failure. That also means it needs no
key and no store at all: a house on the built-in memory has it too.
``<state>/household.json``, readable by the owner alone, holds it.

EVERY AGENT, NOT ONLY ONE THAT REMEMBERS. ``[memory]`` in a package says
whether its agent keeps what PEOPLE tell it, which is about them. These
are the owner's own notes to every agent in the house, so a package that
keeps nothing about anybody is still told them.

SMALL ON PURPOSE. ``MOST`` facts of ``LONGEST`` characters at most: the
layer goes into every turn, and a small local model's window is where
an overgrown one is paid for. A fact past either is refused with the
reason, never cut.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

FILE = "household.json"
#: The most facts kept for everyone, and the longest one.
MOST, LONGEST = 40, 300
#: The words that start a household fact, after ``/remember``.
FOR_EVERYONE = ("for everyone", "for everybody", "for the house", "for the household")
WORD = "/household"


class HouseholdProblem(ValueError):
    """A fact that can't be kept, said in words the person can act on."""


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    by: str
    at: str


class Household:
    """The household's facts and the offers waiting on the owner."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def _read(self) -> dict:
        try:
            raw = json.loads(self.path.read_text())
        except FileNotFoundError:
            return {"facts": [], "offered": []}
        except (OSError, json.JSONDecodeError):
            return {"facts": [], "offered": []}
        return {k: [Fact(**f) for f in raw.get(k, []) if isinstance(f, dict)]
                for k in ("facts", "offered")}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {k: [asdict(f) for f in v] for k, v in data.items()}
        tmp = self.path.with_name(f".{FILE}.{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(body, out, indent=2)
            out.write("\n")
        os.replace(tmp, self.path)

    def facts(self) -> list[Fact]:
        return self._read()["facts"]

    def offered(self) -> list[Fact]:
        return self._read()["offered"]

    def add(self, text: str, by: str) -> Fact:
        """Kept for everyone, on the owner's word."""
        data = self._read()
        fact = self._fact(text, by, data["facts"])
        if len(data["facts"]) >= MOST:
            raise HouseholdProblem(f"there are already {MOST} things everyone knows; "
                                   "forget one first (/household forget N)")
        data["facts"].append(fact)
        self._write(data)
        return fact

    def offer(self, text: str, by: str) -> Fact:
        """Waiting for the owner's yes."""
        data = self._read()
        fact = self._fact(text, by, data["facts"] + data["offered"])
        data["offered"] = (data["offered"] + [fact])[-MOST:]
        self._write(data)
        return fact

    def take(self, which: str, *, keep: bool) -> Fact:
        """An offer kept (``keep``) or turned down, by number or id."""
        data = self._read()
        fact = _pick(data["offered"], which, "offered")
        data["offered"] = [f for f in data["offered"] if f.id != fact.id]
        if keep:
            if len(data["facts"]) >= MOST:
                raise HouseholdProblem(f"there are already {MOST} things everyone "
                                       "knows; forget one first")
            data["facts"].append(fact)
        self._write(data)
        return fact

    def forget(self, which: str) -> Fact:
        data = self._read()
        fact = _pick(data["facts"], which, "kept")
        data["facts"] = [f for f in data["facts"] if f.id != fact.id]
        self._write(data)
        return fact

    def layer(self) -> str | None:
        """The prompt layer every turn gets; None with nothing kept."""
        facts = self.facts()
        if not facts:
            return None
        lines = "\n".join(f"- {f.text}" for f in facts)
        return ("## The household\n"
                "True for everyone in this house, whoever you are talking to "
                "(kept by the owner):\n" + lines)

    @staticmethod
    def _fact(text: str, by: str, already: list[Fact]) -> Fact:
        text = " ".join((text or "").split())
        if not text:
            raise HouseholdProblem("say what everyone should know, after "
                                   "/remember for everyone")
        if len(text) > LONGEST:
            raise HouseholdProblem(f"that's {len(text)} characters; keep it under "
                                   f"{LONGEST}, one fact at a time")
        if any(f.text.lower() == text.lower() for f in already):
            raise HouseholdProblem("that one is already there")
        return Fact(id=secrets.token_hex(3), text=text, by=by,
                    at=datetime.now(UTC).isoformat(timespec="seconds"))


def _pick(facts: list[Fact], which: str, what: str) -> Fact:
    which = (which or "").strip().lstrip("#")
    if which.isdigit() and 1 <= int(which) <= len(facts):
        return facts[int(which) - 1]
    for fact in facts:
        if fact.id == which:
            return fact
    raise HouseholdProblem(f"there's no {what} #{which or '?'}; send /household to see them")


# ---- the chat's words ---------------------------------------------------------

def for_everyone(text: str) -> str | None:
    """The fact after ``/remember for everyone``; None for any other words."""
    words = text.strip()
    if not words.lower().startswith("/remember"):
        return None
    rest = words[len("/remember"):].strip()
    for lead in FOR_EVERYONE:
        if rest.lower().startswith(lead):
            return rest[len(lead):].strip(" :,-")
    return None


def is_word(text: str) -> bool:
    return text.strip().lower().split()[:1] == [WORD]


def listing(house: Household, *, owner: bool) -> str:
    facts = house.facts()
    out = (["What everyone's agents know here:"]
           + [f"{i}. {f.text}" for i, f in enumerate(facts, 1)]
           if facts else ["Nothing is kept for everyone yet. "
                          "Say /remember for everyone <what> to add one."])
    offered = house.offered()
    if owner and offered:
        out += ["", "Offered, waiting on you (/household yes N, /household no N):"]
        out += [f"{i}. {f.text} -- from {f.by}" for i, f in enumerate(offered, 1)]
    if owner and facts:
        out += ["", "/household forget N takes one away."]
    return "\n".join(out)


def offer_notice(fact: Fact, number: int) -> str:
    return (f"{fact.by} offers this for everyone's agents to know:\n"
            f"\"{fact.text}\"\n"
            f"/household yes {number} to keep it, /household no {number} to not.")

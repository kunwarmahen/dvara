"""Each person's memory, kept as theirs.

A package decides WHETHER its agent remembers the people it talks to
(``[memory] via`` in its agent.toml; nothing said means nothing kept).
This module decides WHOSE memories a turn reads and writes, and, when the
owner named one, WHERE they are kept.

THEIR NAME, NEVER THE MACHINE'S. Yantra files memories under
``$YANTRA_USER``, else the login name -- right for a person at their own
terminal, and wrong behind a door, where it would file every person's
"lives near RDU" under the owner's login and read it back to anybody who
asked. So every turn names its person: their id in the actors file, or
the name ``memory.json`` gives them in the store (the owner, say, whose
store already knows them by their login name).

THE OWNER CHOOSES THE STORE, THE PACKAGE ONLY WHETHER. ``--memory FILE``
names one MCP server, in the format of Yantra's ``--mcp-config``, that
keeps memories somewhere better than the built-in file (Smritikosh,
which searches by meaning). A package that asks for memory -- ``local``
or any store -- then gets that one. The server starts beside each turn,
for that person, and stops when the turn ends, like Samay's (one server
per turn, so nothing outlives the turn that could carry one person's
memories into another's). Its settings may say ``${DVARA_MEMORY_USER}``
and ``${DVARA_MEMORY_KEY}``, which become the person's name in the store
and their own key there.

ONE KEY EACH. ``<state>/memory.json`` holds every person's key, readable
by the owner alone, the way ``sarathi smritikosh`` writes it::

    {"people": {"owner": {"user": "asha", "key": "sk-..."},
                "priya": {"user": "dvara-priya", "key": "sk-..."}}}

A PERSON WITH NO KEY GETS NO MEMORY, never somebody else's: the turn goes
on without it and the owner is told once. A store key that reads
everybody's would make one model mistake enough to show one person
another's facts; a key per person makes it impossible.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

#: Where each person's name and key in the store live, under --state.
PEOPLE_FILE = "memory.json"
#: The two words a store's settings may use for this turn's person.
USER_REF, KEY_REF = "DVARA_MEMORY_USER", "DVARA_MEMORY_KEY"
_REF = re.compile(r"\$\{(" + USER_REF + "|" + KEY_REF + r")\}")


class MemoryProblem(ValueError):
    """A store file or a people file that cannot be used."""


@dataclass(frozen=True)
class Person:
    """Whose memories a turn reads, and the key that opens only those."""

    user: str
    key: str | None = None


def people(state: Path) -> dict[str, Person]:
    """``memory.json`` read now (it is rewritten while the door runs, when
    a new person is given an account); empty when there is none."""
    path = Path(state) / PEOPLE_FILE
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise MemoryProblem(f"{path}: {exc}") from None
    table = raw.get("people") if isinstance(raw, dict) else None
    if not isinstance(table, dict):
        raise MemoryProblem(f"{path}: expected {{\"people\": {{ID: {{user, key}}}}}}")
    out = {}
    for actor, entry in table.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("user", actor), str):
            raise MemoryProblem(f"{path}: people.{actor} must be {{user, key}}")
        key = entry.get("key")
        out[actor] = Person(user=entry.get("user") or actor,
                            key=key if isinstance(key, str) and key else None)
    return out


def person(state: Path, actor: str) -> Person:
    """This person's name in the store: memory.json's, else their id."""
    return people(state).get(actor) or Person(user=actor)


def write_people(state: Path, table: dict[str, Person]) -> Path:
    """memory.json, readable by its owner alone from the first byte."""
    path = Path(state) / PEOPLE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"people": {actor: {"user": p.user, **({"key": p.key} if p.key else {})}
                       for actor, p in sorted(table.items())}}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(body, out, indent=2)
        out.write("\n")
    os.chmod(path, 0o600)
    return path


@dataclass(frozen=True)
class Store:
    """The owner's store: one MCP server, started per turn per person."""

    name: str
    server: dict
    where: str

    @classmethod
    def load(cls, path: Path) -> Store:
        """Read now, so a broken file stops the start where the owner is."""
        try:
            raw = json.loads(Path(path).read_text())
        except FileNotFoundError:
            raise MemoryProblem(f"--memory: no such file: {path}") from None
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryProblem(f"--memory {path}: {exc}") from None
        servers = raw.get("servers") if isinstance(raw, dict) else None
        if not isinstance(servers, dict) or len(servers) != 1:
            raise MemoryProblem(f"--memory {path}: name exactly one server, as "
                                "{\"servers\": {NAME: {command, args, env}}}")
        (name, server), = servers.items()
        if not isinstance(server, dict) or not server.get("command"):
            raise MemoryProblem(f"--memory {path}: server {name!r} has no command")
        from yantra.memory import check_mode

        try:
            check_mode(name, "--memory")
        except ValueError as exc:
            raise MemoryProblem(str(exc)) from None
        if name in ("local", "off"):
            raise MemoryProblem(f"--memory {path}: {name!r} is not a server's name")
        return cls(name=name, server=server, where=str(path))

    def config_for(self, who: Person):
        """The server's settings with this person's name and key in them."""
        from yantra.mcp import parse_mcp_text

        if who.key is None:
            raise MemoryProblem("no key of their own in " + PEOPLE_FILE)
        words = {USER_REF: who.user, KEY_REF: who.key}

        def fill(value):
            if isinstance(value, str):
                return _REF.sub(lambda m: words[m.group(1)], value)
            if isinstance(value, list):
                return [fill(v) for v in value]
            if isinstance(value, dict):
                return {k: fill(v) for k, v in value.items()}
            return value

        configs = parse_mcp_text(json.dumps({"servers": {self.name: fill(self.server)}}))
        return configs[0]


__all__ = ["KEY_REF", "PEOPLE_FILE", "USER_REF", "MemoryProblem", "Person", "Store",
           "people", "person", "write_people"]

"""Actors: who is allowed to talk to what, and what they may spend.

Yantra's entire world is "the operator" -- the person at the keyboard,
present, trusted and singular. None of those three survive a service, and
this module is where the missing noun gets defined.

AN ACTOR IS ASSIGNED, NEVER ASSERTED. Nothing that arrives from outside
gets to say who it is. A channel adapter maps its own native identity (a
Telegram user id, say) onto an actor id from a file the owner wrote, and
an id that is not in that file is not served. The whole security model of
a personal service rests on that sentence, so the file is deliberately
boring: TOML, reviewable, diffable, and it holds no secrets.

    [actor.mahen]
    agents           = ["researcher"]   # omit => every agent in the roster
    max_usd_per_turn = 0.25
    max_usd_per_day  = 2.00

``agents`` follows ``AgentSpec.tool_allow``'s convention exactly: absent
means everything, a list is a COMPLETE whitelist, and an empty list is an
error rather than a silent "this person may reach nothing" -- because an
empty allowlist is far likelier to be a bug than an intention.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from dvara.errors import ConfigProblem, Refused

#: Keys an actor table may carry. UNKNOWN KEYS ARE ERRORS: a misspelled
#: ``max_usd_per_day`` that quietly means "no ceiling" is the exact
#: failure a ceiling exists to prevent (the same rule Yantra's package
#: loader applies to ``agent.toml``).
ACTOR_KEYS = frozenset({"agents", "max_usd_per_turn", "max_usd_per_day"})


@dataclass(frozen=True)
class Actor:
    """One person the owner has decided to serve."""

    id: str
    #: None means every agent in the roster; a tuple is a complete whitelist.
    agents: tuple[str, ...] | None = None
    max_usd_per_turn: float | None = None
    max_usd_per_day: float | None = None

    def may_use(self, agent: str) -> bool:
        return self.agents is None or agent in self.agents


class ActorBook:
    """The owner's roster of people, loaded from one TOML file."""

    def __init__(self, actors: dict[str, Actor]) -> None:
        self._actors = dict(actors)

    def __len__(self) -> int:
        return len(self._actors)

    def ids(self) -> list[str]:
        return sorted(self._actors)

    def get(self, actor_id: str) -> Actor:
        """The actor, or a refusal.

        The refusal says nothing about who else exists. A stranger probing
        a bot learns only that they are not on the list.
        """
        try:
            return self._actors[actor_id]
        except KeyError:
            raise Refused("you are not on this service's list of people") from None

    def may(self, actor_id: str, agent: str) -> Actor:
        """The actor, having checked they may reach ``agent``."""
        actor = self.get(actor_id)
        if not actor.may_use(agent):
            raise Refused(f"you do not have access to the agent {agent!r}")
        return actor

    @classmethod
    def from_toml(cls, path: Path) -> ActorBook:
        """Parse the owner's file, complaining loudly about every mistake."""
        path = Path(path).expanduser()
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ConfigProblem(f"no actors file at {path}") from None
        except tomllib.TOMLDecodeError as exc:
            raise ConfigProblem(f"{path}: {exc}") from None
        return cls.from_dict(raw, where=path)

    @classmethod
    def from_dict(cls, raw: dict, *, where: Path | str = "<memory>") -> ActorBook:
        table = raw.get("actor")
        if not isinstance(table, dict) or not table:
            raise ConfigProblem(
                f"{where}: no [actor.NAME] tables -- a service with no "
                f"actors can serve nobody"
            )
        actors = {}
        for name, body in table.items():
            if not isinstance(body, dict):
                raise ConfigProblem(f"{where}: [actor.{name}] must be a table")
            unknown = sorted(set(body) - ACTOR_KEYS)
            if unknown:
                raise ConfigProblem(
                    f"{where}: [actor.{name}] has unknown key(s) "
                    f"{', '.join(unknown)}; known: "
                    f"{', '.join(sorted(ACTOR_KEYS))}"
                )
            actors[name] = Actor(
                id=name,
                agents=_agents(body.get("agents"), name, where),
                max_usd_per_turn=_money(body, "max_usd_per_turn", name, where),
                max_usd_per_day=_money(body, "max_usd_per_day", name, where),
            )
        return cls(actors)


def _agents(value, name: str, where) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigProblem(f"{where}: [actor.{name}] agents must be a list of names")
    if not value:
        raise ConfigProblem(
            f"{where}: [actor.{name}] agents is present but empty, which "
            f"would leave this person no agents at all; omit the key to "
            f"allow every agent in the roster"
        )
    return tuple(value)


def _money(body: dict, key: str, name: str, where) -> float | None:
    value = body.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigProblem(f"{where}: [actor.{name}] {key} must be a number")
    if value <= 0:
        raise ConfigProblem(
            f"{where}: [actor.{name}] {key} must be greater than zero "
            f"(got {value}); a ceiling of nothing is a refusal to serve "
            f"this person, which is done by leaving them out of the file"
        )
    return float(value)

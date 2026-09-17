"""dvara -- the door your agents live behind.

Yantra makes an agent you can name, hand to someone, meter and gate: a
directory with an ``agent.toml`` in it. dvara is where those directories
live once you stop watching them -- one process, many people, many
agents, many conversations, and the owner's money and permissions around
all of it.

The whole of it, in one call::

    from pathlib import Path
    from dvara import ActorBook, Roster, Service

    service = Service(
        roster=Roster(Path("~/agents")),
        actors=ActorBook.from_toml(Path("~/dvara/actors.toml")),
        state=Path("~/dvara/state"),
    )
    reply = await service.deliver(actor="mahen", agent="researcher",
                                  thread="cli", text="what changed today?")

Two rules run through every module here, and both are stated where they
are enforced rather than promised:

* **dvara never parses ``agent.toml``.** It calls Yantra's
  ``load_package``. One parser, in the framework, with the tests.
* **The dependency edge runs one way.** dvara imports Yantra; Yantra
  never learns dvara exists. When this package needs a seam that does not
  exist -- an awaitable permission gate, for instance -- that is a Yantra
  feature argued on Yantra's terms, not a special case for a caller the
  framework is not supposed to know about.
"""

from dvara.actors import Actor, ActorBook, Channel
from dvara.asks import Answer, Ask, AskDesk, NotYours
from dvara.errors import ConfigProblem, DvaraError, Refused
from dvara.gate import Policy
from dvara.keys import parse_key, session_key
from dvara.money import Ceiling, compose, day_start, next_reset
from dvara.roster import Roster
from dvara.runs import Run, RunStore
from dvara.service import Reply, Service

__all__ = [
    "Actor",
    "ActorBook",
    "Answer",
    "Ask",
    "AskDesk",
    "Ceiling",
    "Channel",
    "ConfigProblem",
    "DvaraError",
    "NotYours",
    "Policy",
    "Refused",
    "Reply",
    "Roster",
    "Run",
    "RunStore",
    "Service",
    "compose",
    "day_start",
    "next_reset",
    "parse_key",
    "session_key",
]

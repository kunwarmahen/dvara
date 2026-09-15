"""The roster: which agents exist, resolved by NAME from one owner root.

This module is the one whose failure is catastrophic, so it is the one
with the shortest job: turn a name into an ``AgentSpec``, and refuse
every name that is not plainly a directory the owner put in the root.

Why it matters is stated in Yantra's note 32. Building an agent from a
package RUNS ITS PYTHON -- ``tools/*.py`` is imported as the invoking
user, at import time, before any permission gate exists. That is normal
and fine for a package a human chose. It stops being fine the instant a
package path can come from a message, a webhook body, or a string a model
produced. A service that let a Telegram message name a path would be
handing remote code execution to anyone who can find the bot.

So: NAMES, NEVER PATHS. One path segment, matched against a conservative
pattern, joined to the owner's root, and then -- after ``resolve()`` --
checked to still be INSIDE that root, because a symlink is a path that
lies about where it goes. Three cheap checks, and every one of them has
to fail closed.

``load_package`` itself imports nothing (it parses TOML and names
directories), which is what lets ``names()`` list a whole root without
executing a line of anyone's code. Code runs later, in ``spec.build_*``,
at the moment a human's request actually reached an agent.
"""

from __future__ import annotations

import re
from pathlib import Path

from yantra import AgentSpec, load_package
from yantra.errors import ConfigError
from yantra.package import MANIFEST

from dvara.errors import ConfigProblem, Refused

#: One path segment: starts alphanumeric, then alphanumerics, dot, dash,
#: underscore. Rejects "..", "a/b", "/etc/passwd", "~", hidden dirs and
#: anything with a NUL or a newline in it -- by ALLOWING a short list
#: rather than by denying a long one, which is the only version of this
#: check that stays correct as people invent new ways to write a path.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class Roster:
    """Every agent package under one owner-controlled directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ConfigProblem(f"agent root is not a directory: {self.root}")

    def names(self) -> list[str]:
        """Sorted names of every directory here that holds an ``agent.toml``.

        A pure read: no package is loaded and no package's code runs.
        """
        found = []
        for child in self.root.iterdir():
            if child.is_dir() and NAME.match(child.name) \
                    and (child / MANIFEST).is_file():
                found.append(child.name)
        return sorted(found)

    def path(self, name: str) -> Path:
        """The package directory for ``name``, or a ``Refused``.

        The escape check is the point. ``(root / name).resolve()`` follows
        symlinks; ``is_relative_to(root)`` then asks whether we are still
        where we meant to be. Without it, ``ln -s / evil`` inside the root
        turns a name into any path on the machine.
        """
        if not NAME.match(name or ""):
            raise Refused(f"no agent called {name!r} here")
        candidate = (self.root / name).resolve()
        if not candidate.is_relative_to(self.root):
            raise Refused(f"no agent called {name!r} here")
        if not (candidate / MANIFEST).is_file():
            raise Refused(f"no agent called {name!r} here")
        return candidate

    def spec(self, name: str) -> AgentSpec:
        """The package's ``AgentSpec``.

        dvara NEVER parses ``agent.toml``. One parser lives in Yantra,
        with Yantra's tests; a second dialect is how two formats that
        disagree get born.

        A manifest that does not parse is the OWNER's problem, not the
        asker's, so it does not leak upward as a chatty error: the person
        who typed a message learns the agent is unavailable, and the
        service's log carries the real reason.
        """
        where = self.path(name)
        try:
            return load_package(where)
        except ConfigError as exc:
            raise Refused(
                f"the agent {name!r} is unavailable -- its owner needs to "
                f"fix its manifest"
            ) from exc

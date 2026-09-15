"""The permission gate when nobody is in the room.

The contract: dvara consumes a package's ``permissions.mode`` as a FLOOR
IT MAY TIGHTEN BUT NEVER LOOSEN. A package that ships ``mode = "yolo"``
does not get yolo because it asked; it gets yolo only if the owner of the
machine it runs on also said so.

Then the sentence that decides what v1 is: "ask" WITH NOBODY PRESENT IS
NOT A QUESTION, IT IS A HANG. There is no human attached to a service at
three in the morning, so a gate that waits for one either blocks forever
or lies. dvara's answer is to decide by policy alone -- tools that
declared ``read_only`` are approved, everything else is denied -- and to
let the denial arrive as DATA, which is what Yantra's gate already does:
a denied call becomes an error result the model can read and route
around, never an exception that kills the turn.

Two things this leaves open, both recorded rather than hidden:

* ``read_only`` is the tool author's own declaration and nothing checks
  it. An author who writes ``read_only = True`` on a tool that deletes
  files has lied to this gate, and no service can catch that. It is the
  same trust a package asks for when it ships ``tools/*.py`` at all.
* A real "ask" -- escalating to a person over the channel they are
  already in -- needs something Yantra does not have: ``PermissionFn`` is
  synchronous and ``AsyncAgent`` calls it inline inside the running
  coroutine, so a gate that waited for a human would block the event loop
  and every other conversation with it. That is a missing seam in the
  framework, not a puzzle to solve here with a thread and a queue.
"""

from __future__ import annotations

from dataclasses import dataclass

from yantra import PermissionFn, allow_read_only, yolo

#: Strictest first. Yantra's MODES in the one order that lets "tighten,
#: never loosen" be a comparison instead of a paragraph.
LADDER = ("ask", "yolo")


def stricter(left: str | None, right: str | None) -> str:
    """The tighter of two modes; unknown or absent reads as the tightest."""
    rank = {mode: i for i, mode in enumerate(LADDER)}
    return min(
        (left or LADDER[0], right or LADDER[0]),
        key=lambda mode: rank.get(mode, 0),
    )


@dataclass(frozen=True)
class Policy:
    """What the OWNER allows, independent of what any package asks for."""

    mode: str = "ask"

    def effective(self, package_mode: str | None) -> str:
        return stricter(self.mode, package_mode)

    def gate(self, package_mode: str | None) -> PermissionFn:
        """The ``PermissionFn`` one turn runs under.

        Yantra's own two functions, chosen between -- not wrapped. A
        wrapper here would be a third place a permission decision is
        made, and there is no third decision to make.
        """
        if self.effective(package_mode) == "yolo":
            return yolo
        return allow_read_only

"""A turn watched while it runs: the words as they come, each step as a line.

A channel used to get one thing from a turn, its answer, and nothing
until then. On a page that is a chat that sits still for a minute and
then fills; on Telegram it is "typing…" with no way to tell working from
stuck. Yantra's own page shows the work as it happens, and a person
talking through this service should see the same.

THE PERSON SEES WHAT THEIR AGENT DOES, NEVER WHAT IT READ. A step is the
tool and its one-line summary -- the same words a question about it
would show them (``tool.summary``) -- and whether it worked. A tool's
output stays out: it can be a whole inbox, a page of somebody's site,
or the owner's rule that refused it, and the answer is where the agent
says what of it matters.

A WATCHER CANNOT COST THE TURN. It is a plain function, called inline
from the loop that is already reading the events. One that raises is
dropped for the rest of the turn; the answer still arrives.

``deliver(..., watch=)`` and ``resume(..., watch=)`` take one. Each call
gets a small dict:

* ``{"kind": "text", "text": ...}`` -- part of the answer, as written;
* ``{"kind": "using", "tool": ...}`` -- the model has chosen a tool;
* ``{"kind": "step", "tool", "said", "ok", "refused"}`` -- it ran (or
  was refused: ``refused`` is the gate's code, never a sentence).

``Live`` is that stream kept as a page draws it: text run together,
steps between.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from yantra import TextDelta, ToolCallStart, ToolExecuted

#: One event, as a channel gets it.
Watcher = Callable[[dict], None]

#: The longest step line handed on; a summary is one line, and a long
#: command is still that command.
SAID_AT_MOST = 200
#: Steps a live view keeps; a turn of sixty calls shows its last ones.
STEPS_KEPT = 40


def said(agent: Any, call: Any) -> str:
    """The step's one line: the tool's own summary, as a question shows it."""
    try:
        line = agent._get_visible_tool(call.name).summary(call.arguments, agent.ctx)
    except Exception:          # a broken summary is a name, never a crash
        line = call.name
    line = " ".join(str(line).split())
    if not line.startswith(call.name):
        line = f"{call.name}: {line}"
    return line if len(line) <= SAID_AT_MOST else line[:SAID_AT_MOST - 1] + "…"


def shown(event: Any, agent: Any) -> dict | None:
    """One of Yantra's events, as a watcher gets it; None for the rest."""
    if isinstance(event, TextDelta):
        return {"kind": "text", "text": event.text} if event.text else None
    if isinstance(event, ToolCallStart):
        return {"kind": "using", "tool": event.name}
    if isinstance(event, ToolExecuted):
        return {"kind": "step", "tool": event.call.name, "said": said(agent, event.call),
                "ok": not event.result.is_error, "refused": event.refusal}
    return None


class Safely:
    """A watcher that can fail without the turn noticing."""

    def __init__(self, watch: Watcher | None) -> None:
        self._watch = watch

    def __call__(self, event: dict) -> None:
        if self._watch is None:
            return
        try:
            self._watch(event)
        except Exception:      # see the module docstring
            self._watch = None


class Live:
    """A running turn as a page draws it: text and steps in order."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.using: str | None = None

    def __call__(self, event: dict) -> None:
        kind = event.get("kind")
        if kind == "text":
            if self.items and "text" in self.items[-1]:
                self.items[-1]["text"] += event["text"]
            else:
                self.items.append({"text": event["text"]})
        elif kind == "using":
            self.using = event["tool"]
        elif kind == "step":
            self.using = None
            self.items.append({"step": event["said"], "ok": event["ok"],
                               "refused": event.get("refused")})
            steps = [i for i in self.items if "step" in i]
            if len(steps) > STEPS_KEPT:
                self.items.remove(steps[0])

    def as_dict(self) -> dict:
        return {"items": [dict(i) for i in self.items], "using": self.using}

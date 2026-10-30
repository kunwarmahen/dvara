"""A run in the ledger, step by step (Yantra's steps.py).

The ledger keeps a run's SHAPE on purpose (runs.py: names, not
arguments). What each step was given and what came back is in the run's
conversation, in the session store, where it always was. Yantra notes
each step's time, its wait for a yes and who gave it, beside that
conversation, under the turn's tag -- and Dvara tags every turn with its
run id (``agent.turn_tag``), so a run finds its own steps.

TWO READERS, TWO RULES. The door (``GET /runs/{id}/steps``, its own
token: Samay showing a schedule's run) gets the whole turn. The owner's
page follows its own rule (page.py): a person's words are theirs, so for
anybody else's run it shows the SHAPE -- which tools, when, how long,
who said yes, what was refused -- and not what the tools were given,
what they read, the pictures, or the answer.

A run whose conversation is gone (a schedule's is let go a week after,
``tidy``; a person's after ``/chats delete``) has no steps to show, and
says so. One whose chat merely moved on (``/new``) is still in the
person's kept conversations, where the web channel looks next (web.py,
past.py). A run from before the tags is found by its message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yantra import steps
from yantra.session import SessionStore

from dvara.keys import session_key
from dvara.runs import Run

GONE = ("its conversation is no longer kept (a schedule's run is let go a "
        "week after it ran; a deleted conversation is gone)")


class NoSteps(LookupError):
    """No such run, or nothing left to show of it."""


def timeline(sessions: SessionStore, run: Run | None, *, words: bool = True) -> dict:
    if run is None:
        raise NoSteps("no such run")
    payload = sessions.load_latest(session_key(run.actor, run.agent, run.thread))
    if payload is None:
        raise NoSteps(GONE)
    try:
        view = steps.timeline(payload, run.id)
    except LookupError:
        view = _by_message(payload, run.message)
    view["run"] = run.id
    return view if words else shape(view)


def _by_message(payload: dict, message: str) -> dict:
    count = len(steps.turns(payload))
    for n in range(count, 0, -1):
        view = steps.timeline(payload, n)
        if view["message"].strip() == (message or "").strip():
            return view
    raise NoSteps(GONE)


def shape(view: dict[str, Any]) -> dict[str, Any]:
    """The turn without anybody's words: tools, times, answers to asks."""
    out = {**view, "message": None, "answer": None, "words": False}
    out["steps"] = [{**s, "arguments": None, "result": None, "short": None,
                     "pictures": [], "pictured": len(s.get("pictures") or [])}
                    for s in view["steps"]]
    return out


def sessions_in(state: Path) -> SessionStore:
    return SessionStore(state / "sessions.sqlite3")

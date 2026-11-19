"""``/why``: what started the agent's last run, what let each step happen,
and what it went by about the person.

An agent that turns the heat on at two in the morning, or sends a
message nobody typed, leaves the person with one question, and until
now its answer was spread over four places: the schedule or watch that
started it (Samay's page, Prahari's page), what each call was allowed
by (the grants page, as counts), what each step did (``/steps``, for
the chat's own turns only), and what it believed about them (nowhere).
The ledger already kept the first two for every run (``came_by``, the
thread a program names, and each call's ``decided_by``), so ``/why``
reads them back in words, for the person's own runs and nobody else's:

    /why       your last run, any agent's: typed, scheduled or watched
    /why 2     the one before it (up to WHY_BACK)

WHAT LET IT HAPPEN, CALL BY CALL. A call that ran was let through by one
of four things, and the ledger says which: the person's yes on a
channel, a standing rule, a grant made ahead with a schedule, one yes
for the whole task -- or, with none of those, the rung (a look that
changes nothing needs no yes, and a person or agent on ``yolo`` asked
nobody). A refused call says why in the gate's own token, worded here.

WHAT IT WENT BY. Yantra notes, at each answer, which of the memories,
facts and guesses it was shown the answer drew on (its
``Memory.leaned``); Dvara keeps them with the run. That is a judgement
from words in the answer, not the model's own account of its reasons,
and the reply says so: "it seems to have gone by".

THE PERSON'S OWN, NOT A TURN. Answered here, never by a model, and it
costs nothing. A run is found by its person only (any of their agents'),
so ``/why`` can never show anyone else's.
"""

from __future__ import annotations

import re

from dvara.runs import CAME_BY_NAMES, Run

#: How far back ``/why N`` may reach.
WHY_BACK = 20
#: A step list longer than this is cut, with a count of the rest.
STEPS_SHOWN = 15

#: The gate's refusal tokens (Yantra's permissions.py), as a person says them.
REFUSALS = {
    "policy": "a rule or the rung said no",
    "user": "you said no",
    "timeout": "nobody answered in time",
    "unattended": "nobody was there to ask",
    "held": "it was waiting for a yes when the turn stopped",
    "needs_person": "it needed a person's yes and only a blanket yes was on offer",
    "out_of_time": "the day's waiting was used up",
    "unspecified": "the gate said no without saying why",
}

_SAMAY = re.compile(r"^samay-([0-9a-f]{6,})-")
_PRAHARI = re.compile(r"^prahari-([0-9a-f]{6,})-")
_VIDHI = re.compile(r"^vidhi-(.+)-[^-]+$")
_WATCH_NAME = re.compile(r'watching for the person: "([^"]+)"')


def word_of(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() == "/why"


def which(text: str) -> int | str:
    """1 for ``/why``, N for ``/why N``; words to send back otherwise."""
    rest = text.strip().split()[1:]
    if not rest:
        return 1
    if len(rest) == 1 and rest[0].isdigit() and 1 <= int(rest[0]) <= WHY_BACK:
        return int(rest[0])
    return f"Send /why for the last thing I did, or /why 2 … /why {WHY_BACK} for earlier ones."


def started_by(run: Run) -> str:
    """Who or what asked for this run, in a sentence."""
    if (found := _SAMAY.match(run.thread)) is not None:
        return f"Your schedule {found.group(1)} (Samay) started it; nobody typed it."
    if (found := _PRAHARI.match(run.thread)) is not None:
        name = _WATCH_NAME.search(run.message or "")
        what = f'"{name.group(1)}"' if name else found.group(1)
        return f"Your watch {what} (Prahari) saw what it was waiting for and started it."
    if (found := _VIDHI.match(run.thread)) is not None:
        return f"Your routine {found.group(1)} (Vidhi) started it."
    if run.thread.startswith("vaani:"):
        return f"You asked out loud, at the {run.thread.split(':', 1)[1]} puck."
    way = CAME_BY_NAMES.get(run.came_by or "")
    if run.unattended:
        return f"A program ({way or run.came_by or 'Dvara'}) started it; nobody typed it."
    return f"You asked, on {way}." if way else "You asked."


def asked(run: Run) -> str:
    """What the run was asked, without a program's framing in brackets."""
    text = (run.message or "").strip()
    if text.startswith("("):
        # the framing may hold brackets of its own ("(every hour)"): the
        # task starts after the bracket that closes the first one
        depth, end = 0, -1
        for i, ch in enumerate(text):
            depth += (ch == "(") - (ch == ")")
            if depth == 0:
                end = i
                break
        rest = text[end + 1:].strip() if end > 0 else ""
        text = rest.split("\n\n(", 1)[0].strip() or text
    text = " ".join(text.split())
    return text if len(text) <= 160 else text[:159] + "…"


def tool_words(name: str) -> str:
    """``mcp__homeassistant-home__call_service`` -> ``call_service (homeassistant-home)``."""
    if name.startswith("mcp__"):
        _, server, tool = (name.split("__", 2) + ["", ""])[:3]
        return f"{tool} ({server})" if tool else name
    return name


def let_through(step, *, rung: str | None) -> str:
    """Why one call happened, or why it didn't."""
    if not step.ran:
        return "refused: " + REFUSALS.get(step.refusal or "", step.refusal or "refused")
    kind, _, detail = (step.decided_by or "").partition(":")
    if kind == "asked":
        return f"you said yes{f' on {detail}' if detail else ''}"
    if kind == "rule":
        return f"your standing rule {detail} allows it"
    if kind == "ahead":
        return "the grant you gave the schedule allows it"
    if kind == "for_turn":
        return "your yes for the whole task"
    if rung == "yolo":
        return "ran unasked: this agent may act without asking"
    return "it only looks, so nothing needed asking"


def explain(run: Run, *, rung: str | None = None, back: int = 1) -> str:
    """The whole ``/why`` reply for one run."""
    when = run.started_at.astimezone().strftime("%a %d %b %H:%M")
    lines = [f"Why: \"{asked(run)}\" ({when}{', ' + str(back) + ' back' if back > 1 else ''})",
             started_by(run)]
    if run.tools:
        lines += ["", "What it did:"]
        # the same call let through the same way, in a row, is one line
        said: list[list] = []
        for step in run.tools:
            line = f"{tool_words(step.name)}: {let_through(step, rung=rung)}"
            if said and said[-1][0] == line:
                said[-1][1] += 1
            else:
                said.append([line, 1])
        for n, (line, times) in enumerate(said[:STEPS_SHOWN], 1):
            name, _, reason = line.partition(": ")
            lines.append(f"{n}. {name}{f' ×{times}' if times > 1 else ''}: {reason}")
        if len(said) > STEPS_SHOWN:
            lines.append(f"…and {len(said) - STEPS_SHOWN} more steps.")
    else:
        lines += ["", "It used no tools: it answered from what it knew."]
    if run.leaned_on:
        lines += ["", "What it seems to have gone by about you:"]
        lines += [f"- {fact}" for fact in run.leaned_on]
    if run.kept:
        lines += ["", "What it kept about you:"] + [f"- {fact}" for fact in run.kept]
    end = {"end_turn": "It finished", "held": "It stopped to wait for a yes",
           "refused": "It was refused before it started"}.get(run.stop_reason,
                                                              f"It ended: {run.stop_reason}")
    cost = f", costing ${run.cost_usd:.2f}" if run.cost_usd else ""
    lines += ["", f"{end}{cost}" + (f" ({run.model})." if run.model else ".")]
    return "\n".join(lines)


def nothing(back: int) -> str:
    return ("I haven't done anything for you here yet." if back == 1 else
            f"There's nothing {back} back. Send /why for the last one.")

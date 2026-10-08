"""Is the phone free for a scheduled run? Asked before the run starts.

A schedule that works the phone (Samay's ``phone``) runs when nobody
started it, on a phone that is somebody's. Three things can be true of
that phone when the time comes, and Sparsh says which
(``sparsh state --json``):

    in_use   the screen is on and unlocked: someone has it in hand.
             CHECKED AGAIN EACH MINUTE FOR UP TO TEN, then the run is
             skipped and says so. A run that grabbed a phone out of
             someone's hand would tap through whatever they were doing.
    locked   only its person can open it, and an agent can't (it would
             need their PIN). THEY ARE ASKED, in their own chat, to
             unlock it for this schedule; the run waits the schedule's
             own wait for that, then is skipped. Unlocked after being
             asked is a yes: the run goes, though the screen is on.
    asleep   the screen is off and there is no lock: woken, and the run
             goes.

``unknown`` (an iPhone says only whether it is locked) goes, as asleep
does, without waking. A phone that can't be reached at all is a skip,
in Sparsh's words.

Nothing here touches the phone except the wake: what the run does is
the turn's business, after this said go.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

#: How long a phone in someone's hand is waited on, and how often looked at.
IN_USE_FOR, IN_USE_EVERY = 600.0, 60.0
#: How often a locked phone is looked at, once its person was asked.
LOCKED_EVERY = 20.0
#: How long one ``sparsh state`` may take.
STATE_TIMEOUT = 30.0


@dataclass(frozen=True)
class Phone:
    """How to reach the phone from here, as functions (tests give fakes)."""

    state: Callable[[], Awaitable[str]]
    wake: Callable[[], Awaitable[None]]


def through(sparsh: str) -> Phone:
    """The phone, through the sparsh program the door was started with."""

    def run(*args: str) -> str:
        done = subprocess.run([sparsh, *args], capture_output=True, text=True,
                              timeout=STATE_TIMEOUT)
        if done.returncode != 0:
            said = (done.stderr or done.stdout).strip().splitlines()
            raise RuntimeError(said[-1].removeprefix("sparsh: ") if said
                               else f"sparsh {args[0]} failed")
        return done.stdout

    async def state() -> str:
        out = await asyncio.to_thread(run, "state", "--json")
        return str(json.loads(out).get("state") or "unknown")

    async def wake() -> None:
        await asyncio.to_thread(run, "wake")

    return Phone(state=state, wake=wake)


async def ready(phone: Phone, *, wait: float, ask: Callable[[str], Awaitable[None]],
                about: str, clock: Callable[[], float] | None = None,
                sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> str | None:
    """None when the run may go; otherwise why it is skipped, in a
    sentence for the logbook. ``ask`` puts a line in the person's chat;
    ``about`` names the schedule there."""
    clock = clock or asyncio.get_running_loop().time
    started = clock()
    asked_at: float | None = None
    while True:
        try:
            state = await phone.state()
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return f"skipped: the phone couldn't be reached ({exc})"
        if state == "asleep":
            try:
                await phone.wake()
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                return f"skipped: the phone couldn't be woken ({exc})"
            return None
        if state == "unknown":
            return None
        if state == "in_use":
            if asked_at is not None:
                return None          # unlocked for this run: go
            if clock() - started >= IN_USE_FOR:
                return (f"skipped: the phone was in use for {IN_USE_FOR / 60:.0f} "
                        "minutes, so it was left alone")
            await sleep(IN_USE_EVERY)
            continue
        # locked
        if asked_at is None:
            asked_at = clock()
            await ask(f"Your phone is locked, and a schedule wants it now: {about}\n"
                      f"Unlock it and it will start; it waits {wait / 60:.0f} minutes.")
        if clock() - asked_at >= wait:
            return (f"skipped: the phone stayed locked for {wait / 60:.0f} minutes "
                    "after you were asked to unlock it")
        await sleep(LOCKED_EVERY)

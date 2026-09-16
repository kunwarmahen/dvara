"""Questions waiting for a person, and the answers coming back.

Note 01 said the sentence that decided v1: "ask" with nobody present is
not a question, it is a hang. This module is what changes when somebody
IS present -- and the reason it can exist at all is a framework seam that
did not use to be there. A ``PermissionFn`` may now answer with an
awaitable, and ``AsyncAgent`` awaits it, so a gate that waits for a human
SUSPENDS rather than blocking the event loop and every other
conversation on it.

What the framework deliberately refused to build is the other half. A
deadline that denies is policy, and policy belongs to whoever owns the
conversation -- which is this service, not the library underneath it. So
the timeout lives here.

Four decisions, each of which could have gone the other way:

**A QUESTION IS A CAPABILITY, AND ALSO ADDRESSED.** An ask id is
unguessable, and answering still requires naming the actor it was put to.
Either check alone is weaker than it looks: ids travel out through a
channel and can be forwarded, and an actor id on its own is a name
anybody on the roster can type. Both together mean a leaked question is
useless to the person it leaked to.

**PENDING QUESTIONS LIVE IN MEMORY, AND DIE WITH THE PROCESS.** Not a
table. A question is a promise that a turn is still standing there
waiting for the answer, and no turn survives a restart -- agents are
rebuilt per turn and the coroutine that asked is gone. A persisted ask
would outlive the only thing that could act on it, which is not
durability, it is a lie with a timestamp on it.

**A DELIVERY THAT FAILS IS A DENIAL, IMMEDIATELY.** If the notifier
raises -- the bot is down, the token expired -- there is nobody waiting
at the other end and the deadline would just be two silent minutes. The
call is refused at once, and the model is told the difference: nobody
could be reached is not the same fact as nobody answered.

**SILENCE DENIES.** A deadline that approved would make an absent owner
the most permissive setting in the system, which is exactly backwards.
The refusal says how long it waited, because a model that knows it was
refused for silence can ask again later; one told only "denied" cannot.

And one thing that is not a decision so much as a fact about where
answers come from: AN ANSWER MAY ARRIVE FROM ANOTHER THREAD. The turn
suspends on one event loop, and a channel adapter is under no obligation
to be asyncio at all -- a long-polling bot in a worker thread is an
ordinary way to write one. Resolving a future from the wrong thread does
not raise; it simply never wakes the loop, so the turn waits out its
deadline and is refused for a silence that was actually an approval. The
desk remembers which loop each question is waiting on, so an answer from
anywhere lands.
"""

from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

#: Long enough that a person can pick up their phone, short enough that a
#: forgotten question does not pin a conversation open all afternoon. The
#: owner sets it on ``Policy``; this is only the value nobody chose.
DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class Ask:
    """One "may I?" put to one person.

    Everything a channel needs to render the question, and nothing that
    would let a channel decide it. ``summary`` is the tool's own one-line
    preview -- the literal command, the literal path -- built by Yantra so
    that what the person approves is what runs.
    """

    id: str
    actor: str
    agent: str
    thread: str
    tool: str
    summary: str
    asked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict:
        """The wire shape. One place, so a channel and the HTTP surface agree."""
        return {"id": self.id, "actor": self.actor, "agent": self.agent,
                "thread": self.thread, "tool": self.tool,
                "summary": self.summary,
                "asked_at": self.asked_at.isoformat(timespec="seconds")}


@dataclass(frozen=True)
class Answer:
    """What came back, and what the MODEL should be told about it.

    The reason is not decoration. A model that believes a person refused
    it argues with the person; a model told that the question timed out
    tries something smaller; a model told nobody could be reached stops
    asking for this kind of thing altogether. Three different denials
    produce three different next moves, so they are three different
    sentences.
    """

    approved: bool
    reason: str | None = None


#: How a question reaches a person. Given an ``Ask``, put it where they
#: are; the answer comes back through ``AskDesk.answer`` from wherever
#: that is. Delivery and reply are deliberately separate paths -- see the
#: module docstring of ``service.py`` on why answering by SENDING A
#: MESSAGE cannot work.
Notifier = Callable[[Ask], Awaitable[None]]


class AskDesk:
    """The questions in flight, and the one place an answer may land.

    One desk per service. It is deliberately not per-actor: a channel
    adapter serving six people polls one desk and routes each question to
    its own person, which is the arrangement that keeps the routing bug in
    the adapter rather than in the service.
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT,
                 notify: Notifier | None = None) -> None:
        if timeout <= 0:
            raise ValueError(
                "an ask timeout of zero or less is a service that denies "
                "before it asks; say so with Policy(mode='read_only') "
                "instead, where it is legible")
        self.timeout = float(timeout)
        self.notify = notify
        self._waiting: dict[
            str, tuple[Ask, asyncio.Future[bool], asyncio.AbstractEventLoop]
        ] = {}

    # ---- the asking side ---------------------------------------------------

    async def put(self, *, actor: str, agent: str, thread: str, tool: str,
                  summary: str) -> Answer:
        """Ask, wait, and come back with a decision either way.

        Never raises for anything a person or a channel could have caused:
        this is called from inside a permission gate, and an exception
        there becomes a broken turn instead of a refused tool call. The
        one thing that does propagate is cancellation -- a turn whose
        caller hung up did not just get told "no", and history must not
        record one.

        THE DEADLINE COVERS THE QUESTION, NOT JUST THE WAITING. Delivery
        runs as a task alongside the wait rather than in front of it,
        which matters for the notifier that does both jobs at once: the
        terminal prompt asks AND collects, and if this awaited delivery
        first, the clock would not start until somebody had already
        typed. A deadline that only applies to the front ends that do not
        need it is not a deadline.
        """
        ask = Ask(id=secrets.token_urlsafe(16), actor=actor, agent=agent,
                  thread=thread, tool=tool, summary=summary)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._waiting[ask.id] = (ask, future, loop)
        delivery = (None if self.notify is None
                    else asyncio.ensure_future(self.notify(ask)))
        deadline = loop.time() + self.timeout
        try:
            while True:
                left = deadline - loop.time()
                if left <= 0:
                    return Answer(False, _timed_out(tool, self.timeout))
                watching = {future}
                if delivery is not None and not delivery.done():
                    watching.add(delivery)
                done, _ = await asyncio.wait(
                    watching, timeout=left,
                    return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    return Answer(False, _timed_out(tool, self.timeout))
                if delivery in done and delivery.exception() is not None:
                    return Answer(False,
                                  _undeliverable(tool, delivery.exception()))
                if future.done():
                    if future.result():
                        return Answer(True)
                    return Answer(False, _refused(tool, actor))
                # Delivered, and nobody has answered yet. Round again on
                # what is left of the deadline.
        finally:
            # Whatever happened -- answered, timed out, the caller hung up
            # -- the question is over. A desk that kept them would hand a
            # channel a list of questions nobody is waiting on.
            self._waiting.pop(ask.id, None)
            if delivery is not None and not delivery.done():
                delivery.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await delivery

    # ---- the answering side ------------------------------------------------

    def pending(self, actor: str | None = None) -> list[Ask]:
        """Questions still standing, oldest first."""
        asks = [ask for ask, _, _ in self._waiting.values()
                if actor is None or ask.actor == actor]
        return sorted(asks, key=lambda a: a.asked_at)

    def get(self, ask_id: str) -> Ask | None:
        found = self._waiting.get(ask_id)
        return found[0] if found else None

    def answer(self, ask_id: str, *, actor: str, approve: bool) -> bool:
        """Land one decision. False when there was nothing to land on.

        WRONG ACTOR IS NOT AN ANSWER. The id alone would be enough for
        anyone it was ever forwarded to, and the actor alone is a name off
        a roster; requiring both is what makes a question answerable only
        by the person it was put to. A mismatch resolves nothing -- the
        real person can still answer, and the turn keeps waiting.
        """
        found = self._waiting.get(ask_id)
        if found is None:
            return False
        ask, future, loop = found
        if ask.actor != actor:
            raise NotYours(ask_id)
        if future.done():
            # Two answers raced, or one arrived just as the deadline
            # passed. The first one stands; saying so beats pretending the
            # second one did something.
            return False
        if _running_loop() is loop:
            future.set_result(bool(approve))
        else:
            # From anywhere else -- another thread, another loop -- the
            # answer has to be handed to the loop that is waiting on it.
            # Scheduled rather than set, so this returns "posted", not
            # "already delivered"; the difference is one tick of an event
            # loop that is not ours to run.
            loop.call_soon_threadsafe(_resolve, future, bool(approve))
        return True


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _resolve(future: asyncio.Future[bool], approve: bool) -> None:
    """Set the result, unless the deadline got there first."""
    if not future.done():
        future.set_result(approve)


class NotYours(Exception):
    """Somebody tried to answer a question that was put to somebody else."""

    def __init__(self, ask_id: str) -> None:
        super().__init__(f"question {ask_id} was not put to you")


# ---- the three refusals, written once --------------------------------------


def _refused(tool: str, actor: str) -> str:
    return (f"{tool} was denied: {actor} was asked and said no. They are "
            f"reachable, so a different approach may be worth proposing, "
            f"but do not re-run this call.")


def _timed_out(tool: str, seconds: float) -> str:
    return (f"{tool} was denied: nobody answered within "
            f"{_duration(seconds)}. This is silence, not a refusal -- the "
            f"person may simply be away.")


def _undeliverable(tool: str, exc: Exception) -> str:
    return (f"{tool} was denied: the question could not be delivered to "
            f"anyone ({type(exc).__name__}). Nothing is listening, so "
            f"asking again will not help.")


def _duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:g} seconds"
    return f"{seconds / 60:g} minutes"

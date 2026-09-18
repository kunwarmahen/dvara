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
could be reached is not the same fact as nobody answered. With a person
reachable SEVERAL ways this becomes "every delivery failed": one channel
down while another is up is a question that arrived, and the wait goes
on.

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

## One person, one queue, however many channels

``route(kind, notifier)`` is the fifth decision, and it arrived with the
channel table in ``actors.py``. A desk used to hold ONE notifier, which
was exactly right while a service had one way in and quietly wrong the
moment it had two: a question raised by a turn that came over HTTP had
nowhere to go but the HTTP poller, even with the person sitting in a chat
app the service could have reached.

So delivery is routed by the CHANNEL and the question is addressed to the
PERSON, and those are deliberately different things:

* A question is PUT to an actor and delivered to every channel that actor
  is reachable on for which a notifier is registered. Ask on the laptop,
  approve from the phone.
* An answer names the actor and the id, exactly as before. It does not
  name a channel, and it does not have to arrive back on the channel that
  delivered it -- which is the entire point. THE QUEUE IS THE PERSON'S,
  NOT THE CHANNEL'S.
* ``notify`` survives untouched, as the CATCH-ALL. A front end that is
  the only place a question could possibly go -- the terminal, whose
  notifier both asks and collects -- registers no kind and gets
  everything. A desk with neither a catch-all nor a route delivers
  nothing and waits, which is the polling service note 02 built and is
  why "nothing was delivered" is not by itself a refusal.

The address a question is delivered to rides on the ``Ask`` itself, as
``to``, one copy per channel. THAT FIELD IS NOT ON THE WIRE. ``as_dict``
is what ``GET /asks`` returns and an unfiltered listing there would hand
every adapter every person's chat id -- a poller already knows where it
is polling from, so the address is delivery's business and nobody
else's.
"""

from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from yantra import REFUSED_TIMEOUT, REFUSED_UNATTENDED, REFUSED_USER

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
    #: Where this copy is being delivered, in the receiving channel's own
    #: terms, or None for the catch-all notifier that has only one place
    #: to put it. One question becomes one copy per channel; the id is
    #: shared, because it is the same question and the first answer on
    #: any of them settles it.
    to: str | None = None

    def as_dict(self) -> dict:
        """The wire shape. One place, so a channel and the HTTP surface agree.

        ``to`` is omitted on purpose -- see the module docstring. An
        address is for the notifier being handed the question, not for
        everyone who can list what is pending.
        """
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

    And three different CODES, which are for whoever wired the gates up
    rather than for the model (Yantra's note 39). A host that wants to
    count timeouts separately from refusals should not have to match on
    English to do it, and a sentence written for a model is going to be
    reworded eventually.
    """

    approved: bool
    reason: str | None = None
    code: str = REFUSED_USER
    #: Where the person answered from -- a channel kind, "terminal", or
    #: whatever the front end that took the answer calls itself. None when
    #: nobody answered (a timeout, an undeliverable question) or when the
    #: front end did not say.
    #:
    #: NOT A SECOND IDENTITY. The actor is still the whole of who decided;
    #: this is only the door they happened to be standing in, recorded
    #: because "where were you when you approved this?" is a question an
    #: owner asks of a Run six months later and nothing could answer.
    via: str | None = None


#: How a question reaches a person. Given an ``Ask``, put it where they
#: are; the answer comes back through ``AskDesk.answer`` from wherever
#: that is. Delivery and reply are deliberately separate paths -- see the
#: module docstring of ``service.py`` on why answering by SENDING A
#: MESSAGE cannot work.
Notifier = Callable[[Ask], Awaitable[None]]


class AskDesk:
    """The questions in flight, and the one place an answer may land.

    One desk per service. It is deliberately not per-actor and not
    per-channel: one queue holds every question this process is waiting
    on, a question is filtered out of it by the PERSON it was put to, and
    any channel that person holds may answer any of them.
    """

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT,
                 notify: Notifier | None = None) -> None:
        if timeout <= 0:
            raise ValueError(
                "an ask timeout of zero or less is a service that denies "
                "before it asks; say so with Policy(mode='read_only') "
                "instead, where it is legible")
        self.timeout = float(timeout)
        #: The catch-all: everything, with no address, for a front end
        #: that is the only place a question could go.
        self.notify = notify
        self._routes: dict[str, Notifier] = {}
        #: The future resolves with (approved, via) rather than a bare
        #: bool, because the two facts are settled by the same person in
        #: the same act and a second channel for the second one would be
        #: a second thing that can be late or lost.
        self._waiting: dict[
            str, tuple[Ask, asyncio.Future[tuple[bool, str | None]],
                       asyncio.AbstractEventLoop]
        ] = {}

    def route(self, kind: str, notify: Notifier) -> None:
        """Deliver questions for ``kind`` channels through ``notify``.

        One notifier per kind, and re-registering replaces: an adapter
        that reconnects should not end up delivering everything twice,
        and a list of notifiers per kind is a feature nobody has needed.

        The notifier is handed a copy of the ``Ask`` with ``to`` set to
        that person's address on this channel, so one Telegram bridge
        serving six people needs no roster of its own -- the address it
        must send to arrives with the question.
        """
        self._routes[kind] = notify

    # ---- the asking side ---------------------------------------------------

    async def put(self, *, actor: str, agent: str, thread: str, tool: str,
                  summary: str,
                  reach: Sequence[tuple[str, str]] = ()) -> Answer:
        """Ask, wait, and come back with a decision either way.

        Never raises for anything a person or a channel could have caused:
        this is called from inside a permission gate, and an exception
        there becomes a broken turn instead of a refused tool call. The
        one thing that does propagate is cancellation -- a turn whose
        caller hung up did not just get told "no", and history must not
        record one.

        ``reach`` is that person's ``(kind, address)`` pairs, straight off
        their roster entry. Plain tuples rather than the ``Actor`` they
        came from, because this module must not import ``actors`` -- that
        module imports ``gate``, which imports this one.

        THE DEADLINE COVERS THE QUESTION, NOT JUST THE WAITING. Deliveries
        run as tasks alongside the wait rather than in front of it, which
        matters for the notifier that does both jobs at once: the terminal
        prompt asks AND collects, and if this awaited delivery first, the
        clock would not start until somebody had already typed. A deadline
        that only applies to the front ends that do not need it is not a
        deadline.
        """
        ask = Ask(id=secrets.token_urlsafe(16), actor=actor, agent=agent,
                  thread=thread, tool=tool, summary=summary)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[tuple[bool, str | None]] = loop.create_future()
        self._waiting[ask.id] = (ask, future, loop)
        deliveries = self._deliver(ask, reach)
        deadline = loop.time() + self.timeout
        try:
            while True:
                left = deadline - loop.time()
                if left <= 0:
                    return Answer(False, _timed_out(tool, self.timeout),
                                  REFUSED_TIMEOUT)
                watching = {future} | {d for d in deliveries if not d.done()}
                done, _ = await asyncio.wait(
                    watching, timeout=left,
                    return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    return Answer(False, _timed_out(tool, self.timeout),
                                  REFUSED_TIMEOUT)
                # EVERY route failing is the fact that matters, not any
                # one of them. One bridge down while another is up is a
                # question that reached the person; refusing on the first
                # exception would make the least reliable channel the one
                # that decides. Only when nothing got through is there
                # nobody at the other end.
                if deliveries and all(d.done() for d in deliveries):
                    failures = [d.exception() for d in deliveries]
                    if all(exc is not None for exc in failures):
                        return Answer(False, _undeliverable(tool, failures[0]),
                                      REFUSED_UNATTENDED)
                if future.done():
                    approved, via = future.result()
                    if approved:
                        return Answer(True, via=via)
                    return Answer(False, _refused(tool, actor), REFUSED_USER,
                                  via=via)
                # Delivered, and nobody has answered yet. Round again on
                # what is left of the deadline.
        finally:
            # Whatever happened -- answered, timed out, the caller hung up
            # -- the question is over. A desk that kept them would hand a
            # channel a list of questions nobody is waiting on.
            self._waiting.pop(ask.id, None)
            for delivery in deliveries:
                if not delivery.done():
                    delivery.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await delivery

    def _deliver(self, ask: Ask, reach: Sequence[tuple[str, str]]
                 ) -> list[asyncio.Future]:
        """Start one delivery per place this question can go.

        NOTHING TO DELIVER TO IS NOT A REFUSAL. A desk with no catch-all
        and no route for any channel this person holds is the polling
        service note 02 built -- ``GET /asks`` is how the question gets
        found, and denying because no push route existed would break the
        one front end that never had one. Silence still ends at the
        deadline; it just is not shortened here.
        """
        started = []
        for kind, address in reach:
            notify = self._routes.get(kind)
            if notify is not None:
                started.append(asyncio.ensure_future(
                    notify(replace(ask, to=address))))
        if self.notify is not None:
            started.append(asyncio.ensure_future(self.notify(ask)))
        return started

    # ---- the answering side ------------------------------------------------

    def pending(self, actor: str | None = None) -> list[Ask]:
        """Questions still standing, oldest first."""
        asks = [ask for ask, _, _ in self._waiting.values()
                if actor is None or ask.actor == actor]
        return sorted(asks, key=lambda a: a.asked_at)

    def get(self, ask_id: str) -> Ask | None:
        found = self._waiting.get(ask_id)
        return found[0] if found else None

    def answer(self, ask_id: str, *, actor: str, approve: bool,
               via: str | None = None) -> bool:
        """Land one decision. False when there was nothing to land on.

        WRONG ACTOR IS NOT AN ANSWER. The id alone would be enough for
        anyone it was ever forwarded to, and the actor alone is a name off
        a roster; requiring both is what makes a question answerable only
        by the person it was put to. A mismatch resolves nothing -- the
        real person can still answer, and the turn keeps waiting.

        ``via`` is where this answer came from, and it is the ANSWERING
        front end's word rather than the delivering one's: a question that
        went out to three channels was answered on exactly one, and only
        the thing that took the press knows which. It is optional because
        it is a record and never a check -- a front end that does not say
        still gets its answer landed, which keeps an old caller working
        and keeps this from becoming a second identity to get wrong.
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
            future.set_result((bool(approve), via))
        else:
            # From anywhere else -- another thread, another loop -- the
            # answer has to be handed to the loop that is waiting on it.
            # Scheduled rather than set, so this returns "posted", not
            # "already delivered"; the difference is one tick of an event
            # loop that is not ours to run.
            loop.call_soon_threadsafe(_resolve, future, bool(approve), via)
        return True


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _resolve(future: asyncio.Future[tuple[bool, str | None]], approve: bool,
             via: str | None) -> None:
    """Set the result, unless the deadline got there first."""
    if not future.done():
        future.set_result((approve, via))


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

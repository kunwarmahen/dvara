"""The service: one message in, one reply out, for as long as it is up.

Everything else in this package is a noun; this is the verb. ``deliver``
is the whole of dvara's behaviour, and the order of its steps is the
design:

    who is this  ->  may they  ->  which package  ->  what may it spend
    ->  build  ->  rehydrate  ->  run  ->  save  ->  record  ->  reply

Four decisions are worth stating out loud, because each one is a place a
service could reasonably have been built the other way.

**A FRESH AGENT PER TURN.** Not a dict of warm ``AsyncAgent``s. Warm
agents buy latency and cost three things: memory that grows with every
actor who ever said hello, a spec that goes stale the moment a package is
edited on disk, and a crash that loses history nobody wrote down.
Rebuilding is also the only version of this where a restart is a
non-event, which is the entire point of an always-on thing.

**ONE PROVIDER, HELD -- AND GIVEN BACK.** The opposite decision, for the
opposite reason. ``Provider.__init__`` opens an httpx connection pool --
two, in fact, one sync and one async -- so resolving a provider per turn
would leak pools for as long as the process lived. Providers are cached
by name for the life of the service and passed in via
``build_async(provider=...)``, the pre-resolved-provider seam Yantra grew
for its CLI. Held is only half of it: ``aclose`` hands both pools back
through the provider's own ``aclose``, because a process that is asked to
stop should stop owning file descriptors.

**HISTORY IS RESTORED; IDENTITY IS REBUILT.** A checkpoint holds two
different things and only one of them is the conversation. Restoring the
system prompt, the model and ``max_iterations`` along with the messages
is exactly right for ``/load`` at a keyboard and exactly wrong here: a
package whose prompt was fixed this morning must take effect this
afternoon, and an owner who switched models must not be silently
overruled by whatever answered last week. ``apply_payload(...,
history_only=True)`` asks for the half this host wants. What comes out of
the store is the conversation; everything else comes out of the package.

**ONE LOCK PER SESSION KEY.** Two messages in one thread serialize.
Interleaving them would put two user messages into one history with one
assistant reply between them, and Yantra's resumability invariant holds
at prompt boundaries for a reason.
The lock lives only while a turn holds it or a message waits on it
(``locks.py``), so a process that stays up for months holds one per
conversation in flight, not one per conversation it has ever served.

That lock is held while a turn waits for a person to approve a tool call,
and the consequence is worth stating before somebody meets it: A PENDING
QUESTION IS NOT ANSWERED BY SENDING A MESSAGE. Typing "yes" into the
thread queues that message behind the very turn it was meant to release,
where it sits until the deadline passes. Answers arrive through the desk
(``AskDesk.answer``, ``POST /asks/{id}``), which is a separate path on
purpose -- an approval is not a sentence for the model to read, it is a
decision about a call that is already in flight.

A HELD TURN IS NOT ANSWERED BY A MESSAGE EITHER, BUT A MESSAGE ENDS IT.
When the owner has told silence to hold (``--on-timeout hold``), an
unanswered question stops the turn instead of refusing the call, the lock
is let go, and the turn waits in ``holds.py`` -- across a restart, if it
comes to that. ``resume`` carries it on with the person's answers.
Sending something else instead is allowed and means "never mind": the
waiting calls are set aside and the new message is answered.

No streaming in v1. One message, one reply: channels are turn-shaped, and
a bot that streams is a bot that edits the same message forty times and
gets rate-limited for it.

**A TURN IS WATCHED, NOT JUST AWAITED.** The event loop here reads two
kinds of event, not one. ``TurnEnd`` is the answer; every ``ToolExecuted``
along the way is HOW the turn got there, and it goes onto the Run --
which is what lets a failure become a case that asserts a trajectory
rather than a case that asserts a turn finished (``cases.py``). It costs
one branch in a loop that was already running, which is the whole reason
it is done here and not by a second pass over anything.

The gate writes what DECIDED each of those calls into a ``Decisions``
(``gate.py``), keyed by the call's own id, and this loop joins the two on
that id. Two halves of one turn, met in the middle: the loop knows what
happened and the gate knows why, and neither of them knows both.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from yantra import (
    HELD,
    AgentSpec,
    ToolExecuted,
    Provider,
    bills_nothing,
    SessionStore,
    TurnEnd,
    Usage,
    apply_payload,
    default_model,
    get_provider,
    load_settings,
    session_cost,
)
from yantra.config import guess_provider
from yantra.errors import ConfigError
from yantra.hold import check_answers, held_task
from yantra.unattended import is_unattended
from yantra.unattended import scope as unattended_scope

from dvara import money, patience
from dvara.accounts import AccountDesk, is_command, looks_pasted, owners_client_file
from dvara.actors import OWN_SETU, Actor, ActorBook, Channel
from dvara.asks import AskDesk
from dvara.errors import ConfigProblem, Refused
from dvara.gate import Decisions, Policy
from dvara.holds import (DEFAULT_KEEP, Hold, HoldBook, NoSuchHold,
                         NotYourHold, Waiting, waiting_text)
from dvara.keys import session_key, workspace_parts
from dvara.locks import KeyedLocks
from dvara.notices import NoticeDesk, Sent
from dvara.roster import Roster
from dvara.runs import Run, RunStore, ToolStep


#: Where a person on a channel sees their schedules: by asking.
SEEN_HERE = ("The person sees their schedules by asking you: list them with "
             "`mcp__samay__list_schedules`, and pause or delete one when they say so.")


#: How a person here gets an account connected: by sending the command
#: themselves (accounts.py) -- never by an agent, which only says how.
CONNECT_HERE = ("the person connects it by sending, themselves, /connect followed "
                "by its name (/connect gmail); you cannot do it for them -- say so")
#: For a person whose accounts live in a folder the owner looks after.
CONNECT_THERE = ("the person cannot connect one from here; the owner of this "
                 "service connects it for them -- say so, and say which")


#: A stopped clock, on a service: the owner's to start, not the person's.
CLOCK_OFF = ("Samay's clock is not running on this service right now: when you "
             "make a schedule, say it will start running once the service's owner "
             "starts it. Do not ask the person to run anything.")


def _default_provider(name: str) -> Provider:
    """Yantra's own resolution: settings from the environment, one pool."""
    return get_provider(name, load_settings(name))


@dataclass(frozen=True)
class Reply:
    """What one turn came to. Everything a channel needs and nothing more."""

    text: str
    run_id: str | None
    agent: str
    stop_reason: str
    detail: str | None = None
    cost_usd: float | None = None
    usage: Usage | None = None
    #: Who the turn ran as. Worth returning rather than assuming, because
    #: a caller that arrived with a channel identity never named an actor
    #: and would otherwise have to ask a second time to answer a question
    #: this turn raised. None only when the resolution itself refused.
    actor: str | None = None
    #: One short line to put under the answer, or None for none -- what
    #: this person's roster entry asked to be shown (money.receipt).
    #:
    #: NOT PART OF ``text``, on purpose. ``run.reply`` is the archive of
    #: what the agent SAID, and a footer appended to it is a sentence the
    #: agent did not say, read back months later by whoever is asking why
    #: a turn answered badly. Keeping it separate also leaves the channel
    #: to decide how a footer looks in its own medium, rather than this
    #: service picking a separator for every channel there will ever be.
    receipt: str | None = None
    #: The turn stopped for approval nobody gave in time and is waiting in
    #: the queue (holds.py) -- what a channel shows, with the id it
    #: answers by. None for every turn that did not stop.
    held: Hold | None = None
    #: An UNATTENDED turn's three lists (Yantra's unattended.py), for the
    #: program that asked for it -- a scheduler: what only a person can
    #: fix (a sign-in), what another process was using (a browser
    #: profile), and which tools were refused. Empty on any other turn
    #: except ``refused``, which is read off the run's own steps.
    needs: tuple[str, ...] = ()
    busy: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"


class Service:
    """Many people, many agents, many conversations, one process."""

    def __init__(self, *, roster: Roster, actors: ActorBook, state: Path,
                 policy: Policy | None = None,
                 asks: AskDesk | None = None,
                 provider_name: str | None = None,
                 model: str | None = None,
                 provider_factory: Callable[[str], Provider] | None = None,
                 log=None,
                 hold_for: float = DEFAULT_KEEP,
                 samay: str | None = None,
                 ) -> None:
        self.roster = roster
        self.actors = actors
        self.state = Path(state).expanduser().resolve()
        self.policy = policy or Policy()
        # Escalation is OPT-IN, and its absence is the whole of the old
        # behaviour. No desk means no route to a person, which means "ask"
        # decides by policy alone rather than waiting on somebody who was
        # never wired up. A service that started blocking because a mode
        # string somewhere said "ask" would be a service that hangs the
        # day it is deployed.
        self.asks = asks
        # The operator's overrides, in the CLI's own resolution order:
        # what the service was told  >  what the package says  >  the
        # environment's default. An Ollama owner must be able to run a
        # package authored against a cloud model without editing it.
        self.provider_name = provider_name
        self.model = model
        #: Where the one thing this service has to tell a HUMAN goes. It
        #: has exactly one use -- an owner's file that has stopped
        #: parsing -- and that message has nowhere else to be: the person
        #: who can fix it is not in the conversation, and the person who
        #: IS in the conversation must not be handed somebody else's
        #: config error. Resolved at the moment of writing rather than
        #: bound now, so a host that redirects stderr later is obeyed.
        self.log = log
        self._complained: str | None = None
        #: The samay program, when the owner turned schedules on
        #: (``--samay``): each person's turn gets Samay's tools, for
        #: that person, on this road (``_schedules``). None: no turn does.
        self.samay = samay

        self.state.mkdir(parents=True, exist_ok=True)
        self.sessions = SessionStore(self.state / "sessions.sqlite3")
        self.runs = RunStore(self.state / "runs.sqlite3")
        # Always open, even when nothing is configured to hold: a turn
        # held yesterday by a service started with --on-timeout hold can
        # still be answered today by one started without it. Whether
        # silence holds is a policy for new questions, not a way to
        # strand old ones (holds.py).
        self.holds = HoldBook(self.state / "holds.sqlite3", keep_for=hold_for)
        #: Telling a person something nobody asked about (notices.py).
        self.notices = NoticeDesk()
        # The one seam between this service and the network. Injected so
        # tests exercise the real assembly against a scripted provider,
        # and so an embedder that already holds a provider does not open
        # a second connection pool to the same endpoint.
        self._provider_factory = provider_factory or _default_provider
        self._providers: dict[str, Provider] = {}
        self._locks: KeyedLocks[str] = KeyedLocks()
        #: A person's own accounts, from the chat: /connect, /accounts,
        #: /disconnect and the address pasted back (accounts.py). Handled
        #: before any turn, and never seen by an agent.
        self.accounts = AccountDesk(
            notify=lambda actor, text: self.notify(text=text, actor=actor),
            log=self._note, client_file=self._owners_client_file)
        self._client_file: tuple[str | None] | None = None

    def _owners_client_file(self) -> str | None:
        if self._client_file is None:            # asked once, when first needed
            self._client_file = (owners_client_file(),)
        return self._client_file[0]

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Give back the sockets. A service that is asked to stop, stops.

        ``Provider.close()`` is the framework's own promise, which it was
        not when this was first written: shutdown used to reach past the
        provider and close ``.client`` itself, because there was nothing
        else to call. Reaching into another package's attributes works
        right up until the day it does not, and a service that leaks a
        connection pool per provider does not find out for hours.

        THE SYNC HALF CANNOT CLOSE THE ASYNC POOL. An ``AsyncClient`` is
        only closable from inside a running loop, so this closes what it
        honestly can; ``aclose`` is what an async host wants, and what
        every caller in this package uses.
        """
        for provider in self._providers.values():
            provider.close()
        self._providers.clear()
        self.runs.close()
        self.holds.close()

    async def aclose(self) -> None:
        """Give back BOTH pools. The shutdown a running service calls.

        Not ``close()`` with an await bolted on the front: the provider
        closes both of its own pools in the right order, and this stays a
        loop over providers rather than a loop over their internals.
        """
        await self.accounts.aclose()
        for provider in self._providers.values():
            await provider.aclose()
        self._providers.clear()
        self.runs.close()
        self.holds.close()

    # ---- the owner's files, read again -------------------------------------

    def _note(self, line: str) -> None:
        """One line for the owner, once per distinct problem.

        Deduplicated because this is called per TURN: a file that has
        stopped parsing has stopped parsing for every turn after it, and
        a service that printed the same paragraph a hundred times an hour
        is a service whose log nobody reads. The state clears when the
        problem changes or goes away, so the NEXT breakage is loud again.
        """
        if line != self._complained:
            self._complained = line
            print(line, file=self.log or sys.stderr)

    def refresh(self) -> None:
        """Pick up an edited actors or policy file, without a restart.

        A BAD FILE KEEPS THE LAST GOOD ONE. That is the whole policy, and
        it is the reason this lives here rather than in either parser. An
        owner adding a guest at midnight who leaves a quote off is one
        typo away from a service that refuses everybody -- including
        themselves, including the person who would fix it -- so a reread
        that raises is a complaint on the way past and nothing else. The
        roster in force stays the one that was in force a second ago.

        The opposite reading is defensible at STARTUP and is what happens
        there: a broken file is exit 2 and nothing serves, because nobody
        is depending on the process yet. The difference between those two
        answers is whether there is already something to lose.

        Cheap enough to do per turn: two ``stat`` calls against a model
        round trip.
        """
        try:
            if self.actors.changed():
                self.actors = self.actors.reread()
                self._note(f"reloaded {self.actors.source} "
                           f"({len(self.actors)} actor(s))")
        except ConfigProblem as exc:
            self._note(f"{exc}\n  -- keeping the roster already loaded; "
                       f"nothing changed for anybody talking right now")
        try:
            if self.policy.rules.changed():
                rules = self.policy.rules.reread()
                self.policy = replace(self.policy, rules=rules)
                self._note(f"reloaded {rules.source} ({len(rules)} rule(s))")
        except ConfigProblem as exc:
            self._note(f"{exc}\n  -- keeping the rules already loaded")

    # ---- telling, unasked ----------------------------------------------------

    async def notify(self, *, text: str, actor: str | None = None,
                     via: Channel | None = None) -> tuple[str, Sent]:
        """Send ``text`` to a person on their channels (notices.py).

        Who is named the two ways a turn names them, exactly one of the
        two. Refused for nobody on the roster, and for an empty text --
        a blank message on somebody's phone at 08:00 is worse than none.
        """
        self.refresh()
        if (actor is None) == (via is None):
            raise Refused("a notice needs exactly one of an actor or a "
                          "channel identity")
        who = (self.actors.get(actor) if actor is not None
               else self.actors.resolve(via.kind, via.id))
        if not text.strip():
            raise Refused("a notice needs some text")
        return who.id, await self.notices.send(who.id, who.reach(), text)

    # ---- the verb ----------------------------------------------------------

    def _whom(self, actor: str | None, via: Channel | None,
              thread: str) -> tuple[str, str]:
        """Settle who is talking and under which thread, from either form.

        EXACTLY ONE OF THE TWO, and both mistakes are refused rather than
        resolved. Neither is a caller that forgot to say who it is;
        BOTH is a caller saying it twice, and the only way to honour that
        would be to decide which of the two wins -- at which point a
        bridge with a stale hard-coded actor id quietly overrules the
        roster, or quietly does not, and nobody can tell which from the
        outside.
        """
        if (actor is None) == (via is None):
            raise Refused("a turn needs exactly one of an actor or a channel "
                          "identity to say who is talking")
        if via is None:
            return actor, thread
        return self.actors.resolve(via.kind, via.id).id, f"{via.kind}:{thread}"


    async def deliver(self, *, agent: str, thread: str, text: str,
                      actor: str | None = None,
                      via: Channel | None = None,
                      unattended: bool = False,
                      allow_tools: Sequence[str] = ()) -> Reply:
        """Run one turn for one person, and answer them either way.

        Never raises for anything a person could have caused. A refusal is
        a reply; so is a crash inside somebody's tool. The caller is a
        channel adapter, and an exception there is a message that silently
        never arrives.

        TWO WAYS TO SAY WHO, AND EXACTLY ONE PER CALL. ``actor`` names
        somebody straight off the roster, which is what the CLI does and
        what a trusted bridge that already did its own mapping does.
        ``via`` hands over a channel's native identity and lets the roster
        do the mapping -- the form an adapter should prefer, because it is
        the form in which the adapter cannot get the answer wrong.

        THE CHANNEL QUALIFIES THE THREAD. Two channels resolving to one
        person is the point of ``via``; two channels whose thread ids
        happen to collide sharing one conversation is not, and before the
        roster joined them it was only the differing actor ids keeping
        them apart. So a turn that came in through a channel is keyed
        under ``kind:thread``. It is done here rather than asked of
        adapters because a rule that holds only when every adapter
        remembers it is not a rule, and the cost is one prefix on the
        path that has a channel to name -- keys made by callers naming an
        actor directly are untouched, and so is every checkpoint already
        written under one.

        UNATTENDED IS A TURN NOBODY STARTED BY TYPING. A program (a
        scheduler) asked for it, and the person it runs as may be asleep:
        Yantra is told so for this turn alone (its ``unattended.scope``),
        so a browser hands nothing to a window nobody is at, and the reply
        carries what the turn needed from them. A question that CAN reach
        them still does -- that is what this service is for -- and
        ``allow_tools`` are the questions they answered ahead of time,
        when they accepted the schedule (``gate.put`` says what that can
        and cannot grant).
        """
        started = datetime.now(UTC)
        self.refresh()
        try:
            actor, thread = self._whom(actor, via, thread)
            who = self.actors.may(actor, agent)
            spec = self.roster.spec(agent)
            key = session_key(actor, agent, thread)
        except Refused as exc:
            return Reply(text=str(exc), run_id=None, agent=agent,
                         actor=actor, stop_reason="refused")
        if not text.strip():
            return Reply(text="say something and I will answer it",
                         run_id=None, agent=agent, actor=actor,
                         stop_reason="refused")
        if not unattended:
            # The person's own accounts: theirs to act on, not a turn.
            # Nothing of it is kept -- no run, no history -- because a
            # pasted address carries a sign-in's code (accounts.py).
            said = await self._account_words(who, spec, text)
            if said is not None:
                return Reply(text=said, run_id=None, agent=agent, actor=actor,
                             stop_reason="accounts")

        async with self._locks.hold(key):
            # Costing zero until something is spent. The distinction the
            # ledger draws is between "nothing was spent" and "tokens
            # were spent that nobody can price", and a refusal is firmly
            # the first: reading "unpriced" against a turn that never
            # reached a model is the store admitting to a doubt it does
            # not have.
            run = Run(actor=actor, agent=agent, thread=thread, message=text,
                      started_at=started, cost_usd=0.0)
            try:
                if not unattended:
                    return await self._turn(spec=spec, who=who, key=key,
                                            run=run)
                with unattended_scope() as record:
                    reply = await self._turn(spec=spec, who=who, key=key,
                                             run=run,
                                             ahead=tuple(allow_tools))
                return replace(reply, needs=tuple(record.needs),
                               busy=tuple(record.busy))
            except Refused as exc:
                run.reply, run.stop_reason = str(exc), "refused"
                self.runs.record(run)
                return Reply(text=str(exc), run_id=run.id, agent=agent,
                             actor=actor, stop_reason="refused")
            except asyncio.CancelledError:
                # A dropped connection is not a failure of the agent, and
                # Yantra's loop already left history resumable. Record what
                # happened so the row does not silently go missing, then
                # let the cancellation continue on its way.
                run.stop_reason, run.reply = "cancelled", ""
                self.runs.record(run)
                raise
            except Exception as exc:  # noqa: BLE001 -- see the docstring
                run.stop_reason = "error"
                run.detail = f"{type(exc).__name__}: {exc}"
                run.reply = "that went wrong at my end"
                self.runs.record(run)
                return Reply(text=run.reply, run_id=run.id, agent=agent,
                             actor=actor, stop_reason="error",
                             detail=run.detail)

    async def resume(self, hold_id: str, *,
                     answers: Mapping[str, bool | str],
                     actor: str | None = None,
                     via: Channel | None = None,
                     door: str | None = None) -> Reply:
        """Answer a held turn, and let it carry on (notes/16).

        ``answers`` has one entry per waiting call, by call id: True runs
        it, False refuses it, and a string refuses it in the person's own
        words, which the model reads. ``door`` is where the answer came
        from, for the Run -- the same record ``AskDesk.answer`` keeps.

        A REFUSAL BEFORE THE TURN IS RAISED, NOT REPLIED. Unlike
        ``deliver``, the caller here is an approval path -- a button, a
        POST, a command -- that already has to tell "that is not yours"
        from "that is gone", and a reply-shaped refusal would make every
        one of them parse a sentence. ``NotYourHold`` and ``NoSuchHold``
        say which; any other ``Refused`` is the answers or the person's
        access. Once the turn is running, it answers exactly as
        ``deliver`` does: a reply either way.

        A RESUME IS A NEW TURN. It is checked against today's money
        before anything is used up, so a person whose allowance is spent
        keeps their hold and can answer it tomorrow.
        """
        started = datetime.now(UTC)
        self.refresh()
        actor, _ = self._whom(actor, via, "")
        door = door or (via.kind if via is not None else None)
        hold = self.holds.get(hold_id)
        if hold is None:
            raise NoSuchHold(
                "no held turn with that id is waiting -- it was answered, "
                "set aside by a newer message, or has expired")
        if hold.actor != actor:
            raise NotYourHold(hold_id)
        if self.holds.expired(hold):
            self.holds.drop(hold.id)
            raise NoSuchHold(
                f"that turn was held more than "
                f"{patience.duration(self.holds.keep_for)} ago and can no "
                f"longer be answered; ask again if it is still wanted")
        for call_id, answer in answers.items():
            if not isinstance(answer, bool | str):
                raise Refused(
                    f"the answer for {call_id} must be true, false, or your "
                    f"reason for refusing it")
        who = self.actors.may(actor, hold.agent)
        spec = self.roster.spec(hold.agent)

        async with self._locks.hold(hold.key):
            # Looked up again under the lock: two answers racing for one
            # hold must not both carry it on.
            if self.holds.get(hold_id) is None:
                raise NoSuchHold("that turn was answered a moment ago")
            run = Run(actor=actor, agent=hold.agent, thread=hold.thread,
                      message="", started_at=started, cost_usd=0.0)
            try:
                return await self._turn(spec=spec, who=who, key=hold.key,
                                        run=run, resuming=hold,
                                        answers=answers, door=door)
            except (NoSuchHold, NotYourHold):
                raise
            except Refused as exc:
                if self.holds.get(hold_id) is not None:
                    # Refused before the hold was used -- bad answers, a
                    # spent allowance. Nothing ran; nothing to record.
                    raise
                run.reply, run.stop_reason = str(exc), "refused"
                self.runs.record(run)
                return Reply(text=str(exc), run_id=run.id, agent=run.agent,
                             actor=actor, stop_reason="refused")
            except asyncio.CancelledError:
                run.stop_reason, run.reply = "cancelled", ""
                self.runs.record(run)
                raise
            except Exception as exc:  # noqa: BLE001 -- as deliver
                run.stop_reason = "error"
                run.detail = f"{type(exc).__name__}: {exc}"
                run.reply = "that went wrong at my end"
                self.runs.record(run)
                return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                             actor=actor, stop_reason="error",
                             detail=run.detail)

    # ---- one turn, in the order that works ---------------------------------

    async def _turn(self, *, spec: AgentSpec, who: Actor, key: str,
                    run: Run, resuming: Hold | None = None,
                    answers: Mapping[str, bool | str] | None = None,
                    door: str | None = None,
                    ahead: tuple[str, ...] = ()) -> Reply:
        provider_name = self.provider_name or spec.provider or guess_provider()
        model = self.model or spec.model or default_model(provider_name)
        run.model = model

        # Written by the gate as calls are decided, read when the Run is
        # assembled. It has to exist before the gate is built, which is
        # why it is here rather than beside the loop that fills the rest.
        decisions = Decisions()
        run.agent_version = spec.version
        ceiling = self._ceiling(spec=spec, who=who)
        if ceiling.amount is not None and ceiling.amount <= 0:
            raise Refused(
                f"your daily allowance is spent; it comes back at "
                f"{money.next_reset():%H:%M UTC on %-d %b}"
            )

        # The other allowance, read from the same ledger at the same
        # moment. Not a refusal of the turn when it is spent, unlike
        # money: a turn with no waiting left can still do everything
        # that needs nobody, and gate.put refuses only what would have
        # been asked (patience.py).
        wait = patience.Patience(patience.remaining_today(
            who.max_wait_per_day,
            (0.0 if who.max_wait_per_day is None
             else self.runs.waited_since(who.id, money.day_start()))))

        provider = self._provider(provider_name)
        try:
            agent = replace(spec, max_usd_per_turn=ceiling.amount).build_async(
                permissions=self.policy.gate(
                    spec.permissions_mode,
                    actor_mode=who.permissions,
                    desk=self.asks,
                    actor=who.id, agent=run.agent, thread=run.thread,
                    reach=who.reach(),
                    decisions=decisions,
                    patience=wait,
                    ahead=ahead,
                ),
                cwd=self._workspace(key),
                provider=provider,
                provider_name=provider_name,
                model=model,
            )
        except ConfigError as exc:
            # The commonest one: a ceiling on a model nobody can price.
            # At a keyboard that is a startup error; here it has to become
            # a sentence, or a channel adapter gets a traceback.
            raise Refused(f"that agent cannot run right now: {exc}") from exc

        servers = await self._servers(agent, who=who, run=run, key=key, spec=spec)
        try:
            return await self._run_turn(
                agent, key=key, run=run, resuming=resuming, answers=answers,
                door=door, decisions=decisions, wait=wait, ceiling=ceiling,
                provider_name=provider_name, who=who)
        finally:
            if servers is not None:
                await asyncio.to_thread(servers.shutdown)

    async def _servers(self, agent, *, who: Actor, run: Run, key: str, spec: AgentSpec):
        """The MCP servers this turn gets, all stopped when it ends: the
        person's own accounts (``_accounts``) and Samay's tools
        (``_schedules``). None when there are none to start."""
        accounts = who.setu is not None and bool(spec.connections)
        schedules = self.samay is not None and not is_unattended()
        if not (accounts or schedules):
            return None
        from yantra.mcp import MCPManager

        manager = MCPManager(agent.registry, agent=agent,
                             memory_path=self._workspace(key) / ".yantra" / "mcp.json")
        if accounts:
            await self._accounts(agent, manager, who=who, spec=spec)
        if schedules:
            await self._schedules(agent, manager, who=who, run=run)
        return manager

    async def _account_words(self, who: Actor, spec: AgentSpec, text: str) -> str | None:
        """``/connect``, ``/accounts``, ``/disconnect`` or a pasted
        address, answered for this person; None for anything else."""
        if not (looks_pasted(text) or is_command(text)):
            return None
        from yantra.setu_link import needs_allow

        return await self.accounts.handle(
            actor=who.id, text=text, home=self.setu_home(who), own=who.setu == OWN_SETU,
            narrowed=who.setu_accounts, needs=needs_allow(spec.connections))

    def setu_home(self, who: Actor) -> Path | None:
        """Where this person's sign-ins live, made (yours alone) when it
        is a folder of their own under this service's state."""
        if who.setu is None:
            return None
        if who.setu != OWN_SETU:
            return Path(who.setu)
        home = self.state / "setu" / who.id
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        return home

    async def _accounts(self, agent, manager, *, who: Actor, spec: AgentSpec) -> None:
        """The person's OWN accounts, as far as the package asked.

        THEIR FOLDER, NEVER ANYBODY ELSE'S. Setu is read in this person's
        home (``SETU_HOME``) and every connector asks there for its pass,
        so one person's agent cannot reach another's inbox or the owner's
        -- unless the owner pointed them at a folder on purpose, and then
        ``setu_accounts`` can narrow it to the accounts meant.

        BOTH MUST ALLOW. A connection is used only when the package's
        ``[connections] needs`` names its connector, at the package's
        level at most: the person's sign-in is not a reason for an agent
        that never asked to read their mail. A scheduled turn gets the
        same, because the person made the schedule (its card said what
        it reads). A Setu that cannot be read costs the accounts, never
        the turn.
        """
        from yantra.mcp import MCPError
        from yantra.setu_link import Setu, SetuLinkError, account_of, load, needs_allow

        needs = needs_allow(spec.connections)
        home = str(self.setu_home(who))
        try:
            link = await asyncio.to_thread(load, "on", None, home)
        except SetuLinkError as exc:
            self._note(f"dvara: {who.id}'s accounts are off for this turn -- setu: {exc}")
            return
        allow = {}
        for row in (link.connections if link is not None else []):
            account = f"{row.get('connector')}:{account_of(row)}"
            if who.setu_accounts is not None and account not in who.setu_accounts:
                continue
            if row.get("connector") in needs:
                allow[account] = needs[row["connector"]]
        setu = Setu(mode="on", home=home, link=link, allow=allow,
                    package=spec.name, mention=frozenset(needs),
                    connect_how=CONNECT_HERE if who.setu == OWN_SETU else CONNECT_THERE)
        try:
            done = await asyncio.to_thread(setu.sync, manager, agent)
        except MCPError as exc:
            self._note(f"dvara: {who.id}'s accounts are off for this turn -- {exc}")
            return
        for note in done.notes:
            self._note(f"dvara: {who.id}: setu: {note}")
        agent.setu = setu        # Samay's card names what a schedule reads

    async def _schedules(self, agent, manager, *, who: Actor, run: Run) -> None:
        """Samay's tools for this turn's person, or None.

        ONE SERVER PER TURN, FOR THAT PERSON. ``samay mcp --for <actor>``
        starts beside the agent and stops when the turn ends, like the
        agent itself (a fresh agent per turn, above): nothing outlives a
        turn that could carry one person's schedules into another's. A
        schedule made here runs this agent, as this person, on this road
        (``--runner dvara``), so their allowance and the owner's rules
        apply to every run. Creating one is a write, asked about on the
        person's channel with Yantra's card in words (its notes/115).

        A SCHEDULED TURN GETS NONE: nobody is there to say yes. And a
        Samay that will not start costs the turn its tools, never the
        turn -- the owner hears about it once.
        """
        from yantra.mcp import MCPError
        from yantra.samay_link import Samay, SamayLinkError, load

        try:
            found = await asyncio.to_thread(load, "on", self.samay)
            assert found is not None
            link = Samay(mode="on", data=found[0], program=found[1],
                         person=who.id, agent=run.agent, runner="dvara",
                         seen_at=SEEN_HERE, clock_off=CLOCK_OFF)
            await asyncio.to_thread(link.connect, manager, agent)
        except (MCPError, SamayLinkError) as exc:
            self._note(f"dvara: schedules are off for this turn -- samay: {exc}")

    async def _run_turn(self, agent, *, key: str, run: Run,
                        resuming: Hold | None, answers, door: str | None,
                        decisions: Decisions, wait, ceiling, provider_name: str,
                        who: Actor) -> Reply:
        self._rehydrate(agent, key)
        if resuming is not None:
            events = self._carry_on(agent, resuming, answers or {}, run,
                                    decisions, door)
        else:
            if agent.held is not None:
                # A NEW MESSAGE SETS A HELD TURN ASIDE -- Yantra answers the
                # waiting calls "set aside, never ran" as this turn begins
                # (its note 88), and the queue follows the conversation
                # rather than offering an answer nothing can take.
                self.holds.drop_key(key)
            events = agent.run_streaming(run.message)
        before_total = _copy(agent.total_usage)
        before_models = {m: _copy(u) for m, u in agent.usage_by_model.items()}

        end: TurnEnd | None = None
        try:
            async for event in events:
                if isinstance(event, TurnEnd):
                    end = event
                    if end.reason == "held" and agent.held is not None:
                        # Named on the hold before the checkpoint below is
                        # written, so the Run that answers it can say which
                        # one it continues even after a restart.
                        agent.held.recorded = run.id
                elif isinstance(event, ToolExecuted):
                    # A REFUSED CALL IS STILL ONE OF THESE, which is
                    # Yantra's own decision and the reason this is one
                    # branch rather than two: the loop turns a denial into
                    # an error result rather than an exception, so a
                    # refusal, a crash and a success all arrive here and
                    # ``refusal`` is what tells them apart.
                    run.tools.append(ToolStep(
                        event.call.name, event.refusal,
                        decisions.of(event.call.id)))
        finally:
            # Save even when the turn died. Yantra guarantees history is
            # resumable at this point -- outstanding tool calls have
            # synthesized results -- so what is written is always loadable.
            self.sessions.save(agent, provider_name=provider_name,
                               session_id=key)
            # AND ACCOUNT FOR IT. A turn that raised on its fourth model
            # call still paid for the first three, and this is the only
            # place that knows it: the handler upstairs has a Run and no
            # agent. Leave it out and a crash erases its own cost --
            # which the daily allowance then never sees, so a person with
            # a $2 day can spend all afternoon in failing turns. Zero
            # tokens is also a real answer, and cheap to write down.
            run.usage = _delta(before_total, agent.total_usage)
            run.cost_usd = _cost(before_models, agent.usage_by_model,
                                 provider_name=provider_name)
            run.answered_from = list(decisions.channels)
            run.waited_seconds = round(wait.waited, 3)
            run.ended_at = datetime.now(UTC)

        run.stop_reason = end.reason if end else "error"
        run.detail = end.detail if end else None
        run.reply = (end.response.message.text().strip()
                     if end and end.response is not None else "")
        held = None
        if run.stop_reason == "held" and agent.held is not None:
            held = self._keep(agent, key, run, decisions)
            run.reply = waiting_text(held)
        if not run.reply:
            run.reply = _explain(run.stop_reason, run.detail, ceiling)
        self.runs.record(run)
        return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                     actor=run.actor, stop_reason=run.stop_reason,
                     detail=run.detail, cost_usd=run.cost_usd,
                     usage=run.usage,
                     receipt=self._receipt(who, run, provider_name),
                     held=held,
                     refused=tuple(dict.fromkeys(
                         step.name for step in run.tools
                         if step.refusal not in (None, HELD))))

    def _keep(self, agent, key: str, run: Run,
              decisions: Decisions) -> Hold:
        """File a turn that stopped, and put its waiting calls on the Run.

        A HELD CALL IS A STEP, marked ``held``. The loop reports no
        ``ToolExecuted`` for it -- it has no result -- so without this the
        ledger would show a turn that stopped for no visible reason.
        """
        waiting = agent.held.waiting
        for request in waiting:
            run.tools.append(ToolStep(request.tool_name, HELD,
                                      decisions.of(request.call_id)))
        return self.holds.keep(
            key=key, actor=run.actor, agent=run.agent, thread=run.thread,
            run_id=run.id,
            held_at=datetime.fromtimestamp(agent.held.at, UTC),
            calls=[Waiting(r.call_id, r.tool_name, r.summary)
                   for r in waiting])

    def _carry_on(self, agent, hold: Hold, answers: Mapping[str, bool | str],
                  run: Run, decisions: Decisions, door: str | None):
        """Check a hold against the conversation, use it up, and resume.

        EVERYTHING THAT CAN BE WRONG IS FOUND BEFORE THE ROW GOES. The
        checkpoint may no longer hold this turn (a newer message set it
        aside, somebody cleared the conversation), or the answers may not
        match what is waiting; either is a refusal that costs nothing and
        leaves the person free to try again. Only then is the row dropped
        -- before a single call runs, so a crash cannot run one twice
        (holds.py).
        """
        if agent.held is None or agent.held.ids != [c.call_id
                                                    for c in hold.calls]:
            self.holds.drop(hold.id)
            raise NoSuchHold(
                "that turn is no longer waiting: the conversation moved on "
                "since it was held, so there is nothing to carry on")
        try:
            check_answers(agent.held, answers, agent.history)
        except ValueError as exc:
            raise Refused(str(exc)) from None
        run.message = held_task(agent.history) or run.message
        run.resumes = agent.held.recorded or hold.run_id
        self.holds.drop(hold.id)
        for call_id in answers:
            # The person settled every one of these, from wherever they
            # answered -- the same record a question answered in time
            # leaves (gate.py).
            decisions.by_person(call_id, door)
        return agent.resume(dict(answers))

    # ---- the pieces --------------------------------------------------------

    def _ceiling(self, *, spec: AgentSpec, who: Actor) -> money.Ceiling:
        """Package ∧ actor ∧ what is left of today. See money.py."""
        spent = (0.0 if who.max_usd_per_day is None
                 else self.runs.spent_since(who.id, money.day_start()))
        return money.compose(
            package=spec.max_usd_per_turn,
            actor_turn=who.max_usd_per_turn,
            remaining_today=money.remaining_today(who.max_usd_per_day, spent),
        )

    def _receipt(self, who: Actor, run: Run, provider_name: str) -> str | None:
        """The line under the answer, asked for AFTER the run is recorded.

        Order matters and is the whole of this method's difficulty. The
        allowance figure a person wants is what is left NOW, which is to
        say after the turn they just paid for -- and reading it back out
        of the ledger, rather than subtracting in memory from the number
        ``_ceiling`` started with, is what makes it the same figure the
        next turn will be gated on. An unpriced turn contributes nothing
        to either, so the two cannot drift.
        """
        if who.receipt is None:
            return None
        remaining = None
        waiting = None
        if who.receipt == "remaining":
            remaining = money.remaining_today(
                who.max_usd_per_day,
                self.runs.spent_since(who.id, money.day_start()))
            # The other allowance, read back the same way and for the same
            # reason (notes/15). A free provider silences the money half
            # and not this one: waiting on a person costs the same on
            # every road.
            waiting = patience.receipt(
                patience.remaining_today(
                    who.max_wait_per_day,
                    self.runs.waited_since(who.id, money.day_start())),
                run.waited_seconds)
        spent = money.receipt(who.receipt, cost_usd=run.cost_usd,
                              free=bills_nothing(provider_name),
                              remaining=remaining)
        return " · ".join(part for part in (spent, waiting) if part) or None

    def _provider(self, name: str) -> Provider:
        """One connection pool per provider, for the life of the service."""
        if name not in self._providers:
            self._providers[name] = self._provider_factory(name)
        return self._providers[name]

    def _workspace(self, key: str) -> Path:
        """Where this conversation's agent may write.

        NOT the package directory. An agent that edits the folder you
        review and commit is an agent whose package stops being
        reviewable, which is the one property the whole format exists to
        have. The key's components are already percent-escaped, so a
        thread id somebody else chose cannot climb out of here.
        """
        actor, agent, thread = workspace_parts(key)
        work = self.state / "work" / actor / agent / thread
        work.mkdir(parents=True, exist_ok=True)
        return work

    def _rehydrate(self, agent, key: str) -> None:
        """Restore the conversation; keep the identity we just built.

        ``history_only`` is the framework's word for this distinction, and
        it did not exist when this service was first written: the code
        here captured the three identity fields, let ``apply_payload``
        overwrite them, and put them back. That worked, and it meant
        dvara had to know WHICH fields a checkpoint carries -- so the day
        a fourth one was added, this would have silently started
        restoring it. Naming the half you want is the version that
        survives the format growing.
        """
        payload = self.sessions.load_latest(key)
        if payload is not None:
            apply_payload(agent, payload, history_only=True)


# ---- small pure helpers ----------------------------------------------------


def _copy(usage: Usage) -> Usage:
    return Usage(usage.input_tokens, usage.output_tokens,
                 usage.cache_read_tokens, usage.cache_write_tokens)


def _delta(before: Usage, after: Usage) -> Usage:
    """This TURN's tokens, not the session's.

    ``agent.total_usage`` is cumulative and a rehydrated agent starts a
    turn already carrying last week's numbers. Billing the difference is
    what keeps a Run row about the turn it describes.
    """
    return Usage(
        input_tokens=after.input_tokens - before.input_tokens,
        output_tokens=after.output_tokens - before.output_tokens,
        cache_read_tokens=after.cache_read_tokens - before.cache_read_tokens,
        cache_write_tokens=after.cache_write_tokens - before.cache_write_tokens,
    )


def _cost(before: dict[str, Usage], after: dict[str, Usage], *,
          provider_name: str) -> float | None:
    """Dollars for this turn, or None when any of it cannot be priced.

    Per MODEL, because one turn can span two of them (a sub-agent on a
    cheaper slug is the obvious case) and a single rate would be a guess.
    ``session_cost`` reports whether it managed to price everything; when
    it did not, this returns None rather than a total that quietly
    understates -- the same refusal to guess that ``price_for`` makes.

    A MISSING PRICE MEANS TWO OPPOSITE THINGS, which is why the provider
    is an argument here. On a local server there is nothing to pay and
    $0.00 is the true answer; on a hosted one the same silence means
    nobody knows, and writing zero into a row an owner will later sum is
    how a bill becomes a surprise.
    """
    buckets = {}
    for model, usage in after.items():
        buckets[model] = _delta(before.get(model, Usage()), usage)
    live = {m: u for m, u in buckets.items()
            if u.input_tokens or u.output_tokens
            or u.cache_read_tokens or u.cache_write_tokens}
    if not live:
        return 0.0
    dollars, fully_priced = session_cost(live)
    if fully_priced:
        return dollars
    return 0.0 if bills_nothing(provider_name) else None


def _explain(reason: str, detail: str | None, ceiling: money.Ceiling) -> str:
    """A sentence for a turn that produced no words of its own.

    "over_budget" is not an answer to a person; it is a log line. Whose
    ceiling stopped them, and when it comes back, is.
    """
    if reason == "over_budget":
        whose = {
            "today": (f"your daily allowance ran out mid-answer; it comes "
                      f"back at {money.next_reset():%H:%M UTC on %-d %b}"),
            "actor": "you reached the spending limit set for you",
            "package": "this agent reached the cost ceiling its author set",
        }.get(ceiling.whose or "", "the cost ceiling was reached")
        return f"{whose}. {detail}" if detail else whose
    if reason == "max_iterations":
        return "I worked as long as I am allowed to and did not finish that one"
    if reason == "cancelled":
        return "that was interrupted"
    return detail or "I have no answer for that"

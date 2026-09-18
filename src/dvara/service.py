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

That lock is held while a turn waits for a person to approve a tool call,
and the consequence is worth stating before somebody meets it: A PENDING
QUESTION IS NOT ANSWERED BY SENDING A MESSAGE. Typing "yes" into the
thread queues that message behind the very turn it was meant to release,
where it sits until the deadline passes. Answers arrive through the desk
(``AskDesk.answer``, ``POST /asks/{id}``), which is a separate path on
purpose -- an approval is not a sentence for the model to read, it is a
decision about a call that is already in flight.

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
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from yantra import (
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

from dvara import money
from dvara.actors import Actor, ActorBook, Channel
from dvara.asks import AskDesk, Escalations
from dvara.errors import Refused
from dvara.gate import Policy
from dvara.keys import session_key, workspace_parts
from dvara.roster import Roster
from dvara.runs import Run, RunStore, ToolStep


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

        self.state.mkdir(parents=True, exist_ok=True)
        self.sessions = SessionStore(self.state / "sessions.sqlite3")
        self.runs = RunStore(self.state / "runs.sqlite3")
        # The one seam between this service and the network. Injected so
        # tests exercise the real assembly against a scripted provider,
        # and so an embedder that already holds a provider does not open
        # a second connection pool to the same endpoint.
        self._provider_factory = provider_factory or _default_provider
        self._providers: dict[str, Provider] = {}
        self._locks: dict[str, asyncio.Lock] = {}

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

    async def aclose(self) -> None:
        """Give back BOTH pools. The shutdown a running service calls.

        Not ``close()`` with an await bolted on the front: the provider
        closes both of its own pools in the right order, and this stays a
        loop over providers rather than a loop over their internals.
        """
        for provider in self._providers.values():
            await provider.aclose()
        self._providers.clear()
        self.runs.close()

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
                      via: Channel | None = None) -> Reply:
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
        """
        started = datetime.now(UTC)
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

        async with self._lock(key):
            # Costing zero until something is spent. The distinction the
            # ledger draws is between "nothing was spent" and "tokens
            # were spent that nobody can price", and a refusal is firmly
            # the first: reading "unpriced" against a turn that never
            # reached a model is the store admitting to a doubt it does
            # not have.
            run = Run(actor=actor, agent=agent, thread=thread, message=text,
                      started_at=started, cost_usd=0.0)
            try:
                return await self._turn(spec=spec, who=who, key=key, run=run)
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

    # ---- one turn, in the order that works ---------------------------------

    async def _turn(self, *, spec: AgentSpec, who: Actor, key: str,
                    run: Run) -> Reply:
        provider_name = self.provider_name or spec.provider or guess_provider()
        model = self.model or spec.model or default_model(provider_name)
        run.model = model

        # Written by the gate as answers land, read when the Run is
        # assembled. It has to exist before the gate is built, which is
        # why it is here rather than beside the loop that fills the rest.
        escalations = Escalations()
        ceiling = self._ceiling(spec=spec, who=who)
        if ceiling.amount is not None and ceiling.amount <= 0:
            raise Refused(
                f"your daily allowance is spent; it comes back at "
                f"{money.next_reset():%H:%M UTC on %-d %b}"
            )

        provider = self._provider(provider_name)
        try:
            agent = replace(spec, max_usd_per_turn=ceiling.amount).build_async(
                permissions=self.policy.gate(
                    spec.permissions_mode,
                    actor_mode=who.permissions,
                    desk=self.asks,
                    actor=who.id, agent=run.agent, thread=run.thread,
                    reach=who.reach(),
                    escalations=escalations,
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

        self._rehydrate(agent, key)
        before_total = _copy(agent.total_usage)
        before_models = {m: _copy(u) for m, u in agent.usage_by_model.items()}

        end: TurnEnd | None = None
        try:
            async for event in agent.run_streaming(run.message):
                if isinstance(event, TurnEnd):
                    end = event
                elif isinstance(event, ToolExecuted):
                    # A REFUSED CALL IS STILL ONE OF THESE, which is
                    # Yantra's own decision and the reason this is one
                    # branch rather than two: the loop turns a denial into
                    # an error result rather than an exception, so a
                    # refusal, a crash and a success all arrive here and
                    # ``refusal`` is what tells them apart.
                    run.tools.append(ToolStep(event.call.name, event.refusal))
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
            run.answered_from = list(escalations.channels)
            run.ended_at = datetime.now(UTC)

        run.stop_reason = end.reason if end else "error"
        run.detail = end.detail if end else None
        run.reply = (end.response.message.text().strip()
                     if end and end.response is not None else "")
        if not run.reply:
            run.reply = _explain(run.stop_reason, run.detail, ceiling)
        self.runs.record(run)
        return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                     actor=run.actor, stop_reason=run.stop_reason,
                     detail=run.detail, cost_usd=run.cost_usd,
                     usage=run.usage,
                     receipt=self._receipt(who, run, provider_name))

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
        if who.receipt == "remaining":
            remaining = money.remaining_today(
                who.max_usd_per_day,
                self.runs.spent_since(who.id, money.day_start()))
        return money.receipt(who.receipt, cost_usd=run.cost_usd,
                             free=bills_nothing(provider_name),
                             remaining=remaining)

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

    def _lock(self, key: str) -> asyncio.Lock:
        """One lock per conversation.

        Kept forever, on purpose and with a known cost: an entry per
        session key the process has ever served. That is a few hundred
        bytes against a correctness property, and evicting locks safely
        needs a refcount nobody has asked to maintain yet.
        """
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]


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

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

**ONE PROVIDER, HELD.** The opposite decision, for the opposite reason.
``Provider.__init__`` opens an httpx connection pool -- two, in fact, one
sync and one async -- so resolving a provider per turn would leak pools
for as long as the process lived. Providers are cached by name for the
life of the service and passed in via ``build_async(provider=...)``,
the pre-resolved-provider seam Yantra grew for its CLI.

**HISTORY IS RESTORED; IDENTITY IS REBUILT.** ``apply_payload`` restores
the system prompt, the model and ``max_iterations`` along with the
messages, which is exactly right for ``/load`` at a keyboard and exactly
wrong here: a package whose prompt was fixed this morning must take
effect this afternoon, and an owner who switched models must not be
silently overruled by whatever answered last week. So the three identity
fields are captured from the freshly built agent and put back afterwards.
What comes out of the store is the conversation; everything else comes
out of the package.

**ONE LOCK PER SESSION KEY.** Two messages in one thread serialize.
Interleaving them would put two user messages into one history with one
assistant reply between them, and Yantra's resumability invariant holds
at prompt boundaries for a reason.

No streaming in v1. One message, one reply: channels are turn-shaped, and
a bot that streams is a bot that edits the same message forty times and
gets rate-limited for it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from yantra import (
    AgentSpec,
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
from dvara.actors import Actor, ActorBook
from dvara.errors import Refused
from dvara.gate import Policy
from dvara.keys import session_key, workspace_parts
from dvara.roster import Roster
from dvara.runs import Run, RunStore


def _default_provider(name: str):
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

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"


class Service:
    """Many people, many agents, many conversations, one process."""

    def __init__(self, *, roster: Roster, actors: ActorBook, state: Path,
                 policy: Policy | None = None,
                 provider_name: str | None = None,
                 model: str | None = None,
                 provider_factory: Callable[[str], object] | None = None,
                 ) -> None:
        self.roster = roster
        self.actors = actors
        self.state = Path(state).expanduser().resolve()
        self.policy = policy or Policy()
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
        self._providers: dict[str, object] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Give back the sockets. A service that is asked to stop, stops."""
        for provider in self._providers.values():
            client = getattr(provider, "client", None)
            if client is not None:
                client.close()
        self._providers.clear()
        self.runs.close()

    async def aclose(self) -> None:
        """The async half: httpx's async pools need awaiting to close."""
        for provider in self._providers.values():
            aclient = getattr(provider, "aclient", None)
            if aclient is not None:
                await aclient.aclose()
        self.close()

    # ---- the verb ----------------------------------------------------------

    async def deliver(self, *, actor: str, agent: str, thread: str,
                      text: str) -> Reply:
        """Run one turn for one person, and answer them either way.

        Never raises for anything a person could have caused. A refusal is
        a reply; so is a crash inside somebody's tool. The caller is a
        channel adapter, and an exception there is a message that silently
        never arrives.
        """
        started = datetime.now(UTC)
        try:
            who = self.actors.may(actor, agent)
            spec = self.roster.spec(agent)
            key = session_key(actor, agent, thread)
        except Refused as exc:
            return Reply(text=str(exc), run_id=None, agent=agent,
                         stop_reason="refused")
        if not text.strip():
            return Reply(text="say something and I will answer it",
                         run_id=None, agent=agent, stop_reason="refused")

        async with self._lock(key):
            run = Run(actor=actor, agent=agent, thread=thread, message=text,
                      started_at=started)
            try:
                return await self._turn(spec=spec, who=who, key=key, run=run)
            except Refused as exc:
                run.reply, run.stop_reason = str(exc), "refused"
                self.runs.record(run)
                return Reply(text=str(exc), run_id=run.id, agent=agent,
                             stop_reason="refused")
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
                             stop_reason="error", detail=run.detail)

    # ---- one turn, in the order that works ---------------------------------

    async def _turn(self, *, spec: AgentSpec, who: Actor, key: str,
                    run: Run) -> Reply:
        provider_name = self.provider_name or spec.provider or guess_provider()
        model = self.model or spec.model or default_model(provider_name)
        run.model = model

        ceiling = self._ceiling(spec=spec, who=who)
        if ceiling.amount is not None and ceiling.amount <= 0:
            raise Refused(
                f"your daily allowance is spent; it comes back at "
                f"{money.next_reset():%H:%M UTC on %-d %b}"
            )

        provider = self._provider(provider_name)
        try:
            agent = replace(spec, max_usd_per_turn=ceiling.amount).build_async(
                permissions=self.policy.gate(spec.permissions_mode),
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
        finally:
            # Save even when the turn died. Yantra guarantees history is
            # resumable at this point -- outstanding tool calls have
            # synthesized results -- so what is written is always loadable.
            self.sessions.save(agent, provider_name=provider_name,
                               session_id=key)

        run.usage = _delta(before_total, agent.total_usage)
        run.cost_usd = _cost(before_models, agent.usage_by_model,
                             provider_name=provider_name)
        run.ended_at = datetime.now(UTC)
        run.stop_reason = end.reason if end else "error"
        run.detail = end.detail if end else None
        run.reply = (end.response.message.text().strip()
                     if end and end.response is not None else "")
        if not run.reply:
            run.reply = _explain(run.stop_reason, run.detail, ceiling)
        self.runs.record(run)
        return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                     stop_reason=run.stop_reason, detail=run.detail,
                     cost_usd=run.cost_usd, usage=run.usage)

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

    def _provider(self, name: str):
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
        """Restore the conversation; keep the identity we just built."""
        payload = self.sessions.load_latest(key)
        if payload is None:
            return
        identity = (agent.system, agent.model, agent.max_iterations)
        apply_payload(agent, payload)
        agent.system, agent.model, agent.max_iterations = identity

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

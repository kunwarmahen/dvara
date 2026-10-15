"""Skills a person keeps: offered after the answer, kept on their word.

At Yantra's own page, a turn that took several steps is looked at once
it is answered, and what could be done in one step next time is offered
as a skill to keep (Yantra's notes/96, 113). Behind this service nothing
looked: a person on Telegram did the same five-step job every Monday,
and their agent never offered to remember how.

THE LOOK RUNS BEHIND THE ANSWER. The answer goes out first; then Yantra's
learner reads the turn, writes the recipe, and tests it -- on the
person's own allowance, recorded as a Run of its own
(``looked_for_skill``). A new message from them stops it: they want
their agent, not a write-up.

NOBODY IS ASKED FROM BEHIND. A test call that would need a yes is
refused, unasked (gate.NOBODY_ASKED), and the offer says its test waits:
the person's ``/skills keep`` is the yes, and the question comes then,
while they are there to answer it.

A KEPT SKILL IS THEIRS ALONE. One package serves several people. A skill
one of them keeps is saved in THEIR folder for that agent (Yantra's
"project" scope there), never beside the package or in the computer's
own skills, so one person's yes never changes the agent for anyone else.
Making a recipe everybody's is the owner's, by hand.

WHAT WAITS IS KEPT ON DISK, per person per agent, in Yantra's own tray
format (``state/skills/<person>/<agent>.json``) beside the staged files
in their folder, so a restart loses nothing.

THE WORDS ARE THE WAY IN, on every channel: ``/skills`` lists this
agent's skills, the person's own learned ones with how they have done,
and what waits; ``/skills keep N`` and ``/skills drop N`` answer an
offer (by its number or its id); ``/skills forget NAME`` removes one of
their own. A page's buttons send the same words.

``YANTRA_LEARN=off`` stops the looks (Yantra's switch); uses of learned
skills are still counted, as Yantra counts them in any run.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yantra import TurnEnd, default_model
from yantra.config import guess_provider
from yantra.errors import ConfigError

from dvara import gate as gates
from dvara import patience
from dvara.errors import Refused
from dvara.gate import Decisions
from dvara.keys import workspace_parts
from dvara.runs import Run

if TYPE_CHECKING:
    from dvara.actors import Actor
    from dvara.service import Service

#: The word.
WORD = "/skills"
#: Where a kept skill goes: the person's own folder for this agent.
SCOPE = "project"
#: A Run that was a look for a skill, not a turn.
LOOKED = "looked_for_skill"


def word_of(text: str) -> bool:
    """Whether ``text`` is ``/skills`` (with or without more after it)."""
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].lower() in (WORD, WORD + "@")


def rest_of(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def offered_words(agent: str, key: str, offer: Any) -> str:
    """What the person is told when a look finds something."""
    draft = offer.draft
    head = (f"I could update the skill {offer.repairs.name}, which didn't quite work "
            f"this time:" if offer.repairs is not None
            else "I could keep what I just did as a skill, so next time it's one step:")
    return "\n".join([head, "", f"{draft.name} — {draft.description}",
                      f"Test: {_tested(offer)}", "",
                      f"Send /skills keep {key} to keep it, or /skills drop {key}."])


def _tested(offer: Any) -> str:
    if offer.waiting:
        return "waits for your yes; it runs when you keep it"
    if offer.tested is None:
        return "nothing to run"
    return "passed" if offer.tested else "failed"


def offer_extra(agent: str, key: str, offer: Any) -> dict:
    """What a channel may draw beside the words (notices.py)."""
    return {"offer": {"id": key, "agent": agent, "name": offer.draft.name,
                      "description": offer.draft.description,
                      "test": _tested(offer)}}


class Learning:
    """The service's side of it: looks, the offers on disk, the words."""

    def __init__(self, service: Service) -> None:
        self.service = service
        self.state = service.state / "skills"
        self._jobs: set[asyncio.Task] = set()

    # ---- after a turn --------------------------------------------------------

    def mode(self) -> str:
        from yantra.skills.learn import learn_mode

        try:
            return learn_mode()
        except ValueError as exc:
            self.service._note(f"dvara: {exc}; looking for skills as if it said ask")
            return "ask"

    def after_turn(self, agent: Any, end: TurnEnd | None, *, run: Run, key: str,
                   who: Actor, provider_name: str) -> None:
        """Count the learned skills this turn followed, and -- for a person's
        own answered turn -- start the look behind it."""
        if end is None or getattr(agent, "skills", None) is None:
            return
        from yantra.skills.learn import Learner

        mode = self.mode()
        learner = Learner(agent, mode, execute=self._executor(agent, quiet=True))
        try:
            learner.after_turn(end)
        except Exception as exc:     # a counter never costs the answer
            self.service._note(f"dvara: {who.id}: counting skill uses failed -- {exc}")
        if (mode == "off" or run.unattended or end.reason != "end_turn"
                or agent.held is not None):
            return
        job = asyncio.ensure_future(self._look(agent, learner, mode, run=run, key=key,
                                               who=who, provider_name=provider_name))
        self._jobs.add(job)
        job.add_done_callback(self._jobs.discard)

    async def _look(self, agent: Any, learner: Any, mode: str, *, run: Run, key: str,
                    who: Actor, provider_name: str) -> None:
        from dvara.service import _copy, _cost, _delta

        service = self.service
        locks = service._locks
        before_total = _copy(agent.total_usage)
        before_models = {m: _copy(u) for m, u in agent.usage_by_model.items()}
        look = Run(actor=run.actor, agent=run.agent, thread=run.thread,
                   message="(looked at the turn for a skill to keep)",
                   started_at=datetime.now(UTC), cost_usd=0.0, came_by=run.came_by,
                   model=run.model)
        offer = None
        try:
            offer = await asyncio.to_thread(learner.consider, stop=lambda: key in locks)
            look.stop_reason = LOOKED
            look.reply = (f"found {offer.draft.name}" if offer is not None
                          else learner.last_skip or "nothing to keep")
        except Exception as exc:  # noqa: BLE001 -- the answer is already out
            look.stop_reason, look.detail = "error", f"{type(exc).__name__}: {exc}"
            service._note(f"dvara: {who.id}: the look for a skill failed -- {look.detail}")
        finally:
            look.usage = _delta(before_total, agent.total_usage)
            look.cost_usd = _cost(before_models, agent.usage_by_model,
                                  provider_name=provider_name)
            look.ended_at = datetime.now(UTC)
            if look.usage.input_tokens or look.usage.output_tokens or offer is not None:
                service.runs.record(look)     # a look that spent nothing is no Run
        if offer is None:
            return
        name = run.agent
        if mode == "auto" and not offer.waiting:
            skill = learner.save(offer, scope=SCOPE)
            with suppress(Refused):
                await service.notify(actor=who.id,
                                     text=f"I kept a new skill: {skill.name} — "
                                          f"{skill.description}\n\nSend /skills to see yours.")
            return
        cwd = agent.ctx.cwd
        waiting = self._load(who.id, name, cwd, agent, learner)
        for old_key, (_, old) in list(waiting.items()):
            if old.draft.name == offer.draft.name:
                del waiting[old_key]     # one staging folder per name
        offer_key = uuid.uuid4().hex[:4]
        waiting[offer_key] = (learner, offer)
        self._save(who.id, name, cwd, waiting)
        with suppress(Refused):
            await service.notify(actor=who.id, text=offered_words(name, offer_key, offer),
                                 extra=offer_extra(name, offer_key, offer))

    # ---- the offers on disk -------------------------------------------------------

    def _file(self, actor: str, agent: str) -> Path:
        return self.state / actor / f"{agent}.json"

    def _load(self, actor: str, agent: str, cwd: Path, built: Any, learner: Any) -> dict:
        from yantra.web import tray

        recipes, _, _, notes = tray.load(cwd, built, learner, path=self._file(actor, agent))
        for note in notes:
            self.service._note(f"dvara: {actor}/{agent}: {note}")
        return recipes

    def _save(self, actor: str, agent: str, cwd: Path, recipes: dict) -> None:
        from yantra.web import tray

        tray.save(cwd, recipes, [], {}, path=self._file(actor, agent))

    def forget_all(self, actor: str) -> None:
        """A person removed: what waited for them goes too."""
        shutil.rmtree(self.state / actor, ignore_errors=True)

    # ---- the words ------------------------------------------------------------------

    async def words(self, spec: Any, who: Actor, key: str, text: str) -> str:
        """``/skills``, ``/skills keep|drop N``, ``/skills forget NAME``."""
        name = workspace_parts(key)[1]
        if not spec.skills:
            return f"{name} doesn't use skills, so there is nothing to keep here."
        verb, _, target = rest_of(text).partition(" ")
        verb, target = verb.lower(), target.strip()
        if verb and verb not in ("keep", "drop", "forget"):
            return ("Send /skills to see them, /skills keep N or /skills drop N for "
                    "one I offered, or /skills forget NAME for one of yours.")
        if verb and not target:
            return f"Which one? Send /skills {verb} " + ("NAME." if verb == "forget" else "N.")
        quiet = verb != "keep"
        built = self._build(spec, who, key, gated=not quiet)
        if isinstance(built, str):
            return built
        from yantra.skills.learn import Learner

        learner = Learner(built, "ask", execute=self._executor(built, quiet=quiet))
        cwd = built.ctx.cwd
        waiting = self._load(who.id, name, cwd, built, learner)
        if verb == "forget":
            return self._forget(built, target)
        if not verb:
            return _listing(built, waiting)
        found = _pick(waiting, target)
        if found is None:
            return (f"Nothing is waiting as {target}. Send /skills to see what is."
                    if waiting else "Nothing is waiting to be kept.")
        offer_key, (_, offer) = found
        if verb == "drop":
            learner.discard(offer)
            del waiting[offer_key]
            self._save(who.id, name, cwd, waiting)
            return f"Dropped {offer.draft.name}. I won't keep it."
        if offer.waiting:
            # The yes is theirs, now: the test runs, and asks if it must.
            passed = await asyncio.to_thread(learner.test_waiting, offer)
            if not passed:
                self._save(who.id, name, cwd, waiting)
                if offer.waiting:
                    return (f"{offer.draft.name}'s test still hasn't run, so I haven't "
                            f"kept it:\n{_clip(offer.test_output)}")
                return (f"{offer.draft.name}'s test didn't pass, so I haven't kept it:\n"
                        f"{_clip(offer.test_output)}\n\nSend /skills drop {offer_key} "
                        f"to let it go.")
        skill = learner.save(offer, scope=SCOPE)
        del waiting[offer_key]
        self._save(who.id, name, cwd, waiting)
        return (f"Kept {skill.name}. I'll use it the next time you ask for this — "
                f"only for you.")

    def _forget(self, built: Any, target: str) -> str:
        skills = built.skills
        skill = skills.get(target) if skills is not None else None
        if skill is None or not skill.is_learned:
            return f"You have no learned skill called {target}. Send /skills to see yours."
        if Path(built.ctx.cwd).resolve() not in Path(skill.directory).resolve().parents:
            return f"{target} isn't yours to forget: it came with this agent."
        shutil.rmtree(skill.directory)
        return f"Forgot {target}."

    # ---- agents for the words ---------------------------------------------------------

    def _build(self, spec: Any, who: Actor, key: str, *, gated: bool) -> Any:
        """The agent a turn would get, with no message sent and no
        servers: its skills and its bash are all the words need. ``gated``:
        the person's own gate, for a test that may ask them."""
        service = self.service
        provider_name = service.provider_name or spec.provider or guess_provider()
        model = service.model or spec.model or default_model(provider_name)
        _, agent_name, thread = workspace_parts(key)
        permissions = None
        if gated:
            permissions = service.policy.gate(
                spec.permissions_mode, actor_mode=who.permissions, desk=service.asks,
                actor=who.id, agent=agent_name, thread=thread or "skills",
                reach=who.reach(), decisions=Decisions(),
                patience=patience.Patience(None))
        try:
            built = replace(spec, memory=None).build_async(
                **({"permissions": permissions} if permissions is not None else {}),
                cwd=service._workspace(key), provider=service._provider(provider_name),
                provider_name=provider_name, model=model)
        except ConfigError as exc:
            return f"That agent can't be opened right now: {exc}"
        if getattr(built, "skills", None) is None:
            return f"{agent_name} doesn't use skills, so there is nothing to keep here."
        return built

    def _executor(self, agent: Any, *, quiet: bool):
        """How the learner, in its worker thread, runs a test call: on this
        loop, through the agent's own gate -- asking nobody when ``quiet``."""
        loop = asyncio.get_running_loop()

        async def run(call):
            token = gates.NOBODY_ASKED.set(quiet)
            try:
                return await agent._execute(call)
            finally:
                gates.NOBODY_ASKED.reset(token)

        return lambda call: asyncio.run_coroutine_threadsafe(run(call), loop).result()

    async def aclose(self) -> None:
        for job in list(self._jobs):
            job.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await job


def _pick(waiting: dict, target: str):
    if target in waiting:
        return target, waiting[target]
    if target.isdigit() and 1 <= int(target) <= len(waiting):
        offer_key = list(waiting)[int(target) - 1]
        return offer_key, waiting[offer_key]
    return None


def _clip(text: str, cap: int = 600) -> str:
    text = (text or "").strip()
    return text if len(text) <= cap else text[:cap] + "…"


def _listing(built: Any, waiting: dict) -> str:
    from yantra.skills.loader import LEARNED_SOURCES

    """What ``/skills`` answers: theirs, the agent's, and what waits."""
    own = Path(built.ctx.cwd).resolve()
    mine, its, computers = [], [], []
    for skill in sorted(built.skills, key=lambda s: s.name):
        if skill.is_learned and own in Path(skill.directory).resolve().parents:
            record = skill.learned
            counts = (f" (worked {record.worked}, failed {record.failed})"
                      if record is not None else "")
            stale = " — set aside after failing; it will be offered again" \
                if skill.is_stale else ""
            mine.append(f"• {skill.name}{counts}{stale}: {skill.description}")
        elif skill.source in ("user", LEARNED_SOURCES["user"]):
            # the home folder's own (~/.yantra/skills): said as such, since
            # it is the computer's owner's, not this agent's package's
            computers.append(f"• {skill.name}: {skill.description}")
        else:
            its.append(f"• {skill.name}: {skill.description}")
    out = []
    if waiting:
        out.append("Waiting for you:")
        for n, (offer_key, (_, offer)) in enumerate(waiting.items(), start=1):
            out.append(f"{n}. {offer.draft.name} — {offer.draft.description} "
                       f"(test: {_tested(offer)}; id {offer_key})")
        out.append("Send /skills keep N or /skills drop N.")
    out.append("Yours:" if mine else "You haven't kept any skills yet. When a job takes "
               "several steps, I'll offer to keep how it was done.")
    out += mine
    if its:
        out.append("This agent's own:")
        out += its
    if computers:
        out.append("From this computer's own skills:")
        out += computers
    return "\n".join(out)

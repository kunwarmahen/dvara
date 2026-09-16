"""Bias: the four ways a service quietly differs from a session.

A harness at a keyboard has one person, one conversation, one process
that dies when they close it. Every test here is a place where assuming
that would be wrong: histories that must not mix, a package edited on
disk that must take effect, a ceiling that belongs to somebody other than
the author, and a failure that must come back as a sentence instead of a
traceback thrown at a chat window.
"""

from __future__ import annotations

import asyncio

import pytest
from yantra import Usage

from dvara.actors import ActorBook
from dvara.gate import Policy
from dvara.keys import session_key
from tests.conftest import calls, says, write_package


def deliver(service, **kwargs):
    kwargs.setdefault("actor", "owner")
    kwargs.setdefault("agent", "greeter")
    kwargs.setdefault("thread", "t1")
    kwargs.setdefault("text", "hello?")
    return asyncio.run(service.deliver(**kwargs))


# ---- one turn, end to end --------------------------------------------------

def test_a_turn_answers_and_leaves_a_run_behind(make_service):
    service = make_service([says("Hello.", usage=Usage(100, 20, 0, 0))])
    reply = deliver(service)
    assert reply.text == "Hello."
    assert reply.ok

    recorded = service.runs.recent()[0]
    assert recorded.id == reply.run_id
    assert (recorded.actor, recorded.agent, recorded.message) == \
        ("owner", "greeter", "hello?")
    assert recorded.usage.input_tokens == 100


def test_the_agents_own_prompt_reaches_the_model(make_service):
    service = make_service()
    deliver(service)
    system = service.scripted.requests[0]["system"]
    assert "test agent" in system


# ---- many people, many conversations ---------------------------------------

def test_two_threads_of_one_person_do_not_share_a_history(make_service):
    service = make_service([says("one"), says("two")])
    deliver(service, thread="a", text="first")
    deliver(service, thread="b", text="second")
    second_request = service.scripted.requests[1]["messages"]
    assert [m.text() for m in second_request] == ["second"]


def test_the_same_thread_remembers_what_was_said(make_service):
    service = make_service([says("one"), says("two")])
    deliver(service, text="first")
    deliver(service, text="second")
    carried = [m.text() for m in service.scripted.requests[1]["messages"]]
    assert carried == ["first", "one", "second"]


def test_two_people_in_one_thread_id_are_two_conversations(make_service):
    service = make_service([says("one"), says("two")], actors=ActorBook.from_dict(
        {"actor": {"owner": {}, "guest": {}}}))
    deliver(service, actor="owner", thread="shared", text="mine")
    deliver(service, actor="guest", thread="shared", text="theirs")
    assert [m.text() for m in service.scripted.requests[1]["messages"]] == ["theirs"]


def test_one_agent_does_not_inherit_anothers_conversation(make_service,
                                                          agents_root):
    write_package(agents_root, "researcher")
    service = make_service([says("one"), says("two")])
    deliver(service, agent="greeter", text="to the greeter")
    deliver(service, agent="researcher", text="to the researcher")
    assert [m.text() for m in service.scripted.requests[1]["messages"]] == \
        ["to the researcher"]


def test_a_conversation_survives_the_service_that_held_it(make_service):
    first = make_service([says("one")])
    deliver(first, text="remember this")
    first.close()

    second = make_service([says("two")])   # same state directory
    deliver(second, text="still there?")
    carried = [m.text() for m in second.scripted.requests[0]["messages"]]
    assert carried == ["remember this", "one", "still there?"]


# ---- identity is rebuilt, not restored -------------------------------------

def test_an_edited_package_takes_effect_on_the_next_turn(make_service,
                                                         agents_root):
    service = make_service([says("one"), says("two")])
    deliver(service)
    (agents_root / "greeter" / "prompt.md").write_text("You are a NEW agent.")
    deliver(service)
    assert "NEW agent" in service.scripted.requests[1]["system"]


def test_a_rehydrated_turn_uses_the_model_the_service_chose(make_service):
    # apply_payload would restore last week's model along with the
    # messages. The operator's choice has to win.
    service = make_service([says("one"), says("two")])
    deliver(service)
    service.model = "a-different-model"
    deliver(service)
    assert service.scripted.requests[1]["model"] == "a-different-model"


# ---- refusals --------------------------------------------------------------

def test_a_stranger_is_answered_not_raised_at(make_service):
    reply = deliver(make_service(), actor="nobody")
    assert reply.stop_reason == "refused"
    assert not reply.ok
    assert reply.run_id is None      # nothing ran, so nothing is recorded


def test_an_agent_outside_a_persons_whitelist_is_refused(make_service,
                                                         agents_root):
    write_package(agents_root, "researcher")
    reply = deliver(make_service(), actor="guest", agent="researcher")
    assert reply.stop_reason == "refused"
    assert "researcher" in reply.text


def test_an_agent_that_is_not_in_the_root_is_refused(make_service):
    reply = deliver(make_service(), agent="../../etc")
    assert reply.stop_reason == "refused"


def test_an_empty_message_is_refused_before_a_model_is_called(make_service):
    service = make_service([])           # an empty script: any call raises
    assert deliver(service, text="   ").stop_reason == "refused"


# ---- money -----------------------------------------------------------------

def test_the_lowest_ceiling_is_the_one_the_turn_runs_under(make_service,
                                                           agents_root):
    write_package(agents_root, "pricey", body=(
        '[agent]\nname = "pricey"\nprompt = "prompt.md"\n'
        '[budget]\nmax_usd_per_turn = 5.0\n'))
    service = make_service()
    asyncio.run(service.deliver(actor="guest", agent="greeter",
                                thread="t", text="hi"))
    # The guest's $0.02 is below the package's silence; the Budget the
    # agent was built with carries the composed number, not the author's.
    spec = service.roster.spec("greeter")
    assert spec.max_usd_per_turn is None
    who = service.actors.get("guest")
    assert service._ceiling(spec=spec, who=who).amount == pytest.approx(0.02)


def test_a_spent_allowance_refuses_the_turn_before_it_starts(make_service):
    service = make_service([])           # nothing may be called
    store = service.runs
    from dvara.runs import Run
    from datetime import UTC, datetime
    store.record(Run(actor="guest", agent="greeter", thread="t",
                     message="earlier", started_at=datetime.now(UTC),
                     cost_usd=0.10, stop_reason="end_turn"))
    reply = deliver(service, actor="guest", agent="greeter")
    assert reply.stop_reason == "refused"
    assert "allowance" in reply.text
    assert service.runs.recent()[0].stop_reason == "refused"


def test_a_turn_stopped_by_a_ceiling_says_whose_it_was(make_service,
                                                       agents_root,
                                                       priced_model):
    write_package(agents_root, "worker", body=(
        '[agent]\nname = "worker"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["glob"]\n'))
    # One tool call, priced through the roof: the ceiling bites BETWEEN
    # model calls, which is the only place a per-turn meter can bite.
    service = make_service(
        [calls("glob", {"pattern": "*"}, usage=Usage(1_000_000, 0, 0, 0))],
        actors=ActorBook.from_dict(
            {"actor": {"guest": {"agents": ["worker"],
                                 "max_usd_per_turn": 0.02}}}),
    )
    reply = asyncio.run(service.deliver(actor="guest", agent="worker",
                                        thread="t", text="spend it"))
    assert reply.stop_reason == "over_budget"
    assert "limit set for you" in reply.text     # the ACTOR's $0.02, not
    assert "$0.02" in (reply.detail or "")       # the package's silence
    assert service.runs.recent()[0].cost_usd > 0.02


def test_an_unpriceable_model_with_a_ceiling_becomes_a_sentence(make_service):
    # Budget.for_model raises ConfigError rather than carry a ceiling it
    # could never enforce. In a service that has to reach a person.
    service = make_service(model="no-such-model-anywhere")
    reply = deliver(service, actor="guest")
    assert reply.stop_reason == "refused"
    assert "cannot run" in reply.text


# ---- the things a service does that a session never had to --------------

def test_an_agent_writes_in_a_workspace_not_in_the_package(make_service,
                                                           agents_root):
    service = make_service()
    key = session_key("owner", "greeter", "t1")
    work = service._workspace(key)
    assert work.is_dir()
    assert not work.is_relative_to(agents_root)
    assert work.is_relative_to(service.state)


def test_one_provider_is_held_rather_than_one_per_turn(make_service):
    # Provider.__init__ opens two httpx pools. A pool per turn is a leak
    # that only shows up on the day the service has been up a while.
    made: list[str] = []
    service = make_service([says("one"), says("two")])
    original = service._provider_factory
    service._provider_factory = lambda name: (made.append(name)
                                              or original(name))
    deliver(service)
    deliver(service)
    assert made == ["anthropic"]


def test_shutting_the_service_hands_both_pools_back(make_service):
    # The other half of holding a provider. Fifteen providers held for the
    # life of a process is fifteen descriptors; the same fifteen after
    # shutdown is a service that never stops owning anything.
    service = make_service()
    deliver(service)
    provider = service.scripted
    assert not provider.client.is_closed

    asyncio.run(service.aclose())
    assert provider.client.is_closed
    assert provider.aclient.is_closed


def test_the_sync_shutdown_says_so_by_leaving_the_async_pool_alone(
        make_service):
    # Pinned because it is a limitation, not an oversight: an AsyncClient
    # can only be closed from inside a running loop, so a synchronous
    # close that claimed to reach it would be lying. Anything holding a
    # loop calls aclose.
    service = make_service()
    deliver(service)
    provider = service.scripted

    service.close()
    assert provider.client.is_closed
    assert not provider.aclient.is_closed
    asyncio.run(provider.aclose())


def test_two_messages_in_one_thread_do_not_interleave(make_service):
    service = make_service([says("one"), says("two")])

    async def both():
        return await asyncio.gather(
            service.deliver(actor="owner", agent="greeter", thread="t",
                            text="first"),
            service.deliver(actor="owner", agent="greeter", thread="t",
                            text="second"),
        )

    asyncio.run(both())
    # Whichever went second saw the first one's exchange already closed:
    # user, assistant, user -- never user, user.
    second = [m.role for m in service.scripted.requests[1]["messages"]]
    assert second == ["user", "assistant", "user"]


def test_a_turn_that_breaks_at_our_end_comes_back_as_words(make_service):
    service = make_service([])              # empty script -> the loop raises
    reply = deliver(service)
    assert reply.stop_reason == "error"
    assert reply.text == "that went wrong at my end"
    assert service.runs.recent()[0].detail.startswith("AssertionError")


def test_the_owners_policy_is_what_grants_yolo(make_service):
    service = make_service(policy=Policy(mode="yolo"))
    deliver(service)
    assert service.policy.effective("yolo") == "yolo"


def test_a_denied_tool_tells_the_model_nobody_was_asked(make_service,
                                                        agents_root):
    # End to end, because the sentence has to survive the whole path: the
    # gate writes it, Yantra's loop turns it into an error result, and the
    # model reads it on its next call. What it must NOT read is that a
    # user refused -- there is no user in this process at all.
    write_package(agents_root, "scribe", body=(
        '[agent]\nname = "scribe"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file"]\n'))
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("I could not write that, so here it is instead: hi"),
    ])
    reply = asyncio.run(service.deliver(actor="owner", agent="scribe",
                                        thread="t", text="write it down"))
    assert reply.ok

    told = _tool_results(service.scripted.requests[-1]["messages"])
    assert len(told) == 1
    assert "Nobody is available to ask" in told[0]
    assert "denied by user" not in told[0]
    # And the refusal was real, not a message about one.
    work = service._workspace(session_key("owner", "scribe", "t"))
    assert not (work / "notes.txt").exists()


def _tool_results(messages) -> list[str]:
    """Every tool-result text in a message list, in order."""
    found = []
    for message in messages:
        for block in getattr(message, "content", []) or []:
            if type(block).__name__ == "ToolResult":
                found.append(block.content if isinstance(block.content, str)
                             else str(block.content))
    return found


def test_a_free_local_model_costs_zero_rather_than_unknown(make_service):
    # A missing list price means two opposite things. On Ollama there is
    # nothing to pay; on a hosted model the same silence means nobody
    # knows, and a zero written into a row an owner will sum later is how
    # a bill becomes a surprise.
    free = make_service([says("hi", usage=Usage(50, 10, 0, 0))],
                        provider_name="ollama", model="qwen3.8:27b")
    assert deliver(free).cost_usd == 0.0

    hosted = make_service([says("hi", usage=Usage(50, 10, 0, 0))],
                          provider_name="anthropic", model="unknown-slug")
    assert deliver(hosted, thread="t2").cost_usd is None


def test_a_turn_that_crashes_still_pays_for_what_it_spent(make_service,
                                                          agents_root,
                                                          priced_model):
    # Three expensive calls and then a 500 is still three expensive
    # calls. A crash that erased its own cost would let somebody spend
    # all afternoon in failing turns without touching their allowance.
    write_package(agents_root, "worker", body=(
        '[agent]\nname = "worker"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["glob"]\n'))
    # One tool call, then the script runs dry: the loop asks for a second
    # response and the provider raises mid-turn.
    service = make_service(
        [calls("glob", {"pattern": "*"}, usage=Usage(100_000, 0, 0, 0))])
    reply = asyncio.run(service.deliver(actor="owner", agent="worker",
                                        thread="t", text="spend then break"))
    assert reply.stop_reason == "error"

    recorded = service.runs.recent()[0]
    assert recorded.usage.input_tokens == 100_000
    assert recorded.cost_usd == pytest.approx(100.0)   # 100k tok @ $1000/Mtok
    # ...and the allowance can see it, which is the whole point.
    from dvara.money import day_start
    assert service.runs.spent_since("owner", day_start()) == pytest.approx(100.0)


def test_a_recorded_refusal_costs_zero_rather_than_an_unknown(make_service):
    # "unpriced" is the store admitting a doubt; nothing ran, so there is
    # no doubt to admit. A spent allowance is the refusal that DOES leave
    # a row -- it happened to somebody the service serves.
    from datetime import UTC, datetime

    from dvara.runs import Run
    service = make_service([])
    service.runs.record(Run(actor="guest", agent="greeter", thread="t",
                            message="earlier", started_at=datetime.now(UTC),
                            cost_usd=0.10, stop_reason="end_turn"))
    reply = deliver(service, actor="guest", agent="greeter")
    assert reply.stop_reason == "refused"
    assert service.runs.recent()[0].cost_usd == 0.0


def test_someone_the_service_does_not_serve_leaves_no_row(make_service):
    # The other half of the rule, and it is a disk-fill defence: an
    # identity nobody has heard of cannot write rows by knocking.
    service = make_service([])
    assert deliver(service, actor="nobody").run_id is None
    assert service.runs.recent() == []


# ---- escalation: a turn that waits for a person ----------------------------

def scribe(agents_root, name="scribe"):
    """A package whose one tool can change something."""
    write_package(agents_root, name, body=(
        f'[agent]\nname = "{name}"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file"]\n'
        '[permissions]\nmode = "ask"\n'))


async def when_asked(desk, *, approve: bool, actor: str = "owner"):
    """Wait for the turn to reach the gate, then answer its question."""
    while not desk.pending():
        await asyncio.sleep(0)
    ask = desk.pending()[0]
    desk.answer(ask.id, actor=actor, approve=approve)
    return ask


def test_a_yes_lets_the_call_run(make_service, agents_root):
    from dvara.asks import AskDesk
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("written."),
    ], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down"))
        ask = await when_asked(desk, approve=True)
        assert ask.tool == "write_file"
        assert "notes.txt" in ask.summary     # the tool's own preview
        assert ask.agent == "scribe" and ask.thread == "t"
        return await turn

    reply = asyncio.run(go())
    assert reply.ok
    work = service._workspace(session_key("owner", "scribe", "t"))
    assert (work / "notes.txt").read_text() == "hi"


def test_a_no_stops_it_and_says_who_said_no(make_service, agents_root):
    from dvara.asks import AskDesk
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("I could not write that."),
    ], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down"))
        await when_asked(desk, approve=False)
        return await turn

    reply = asyncio.run(go())
    assert reply.ok
    told = _tool_results(service.scripted.requests[-1]["messages"])
    assert "owner was asked and said no" in told[0]
    work = service._workspace(session_key("owner", "scribe", "t"))
    assert not (work / "notes.txt").exists()


def test_silence_refuses_the_call_rather_than_the_turn(make_service,
                                                       agents_root):
    # The turn still ANSWERS. A deadline that killed the conversation
    # would make being away from your phone into an outage.
    from dvara.asks import AskDesk
    scribe(agents_root)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("nobody was around, so here it is in the reply instead: hi"),
    ], asks=AskDesk(timeout=0.05))
    reply = asyncio.run(service.deliver(actor="owner", agent="scribe",
                                        thread="t", text="write it down"))
    assert reply.ok
    told = _tool_results(service.scripted.requests[-1]["messages"])
    assert "nobody answered within 0.05 seconds" in told[0]


def test_one_conversation_waiting_does_not_stop_another(make_service,
                                                        agents_root):
    # THE REASON THE GATE HAD TO BE AWAITABLE. The first turn is parked on
    # a question; the second must run to completion underneath it. With a
    # blocking gate this test deadlocks rather than fails, which is what
    # it would have done in production too.
    from dvara.asks import AskDesk
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("second person, answered"),
        says("written."),
    ], asks=desk)

    async def go():
        waiting = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t1", text="write it down"))
        while not desk.pending():
            await asyncio.sleep(0)

        # A whole other conversation, start to finish, while the first one
        # stands at the gate.
        other = await service.deliver(actor="owner", agent="greeter",
                                      thread="t2", text="hello?")
        assert other.text == "second person, answered"
        assert desk.pending(), "the first turn should still be waiting"

        desk.answer(desk.pending()[0].id, actor="owner", approve=True)
        return await waiting

    assert asyncio.run(go()).ok


def test_a_hung_up_caller_is_not_a_person_saying_no(make_service, agents_root):
    # Cancellation propagates; it does not become a denial. History must
    # not record a refusal nobody made.
    from dvara.asks import AskDesk
    scribe(agents_root)
    desk = AskDesk(timeout=30)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
    ], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down"))
        while not desk.pending():
            await asyncio.sleep(0)
        turn.cancel()
        with pytest.raises(asyncio.CancelledError):
            await turn
        assert desk.pending() == []

    asyncio.run(go())
    assert service.runs.recent()[0].stop_reason == "cancelled"


def test_an_actor_the_owner_will_not_be_woken_for_is_refused_outright(
        make_service, agents_root):
    from dvara.asks import AskDesk
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    quiet = ActorBook.from_dict({"actor": {
        "guest": {"permissions": "read_only"}}})
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("I could not write that."),
    ], asks=desk, actors=quiet)

    reply = asyncio.run(service.deliver(actor="guest", agent="scribe",
                                        thread="t", text="write it down"))
    assert reply.ok
    assert desk.pending() == []          # nobody was disturbed
    told = _tool_results(service.scripted.requests[-1]["messages"])
    assert "Nobody is available to ask" in told[0]

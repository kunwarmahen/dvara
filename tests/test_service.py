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

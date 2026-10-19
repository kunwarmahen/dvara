"""What is remembered about a person, from their own chat (remembering.py).

The bias these tests encode: A FACT KEPT THAT NOBODY AGREED TO, OR KEPT
UNDER THE WRONG PERSON. The look back at ``/new`` proposes sentences
about someone from what they said; a service that wrote them straight to
the store would be deciding for them, and one that wrote them under the
login it runs as would hand them to the next person who asks. So the
tests look back, check nothing is in the store until ``/remember``, and
check that each person's ``/memory`` shows their own facts and nobody
else's. A fact they turned down that comes back at every ``/new`` is
the same failure from the other side: their word ignored. The other
bias is a look back that costs the start-over: a model that fails
mid-look-back must still leave the conversation forgotten.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara import fresh, remembering
from dvara.actors import ActorBook
from dvara.keys import session_key
from tests.conftest import says

REMEMBERING = ('[agent]\nname = "greeter"\nprompt = "prompt.md"\n'
               '[memory]\nvia = "local"\n')
PEOPLE = {"actor": {"owner": {}, "guest": {"agents": ["greeter"]}}}
LOOKED = "fact: Lives in Pune (Asia/Kolkata time)\nfact: Has a cat called Biscuit"


@pytest.fixture
def remembers(agents_root):
    (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
    return agents_root


@pytest.fixture
def make_service(make_service):
    def build(script=None, **kwargs):
        kwargs.setdefault("actors", ActorBook.from_dict(PEOPLE))
        return make_service(script, **kwargs)
    return build


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("YANTRA_USER", "the-machine")


def say(service, text, *, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter", thread=thread,
                                       text=text))


def start_over(service, *, actor="owner", thread="chat"):
    """/new, and the look back that runs behind its answer (notes/51)."""
    async def go():
        reply = await service.deliver(actor=actor, agent="greeter", thread=thread,
                                      text="/new")
        await service.settle()
        return reply
    return asyncio.run(go())


def kept(person):
    from yantra.memory.local import LocalStore
    return [i.statement for i in LocalStore().list(person, 100)]


def test_the_words_are_recognised_with_or_without_the_bots_name():
    assert remembering.word_of("/memory") == "/memory"
    assert remembering.word_of("/remember@SarathiBot 1 2") == "/remember"
    assert remembering.word_of("/memoryx") is None
    assert remembering.word_of("remember this") is None


def test_new_answers_at_once_and_what_it_noticed_comes_after(make_service, remembers):
    """The fresh start is not held for the look back: its answer is the
    plain one, and the list comes as a notice of its own."""
    people = ActorBook.from_dict({"actor": {
        "owner": {"channel": [{"kind": "telegram", "id": "42"}]},
        "guest": {"agents": ["greeter"]}}})
    service = make_service([says("Pune is lovely."), says(LOOKED)], actors=people)
    got: list[str] = []

    async def sender(address, text):
        got.append(text)
    service.notices.route("telegram", sender)
    say(service, "I live in Pune, and Biscuit my cat says hi")
    reply = start_over(service)
    assert reply.text == fresh.STARTED_OVER
    assert len(got) == 1 and got[0].startswith(
        "greeter: Looking back over the conversation we just ended")
    assert "1. Lives in Pune (Asia/Kolkata time)" in got[0]
    assert "2. Has a cat called Biscuit" in got[0]
    assert "Nothing is kept unless you do" in got[0]
    assert kept("owner") == []
    # the look back was one model call, on the record like a turn
    assert len(service.scripted.requests) == 2
    assert service.runs.recent()[0].stop_reason == "looked_back"


def test_new_is_answered_before_its_look_back_has_run(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    said: list[tuple[str, str]] = []

    async def told(actor, text):
        said.append((actor, text))
    service.told_behind = told           # what `dvara say` does with it
    say(service, "I live in Pune")

    async def go():
        reply = await service.deliver(actor="owner", agent="greeter",
                                      thread="chat", text="/new")
        running = bool(service._behind) and len(service.scripted.requests) == 1
        await service.settle()
        return reply, running
    reply, running = asyncio.run(go())
    assert reply.text == fresh.STARTED_OVER and running
    assert len(said) == 1 and said[0][0] == "owner"
    assert "1. Lives in Pune (Asia/Kolkata time)" in said[0][1]
    # the conversation went at once; the look read its copy
    assert service.sessions.load_latest(session_key("owner", "greeter", "chat")) is None


def test_remember_keeps_the_chosen_ones_under_their_own_name(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    say(service, "I live in Pune", actor="guest")
    start_over(service, actor="guest")
    reply = say(service, "/remember 1", actor="guest")
    assert reply.text == "Kept:\n- Lives in Pune (Asia/Kolkata time)"
    assert kept("guest") == ["Lives in Pune (Asia/Kolkata time)"]
    assert kept("the-machine") == [] and kept("owner") == []
    # the one not chosen is still offered, now as number 1
    assert "1. Has a cat called Biscuit" in say(service, "/remember", actor="guest").text


def test_remember_all_and_numbers_that_were_never_listed(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    say(service, "hello")
    start_over(service)
    assert "there's no 7" in say(service, "/remember 7").text
    say(service, "/remember all")
    assert sorted(kept("owner")) == ["Has a cat called Biscuit",
                                     "Lives in Pune (Asia/Kolkata time)"]
    assert "nothing waiting" in say(service, "/remember all").text


def test_memory_lists_their_own_and_forgets_by_id(make_service, remembers):
    from yantra.memory.local import LocalStore
    store = LocalStore()
    mine = store.remember("owner", "Banks with First Federal", {})
    store.remember("guest", "Prefers tea", {})
    service = make_service([])
    listed = say(service, "/memory").text
    assert f"#{mine}  Banks with First Federal" in listed and "tea" not in listed
    assert say(service, f"/memory forget {mine}").text == f"Forgot #{mine}."
    assert kept("owner") == []
    assert "Prefers tea" in say(service, "/memory", actor="guest").text
    assert service.scripted.requests == []          # no model was asked


def test_a_package_that_keeps_no_memories_says_so_and_new_asks_no_model(make_service):
    service = make_service([says("hi")])
    say(service, "hello")
    assert "doesn't keep memories" in say(service, "/memory").text
    assert start_over(service).text == fresh.STARTED_OVER
    assert len(service.scripted.requests) == 1


def test_a_look_back_that_fails_still_starts_over(make_service, remembers, capsys):
    service = make_service([says("hi")])                # nothing scripted for it
    say(service, "hello")
    assert start_over(service).text == fresh.STARTED_OVER
    assert "the look back at /new failed" in capsys.readouterr().err
    assert service.sessions.load_latest(session_key("owner", "greeter", "chat")) is None


def test_what_yantra_noticed_before_shortening_is_listed_under_the_answer(
        make_service, remembers):
    from yantra.memory.reflect import Candidate
    from dvara.runs import Run
    from datetime import UTC, datetime

    service = make_service([])

    class Memory:
        pending = [Candidate("Works nights at the hospital")]

    class Agent:
        memory = Memory()

    run = Run(actor="guest", agent="greeter", thread="t", message="m",
              started_at=datetime.now(UTC), cost_usd=0.0)
    said = service._noticed(Agent(), run)
    assert said.startswith("(I noticed a thing about you") and Agent.memory.pending == []
    assert service.offered.get("guest")[0].statement == "Works nights at the hospital"
    # the same sentence again is not news, and makes no line
    Agent.memory.pending = [Candidate("works nights at the  hospital")]
    assert service._noticed(Agent(), run) == ""
    assert len(service.offered.get("guest")) == 1
    nobody = Run(actor="guest", agent="greeter", thread="t", message="m",
                 started_at=datetime.now(UTC), cost_usd=0.0, unattended=True)
    Agent.memory.pending = [Candidate("x")]
    assert service._noticed(Agent(), nobody) == ""


def test_the_offered_list_is_the_owners_alone(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    say(service, "hello")
    start_over(service)
    assert (service.state / remembering.FILE).stat().st_mode & 0o777 == 0o600


def test_one_fact_said_three_ways_waits_once():
    assert remembering.same("Lives in Pune, India (moved there last month)",
                            "Lives in Pune, India (relocated recently); assume Pune")
    assert remembering.same("Works night shifts as a nurse, which inverts their day",
                            "Works night shifts as a nurse; plan around it")
    assert not remembering.same("Lives in Pune", "Has a dog named Bruno")
    assert not remembering.same("Learning Marathi on days off", "Lives in Pune")


def test_the_look_back_at_new_replaces_what_the_turns_noticed(tmp_path):
    offered = remembering.Offered(tmp_path)
    Offer = remembering.Offer
    assert offered.add("guest", "greeter", [Offer("Lives in Pune, India"),
                                            Offer("Works nights; mornings late")]) == 2
    assert offered.add("guest", "greeter", [Offer("Lives in Pune, India (IST)")]) == 0
    offered.add("guest", "greeter", [Offer("Is learning Marathi")], replace=True)
    assert [o.statement for o in offered.get("guest")] == ["Is learning Marathi"]


def test_what_they_turn_down_is_never_offered_again(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED), says("ok again"), says(LOOKED)])
    say(service, "I live in Pune", actor="guest")
    start_over(service, actor="guest")
    reply = say(service, "/remember not 1", actor="guest")
    assert reply.text == "I won't offer these again:\n- Lives in Pune (Asia/Kolkata time)"
    assert kept("guest") == []
    # the next look back reads them the same way; only the cat comes back
    say(service, "still in Pune", actor="guest")
    start_over(service, actor="guest")
    again = say(service, "/remember", actor="guest").text
    assert "1. Has a cat called Biscuit" in again and "Pune" not in again
    assert len(service.scripted.requests) == 4      # declining asked no model


def test_remember_none_turns_down_everything_waiting(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    say(service, "hello")
    start_over(service)
    assert "Has a cat called Biscuit" in say(service, "/remember none").text
    assert say(service, "/remember").text.startswith("There's nothing waiting")
    assert kept("owner") == []


def test_not_without_numbers_asks_which():
    rest = remembering.declining("not")[1]
    assert remembering.chosen(rest, 2).startswith("Which ones?")
    assert remembering.declining("skip 1 2") == (True, "1 2")
    assert remembering.declining("1 2") == (False, "1 2")


def test_a_declined_fact_said_another_way_stays_declined(tmp_path):
    from dvara.remembering import Offer
    offered = remembering.Offered(tmp_path)
    offered.add("guest", "greeter", [Offer("Lives in Pune"), Offer("Has a cat")])
    offered.take("guest", [1], decline=True)
    assert offered.add("guest", "greeter", [Offer("Lives in Pune, India")],
                       replace=True) == 0
    assert offered.get("guest") == []
    assert offered.declined("guest") == ["Lives in Pune"]
    # keeping is not declining
    offered.add("guest", "greeter", [Offer("Is learning Marathi")])
    offered.take("guest", [1])
    assert offered.declined("guest") == ["Lives in Pune"]

"""What is remembered about a person, from their own chat (remembering.py).

The bias these tests encode: A FACT KEPT THAT NOBODY AGREED TO, OR KEPT
UNDER THE WRONG PERSON. The look back at ``/new`` proposes sentences
about someone from what they said; a service that wrote them straight to
the store would be deciding for them, and one that wrote them under the
login it runs as would hand them to the next person who asks. So the
tests look back, check nothing is in the store until ``/remember``, and
check that each person's ``/memory`` shows their own facts and nobody
else's. A fact they turned down that comes back at every ``/new`` is
the same failure from the other side: their word ignored -- and so is a
"never again" sent by mistake that nothing but the owner can undo, or an
undo that keeps what it should only offer again. The other
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


def test_memory_says_when_one_was_last_used(make_service, remembers):
    # an answer that drew on it keeps it fresh (Yantra reports it); the
    # list says when, so a person can see why an old fact is still first
    from yantra.memory.local import LocalStore
    store = LocalStore()
    rdu = store.remember("owner", "Lives near RDU", {})
    store.remember("owner", "Prefers tea", {})
    store.used("owner", [rdu])
    listed = say(make_service([]), "/memory").text
    first = listed.splitlines()[1]
    assert first.startswith(f"#{rdu}  Lives near RDU  (used 20")
    assert "Prefers tea" in listed and "tea  (used" not in listed


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
    assert reply.text.startswith("I won't offer these again:\n- Lives in Pune (Asia/Kolkata time)")
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


# ---- what they turned down, seen and taken back --------------------------------
# The other side of "never again": a slip of the number was for good, and
# only the owner opening the file could undo it. Undoing must not keep.


def test_declined_lists_newest_first_and_undo_puts_it_back_unkept(make_service, remembers):
    service = make_service([says("ok"), says(LOOKED)])
    say(service, "I live in Pune", actor="guest")
    start_over(service, actor="guest")
    say(service, "/remember not 1", actor="guest")          # Pune
    say(service, "/remember not 1", actor="guest")          # then the cat
    listed = say(service, "/remember declined", actor="guest").text
    assert listed.index("1. Has a cat called Biscuit") < listed.index("2. Lives in Pune")
    undone = say(service, "/remember undo 2", actor="guest").text
    assert undone.startswith("Back on your list (not kept yet):\n- Lives in Pune")
    assert kept("guest") == []                              # undone is not kept
    assert "1. Lives in Pune" in say(service, "/remember", actor="guest").text
    assert "Pune" not in say(service, "/remember declined", actor="guest").text
    say(service, "/remember 1", actor="guest")
    assert kept("guest") == ["Lives in Pune (Asia/Kolkata time)"]
    assert len(service.scripted.requests) == 2              # no model for any of it


def test_undo_of_a_number_not_listed_is_said(make_service, remembers):
    service = make_service([])
    assert say(service, "/remember declined").text.startswith("You haven't turned anything")
    assert "nothing to undo" in say(service, "/remember undo 1").text
    offered = service.offered
    offered.add("owner", "greeter", [remembering.Offer("Has a cat")])
    offered.take("owner", [1], decline=True)
    assert "there's no 3" in say(service, "/remember undo 3").text
    assert "Which ones?" in say(service, "/remember undo").text


def test_undecline_by_words_ignores_what_was_never_declined(tmp_path):
    offered = remembering.Offered(tmp_path)
    offered.add("guest", "greeter", [remembering.Offer("Lives in Pune"),
                                     remembering.Offer("Has a cat")])
    offered.take("guest", [1, 2], decline=True)
    assert offered.undecline("guest", ["Has a cat", "Owns a boat"]) == ["Has a cat"]
    assert offered.declined("guest") == ["Lives in Pune"]
    assert [o.statement for o in offered.get("guest")] == ["Has a cat"]
    assert offered.undecline("other", ["Has a cat"]) == []


def test_the_page_sees_and_undoes_only_their_own(make_service, remembers):
    from fastapi.testclient import TestClient

    from dvara.http import create_app

    service = make_service([], web=True)
    service.offered.add("guest", "greeter", [remembering.Offer("Lives in Pune")])
    service.offered.take("guest", [1], decline=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        mine = client.get("/web/declined", headers=auth, params={"actor": "guest"}).json()
        assert mine == {"declined": ["Lives in Pune"], "waiting": 0}
        theirs = client.get("/web/declined", headers=auth, params={"actor": "owner"}).json()
        assert theirs["declined"] == []
        # the owner can't undo the guest's by naming the words
        client.post("/web/declined", headers=auth,
                    json={"actor": "owner", "undo": ["Lives in Pune"]})
        assert service.offered.declined("guest") == ["Lives in Pune"]
        back = client.post("/web/declined", headers=auth,
                           json={"actor": "guest", "undo": ["Lives in Pune"]}).json()
        assert back == {"back": ["Lives in Pune"], "declined": [], "waiting": 1}
        assert client.post("/web/declined", headers=auth,
                           json={"actor": "guest", "undo": "Lives"}).status_code == 400
    assert kept("guest") == []


def test_what_the_model_kept_itself_is_named_with_the_way_to_undo_it():
    one = remembering.kept_line([("2ad6b855", "Lives in Cary, NC")])
    assert one == "(Kept about you: Lives in Cary, NC -- /memory forget 2ad6b855 to undo.)"
    two = remembering.kept_line([("1", "Lives in Cary, NC"), ("2", "Drives 12 min to RDU")])
    assert "- Lives in Cary, NC (#1)\n- Drives 12 min to RDU (#2)" in two


def test_a_fact_the_turn_kept_is_not_also_offered(make_service, remembers):
    from datetime import UTC, datetime

    from yantra.memory.reflect import Candidate

    from dvara.runs import Run

    service = make_service([])

    class Memory:
        pending = [Candidate("Lives a 12-minute drive from RDU, in the Raleigh area"),
                   Candidate("Has a daughter at college in Detroit")]

    class Agent:
        memory = Memory()

    run = Run(actor="guest", agent="greeter", thread="t", message="m",
              started_at=datetime.now(UTC), cost_usd=0.0,
              kept=["Lives about a 12-minute drive from RDU airport"])
    assert service._noticed(Agent(), run).startswith("(I noticed a thing about you")
    assert [o.statement for o in service.offered.get("guest")] == [
        "Has a daughter at college in Detroit"]


def test_a_fact_kept_and_noticed_in_other_words_is_one_fact():
    kept = ("Lives near RDU (Raleigh-Durham airport) -- the drive there is only "
            "~12 minutes when timing airport pickups/flights.")
    noticed = ("Lives approximately 12 minutes' drive from RDU (Raleigh-Durham) airport, "
               "meaning they can reach the terminal quickly and should plan pickups.")
    assert not remembering.same(noticed, kept)
    assert remembering.about_the_same(noticed, kept)
    assert not remembering.about_the_same("Has a daughter at college in Detroit", kept)


def test_what_a_turn_kept_reaches_the_page_and_its_undo_forgets_only_theirs(
        make_service, remembers):
    from fastapi.testclient import TestClient

    from dvara.gate import Policy
    from dvara.http import create_app
    from tests.conftest import calls

    (remembers / "greeter" / "agent.toml").write_text(
        REMEMBERING + '[permissions]\nmode = "yolo"\n')
    service = make_service([calls("remember", {"statement": "Lives in Cary, NC"}),
                            says("Saved.")], web=True, policy=Policy(mode="yolo"),
                           actors=ActorBook.from_dict({"actor": {
                               "owner": {"permissions": "yolo"},
                               "guest": {"agents": ["greeter"]}}}))
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="web:chat",
                                        text="I live in Cary"))
    from dvara.http import answer_of
    assert answer_of(reply)["text"] == "Saved."
    assert answer_of(reply)["kept"] == [{"id": "1", "statement": "Lives in Cary, NC"}]
    service.web.answered("owner", "greeter", reply)      # as the page's turn writes it
    with TestClient(create_app(service, token=token)) as client:
        # the guest's Undo reaches the guest's own memories, never the owner's
        theirs = client.post("/web/forget", headers=auth, json={
            "actor": "guest", "agent": "greeter", "id": "1"}).json()
        assert theirs["forgot"] is False and kept("owner") == ["Lives in Cary, NC"]
        line = service.web.book.after("owner")[-1]
        assert line.as_dict()["kept"] == [{"id": "1", "statement": "Lives in Cary, NC"}]
        mine = client.post("/web/forget", headers=auth, json={
            "actor": "owner", "agent": "greeter", "id": "1", "line": line.id}).json()
        assert mine == {"said": "Forgot #1.", "forgot": True}
        # drawn again, the page shows it forgotten, with no Undo
        assert service.web.book.get("owner", line.id).as_dict()["kept"] == [
            {"id": "1", "statement": "Lives in Cary, NC", "forgot": True}]
        assert client.post("/web/forget", headers=auth, json={
            "actor": "owner", "agent": "greeter"}).status_code == 400
    assert kept("owner") == []


def test_a_program_reads_what_was_kept_in_the_words(make_service, remembers):
    from dvara.gate import Policy
    from tests.conftest import calls

    (remembers / "greeter" / "agent.toml").write_text(
        REMEMBERING + '[permissions]\nmode = "yolo"\n')
    service = make_service([calls("remember", {"statement": "Lives in Cary, NC"}),
                            says("Saved.")], policy=Policy(mode="yolo"),
                           actors=ActorBook.from_dict({"actor": {
                               "owner": {"permissions": "yolo"}}}))
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="samay-x",
                                        text="brief", unattended=True))
    assert reply.kept == ()
    assert reply.text.endswith("(Kept about you: Lives in Cary, NC -- /memory forget 1 "
                               "to undo.)")

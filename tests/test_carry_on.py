"""A job a restart stopped part way, offered back and carried on (carrying.py).

The bias these tests encode: A JOB THAT VANISHES. A person asked for a
phone or site job, the service was restarted in the middle of it, and
nothing ever said so -- or worse, it was quietly started again from the
top. So the tests stop a turn the way a shutdown does (its task
cancelled mid-job), then check the job is in the store as far as it
got, that its person is told once, that ``/carry`` goes on from the last
step without repeating it, and that a schedule's run is left to Samay.
The other bias is carrying on BY ITSELF: nothing runs until the person
says so, and anything else they send leaves it.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara import carrying
from dvara.actors import ActorBook
from dvara.keys import session_key
from tests.conftest import calls, says


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))


def people():
    return ActorBook.from_dict({"actor": {
        "owner": {"channel": [{"kind": "telegram", "id": "42"}]}}})


def listening(service):
    got: list[str] = []

    async def sender(address, text):
        got.append(text)
    service.notices.route("telegram", sender)
    return got


def stopped_by_a_restart(service, *, thread="chat", text="tidy my notes folder"):
    """Run a turn that does one step, then is cancelled at its next model
    call -- what a shutdown does to a turn in flight."""
    provider = service.scripted
    real = provider._next

    def next_or_stop(**kwargs):
        if len(provider.requests) == 1:      # the second model call
            provider.requests.append(kwargs)
            raise asyncio.CancelledError
        return real(**kwargs)
    provider._next = next_or_stop
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread=thread,
                                    text=text))
    provider._next = real


def say(service, text, *, thread="chat", **kw):
    return asyncio.run(service.deliver(actor="owner", agent="greeter",
                                       thread=thread, text=text, **kw))


class TestStoppedPartWay:
    def test_the_job_is_kept_as_far_as_it_got(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"})],
                               actors=people())
        stopped_by_a_restart(service)

        [(key, info)] = service.sessions.unfinished()
        assert key == session_key("owner", "greeter", "chat")
        assert info["message"] == "tidy my notes folder"
        assert info["steps"] == 1 and info["tools"] == ["read_file"]

    def test_its_person_is_told_once(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"})],
                               actors=people())
        got = listening(service)
        stopped_by_a_restart(service)

        assert asyncio.run(service.tell_stopped()) == 1
        assert asyncio.run(service.tell_stopped()) == 0        # once
        assert "tidy my notes folder" in got[0] and "/carry" in got[0]

    def test_carry_goes_on_from_the_last_step_and_repeats_nothing(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"}),
                                says("Done: three notes moved.")], actors=people())
        stopped_by_a_restart(service)
        asked_before = len(service.scripted.requests)

        reply = say(service, "/carry")

        assert reply.text == "Done: three notes moved."
        sent = service.scripted.requests[asked_before]["messages"]
        assert "stopped here" in sent[-1].text()               # told first
        assert sum(1 for m in sent for c in m.tool_calls()) == 1   # read once
        assert service.sessions.unfinished() == []
        assert service.runs.recent(limit=1)[0].message == "tidy my notes folder"

    def test_anything_else_leaves_it(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"}),
                                says("Sunny.")], actors=people())
        stopped_by_a_restart(service)

        assert say(service, "what's the weather?").text == "Sunny."
        assert say(service, "/carry").text == carrying.NOTHING

    def test_with_nothing_stopped_carry_says_so_and_asks_no_model(self, make_service):
        service = make_service([], actors=people())

        assert say(service, "/carry").text == carrying.NOTHING
        assert service.scripted.requests == []

    def test_a_schedules_run_is_left_to_samay(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"})],
                               actors=people())
        got = listening(service)
        stopped_by_a_restart(service, thread="samay-check-1700000000")

        assert asyncio.run(service.tell_stopped()) == 0
        assert got == []

    def test_samay_carries_its_run_on_with_carry_on(self, make_service):
        service = make_service([calls("read_file", {"path": "notes.txt"}),
                                says("NOTHING NEW")], actors=people())
        stopped_by_a_restart(service, thread="samay-check-1700000000")

        reply = say(service, "check my notes", thread="samay-check-1700000000",
                    unattended=True, carry_on=True)

        assert reply.text == "NOTHING NEW"

"""One folder per person per agent, whichever conversation a turn is in.

The bias these tests encode: A FILE A PERSON'S SCHEDULE WROTE MUST BE ONE
THEIR CHAT CAN READ, AND NOBODY ELSE'S. A person on their phone sees a
file only by asking the agent in their chat, and every scheduled run is a
conversation of its own. So the tests write from a scheduled run and read
from a chat, and then check the walls that must still stand: another
person, and another agent, find nothing.
"""

from __future__ import annotations

import asyncio

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from tests.conftest import calls, says
from tests.test_unattended_turns import scribe


def turn(service, *, actor="owner", agent="scribe", thread="chat", **kw):
    return asyncio.run(service.deliver(actor=actor, agent=agent, thread=thread,
                                       text="go", **kw))


def read_back(service) -> str:
    """What the read_file call returned to the model, in its last request."""
    last = service.scripted.requests[-1]["messages"][-1]
    return " ".join(str(getattr(block, "content", "")) for block in last.content)


def test_a_chat_reads_the_file_its_schedule_wrote(make_service, agents_root):
    scribe(agents_root)
    service = make_service([
        calls("write_file", {"path": "log.txt", "content": "checked at 08:00\n"}),
        says("noted"),
        calls("read_file", {"path": "log.txt"}),
        says("it says checked at 08:00")], asks=AskDesk(timeout=5))
    run = turn(service, thread="samay-s1-100", unattended=True,
               allow_tools=["write_file"])
    assert run.ok
    chat = turn(service, thread="telegram-42")
    assert chat.ok
    assert "checked at 08:00" in read_back(service)


def test_each_run_of_a_schedule_finds_what_the_last_one_wrote(make_service, agents_root):
    scribe(agents_root)
    service = make_service([
        calls("write_file", {"path": "log.txt", "content": "one\n"}), says("ok"),
        calls("read_file", {"path": "log.txt"}), says("ok")],
        asks=AskDesk(timeout=5))
    turn(service, thread="samay-s1-100", unattended=True, allow_tools=["write_file"])
    turn(service, thread="samay-s1-200", unattended=True)
    assert "one" in read_back(service)


def test_another_person_and_another_agent_find_nothing(make_service, agents_root):
    scribe(agents_root)
    people = ActorBook.from_dict({"actor": {"owner": {}, "guest": {}}})
    service = make_service([
        calls("write_file", {"path": "log.txt", "content": "owner's\n"}), says("ok"),
        calls("read_file", {"path": "log.txt"}), says("none")],
        asks=AskDesk(timeout=5), actors=people)
    turn(service, thread="samay-s1-100", unattended=True, allow_tools=["write_file"])
    turn(service, actor="guest", thread="chat")
    assert "owner's" not in read_back(service)
    work = service.state / "work"
    assert (work / "owner" / "scribe" / "log.txt").is_file()
    assert not (work / "guest" / "scribe" / "log.txt").exists()
    assert not (work / "owner" / "greeter").exists()

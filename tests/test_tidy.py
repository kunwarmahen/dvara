"""Letting go of conversations a program started and nobody will continue.

The bias these tests encode: A PERSON'S CONVERSATION IS NEVER TIDIED.
The failure worth designing against is not a few kilobytes too many on
disk; it is a sweep that reaches into somebody's chat because a program
once wrote into it, or that deletes the one thread a person still has a
question waiting on. So every test that tidies something checks, beside
it, the thing that must still be there: their own thread, a held turn,
and every row of the ledger.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from dvara.asks import AskDesk
from dvara.keys import session_key
from tests.conftest import says
from tests.test_unattended_turns import scribe, writes

LATER = datetime.now(UTC) + timedelta(days=30)


def deliver(service, thread, *, unattended=True, **kw):
    return asyncio.run(service.deliver(
        actor="owner", agent="greeter", thread=thread, text="go",
        unattended=unattended, **kw))


def kept(service, thread, agent="greeter"):
    return service.sessions.load_latest(session_key("owner", agent, thread))


def test_a_finished_scheduled_run_goes_once_it_is_old_enough(make_service):
    service = make_service([says("checked")] * 2)
    deliver(service, "samay-1-100")
    work = service.state / "work" / "owner" / "greeter" / "samay-1-100"
    assert kept(service, "samay-1-100") and work.is_dir()

    assert service.tidy() == 0                     # still inside the week
    assert service.tidy(now=LATER) == 1
    assert kept(service, "samay-1-100") is None
    assert not work.exists()
    assert len(service.runs.recent()) == 1         # the record stays
    assert service.tidy(now=LATER) == 0            # and it is not done twice


def test_a_persons_own_thread_is_never_tidied_even_after_a_program_wrote_in(
        make_service):
    service = make_service([says("hi"), says("a finding")])
    deliver(service, "telegram-42", unattended=False)
    deliver(service, "telegram-42")                # a program, into their chat
    assert service.tidy(now=LATER) == 0
    assert kept(service, "telegram-42")


def test_a_thread_with_a_question_still_waiting_is_left_alone(
        make_service, agents_root):
    scribe(agents_root)
    service = make_service([writes()],
                           asks=AskDesk(timeout=0.05, on_timeout="hold"))
    reply = asyncio.run(service.deliver(
        actor="owner", agent="scribe", thread="samay-2-100", text="go",
        unattended=True))
    assert reply.held
    assert service.tidy(now=datetime.now(UTC) + timedelta(hours=1)) == 0
    assert kept(service, "samay-2-100", agent="scribe")


def test_each_unattended_turn_tidies_the_ones_before_it(make_service):
    """Nothing else has to remember to call it."""
    service = make_service([says("one"), says("two")], keep_unattended=0)
    deliver(service, "samay-1-100")
    deliver(service, "samay-1-200")
    assert kept(service, "samay-1-100") is None
    assert kept(service, "samay-1-200")            # its own turn was running


def test_a_negative_keep_is_refused_at_the_start(tmp_path, agents_root,
                                                 capsys):
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    code = main(["--root", str(agents_root), "--actors", str(actors),
                 "--state", str(tmp_path / "s"), "--keep-unattended", "-1",
                 "agents"])
    assert code == 2
    assert "--keep-unattended" in capsys.readouterr().err

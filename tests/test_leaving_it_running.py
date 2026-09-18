"""A process you walk away from, and the three ways it used to need you.

The bias here is that all three failures are invisible from where the
owner is standing.

A second dvara on one state directory does not announce itself as a
second dvara. It announces itself, hours later, as a conversation that
forgot a turn -- because both processes rehydrated the same checkpoint
and both saved, and `SessionStore` appends versions rather than
complaining. So the test that matters is not "two writers contend on
SQLite" (they do, visibly, and that is the symptom) but "the second one
is refused before it opens anything".

An actors file that has stopped parsing is worse: the service is running,
the owner is asleep, and the choice between "refuse everybody" and "keep
the last good roster" is made once, in code, for a moment nobody is
watching. The tests below pin the one that does not lock its owner out of
their own service.

And a question that times out at a keyboard used to leave a thread parked
in a blocking read, which is invisible right up until the process will
not exit.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import sys
import textwrap
import threading

import pytest

from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.claim import Claim
from dvara.errors import ConfigProblem
from dvara.gate import Policy
from dvara.rules import RuleBook

from tests.conftest import says


# ---- one process at a time -------------------------------------------------


def test_a_second_claim_on_one_directory_is_refused(tmp_path):
    first = Claim(tmp_path / "state")
    first.take("dvara serve")
    try:
        with pytest.raises(ConfigProblem, match="already using"):
            Claim(tmp_path / "state").take("dvara telegram")
    finally:
        first.release()


def test_the_refusal_names_who_is_in_there(tmp_path):
    first = Claim(tmp_path / "state")
    first.take("dvara telegram")
    try:
        with pytest.raises(ConfigProblem) as caught:
            Claim(tmp_path / "state").take("dvara say")
    finally:
        first.release()
    said = str(caught.value)
    assert str(os.getpid()) in said
    assert "dvara telegram" in said
    # And the way out, because a refusal with no next move is a wall.
    assert "serve --telegram" in said


def test_two_different_directories_do_not_contend(tmp_path):
    one = Claim(tmp_path / "a")
    two = Claim(tmp_path / "b")
    one.take("dvara serve")
    two.take("dvara serve")          # two services, not one service twice
    one.release()
    two.release()


def test_releasing_lets_the_next_one_in(tmp_path):
    first = Claim(tmp_path / "state")
    first.take("dvara say")
    first.release()
    second = Claim(tmp_path / "state")
    second.take("dvara telegram")     # no stale lock to reason about
    second.release()


def test_a_dead_process_leaves_no_lock_to_clean_up(tmp_path):
    """The reason this is flock and not a pid file.

    A service killed with SIGKILL runs no atexit handler and writes no
    tombstone. The kernel drops the lock when the process dies, so the
    next start is ordinary -- with a pid file this is where the "is 4032
    still the same process?" heuristic lives, and where it is wrong after
    a reboot recycles the number.
    """
    state = tmp_path / "state"
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import time
            from dvara.claim import Claim
            held = Claim({str(state)!r})
            held.take("dvara serve")
            print("held", flush=True)
            time.sleep(60)
        """)],
        stdout=subprocess.PIPE, text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(ConfigProblem):
            Claim(state).take("dvara say")
    finally:
        holder.kill()
        holder.wait(timeout=10)
        holder.stdout.close()
    # No cleanup, no grace period: the file is still there and unlocked.
    assert (state / "dvara.lock").exists()
    taken = Claim(state)
    taken.take("dvara say")
    taken.release()


def test_reading_commands_do_not_claim_anything(tmp_path, agents_root,
                                                capsys):
    """`dvara runs` while the bot is answering somebody is ordinary."""
    from dvara.cli import CLAIMS, main
    assert "runs" not in CLAIMS and "case" not in CLAIMS
    assert "agents" not in CLAIMS

    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    held = Claim(tmp_path / "state")
    held.take("dvara telegram")
    try:
        code = main(["--root", str(agents_root), "--actors", str(actors),
                     "--state", str(tmp_path / "state"), "runs"])
    finally:
        held.release()
    assert code == 0


def test_a_turn_running_command_is_refused_while_one_is_held(tmp_path,
                                                             agents_root,
                                                             capsys):
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    held = Claim(tmp_path / "state")
    held.take("dvara serve")
    try:
        code = main(["--root", str(agents_root), "--actors", str(actors),
                     "--state", str(tmp_path / "state"),
                     "say", "--actor", "owner", "--agent", "greeter", "hi"])
    finally:
        held.release()
    assert code == 2
    assert "already using" in capsys.readouterr().err


def test_a_command_gives_the_claim_back_when_it_finishes(tmp_path,
                                                         agents_root):
    """Two `say`s in a row is not two services, and must not be refused."""
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    argv = ["--root", str(agents_root), "--actors", str(actors),
            "--state", str(tmp_path / "state"), "agents"]
    assert main(argv) == 0
    assert main(argv) == 0


# ---- read it again when it changes -----------------------------------------


def test_a_guest_added_to_the_file_is_served_without_a_restart(
        make_service, tmp_path, agents_root):
    actors = tmp_path / "roster.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    service = make_service([says("one"), says("two")],
                           actors=ActorBook.from_toml(actors))

    first = asyncio.run(service.deliver(actor="guest", agent="greeter",
                                        thread="t", text="hello"))
    assert first.stop_reason == "refused"

    actors.write_text("[actor.owner]\n\n[actor.guest]\n", encoding="utf-8")
    _touch(actors)
    second = asyncio.run(service.deliver(actor="guest", agent="greeter",
                                         thread="t", text="hello"))
    assert second.ok


def test_a_channel_identity_added_at_a_party_works_at_once(make_service,
                                                           tmp_path):
    """The papercut this was named after, in the form it is actually met."""
    actors = tmp_path / "roster.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    service = make_service([says("hello")],
                           actors=ActorBook.from_toml(actors))
    from dvara.actors import Channel

    refused = asyncio.run(service.deliver(via=Channel("telegram", "999"),
                                          agent="greeter", thread="c",
                                          text="hi"))
    assert refused.stop_reason == "refused"

    actors.write_text('[actor.owner]\n\n[[actor.owner.channel]]\n'
                      'kind = "telegram"\nid = 999\n', encoding="utf-8")
    _touch(actors)
    served = asyncio.run(service.deliver(via=Channel("telegram", "999"),
                                         agent="greeter", thread="c",
                                         text="hi"))
    assert served.ok and served.actor == "owner"


def test_a_file_that_stops_parsing_keeps_the_last_good_one(make_service,
                                                           tmp_path, capsys):
    """The decision this feature turns on.

    A typo at midnight must not lock an owner out of the service that is
    the only thing that could tell them about the typo.
    """
    actors = tmp_path / "roster.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    service = make_service([says("still here"), says("and here")],
                           actors=ActorBook.from_toml(actors))

    actors.write_text('[actor.owner\nbroken = ', encoding="utf-8")
    _touch(actors)
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter",
                                        thread="t", text="hello"))
    assert reply.ok
    assert reply.text == "still here"
    err = capsys.readouterr().err
    assert "keeping the roster already loaded" in err


def test_the_complaint_is_made_once_not_once_per_turn(make_service, tmp_path,
                                                      capsys):
    actors = tmp_path / "roster.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    service = make_service([says("a"), says("b"), says("c")],
                           actors=ActorBook.from_toml(actors))
    actors.write_text('[actor.owner\n', encoding="utf-8")
    _touch(actors)
    for _ in range(3):
        asyncio.run(service.deliver(actor="owner", agent="greeter",
                                    thread="t", text="hello"))
    assert capsys.readouterr().err.count("keeping the roster") == 1


def test_a_file_deleted_underneath_keeps_serving_and_says_so(make_service,
                                                             tmp_path,
                                                             capsys):
    """An editor that truncates on save makes this an ACCIDENT, often.

    Which is why the answer is the same as for a file that stopped
    parsing: carry on with the roster already loaded, and tell the one
    person who can do something about it. A service that emptied its
    roster because a text editor was mid-write would be a service that
    locks its owner out for the length of a save.
    """
    actors = tmp_path / "roster.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    service = make_service([says("still here")],
                           actors=ActorBook.from_toml(actors))
    actors.unlink()
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter",
                                        thread="t", text="hello"))
    assert reply.ok and reply.text == "still here"
    err = capsys.readouterr().err
    assert "no actors file" in err
    assert "keeping the roster already loaded" in err


def test_a_policy_file_written_later_is_picked_up(make_service, tmp_path,
                                                  agents_root):
    """An OPTIONAL file that did not exist at startup and does now."""
    from tests.conftest import write_package
    write_package(agents_root, "scribe", body=(
        '[agent]\nname = "scribe"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file"]\n'
        '[permissions]\nmode = "yolo"\n'))
    policy = tmp_path / "policy.toml"
    service = make_service([says("hello"), says("hello again")],
                           policy=Policy(mode="yolo",
                                         rules=RuleBook.from_toml(policy)))
    assert len(service.policy.rules) == 0

    policy.write_text(
        '[[rule]]\ntool = "write_file"\nverdict = "deny"\n'
        'reason = "not today"\n', encoding="utf-8")
    _touch(policy)
    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="hi"))
    assert len(service.policy.rules) == 1


def test_a_book_built_in_memory_never_claims_to_have_changed():
    book = ActorBook.from_dict({"actor": {"owner": {}}})
    assert book.changed() is False
    assert book.reread() is book


# ---- a question you can walk away from -------------------------------------


def test_a_timed_out_question_leaves_no_thread_behind(monkeypatch):
    """The papercut note 02 recorded and could not fix with a thread.

    `to_thread(input)` parks a non-daemon worker in a blocking read; the
    interpreter joins it at exit, so the process waits for a keypress
    nobody has a reason to give any more. What is asserted is the thread
    count, because that IS the bug -- a passing "the answer was a
    refusal" would have passed before this was fixed too.
    """
    from dvara.cli import _ask_at_the_keyboard

    # A pipe with nothing in it: readable never fires, the deadline does.
    read_fd, write_fd = os.pipe()
    stdin = os.fdopen(read_fd, "r")
    monkeypatch.setattr("sys.stdin", stdin)
    before = threading.active_count()

    desk = AskDesk(timeout=0.1)

    async def go():
        desk.notify = _ask_at_the_keyboard(desk)
        return await desk.put(actor="owner", agent="scribe", thread="t",
                              tool="write_file", summary="notes.txt")

    try:
        answer = asyncio.run(go())
    finally:
        stdin.close()
        os.close(write_fd)
    assert answer.approved is False
    assert "nobody answered" in answer.reason
    assert threading.active_count() == before


@pytest.mark.parametrize("answer,approved",
                         [("y", True), ("yes", True), ("", False),
                          ("n", False)])
def test_a_line_that_arrives_is_still_read(monkeypatch, answer, approved):
    """The fallback path, which is what a non-selectable stdin gets."""
    from dvara.cli import _ask_at_the_keyboard

    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))
    desk = AskDesk(timeout=5)

    async def go():
        desk.notify = _ask_at_the_keyboard(desk)
        return await desk.put(actor="owner", agent="scribe", thread="t",
                              tool="write_file", summary="notes.txt")

    assert asyncio.run(go()).approved is approved


def _touch(path) -> None:
    """Make sure a rewritten file looks different to a stamp.

    Two writes inside one filesystem timestamp tick is a real thing on a
    coarse clock, and a test that raced it would be a flake that only
    ever failed on somebody else's machine. The size usually differs too;
    this makes sure of the half that does not.
    """
    stamp = path.stat().st_mtime_ns
    os.utime(path, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))

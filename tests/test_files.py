"""The person's files, sent to them: ``/files`` and ``/file NAME``.

The bias these tests encode: THE FOLDER'S WALLS ARE THE ONLY WALLS, AND
THE MODEL IS NOT ONE OF THEM. A file the person asks for comes from their
folder and nowhere else -- not up a ``..``, not down a link pointing out,
not from the ``.yantra`` bookkeeping beside their records -- and it
arrives without a turn, so no model has to get anything right first.
Every service here is built with an empty script: a model call would
raise "script exhausted".
"""

from __future__ import annotations

import asyncio
import os

from dvara import files


def folder(service, actor="mahen", agent="greeter"):
    work = service.state / "work" / actor / agent
    work.mkdir(parents=True, exist_ok=True)
    return work


def say(service, text, actor="mahen", agent="greeter"):
    return asyncio.run(service.deliver(actor=actor, agent=agent, thread="chat",
                                       text=text))


# ---- what may be picked ----------------------------------------------------


def test_a_name_inside_the_folder_is_found(tmp_path):
    (tmp_path / "log.txt").write_text("up\n")
    assert files.pick(tmp_path, "log.txt") == (tmp_path / "log.txt").resolve()


def test_climbing_out_is_not_found_and_says_nothing_about_outside(tmp_path):
    (tmp_path / "secret").write_text("x")
    mine = tmp_path / "mine"
    mine.mkdir()
    assert files.pick(mine, "../secret") is None
    said, sent = files.answer(mine, "/file ../secret")
    assert sent is None and said.startswith("There's no file called")


def test_a_link_pointing_out_of_the_folder_is_not_followed(tmp_path):
    (tmp_path / "secret").write_text("x")
    mine = tmp_path / "mine"
    mine.mkdir()
    os.symlink(tmp_path / "secret", mine / "innocent.txt")
    assert files.pick(mine, "innocent.txt") is None
    assert "innocent" in files.listing(mine)       # listed, never sent


def test_the_agents_own_bookkeeping_is_never_listed_or_sent(tmp_path):
    (tmp_path / ".yantra").mkdir()
    (tmp_path / ".yantra" / "mcp.json").write_text("{}")
    assert files.pick(tmp_path, ".yantra/mcp.json") is None
    assert files.listing(tmp_path) == "There are no files in your folder here yet."


def test_an_empty_file_is_said_rather_than_sent(tmp_path):
    (tmp_path / "blank.txt").write_text("")
    said, sent = files.answer(tmp_path, "/file blank.txt")
    assert sent is None and "empty" in said


def test_the_listing_is_newest_first_with_sizes(tmp_path):
    (tmp_path / "old.txt").write_text("a" * 2048)
    os.utime(tmp_path / "old.txt", (1, 1))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "new.txt").write_text("b")
    said = files.listing(tmp_path)
    assert said.index("sub/new.txt (1 bytes)") < said.index("old.txt (2 KB)")
    assert said.endswith("Send /file NAME to get one.")


# ---- through the service, which runs no turn -----------------------------------


def test_the_words_are_answered_without_a_turn(make_service):
    from dvara.actors import ActorBook
    service = make_service([], actors=ActorBook.from_dict({"actor": {"mahen": {}}}))
    (folder(service) / "log.txt").write_text("up\n")
    reply = say(service, "/file log.txt")
    assert reply.stop_reason == "files" and reply.run_id is None
    assert [f.name for f in reply.files] == ["log.txt"]
    assert "log.txt" in say(service, "/files").text


def test_another_persons_file_is_not_theirs_to_ask_for(make_service):
    from dvara.actors import ActorBook
    service = make_service([], actors=ActorBook.from_dict(
        {"actor": {"mahen": {}, "guest": {}}}))
    (folder(service) / "log.txt").write_text("mahen's\n")
    reply = say(service, "/file log.txt", actor="guest")
    assert reply.stop_reason == "files" and reply.files == ()
    assert say(service, "/file ../../mahen/greeter/log.txt", actor="guest").files == ()

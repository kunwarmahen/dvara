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


# ---- send_file: the agent sends one --------------------------------------------

from dvara.actors import ActorBook  # noqa: E402
from dvara.asks import AskDesk  # noqa: E402
from dvara.gate import Policy  # noqa: E402
from dvara.rules import Rule, RuleBook  # noqa: E402
from tests.conftest import calls, says, write_package  # noqa: E402

#: Somebody a notice can reach: a scheduled run's file goes that way.
REACHABLE = ActorBook.from_dict({"actor": {"owner": {
    "channel": [{"kind": "telegram", "id": 42}]}}})


def courier(agents_root, allow='["read_file", "write_file", "send_file"]'):
    write_package(agents_root, "courier", body=(
        '[agent]\nname = "courier"\nprompt = "prompt.md"\n'
        f'[tools]\nallow = {allow}\n[permissions]\nmode = "ask"\n'))


def sends(path="log.txt"):
    return calls("send_file", {"path": path})


def chat(service, agent="courier", **kw):
    return asyncio.run(service.deliver(actor="owner", agent=agent, thread="chat",
                                       text="send me the log", **kw))


def answered_yes():
    return Policy(rules=RuleBook([Rule(tool="send_file", verdict="allow")]))


def test_in_a_chat_the_file_goes_with_the_answer(make_service, agents_root):
    courier(agents_root)
    service = make_service([sends(), says("here it is")], policy=answered_yes(),
                           asks=AskDesk(timeout=5))
    (folder(service, "owner", "courier") / "log.txt").write_text("up\n")
    reply = chat(service)
    assert reply.ok and reply.text == "here it is"
    assert [f.name for f in reply.files] == ["log.txt"]


def test_it_is_a_write_so_nobody_answering_means_it_is_not_sent(make_service,
                                                                agents_root):
    courier(agents_root)
    service = make_service([sends(), says("could not")], asks=AskDesk(timeout=0.2))
    (folder(service, "owner", "courier") / "log.txt").write_text("up\n")
    assert chat(service).files == ()


def test_a_package_that_does_not_list_it_does_not_get_it(make_service, agents_root):
    courier(agents_root, allow='["read_file", "write_file"]')
    service = make_service([sends(), says("no such tool")], policy=answered_yes(),
                           asks=AskDesk(timeout=5))
    (folder(service, "owner", "courier") / "log.txt").write_text("up\n")
    assert chat(service).files == ()
    last = service.scripted.requests[-1]
    assert "send_file" not in {t["name"] if isinstance(t, dict) else t.name
                               for t in last.get("tools") or []}


def test_the_agent_cannot_send_from_outside_the_folder(make_service, agents_root,
                                                       tmp_path):
    courier(agents_root)
    (tmp_path / "secret.txt").write_text("x")
    service = make_service([sends("../../../../secret.txt"), says("no")],
                           policy=answered_yes(), asks=AskDesk(timeout=5))
    assert chat(service).files == ()


def test_a_scheduled_run_sends_it_at_once_as_a_notice(make_service, agents_root):
    courier(agents_root)
    service = make_service([sends(), says("sent the report")], actors=REACHABLE,
                           asks=AskDesk(timeout=5))
    (folder(service, "owner", "courier") / "log.txt").write_text("weekly\n")
    got = []

    async def telegram(address, text, file=None):
        got.append((address, text, file and file.name))
    service.notices.route("telegram", telegram)
    reply = asyncio.run(service.deliver(actor="owner", agent="courier",
                                        thread="samay-s1-1", text="go",
                                        unattended=True, allow_tools=["send_file"]))
    assert got == [("42", "log.txt", "log.txt")]
    assert reply.files == ()          # gone already; the answer is text


def test_a_scheduled_run_not_allowed_it_ahead_is_refused(make_service, agents_root):
    courier(agents_root)
    service = make_service([sends(), says("refused")], actors=REACHABLE,
                           asks=AskDesk(timeout=5))
    (folder(service, "owner", "courier") / "log.txt").write_text("x\n")
    reply = asyncio.run(service.deliver(actor="owner", agent="courier",
                                        thread="samay-s1-1", text="go",
                                        unattended=True))
    assert reply.refused == ("send_file",)


def test_a_collected_notice_names_its_file(make_service, agents_root):
    courier(agents_root)
    service = make_service([sends(), says("ok")], actors=REACHABLE,
                           asks=AskDesk(timeout=5))
    (folder(service, "owner", "courier") / "log.txt").write_text("x\n")
    asyncio.run(service.deliver(actor="owner", agent="courier", thread="samay-s1-1",
                                text="go", unattended=True, allow_tools=["send_file"]))
    [kept] = service.notices.take("telegram")
    assert kept.as_dict()["file"].endswith("owner/courier/log.txt")

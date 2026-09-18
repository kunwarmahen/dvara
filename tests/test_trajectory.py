"""What a Run remembers about HOW a turn went, and what it refuses to.

Two biases are encoded here, and they pull in opposite directions.

The first is that a trajectory is worth nothing unless it is EXACT. A
generated case asserts what these rows say, so a name recorded for a call
that never ran turns an eval green that should be red -- the failure mode
of a gate is always that it passes. So the tests below assert the
difference between a call that RAN and a call the gate turned away, at
every layer it has to survive: the event, the row, the JSON, and the case.

The second is that this table is somebody's history and it is already on
disk. A column added today is missing from every store created yesterday,
and the symptom is an INSERT that fails on a running service with no
obvious cause -- so the migration is tested by building the old shape by
hand rather than by trusting that a fresh file has every column.

And one refusal, tested as deliberately as the features: ARGUMENTS ARE
NOT RECORDED. A test that pins their absence is what stops somebody
adding them as an obvious convenience.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime

import pytest

from dvara.asks import AskDesk
from dvara.cases import case_from_run, unasserted
from dvara.gate import Decisions, Policy
from dvara.keys import session_key
from dvara.runs import Run, RunStore, ToolStep

from tests.conftest import calls, says, write_package


def scribe(agents_root, name="scribe"):
    """A package whose one tool can change something."""
    write_package(agents_root, name, body=(
        f'[agent]\nname = "{name}"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file", "read_file"]\n'
        '[permissions]\nmode = "ask"\n'))


def permissive(agents_root, name="freehand"):
    """The same package, asking for yolo.

    Both halves have to say it. The ladder is a MINIMUM, so a package
    that ships "ask" caps the owner's --yolo at "ask" -- which is the
    property note 02 built and the reason a test that wants a call to
    actually RUN has to say yolo twice.
    """
    write_package(agents_root, name, body=(
        f'[agent]\nname = "{name}"\nprompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file", "read_file"]\n'
        '[permissions]\nmode = "yolo"\n'))


async def when_asked(desk, *, approve: bool, actor: str = "owner",
                     via: str | None = None):
    while not desk.pending():
        await asyncio.sleep(0)
    ask = desk.pending()[0]
    desk.answer(ask.id, actor=actor, approve=approve, via=via)
    return ask


def a_run(**over) -> Run:
    body = {"actor": "owner", "agent": "scribe", "thread": "t",
            "message": "write it down",
            "started_at": datetime(2026, 9, 17, 12, 0, tzinfo=UTC)}
    return Run(**{**body, **over})


# ---- what the loop reports -------------------------------------------------


def test_a_turn_that_ran_a_tool_says_which_one(make_service, agents_root):
    permissive(agents_root)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("written."),
    ], policy=Policy(mode="yolo"))

    asyncio.run(service.deliver(actor="owner", agent="freehand", thread="t",
                                text="write it down"))

    run = service.runs.recent(limit=1)[0]
    assert run.tools == [ToolStep("write_file", None)]
    assert run.ran_tools == ["write_file"]
    assert run.refused_tools == []


def test_a_refused_call_is_recorded_with_the_code_that_refused_it(
        make_service, agents_root):
    """The most interesting row in the table, and the easiest to lose.

    A denial reaches the loop as an ordinary ToolExecuted carrying a
    refusal code -- Yantra's own decision -- so a service that recorded
    "a tool call happened" without reading that field would write down a
    write_file that never touched the disk.
    """
    scribe(agents_root)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("I could not write that."),
    ])  # no desk: "ask" with no route is read-only tools only

    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="write it down"))

    run = service.runs.recent(limit=1)[0]
    assert len(run.tools) == 1
    assert run.tools[0].name == "write_file"
    assert run.tools[0].ran is False
    assert run.tools[0].refusal  # a code, whatever Yantra currently calls it
    assert run.ran_tools == []
    assert run.refused_tools == ["write_file"]
    # And the refusal was real rather than a note about one.
    work = service._workspace(session_key("owner", "scribe", "t"))
    assert not (work / "notes.txt").exists()


def test_the_order_the_loop_reported_is_the_order_kept(make_service,
                                                       agents_root):
    permissive(agents_root)
    service = make_service([
        calls("write_file", {"path": "a.txt", "content": "one"},
              call_id="c1"),
        calls("read_file", {"path": "a.txt"}, call_id="c2"),
        says("done."),
    ], policy=Policy(mode="yolo"))

    asyncio.run(service.deliver(actor="owner", agent="freehand", thread="t",
                                text="go"))

    run = service.runs.recent(limit=1)[0]
    assert [step.name for step in run.tools] == ["write_file", "read_file"]
    assert run.ran_tools == ["write_file", "read_file"]


def test_a_turn_that_called_nothing_records_nothing(make_service):
    service = make_service([says("hello")])
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                text="hi"))
    assert service.runs.recent(limit=1)[0].tools == []


def test_a_turn_that_crashed_keeps_what_it_did_before_it_crashed(
        make_service, agents_root):
    """The row that matters most, and the one a `finally` has to reach."""
    permissive(agents_root)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        # The script runs out here, so the loop's next call raises.
    ], policy=Policy(mode="yolo"))

    reply = asyncio.run(service.deliver(actor="owner", agent="freehand",
                                        thread="t", text="write it down"))
    assert reply.stop_reason == "error"
    assert service.runs.recent(limit=1)[0].ran_tools == ["write_file"]


def test_arguments_are_not_recorded(make_service, agents_root):
    """A refusal, pinned. See the module docstring on why it is a test."""
    permissive(agents_root)
    service = make_service([
        calls("write_file", {"path": "secrets.txt", "content": "hunter2"}),
        says("written."),
    ], policy=Policy(mode="yolo"))
    asyncio.run(service.deliver(actor="owner", agent="freehand", thread="t",
                                text="write it down"))

    raw = sqlite3.connect(service.runs.path).execute(
        "SELECT tools FROM runs").fetchone()[0]
    assert "write_file" in raw
    assert "hunter2" not in raw
    assert "secrets.txt" not in raw


# ---- where the answer came from --------------------------------------------


def test_an_approval_records_the_door_it_came_through(make_service,
                                                      agents_root):
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("written."),
    ], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down"))
        await when_asked(desk, approve=True, via="telegram")
        return await turn

    asyncio.run(go())
    run = service.runs.recent(limit=1)[0]
    assert run.answered_from == ["telegram"]
    assert run.ran_tools == ["write_file"]


def test_a_refusal_records_its_door_too(make_service, agents_root):
    """"They said no, from their phone" is as much a fact as the yes."""
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("I could not write that."),
    ], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write it down"))
        await when_asked(desk, approve=False, via="telegram")
        return await turn

    asyncio.run(go())
    run = service.runs.recent(limit=1)[0]
    assert run.answered_from == ["telegram"]
    assert run.refused_tools == ["write_file"]


def test_a_turn_that_asked_nobody_has_no_door(make_service):
    service = make_service([says("hello")], asks=AskDesk(timeout=5))
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                text="hi"))
    assert service.runs.recent(limit=1)[0].answered_from == []


def test_an_unanswered_question_names_no_door(make_service, agents_root):
    """A timeout is not a place. Nobody was standing anywhere."""
    scribe(agents_root)
    service = make_service([
        calls("write_file", {"path": "notes.txt", "content": "hi"}),
        says("nobody answered."),
    ], asks=AskDesk(timeout=0.05))
    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="write it down"))
    run = service.runs.recent(limit=1)[0]
    assert run.answered_from == []
    assert run.refused_tools == ["write_file"]


def test_the_doors_are_a_summary_of_the_per_call_answers():
    """One record, read two ways -- so the two cannot come to disagree."""
    seen = Decisions()
    seen.by_person("c1", "telegram")
    seen.by_person("c2", None)          # answered, channel not named
    seen.by_person("c3", "telegram")    # the same door twice
    seen.by_person("c4", "http")
    assert seen.channels == ["telegram", "http"]
    assert seen.of("c1") == "asked:telegram"
    assert seen.of("c2") == "asked"


def test_a_call_with_no_id_records_nothing():
    """A request built by hand carries "", and "" names no call."""
    seen = Decisions()
    seen.by_person("", "telegram")
    assert seen.by_call == {}


# ---- the store -------------------------------------------------------------


def test_a_trajectory_survives_the_round_trip(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(tools=[ToolStep("read_file"),
                              ToolStep("bash", "policy")],
                       answered_from=["telegram"], stop_reason="end_turn"))
    back = store.recent(limit=1)[0]
    assert back.tools == [ToolStep("read_file", None),
                          ToolStep("bash", "policy")]
    assert back.answered_from == ["telegram"]
    store.close()


def test_nothing_recorded_is_stored_as_nothing(tmp_path):
    """NULL rather than "[]" -- an empty list is not a fact worth a byte."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn"))
    row = sqlite3.connect(store.path).execute(
        "SELECT tools, answered_from FROM runs").fetchone()
    assert row == (None, None)
    assert store.recent(limit=1)[0].tools == []
    store.close()


def test_a_store_written_before_these_columns_gains_them(tmp_path):
    """The migration, against the shape that is actually on somebody's disk.

    Built by hand rather than by an older import, because what has to
    work is a FILE, and the file is all a previous version left behind.
    """
    path = tmp_path / "runs.sqlite3"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE runs (
            id TEXT PRIMARY KEY, actor TEXT NOT NULL, agent TEXT NOT NULL,
            thread TEXT NOT NULL, started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL, message TEXT NOT NULL,
            reply TEXT NOT NULL, model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_read_tokens INTEGER NOT NULL DEFAULT 0,
            cache_write_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL, stop_reason TEXT NOT NULL, detail TEXT);
        INSERT INTO runs (id, actor, agent, thread, started_at, ended_at,
                          message, reply, model, stop_reason)
        VALUES ('old1', 'owner', 'scribe', 't', '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:01+00:00', 'from before', 'ok', 'm',
                'end_turn');
    """)
    old.commit()
    old.close()

    store = RunStore(path)
    # The old row survives, and says the true thing about itself: nothing
    # was recorded, because nothing was recording.
    before = store.get("old1")
    assert before.message == "from before"
    assert before.tools == [] and before.answered_from == []
    # And a new row writes without the INSERT failing on a missing column.
    store.record(a_run(tools=[ToolStep("read_file")], stop_reason="end_turn"))
    assert store.recent(limit=1)[0].ran_tools == ["read_file"]
    store.close()


def test_migrating_twice_is_not_an_error(tmp_path):
    path = tmp_path / "runs.sqlite3"
    RunStore(path).close()
    store = RunStore(path)          # every restart runs this again
    store.record(a_run(tools=[ToolStep("bash", "user")],
                       stop_reason="end_turn"))
    assert store.recent(limit=1)[0].refused_tools == ["bash"]
    store.close()


def test_a_column_that_does_not_parse_reads_as_no_trajectory(tmp_path):
    """`dvara runs` does not stop working because a backup came back odd."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(tools=[ToolStep("read_file")], stop_reason="end_turn"))
    store.close()
    db = sqlite3.connect(tmp_path / "runs.sqlite3")
    db.execute("UPDATE runs SET tools = 'not json at all'")
    db.commit()
    db.close()

    store = RunStore(tmp_path / "runs.sqlite3")
    assert store.recent(limit=1)[0].tools == []
    store.close()


def test_names_are_distinct_and_keep_first_use_order():
    run = a_run(tools=[ToolStep("read_file"), ToolStep("bash", "policy"),
                       ToolStep("read_file"), ToolStep("write_file")])
    assert run.ran_tools == ["read_file", "write_file"]
    assert run.refused_tools == ["bash"]


# ---- the case it becomes ---------------------------------------------------


def test_a_case_requires_the_tools_the_turn_actually_used():
    run = a_run(stop_reason="error", detail="RuntimeError: boom",
                tools=[ToolStep("read_file"), ToolStep("write_file")])
    case = case_from_run(run)
    assert case.required_tools == ["read_file", "write_file"]


def test_a_case_never_forbids_anything_on_its_own(make_service):
    """A trajectory is a description; a prohibition is a judgement."""
    run = a_run(stop_reason="error", detail="RuntimeError: boom",
                tools=[ToolStep("read_file"), ToolStep("bash", "policy")])
    case = case_from_run(run)
    assert case.required_tools == ["read_file"]
    assert case.forbidden_tools == []


def test_a_refused_call_is_reported_beside_the_block_not_inside_it():
    run = a_run(stop_reason="error",
                tools=[ToolStep("read_file"), ToolStep("bash", "policy")])
    advice = unasserted(run)
    assert "bash" in advice
    assert 'forbidden_tools = ["bash"]' in advice


def test_a_turn_with_nothing_refused_says_nothing():
    run = a_run(stop_reason="error", tools=[ToolStep("read_file")])
    assert unasserted(run) is None


def test_a_run_from_before_trajectories_still_makes_a_case():
    """Every row already on disk. The feature may not break the old ones."""
    run = a_run(stop_reason="error", detail="RuntimeError: boom")
    case = case_from_run(run)
    assert case.required_tools == []
    assert unasserted(run) is None


def test_the_case_renders_the_assertion_it_was_given():
    from yantra import render_case
    run = a_run(stop_reason="error", detail="boom",
                tools=[ToolStep("read_file"), ToolStep("write_file")])
    block = render_case(case_from_run(run))
    assert 'required_tools = ["read_file", "write_file"]' in block


def test_the_case_round_trips_through_a_package(tmp_path, agents_root):
    """Rendered here, read back by Yantra's own loader, unchanged."""
    from yantra import load_cases
    from dvara.cases import append
    scribe(agents_root)
    run = a_run(stop_reason="error", detail="boom",
                tools=[ToolStep("read_file"), ToolStep("write_file")])
    append(agents_root / "scribe", case_from_run(run))
    loaded = load_cases(agents_root / "scribe")
    assert loaded[0].required_tools == ["read_file", "write_file"]


# ---- what the owner sees ---------------------------------------------------


def test_runs_prints_the_path_the_turn_took(make_service, agents_root,
                                            capsys, tmp_path, monkeypatch):
    from dvara.cli import main
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn",
                       tools=[ToolStep("read_file"),
                              ToolStep("bash", "policy")],
                       answered_from=["telegram"]))
    store.close()
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "runs"])

    out = capsys.readouterr().out
    assert "read_file -> bash(refused)" in out
    assert "answered from telegram" in out


def test_case_prints_what_it_would_not_assert(agents_root, capsys, tmp_path):
    from dvara.cli import main
    scribe(agents_root)
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    run = a_run(stop_reason="error", detail="boom",
                tools=[ToolStep("read_file"), ToolStep("bash", "policy")])
    store.record(run)
    store.close()
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "case", run.id])

    printed = capsys.readouterr()
    assert 'required_tools = ["read_file"]' in printed.out
    # The judgement stays on stderr, so the block above stays pasteable.
    assert "bash" not in printed.out.split("required_tools")[0]
    assert "forbidden_tools" in printed.err


@pytest.mark.parametrize("raw", ['[]', 'null', '{"a": 1}', '"text"'])
def test_no_stored_shape_makes_a_row_unreadable(tmp_path, raw):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn"))
    store.close()
    db = sqlite3.connect(tmp_path / "runs.sqlite3")
    db.execute("UPDATE runs SET tools = ?", (raw,))
    db.commit()
    db.close()
    store = RunStore(tmp_path / "runs.sqlite3")
    assert isinstance(store.recent(limit=1)[0].tools, list)
    store.close()


def test_what_the_column_holds_is_names_codes_and_who_decided(tmp_path):
    """The stored shape, pinned: a flat triple, not a dict of extras."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn",
                       tools=[ToolStep("bash", "timeout"),
                              ToolStep("read_file", None, "rule:58fbf4ad")]))
    raw = sqlite3.connect(store.path).execute(
        "SELECT tools FROM runs").fetchone()[0]
    assert json.loads(raw) == [["bash", "timeout", None],
                               ["read_file", None, "rule:58fbf4ad"]]
    store.close()


def test_a_row_written_before_the_third_element_still_reads(tmp_path):
    """An OLD row is a row with less to say, not a broken one."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn"))
    store.close()
    db = sqlite3.connect(tmp_path / "runs.sqlite3")
    db.execute("UPDATE runs SET tools = ?",
               (json.dumps([["read_file", None], ["bash", "policy"]]),))
    db.commit()
    db.close()

    store = RunStore(tmp_path / "runs.sqlite3")
    back = store.recent(limit=1)[0]
    assert back.ran_tools == ["read_file"]
    assert back.refused_tools == ["bash"]
    assert [step.decided_by for step in back.tools] == [None, None]
    store.close()

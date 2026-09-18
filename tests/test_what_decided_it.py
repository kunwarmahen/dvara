"""Why a call went the way it did, and which version of the agent did it.

The bias: every fact here is one an owner asks for MONTHS later, when the
thing that could have answered it has gone. A question approved from a
phone at two in the morning, a standing rule that has quietly been saving
you a question a day, a prompt you fixed on Tuesday that changed a
conversation already in progress -- none of them leaves a trace unless
somebody decided in advance that it should.

Two of these were recorded per TURN until the framework grew a call id on
a permission request. Counting would have worked -- a batch is gated
sequentially and reported in submission order -- and that is exactly the
coupling the seam exists to avoid, because a drift in either ordering
files one person's approval against a different call without raising.

So the tests below deliberately run TWO calls in one batch, and answer
them on two different channels. With one call, an implementation that
records per turn passes everything here.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from dvara.asks import AskDesk
from dvara.gate import Policy
from dvara.rules import Rule, RuleBook
from dvara.runs import Run, RunStore, ToolStep

from tests.conftest import says, write_package
from yantra.types import Message, ModelResponse, ToolCall, Usage


def two_calls(*, model: str = "test-model") -> ModelResponse:
    """One batch, two calls -- gated concurrently, reported in order."""
    return ModelResponse(
        message=Message("assistant", [
            ToolCall("call-a", "write_file", {"path": "a.txt",
                                              "content": "one"}),
            ToolCall("call-b", "write_file", {"path": "b.txt",
                                              "content": "two"}),
        ]),
        stop_reason="tool_use", usage=Usage(), model=model,
    )


def scribe(agents_root, *, name="scribe", version="0.1.0", mode="ask"):
    write_package(agents_root, name, body=(
        f'[agent]\nname = "{name}"\nversion = "{version}"\n'
        f'prompt = "prompt.md"\n'
        '[tools]\nallow = ["write_file", "read_file"]\n'
        f'[permissions]\nmode = "{mode}"\n'))


def a_run(**over) -> Run:
    body = {"actor": "owner", "agent": "scribe", "thread": "t",
            "message": "go", "started_at": datetime.now(UTC)}
    return Run(**{**body, **over})


# ---- which call a person released ------------------------------------------


async def answer_each(desk, answers):
    """Answer questions as they arrive, one at a time.

    A BATCH IS GATED SEQUENTIALLY, deliberately: Yantra puts one question
    at a time because three arriving at once in a chat window is a pile
    rather than a prompt. So there is never more than one pending, and a
    test that waited for two would wait forever.
    """
    for approve, via in answers:
        while not desk.pending():
            await asyncio.sleep(0)
        ask = desk.pending()[0]
        desk.answer(ask.id, actor="owner", approve=approve, via=via)
        while desk.get(ask.id) is not None:
            await asyncio.sleep(0)


def test_two_approvals_in_one_batch_land_on_their_own_calls(make_service,
                                                            agents_root):
    """The whole reason the framework grew `PermissionRequest.call_id`.

    Two calls to the SAME tool, decided differently, on two different
    channels. Nothing visible in the events tells them apart -- same
    name, same turn -- so the only thing that can file each answer
    against the call it released is the id the request carried.
    """
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([two_calls(), says("done.")], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write both"))
        await answer_each(desk, [(False, "terminal"), (True, "telegram")])
        return await turn

    asyncio.run(go())
    run = service.runs.recent(limit=1)[0]
    assert len(run.tools) == 2
    assert [step.decided_by for step in run.tools] == \
        ["asked:terminal", "asked:telegram"]
    # And the refusal landed on the call that was refused, not the other.
    assert [step.ran for step in run.tools] == [False, True]


def test_the_doors_are_still_summarised_on_the_turn(make_service,
                                                    agents_root):
    scribe(agents_root)
    desk = AskDesk(timeout=5)
    service = make_service([two_calls(), says("done.")], asks=desk)

    async def go():
        turn = asyncio.create_task(service.deliver(
            actor="owner", agent="scribe", thread="t", text="write both"))
        await answer_each(desk, [(True, "telegram"), (True, "telegram")])
        return await turn

    asyncio.run(go())
    assert service.runs.recent(limit=1)[0].answered_from == ["telegram"]


def test_a_call_the_rung_allowed_records_no_decision(make_service,
                                                     agents_root):
    """Most calls. A field that said "nothing in particular" would be noise."""
    scribe(agents_root, name="freehand", mode="yolo")
    service = make_service([two_calls(), says("done.")],
                           policy=Policy(mode="yolo"))
    asyncio.run(service.deliver(actor="owner", agent="freehand", thread="t",
                                text="write both"))
    run = service.runs.recent(limit=1)[0]
    assert [step.decided_by for step in run.tools] == [None, None]


# ---- which rule settled it -------------------------------------------------


def test_a_standing_deny_is_recorded_against_the_call_it_stopped(
        make_service, agents_root):
    scribe(agents_root)
    book = RuleBook.from_dict({"rule": [
        {"tool": "write_file", "args": {"path": "a.txt"},
         "verdict": "deny", "reason": "not that one"},
    ]})
    service = make_service([two_calls(), says("done.")],
                           policy=Policy(mode="yolo", rules=book))
    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="write both"))

    run = service.runs.recent(limit=1)[0]
    denied = next(iter(book))
    # The rule bit the call it names, and only that one.
    assert run.tools[0].decided_by == f"rule:{denied.id}"
    assert run.tools[0].ran is False
    assert run.tools[1].decided_by is None
    assert run.rules_used == [denied.id]


def test_a_standing_yes_is_recorded_even_though_nothing_visible_happened(
        make_service, agents_root):
    """The question you were NOT asked is the one nobody can see.

    A deny announces itself -- the model is told, the turn changes shape.
    An allow is invisible by construction: the call simply runs, exactly
    as it would have if you had been woken up and said yes. Recording it
    is the only way `dvara rules` can tell a rule that is earning its
    place from one that has never matched anything.
    """
    scribe(agents_root)
    book = RuleBook.from_dict({"rule": [
        {"tool": "write_file", "verdict": "allow"},
    ]})
    service = make_service([two_calls(), says("done.")],
                           asks=AskDesk(timeout=5),
                           policy=Policy(mode="ask", rules=book))
    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="write both"))

    run = service.runs.recent(limit=1)[0]
    allowed = next(iter(book))
    assert [step.decided_by for step in run.tools] == \
        [f"rule:{allowed.id}"] * 2
    assert [step.ran for step in run.tools] == [True, True]


def test_a_rules_id_follows_what_it_says_not_where_it_sits():
    same = Rule(tool="bash", verdict="allow", args={"command": ("git status",)})
    twin = Rule(tool="bash", verdict="allow", args={"command": ("git status",)},
                reason="a sentence for the model, reworded")
    edited = Rule(tool="bash", verdict="allow",
                  args={"command": ("git status", "git diff")})
    assert same.id == twin.id          # rewording is not a new rule
    assert same.id != edited.id        # widening one is
    assert len(same.id) == 8


def test_counting_is_over_calls_not_turns(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn", tools=[
        ToolStep("write_file", None, "rule:aaaa1111"),
        ToolStep("write_file", None, "rule:aaaa1111"),
        ToolStep("bash", "policy", "rule:bbbb2222"),
    ]))
    assert store.rule_counts() == {"aaaa1111": 2, "bbbb2222": 1}
    store.close()


def test_counting_can_be_windowed(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    old = datetime.now(UTC) - timedelta(days=90)
    store.record(a_run(started_at=old, stop_reason="end_turn",
                       tools=[ToolStep("bash", None, "rule:aaaa1111")]))
    store.record(a_run(stop_reason="end_turn",
                       tools=[ToolStep("bash", None, "rule:aaaa1111")]))
    assert store.rule_counts()["aaaa1111"] == 2
    recent = store.rule_counts(datetime.now(UTC) - timedelta(days=30))
    assert recent["aaaa1111"] == 1
    store.close()


def test_a_person_is_not_counted_as_a_rule(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn",
                       tools=[ToolStep("bash", None, "asked:telegram")]))
    assert store.rule_counts() == {}
    store.close()


def test_rules_lists_every_rule_and_marks_the_ones_that_never_fired(
        tmp_path, agents_root, capsys):
    from dvara.cli import main
    policy = tmp_path / "policy.toml"
    policy.write_text(
        '[[rule]]\ntool = "bash"\nargs = { command = ["git status"] }\n'
        'verdict = "allow"\n\n'
        '[[rule]]\ntool = "write_file"\nargs = { path = ["*.env"] }\n'
        'verdict = "deny"\n', encoding="utf-8")
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")

    book = RuleBook.from_toml(policy)
    used, never = list(book)
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn",
                       tools=[ToolStep("bash", None, f"rule:{used.id}")]))
    store.close()

    main(["--root", str(agents_root), "--actors", str(actors),
          "--policy", str(policy), "--state", str(tmp_path / "state"),
          "rules"])

    out = capsys.readouterr().out
    assert "allow  bash command=git status" in out
    assert "deny   write_file path=*.env" in out
    assert "never matched" in out
    # The one that fired has a number; the one that never did has a dot.
    fired = [line for line in out.splitlines() if "bash" in line][0]
    unused = [line for line in out.splitlines() if "write_file" in line][0]
    assert "1" in fired and "·" in unused
    assert never.id not in out          # ids are internal, not the report


def test_rules_with_no_policy_file_says_so_rather_than_printing_nothing(
        tmp_path, agents_root, capsys):
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    assert main(["--root", str(agents_root), "--actors", str(actors),
                 "--state", str(tmp_path / "state"), "rules"]) == 0
    assert "no standing rules" in capsys.readouterr().out


# ---- which version of the agent --------------------------------------------


def test_a_run_records_the_version_the_package_declared(make_service,
                                                        agents_root):
    scribe(agents_root, version="1.2.3")
    service = make_service([says("hello")])
    asyncio.run(service.deliver(actor="owner", agent="scribe", thread="t",
                                text="hi"))
    assert service.runs.recent(limit=1)[0].agent_version == "1.2.3"


def test_a_package_with_no_version_records_none(make_service):
    service = make_service([says("hello")])
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                text="hi"))
    assert service.runs.recent(limit=1)[0].agent_version is None


def test_an_edit_mid_conversation_shows_up_in_the_ledger(tmp_path,
                                                         agents_root, capsys):
    """§11.2, settled: the edit applies, and it is no longer invisible."""
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    started = datetime.now(UTC)
    store.record(a_run(started_at=started, stop_reason="end_turn",
                       agent_version="0.1.0"))
    store.record(a_run(started_at=started + timedelta(minutes=5),
                       stop_reason="end_turn", agent_version="0.2.0"))
    store.close()

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "runs"])

    out = capsys.readouterr().out
    assert "changed after this turn: 0.1.0 -> 0.2.0" in out


def test_the_same_version_twice_says_nothing(tmp_path, agents_root, capsys):
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    started = datetime.now(UTC)
    for minutes in (0, 5):
        store.record(a_run(started_at=started + timedelta(minutes=minutes),
                           stop_reason="end_turn", agent_version="0.1.0"))
    store.close()

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "runs"])
    assert "changed after this turn" not in capsys.readouterr().out


def test_two_threads_at_different_versions_are_not_a_change(tmp_path,
                                                            agents_root,
                                                            capsys):
    """The comparison is per CONVERSATION, not per agent."""
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    started = datetime.now(UTC)
    store.record(a_run(thread="one", started_at=started,
                       stop_reason="end_turn", agent_version="0.1.0"))
    store.record(a_run(thread="two",
                       started_at=started + timedelta(minutes=5),
                       stop_reason="end_turn", agent_version="0.2.0"))
    store.close()

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "runs"])
    assert "changed after this turn" not in capsys.readouterr().out


def test_the_decision_shows_up_in_the_ledger(tmp_path, agents_root, capsys):
    from dvara.cli import main
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n", encoding="utf-8")
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    store.record(a_run(stop_reason="end_turn", tools=[
        ToolStep("read_file", None),
        ToolStep("bash", "policy", "rule:58fbf4ad"),
        ToolStep("write_file", None, "asked:telegram"),
    ]))
    store.close()

    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"), "runs"])

    out = capsys.readouterr().out
    assert ("read_file -> bash(refused)[rule:58fbf4ad] -> "
            "write_file[asked:telegram]") in out


def test_a_case_says_which_version_produced_it(agents_root):
    from dvara.cases import case_from_run
    run = a_run(stop_reason="error", detail="boom", model="qwen",
                agent_version="1.2.3")
    assert "1.2.3" in case_from_run(run).description


def test_a_case_from_a_package_with_no_version_still_reads(agents_root):
    from dvara.cases import case_from_run
    run = a_run(stop_reason="error", detail="boom", model="qwen")
    assert "None" not in case_from_run(run).description

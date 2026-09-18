"""Bias: an owner's mistake answered as if a stranger had made it.

The CLI is where the two error kinds have to stay apart. A wrong actors
file is a ConfigProblem and belongs on stderr with a non-zero exit; a
person asking for an agent they may not have is a Refused and belongs on
stdout as an answer. Confusing the two either floods a channel with the
owner's tracebacks or hides a broken config behind a polite sentence.
"""

from __future__ import annotations

import io
import json

import pytest

from dvara.cli import main
from tests.conftest import EXAMPLES, write_package


@pytest.fixture
def owned(tmp_path, monkeypatch):
    """An owner's whole setup: a root of agents, a file of people, state."""
    root = tmp_path / "agents"
    root.mkdir()
    write_package(root, "greeter")
    actors = tmp_path / "actors.toml"
    actors.write_text('[actor.owner]\n', encoding="utf-8")
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"test-model": {"input": 0.0, "output": 0.0}}))
    monkeypatch.setenv("YANTRA_PRICES", str(prices))
    return ["--root", str(root), "--actors", str(actors),
            "--state", str(tmp_path / "state")]


def test_agents_lists_what_the_service_can_offer(owned, capsys):
    assert main([*owned, "agents"]) == 0
    assert "greeter" in capsys.readouterr().out


def test_a_broken_actors_file_exits_non_zero_on_stderr(tmp_path, owned, capsys):
    actors = tmp_path / "bad.toml"
    actors.write_text("[actor.owner]\nmax_usd_per_dayz = 1\n", encoding="utf-8")
    args = [*owned]
    args[args.index("--actors") + 1] = str(actors)
    assert main([*args, "agents"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "max_usd_per_dayz" in captured.err


def test_a_missing_agent_root_is_an_owners_error(tmp_path, owned):
    args = [*owned]
    args[args.index("--root") + 1] = str(tmp_path / "nowhere")
    assert main([*args, "agents"]) == 2


def test_runs_is_empty_before_anything_has_happened(owned, capsys):
    assert main([*owned, "runs"]) == 0
    assert "no runs" in capsys.readouterr().out


def test_the_shipped_example_root_lists_its_agents(tmp_path, capsys):
    # An example that does not load is documentation that lies.
    assert main(["--root", str(EXAMPLES / "agents"),
                 "--actors", str(EXAMPLES / "actors.toml"),
                 "--state", str(tmp_path / "state"), "agents"]) == 0
    out = capsys.readouterr().out
    assert "greeter" in out and "0.1.0" in out


def test_a_failure_tells_the_owner_why_not_just_that(owned, capsys,
                                                     monkeypatch):
    # The polite sentence is for a channel. The person at the terminal is
    # the one who can fix a wrong base URL, and they need the reason.
    from dvara.service import Service

    async def broken(self, **kwargs):
        from dvara.service import Reply
        return Reply(text="that went wrong at my end", run_id="abc",
                     agent="greeter", stop_reason="error",
                     detail="ProviderError: 404: 404 page not found")

    monkeypatch.setattr(Service, "deliver", broken)
    assert main([*owned, "say", "--actor", "owner", "--agent", "greeter",
                 "hello"]) == 1
    captured = capsys.readouterr()
    assert captured.out.startswith("that went wrong at my end")
    assert "404 page not found" in captured.err


def test_the_ledger_shows_why_a_run_failed(owned, capsys):
    from datetime import UTC, datetime

    from dvara.cli import _service
    from dvara.runs import Run

    args = main.__globals__["build_parser"]().parse_args([*owned, "runs"])
    service = _service(args)
    try:
        service.runs.record(Run(actor="owner", agent="greeter", thread="t",
                                message="hello", started_at=datetime.now(UTC),
                                stop_reason="error",
                                detail="ProviderError: 404: 404 page not found"))
    finally:
        service.close()
    assert main([*owned, "runs"]) == 0
    assert "404 page not found" in capsys.readouterr().out


# ---- the terminal as a channel ---------------------------------------------

def test_without_ask_the_service_has_no_desk_at_all(owned):
    from dvara.cli import _service, build_parser
    service = _service(build_parser().parse_args([*owned, "agents"]))
    try:
        assert service.asks is None
    finally:
        service.close()


def test_ask_gives_the_service_somewhere_to_put_a_question(owned):
    from dvara.cli import _service, build_parser
    args = build_parser().parse_args([*owned, "--ask", "--ask-timeout", "7",
                                      "agents"])
    service = _service(args)
    try:
        assert service.asks is not None
        assert service.asks.timeout == 7
        # And no notifier yet: `serve` must not inherit a prompt that
        # would print a question into a log nobody reads.
        assert service.asks.notify is None
    finally:
        service.close()


def test_a_deadline_of_nothing_is_the_owners_mistake_not_a_traceback(owned,
                                                                     capsys):
    assert main([*owned, "--ask", "--ask-timeout", "0", "agents"]) == 2
    assert "denies before it asks" in capsys.readouterr().err


def typing(monkeypatch, answer: str) -> None:
    """Somebody at the keyboard, as a line of input rather than a stub.

    The read is ``sys.stdin``'s now and not ``input()``'s, because a
    question that times out must not leave a thread parked in a blocking
    read (cli._typed_line). Feeding the real object is also the more
    honest test: what the front end does with the stream is part of what
    is under test.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{answer}\n"))


def test_say_prints_the_question_and_takes_the_answer(owned, monkeypatch,
                                                      capsys):
    # The keyboard is the channel. Both halves come from this front end:
    # the question is printed here, and the answer is a keystroke.
    typing(monkeypatch, "y")

    import asyncio

    from dvara.asks import AskDesk
    from dvara.cli import _ask_at_the_keyboard

    desk = AskDesk(timeout=5)

    async def go():
        desk.notify = _ask_at_the_keyboard(desk)
        return await desk.put(actor="owner", agent="scribe", thread="t",
                              tool="write_file",
                              summary="notes.txt <- 2 bytes")

    assert asyncio.run(go()).approved
    err = capsys.readouterr().err
    assert "scribe wants to run write_file" in err
    assert "notes.txt <- 2 bytes" in err
    # The prompt goes to stderr with the question, not to stdout: the
    # answer on stdout is the agent's, and a prompt in the middle of it is
    # a line somebody piping this has to strip.
    assert "approve? [y/N]" in err


@pytest.mark.parametrize("answer,approved",
                         [("y", True), ("yes", True), ("Y", True),
                          ("", False), ("n", False), ("maybe", False)])
def test_anything_that_is_not_yes_is_no(owned, monkeypatch, answer, approved):
    # A stray newline is not consent, and neither is "maybe".
    typing(monkeypatch, answer)

    import asyncio

    from dvara.asks import AskDesk
    from dvara.cli import _ask_at_the_keyboard

    desk = AskDesk(timeout=5)

    async def go():
        desk.notify = _ask_at_the_keyboard(desk)
        return await desk.put(actor="owner", agent="scribe", thread="t",
                              tool="write_file", summary="notes.txt")

    assert asyncio.run(go()).approved is approved


# ---- the policy file --------------------------------------------------------

def test_with_no_policy_file_the_service_has_no_rules(owned):
    """The property the whole rule layer rests on: an owner who has never
    written a policy file is not missing one, and the gate underneath is
    note 02's, chosen by the same branch it always was."""
    from dvara.cli import _service, build_parser
    service = _service(build_parser().parse_args([*owned, "agents"]))
    try:
        assert len(service.policy.rules) == 0
    finally:
        service.close()


def test_a_named_policy_file_that_is_not_there_is_an_owners_error(owned,
                                                                  capsys,
                                                                  tmp_path):
    """Being handed silence for a typo'd path would mean a policy file
    that does nothing and no way to tell."""
    assert main([*owned, "--policy", str(tmp_path / "nope.toml"),
                 "agents"]) == 2
    assert "no policy file" in capsys.readouterr().err


def test_a_policy_file_reaches_the_gate(owned, tmp_path):
    from dvara.cli import _service, build_parser
    policy = tmp_path / "policy.toml"
    policy.write_text('[[rule]]\ntool = "bash"\nverdict = "deny"\n',
                      encoding="utf-8")
    args = build_parser().parse_args([*owned, "--policy", str(policy),
                                      "agents"])
    service = _service(args)
    try:
        assert len(service.policy.rules) == 1
        assert service.policy.gate("yolo") is not None
    finally:
        service.close()


def test_a_wildcard_in_an_allow_stops_the_service_starting(owned, capsys,
                                                           tmp_path):
    """The one mistake in this format that is invisible in a diff, caught
    before a single turn runs."""
    policy = tmp_path / "policy.toml"
    policy.write_text('[[rule]]\ntool = "bash"\n'
                      'args = { command = "git status*" }\n'
                      'verdict = "allow"\n', encoding="utf-8")
    assert main([*owned, "--policy", str(policy), "agents"]) == 2
    assert "wildcard" in capsys.readouterr().err


# ---- the failure loop -------------------------------------------------------

def _one_run(owned, tmp_path, **overrides):
    """A recorded run in the owner's own store, ready to draw a case from."""
    from datetime import UTC, datetime

    from dvara.runs import Run, RunStore
    store = RunStore(tmp_path / "state" / "runs.sqlite3")
    fields = dict(actor="owner", agent="greeter", thread="t",
                  message="do the thing",
                  started_at=datetime(2026, 9, 17, 9, 30, tzinfo=UTC),
                  stop_reason="error", detail="ToolError: boom",
                  id="a8ba6c09f2d9")
    fields.update(overrides)
    store.record(Run(**fields))
    store.close()
    return fields["id"]


def test_case_prints_a_block_a_person_can_paste(owned, tmp_path, capsys):
    _one_run(owned, tmp_path)
    assert main([*owned, "case", "a8ba6c09"]) == 0
    out = capsys.readouterr()
    assert out.out.startswith("[[case]]")
    # The warning goes to stderr so the block above stays pasteable.
    assert "somebody's own words" in out.err


def test_a_prefix_is_enough_and_a_wrong_one_is_not(owned, tmp_path, capsys):
    _one_run(owned, tmp_path)
    assert main([*owned, "case", "nope"]) == 1
    assert "no run matching" in capsys.readouterr().err


def test_case_does_not_touch_the_package_without_write(owned, tmp_path):
    from dvara.cases import suite_file
    _one_run(owned, tmp_path)
    assert main([*owned, "case", "a8ba6c09"]) == 0
    assert not suite_file(tmp_path / "agents" / "greeter").exists()


def test_write_puts_it_in_the_packages_gate(owned, tmp_path, capsys):
    from yantra import load_cases

    from dvara.cases import suite_file
    _one_run(owned, tmp_path)
    assert main([*owned, "case", "a8ba6c09", "--write"]) == 0
    package = tmp_path / "agents" / "greeter"
    assert suite_file(package).exists()
    assert [c.id for c in load_cases(package)] == ["trace-a8ba6c09"]
    # And it says how to run the thing it just wrote.
    assert "--eval --case" in capsys.readouterr().out


def test_a_refused_run_is_an_error_with_a_reason(owned, tmp_path, capsys):
    _one_run(owned, tmp_path, stop_reason="refused", detail=None)
    assert main([*owned, "case", "a8ba6c09"]) == 1
    assert "before any agent ran" in capsys.readouterr().err


# ---- speaking as a channel identity ----------------------------------------

def test_as_maps_a_channel_identity_onto_an_actor():
    from dvara.cli import _as_channel
    channel = _as_channel("telegram:8675309")
    assert (channel.kind, channel.id) == ("telegram", "8675309")


def test_as_splits_on_the_first_colon_only():
    """A kind cannot contain one; plenty of native ids can."""
    from dvara.cli import _as_channel
    assert _as_channel("matrix:@me:example.org").id == "@me:example.org"


@pytest.mark.parametrize("spec", ["telegram", "telegram:", ":8675309", ":"])
def test_a_malformed_as_is_an_error_not_a_guess(spec):
    from dvara.cli import _as_channel
    from dvara.errors import ConfigProblem
    with pytest.raises(ConfigProblem):
        _as_channel(spec)


def test_an_actor_and_a_channel_cannot_both_be_given(owned):
    from dvara.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args([*owned, "say", "--actor", "owner",
                                   "--as", "telegram:1", "--agent", "greeter",
                                   "hi"])


def test_saying_nothing_about_who_is_talking_is_an_error(owned):
    from dvara.cli import build_parser
    with pytest.raises(SystemExit):
        build_parser().parse_args([*owned, "say", "--agent", "greeter", "hi"])


# ---- the bot -------------------------------------------------------------


def test_telegram_without_a_token_says_which_variable_is_missing(owned,
                                                                 capsys):
    """A missing credential is the owner's, and is never a polite sentence.

    The check is before anything else on purpose: a bot that got as far
    as resolving a package before complaining about a token has already
    run somebody's Python to find out something it could have known from
    the environment.
    """
    assert main([*owned, "telegram", "--agent", "greeter"]) == 2
    assert "TELEGRAM_TOKEN" in capsys.readouterr().err


def test_a_token_on_the_command_line_is_not_a_thing_you_can_do(owned):
    """There is no --token, and that is the feature.

    A bot token is a credential, and a credential on a command line is in
    the shell history and readable in every `ps` on the box.
    """
    with pytest.raises(SystemExit):
        main([*owned, "telegram", "--agent", "greeter", "--token", "x:y"])


def test_a_bad_token_is_refused_before_a_single_poll(owned, capsys,
                                                     monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "not-a-token")
    assert main([*owned, "telegram", "--agent", "greeter"]) == 2
    assert "BotFather" in capsys.readouterr().err


def test_an_agent_that_is_not_there_is_named_before_the_bot_starts(owned,
                                                                   capsys,
                                                                   monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "8675309:AAnot-a-real-token")
    assert main([*owned, "telegram", "--agent", "ghost"]) == 2
    assert "ghost" in capsys.readouterr().err

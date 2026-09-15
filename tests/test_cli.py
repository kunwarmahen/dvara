"""Bias: an owner's mistake answered as if a stranger had made it.

The CLI is where the two error kinds have to stay apart. A wrong actors
file is a ConfigProblem and belongs on stderr with a non-zero exit; a
person asking for an agent they may not have is a Refused and belongs on
stdout as an answer. Confusing the two either floods a channel with the
owner's tracebacks or hides a broken config behind a polite sentence.
"""

from __future__ import annotations

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

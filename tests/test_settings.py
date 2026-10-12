"""The owner's files, changed from a page (settings.py, tomledit.py).

The bias these tests encode: A CHANGE FROM A PAGE THAT BREAKS THE FILE,
OR TAKES THE OWNER'S WORDS WITH IT. A person added from a form must
leave every other line -- comments, other people, keys the form doesn't
show -- as it was; a change Dvara couldn't load must not be written at
all; and the file before is kept. The other bias is a page reaching
outside Dvara's folders: names are names, never paths.
"""

from __future__ import annotations

import json
import tomllib

import pytest

from dvara import settings, tomledit
from dvara.errors import ConfigProblem

ACTORS = """\
# Who may talk to your agents. Comments like this one must survive.
[actor.owner]
setu = "~/.local/state/setu"
setu_manage = true
max_wait_per_day = 600     # a key the page doesn't show
[[actor.owner.channel]]
kind = "telegram"
id = "111"
[[actor.owner.channel]]
kind = "slack"
id = "U1"

# a note about the guest
[actor.guest]
agents = ["greeter"]
"""


@pytest.fixture
def actors(tmp_path):
    path = tmp_path / "actors.toml"
    path.write_text(ACTORS)
    return path


def test_a_new_person_is_added_and_every_other_line_is_kept(actors):
    got = settings.set_person(actors, "priya", {"agents": ["greeter"], "setu": "own",
                                                "telegram": ["8675309"],
                                                "max_usd_per_day": 0.5})
    assert got["setu"] == "own" and got["telegram"] == ["8675309"]
    text = actors.read_text()
    assert text.startswith(ACTORS)                       # byte for byte
    assert tomllib.loads(text)["actor"]["priya"]["setu"] is True
    assert (actors.parent / "actors.toml.bak").read_text() == ACTORS


def test_a_change_keeps_what_the_form_does_not_show(actors):
    settings.set_person(actors, "owner", {"telegram": ["222"], "phone": True})
    owner = tomllib.loads(actors.read_text())["actor"]["owner"]
    assert owner["max_wait_per_day"] == 600 and owner["setu_manage"] is True
    assert {(c["kind"], c["id"]) for c in owner["channel"]} == {("slack", "U1"),
                                                                ("telegram", "222")}
    assert "# a note about the guest" in actors.read_text()
    assert "[actor.guest]" in actors.read_text()


def test_a_change_dvara_could_not_load_is_not_written(actors):
    with pytest.raises(ConfigProblem, match="permissions"):
        settings.set_person(actors, "guest", {"permissions": "everything"})
    with pytest.raises(ConfigProblem, match="Telegram id is a number"):
        settings.set_person(actors, "guest", {"telegram": ["@guest"]})
    assert actors.read_text() == ACTORS


def test_a_name_is_never_a_path(actors, tmp_path):
    for bad in ("../x", "a/b", "", "x" * 41):
        with pytest.raises(ConfigProblem):
            settings.set_person(actors, bad, {})
    with pytest.raises(ConfigProblem):
        settings.set_agent(tmp_path, "../etc", {})


def test_removing_a_person_takes_their_table_and_nothing_else(actors):
    settings.remove_person(actors, "guest")
    text = actors.read_text()
    assert "[actor.guest]" not in text and "[[actor.owner.channel]]" in text
    with pytest.raises(ConfigProblem):
        settings.remove_person(actors, "owner")          # nobody left to serve


def test_the_rules_are_written_and_a_wide_allow_refused(tmp_path):
    policy = tmp_path / "policy.toml"
    settings.set_rules(policy, [{"tool": "bash", "args": {"command": "git status"},
                                 "verdict": "allow"}])
    assert tomllib.loads(policy.read_text())["rule"][0]["args"] == {"command": "git status"}
    before = policy.read_text()
    with pytest.raises(ConfigProblem):
        settings.set_rules(policy, [{"tool": "bash", "args": {"command": "git *"},
                                     "verdict": "allow"}])
    assert policy.read_text() == before


def agent(root, name="greeter"):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "agent.toml").write_text(
        '# my greeter\n[agent]\nname = "greeter"\nprompt = "prompt.md"\n\n'
        '[tools]\nallow = ["ask_user"]\n')
    (folder / "prompt.md").write_text("Be brief.\n")
    return folder


def test_an_agent_is_changed_as_yantra_loads_it(tmp_path):
    folder = agent(tmp_path)
    settings.set_agent(tmp_path, "greeter", {"memory": {"via": "local"}}, "Be kind.\n")
    meta = tomllib.loads((folder / "agent.toml").read_text())
    assert meta["memory"] == {"via": "local"} and meta["tools"]["allow"] == ["ask_user"]
    assert (folder / "agent.toml").read_text().startswith("# my greeter")
    assert (folder / "prompt.md").read_text() == "Be kind.\n"
    before = (folder / "agent.toml").read_text()
    with pytest.raises(ConfigProblem):
        settings.set_agent(tmp_path, "greeter", {"memory": {"by": "magic"}})
    assert (folder / "agent.toml").read_text() == before


def test_an_agent_added_from_an_example_and_removed_aside(tmp_path):
    examples, root = tmp_path / "examples", tmp_path / "agents"
    agent(examples)
    root.mkdir()
    settings.add_agent(root, "helper", examples / "greeter")
    assert tomllib.loads((root / "helper" / "agent.toml").read_text())["agent"]["name"] \
        == "helper"
    aside = settings.remove_agent(root, "helper")
    assert not (root / "helper").exists() and (aside / "agent.toml").is_file()


def test_a_whole_file_as_text_is_checked_first(actors):
    with pytest.raises(ConfigProblem, match="unknown key"):
        settings.write_text("actors", actors, "[actor.x]\nbogus = 1\n")
    assert actors.read_text() == ACTORS
    settings.write_text("actors", actors, "[actor.x]\n")
    assert actors.read_text() == "[actor.x]\n"


def test_the_command_speaks_json_and_refuses_with_exit_two(actors, capsys, monkeypatch):
    import io

    from dvara.cli import main
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"agents": ["greeter"]})))
    assert main(["--actors", str(actors), "settings", "person", "ravi"]) == 0
    assert json.loads(capsys.readouterr().out)["person"]["id"] == "ravi"
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert main(["--actors", str(actors), "settings", "text", "actors"]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_the_editor_leaves_a_table_inside_a_string_alone():
    text = 'a = """\n[actor.fake]\n"""\n[actor.real]\nx = 1\n'
    assert tomledit.span(text, "actor.fake") is None
    assert tomledit.drop(text, "actor.real").startswith('a = """\n[actor.fake]')

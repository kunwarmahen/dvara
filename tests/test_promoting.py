"""A person's learned skill made a tool, from the settings page (promoting.py).

The bias is A TOOL MADE THAT SHOULDN'T BE, OR IN THE WRONG PLACE. A skill
that isn't there, or a name that is a path, makes nothing; a test that
fails keeps nothing; one that passes keeps the tool in that person's own
folder, where only their agent finds it; and the page sees every
person's learned skills with how each has done.
"""

from __future__ import annotations

import json

import pytest

from dvara import promoting, settings
from tests.conftest import ScriptedProvider, says, write_package

SCRIPT = 'import sys\nprint("greeted", sys.argv[1])\n'
TOOL = {"name": "greet_person",
        "description": "Greet someone by name through the greeting script.",
        "parameters": {"type": "object",
                       "properties": {"who": {"type": "string", "description": "who"}},
                       "required": ["who"]},
        "argv": ["{who}"], "test": {"who": "world"}}


def kept(state, person="owner", agent="helper", script=SCRIPT,
         line="2026-09-28 · worked 5 · failed 0 · last ok 2026-09-29"):
    folder = state / "work" / person / agent / promoting.LEARNED / "greet-someone"
    (folder / "scripts").mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: greet-someone\ndescription: Greet someone by name through the "
        f"greeting script. Use when asked to greet.\norigin: learned\nlearned: {line}\n"
        '---\n\n1. Run python3 "$SKILL_DIR/scripts/greet.py" WHO.\n')
    (folder / "scripts" / "greet.py").write_text(script)
    return folder


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "agents"
    root.mkdir()
    write_package(root, "helper", body=(
        '[agent]\nname = "helper"\nprompt = "prompt.md"\n[skills]\nenabled = true\n'))
    return root


def make(root, state, replies, **kw):
    return promoting.make_tool(root=root, state=state, agent="helper",
                               person=kw.pop("person", "owner"),
                               skill=kw.pop("skill", "greet-someone"),
                               provider="anthropic", model="m",
                               client=ScriptedProvider(replies), **kw)


def proposal():
    return says(f"=== TOOL ===\n{json.dumps(TOOL)}\n=== END ===\n")


def test_the_page_sees_each_persons_learned_skills_and_how_they_did(tmp_path, root):
    state = tmp_path / "state"
    kept(state)
    kept(state, person="maya", line="2026-09-28 · worked 1 · failed 2")
    rows = {r["person"]: r for r in promoting.learned(state, "helper")}
    assert rows["owner"]["suggest"] and rows["owner"]["script"] and rows["owner"]["tool"] is None
    assert rows["maya"]["worked"] == 1 and not rows["maya"]["suggest"]
    shown = settings.show(root=root, actors=tmp_path / "a.toml", policy=tmp_path / "p.toml",
                          state=state)
    helper = next(a for a in shown["agents"] if a["name"] == "helper")
    assert {r["person"] for r in helper["learned"]} == {"owner", "maya"}


def test_a_passing_test_keeps_the_tool_in_that_persons_folder(tmp_path, root):
    state = tmp_path / "state"
    folder = kept(state)
    made = make(root, state, [proposal()])
    assert made["kept"] and made["tool"] == "greet_person" and made["test"]["passed"]
    assert "greeted world" in made["test"]["output"]
    assert (folder / "tool.json").is_file()
    assert promoting.learned(state, "helper")[0]["tool"] == "greet_person"


def test_a_failing_test_keeps_nothing(tmp_path, root):
    state = tmp_path / "state"
    folder = kept(state, script="import sys\nsys.exit('nope')\n")
    made = make(root, state, [proposal()])
    assert not made["kept"] and "nope" in made["test"]["output"]
    assert not (folder / "tool.json").exists()


@pytest.mark.parametrize("skill", ["no-such-skill", "../../etc", ".."])
def test_a_skill_that_is_not_theirs_or_is_a_path_makes_nothing(tmp_path, root, skill):
    state = tmp_path / "state"
    kept(state)
    with pytest.raises(ValueError, match="no learned skill"):
        make(root, state, [], skill=skill)
    with pytest.raises(ValueError, match="no learned skill"):
        make(root, state, [], person="maya")

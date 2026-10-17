"""The boxes on the settings page (toolbox.py, settings.show).

The bias is A SAVE FROM THE BOXES THAT CHANGES WHAT THE AGENT GETS
WITHOUT ANYBODY TICKING ANYTHING. A box starts ticked exactly when the
allow list already lets that tool in (a pattern included); a name no box
stands for is handed back to be kept as written; a family's members come
from what a turn really met, given or turned away; and no box ticked is
refused, never read as "every tool".
"""

from __future__ import annotations

import json

from dvara import settings, toolbox

from test_settings import agent


def write_seen(state, person, name, given, could=()):
    folder = state / "tools" / person
    folder.mkdir(parents=True, exist_ok=True)
    row = lambda n: {"name": n, "said": n, "asks": n.endswith("create_schedule")}  # noqa: E731
    (folder / f"{name}.json").write_text(json.dumps(
        {"tools": [row(n) for n in given], "could": [row(n) for n in could]}))


def test_every_builtin_dvaras_own_and_both_families_are_offered():
    names = {r["name"] for r in toolbox.toolbox()["tools"]}
    assert {"read_file", "web_fetch", "load_skill", "send_file",
            "mcp__samay__*", "mcp__sparsh__*"} <= names


def test_a_box_is_ticked_by_its_name_or_a_pattern_the_owner_wrote():
    assert toolbox.ticked(["web_fetch"], "web_fetch")
    assert toolbox.ticked(["browser_*"], "browser_open")
    assert not toolbox.ticked(["browser_*"], "bash")
    assert toolbox.ticked(None, "bash")          # no list: everything


def test_a_name_no_box_stands_for_is_kept_for_advanced():
    rows = toolbox.toolbox()["tools"]
    assert toolbox.covered(["web_fetch", "amazon_*", "mcp__samay__*"], rows) == ["amazon_*"]


def test_a_familys_members_are_what_some_turn_met_given_or_turned_away(tmp_path):
    write_seen(tmp_path, "mahen", "minder", ["mcp__samay__list_schedules"],
               could=["mcp__sparsh__look"])
    write_seen(tmp_path, "priya", "minder", ["mcp__samay__create_schedule"])
    rows = {r["name"]: r for r in toolbox.toolbox(tmp_path)["tools"]}
    assert [m["name"] for m in rows["mcp__samay__*"]["members"]] == [
        "mcp__samay__create_schedule", "mcp__samay__list_schedules"]
    assert [m["name"] for m in rows["mcp__sparsh__*"]["members"]] == ["mcp__sparsh__look"]


def test_before_any_turn_a_family_is_its_sentence_alone(tmp_path):
    rows = {r["name"]: r for r in toolbox.toolbox(tmp_path)["tools"]}
    assert rows["mcp__samay__*"]["members"] == [] and rows["mcp__samay__*"]["said"]


def test_show_ticks_each_agents_boxes_from_its_own_allow_list(tmp_path):
    root = tmp_path / "agents"
    agent(root)
    (root / "minder").mkdir()
    (root / "minder" / "agent.toml").write_text(
        '[agent]\nname = "minder"\n\n[tools]\nallow = ["web_fetch", "amazon_*", "mcp__samay__*"]\n')
    (root / "minder" / "prompt.md").write_text("Be brief.\n")
    (root / "open").mkdir()
    (root / "open" / "agent.toml").write_text('[agent]\nname = "open"\n')
    (root / "open" / "prompt.md").write_text("Hi.\n")
    out = settings.show(root=root, actors=tmp_path / "actors.toml",
                        policy=tmp_path / "policy.toml", state=tmp_path / "state")
    tools = {a["name"]: a["tools"] for a in out["agents"]}
    assert tools["greeter"]["ticked"] == ["ask_user"] and not tools["greeter"]["every"]
    assert set(tools["minder"]["ticked"]) == {"web_fetch", "mcp__samay__*"}
    assert tools["minder"]["advanced"] == ["amazon_*"]
    assert tools["open"]["every"] and tools["open"]["ticked"] == []


def test_no_box_ticked_is_refused_not_taken_as_every_tool(tmp_path):
    import pytest

    from dvara.errors import ConfigProblem

    folder = agent(tmp_path)
    before = (folder / "agent.toml").read_text()
    with pytest.raises(ConfigProblem, match="no tools at all"):
        settings.set_agent(tmp_path, "greeter", {"tools": {"allow": []}})
    assert (folder / "agent.toml").read_text() == before

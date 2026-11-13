"""Every standing yes in one list, and grants that run out.

The bias: a grant is given once and then forgotten, so the failures here
are all SILENT ones. A rule whose last day passed but still answers. An
ended rule that turns a question into a refusal (or worse, a yes). A
person listed as asking first when the agent they talk to never asks. A
schedule granted a whole server by pattern that nobody can see. Each test
pins one of those to the place an owner would look.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from dvara import grants
from dvara.actors import ActorBook
from dvara.claim import Claim, holder
from dvara.errors import ConfigProblem
from dvara.roster import Roster
from dvara.rules import RuleBook
from dvara.runs import Run, RunStore, ToolStep

from tests.conftest import write_package


def book(text: str) -> ActorBook:
    import tomllib
    return ActorBook.from_dict(tomllib.loads(text))


def agent(root, name, mode):
    write_package(root, name, body=(
        f'[agent]\nname = "{name}"\nversion = "0.1.0"\nprompt = "prompt.md"\n'
        f'[tools]\nallow = ["write_file"]\n[permissions]\nmode = "{mode}"\n'))


# ---- a rule that runs out --------------------------------------------------


def test_a_rule_past_its_last_day_answers_nothing():
    rules = RuleBook.from_dict({"rule": [
        {"tool": "write_file", "verdict": "allow", "until": date(2020, 1, 1)}]})
    assert rules.decide("write_file", {}) is None


def test_a_rule_answers_on_its_last_day():
    today = date.today()
    rules = RuleBook.from_dict({"rule": [
        {"tool": "write_file", "verdict": "allow", "until": today.isoformat()}]})
    assert rules.decide("write_file", {}).verdict == "allow"


def test_an_ended_deny_does_not_hide_a_live_allow_and_vice_versa():
    rules = RuleBook.from_dict({"rule": [
        {"tool": "bash", "verdict": "deny", "until": "2020-01-01"},
        {"tool": "bash", "verdict": "allow", "args": {"command": "ls"}}]})
    assert rules.decide("bash", {"command": "ls"}).verdict == "allow"


def test_moving_the_date_keeps_the_rules_count():
    one = RuleBook.from_dict({"rule": [{"tool": "x", "verdict": "allow",
                                        "until": "2030-01-01"}]})
    two = RuleBook.from_dict({"rule": [{"tool": "x", "verdict": "allow",
                                        "until": "2031-06-01"}]})
    assert next(iter(one)).id == next(iter(two)).id


@pytest.mark.parametrize("bad", ["next week", "2026-13-01", 5,
                                 datetime(2030, 1, 1, 17, 0)])
def test_until_that_is_not_a_day_is_refused_with_the_fix(bad):
    with pytest.raises(ConfigProblem, match="until = 2026-12-31"):
        RuleBook.from_dict({"rule": [{"tool": "x", "verdict": "allow", "until": bad}]})


# ---- the house's rung is written where a reader can find it -----------------


def test_serve_writes_the_houses_rung_into_its_claim(tmp_path):
    claim = Claim(tmp_path)
    claim.take("dvara serve", at="http://x", rung="yolo")
    try:
        assert holder(tmp_path)["rung"] == "yolo"
    finally:
        claim.release()


# ---- what each grant was used for -------------------------------------------


def test_grant_use_counts_what_settled_each_call(tmp_path):
    runs = RunStore(tmp_path / "runs.sqlite3")
    now = datetime.now(UTC)
    runs.record(Run(actor="asha", agent="a", thread="t", message="m", started_at=now,
                    tools=[ToolStep("write_file", decided_by="rule:abcd1234"),
                           ToolStep("write_file", decided_by="asked:telegram"),
                           ToolStep("read_file"),
                           ToolStep("bash", refusal="user", decided_by="asked:web")]))
    runs.record(Run(actor="asha", agent="a", thread="u", message="m", started_at=now,
                    unattended=True,
                    tools=[ToolStep("write_file", decided_by="ahead")]))
    used = runs.grant_use(now - timedelta(days=1))
    assert used["people"]["asha"] == {"ran": 4, "asked": 1, "rule": 1, "ahead": 1,
                                      "for_turn": 0, "refused": 1, "by_program": 1}
    assert "abcd1234" in used["rules_last"]


# ---- the report ---------------------------------------------------------------


@pytest.fixture
def house(tmp_path):
    root = tmp_path / "agents"
    agent(root, "careful", "ask")
    agent(root, "free", "yolo")
    people = book('[actor.mahen]\npermissions = "yolo"\n'
                  '[actor.kid]\npermissions = "ask"\nagents = ["free"]\n'
                  'trusted = ["samay"]\napprover = "mahen"\n')
    return root, people, RunStore(tmp_path / "runs.sqlite3")


def test_a_persons_rung_is_the_strictest_of_house_person_and_agent(house):
    root, people, runs = house
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung="yolo", owner="mahen")
    by = {p["id"]: {a["agent"]: a["rung"] for a in p["agents"]} for p in data["people"]}
    assert by["mahen"] == {"careful": "ask", "free": "yolo"}
    assert by["kid"] == {"free": "ask"}           # their own ask wins over yolo
    looks = " ".join(item["said"] for item in data["look"])
    assert "mahen's free changes things without asking" in looks
    assert "kid's" not in looks


def test_a_house_on_ask_lets_nobody_change_things_unasked(house):
    root, people, runs = house
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung="ask", owner="mahen")
    assert all(a["rung"] != "yolo" for p in data["people"] for a in p["agents"])


def test_dvara_not_running_says_the_rung_was_assumed(house):
    root, people, runs = house
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung=None, owner="mahen")
    assert data["house"] == {"rung": None, "assumed": True, "serving": False}
    assert "isn't running" in grants.lines(data)[0]
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung=None, owner="mahen", serving=True)
    assert "started before it wrote its rung down" in grants.lines(data)[0]


def test_ended_ending_and_unused_rules_are_worth_a_look(house):
    root, people, runs = house
    soon = (date.today() + timedelta(days=3)).isoformat()
    rules = RuleBook.from_dict({"rule": [
        {"tool": "a_tool", "verdict": "allow", "until": "2020-01-01"},
        {"tool": "b_tool", "verdict": "deny", "until": soon},
        {"tool": "c_tool", "verdict": "allow"}]})
    data = grants.report(book=people, rules=rules, roster=Roster(root), runs=runs,
                         house_rung="ask", owner="mahen")
    states = {r["tool"]: r["state"] for r in data["rules"]}
    assert states == {"a_tool": "ended", "b_tool": "ending", "c_tool": "on"}
    said = [item["said"] for item in data["look"]]
    assert any("a_tool ended on 2020-01-01" in s for s in said)
    assert any(f"b_tool ends on {soon}" in s for s in said)
    assert any("allow c_tool settled nothing in 30 days" in s for s in said)


def test_samay_and_prahari_grants_are_listed_and_patterns_flagged(house, monkeypatch):
    root, people, runs = house
    answers = {
        ("samay", "list"): [
            {"id": "s1", "owner": "local", "sentence": "every morning", "state": "active",
             "allow_tools": ["mcp__setu__*"]},
            {"id": "s2", "owner": "kid", "sentence": "no grants", "state": "active",
             "allow_tools": []},
            {"id": "s3", "owner": "stranger", "sentence": "x", "allow_tools": ["y"]},
            {"id": "s4", "owner": "kid", "sentence": "once, done", "state": "done",
             "allow_tools": ["web_fetch"]}],
        ("prahari", "list"): [
            {"id": "w1", "owner": "kid", "name": "ice cream", "state": "active",
             "check": {"tool": "web_fetch"}, "allow_tools": ["write_file"]}],
        ("prahari", "indriya", "list", "--all"): [
            {"id": "i1", "owner": "local", "name": "outside-temp", "state": "active",
             "check": {"tool": "mcp__ha__get_state"}, "share": "house"}],
    }
    monkeypatch.setattr(grants, "_ask", lambda program, *argv: (answers[(program, *argv)],
                                                                  None))
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung="ask", owner="mahen", samay="samay", prahari="prahari")
    assert [(s["id"], s["person"]) for s in data["schedules"]] == [("s1", "mahen")]
    assert data["watches"][0]["looks_with"] == "web_fetch"
    assert data["watches"][0]["then_tools"] == ["write_file"]
    assert data["indriyas"][0]["person"] == "mahen"
    assert any("mcp__setu__*" in item["said"] for item in data["look"])
    text = "\n".join(grants.lines(data))
    assert "may use mcp__setu__*" in text and "looks with web_fetch" in text


def test_a_sibling_that_does_not_answer_is_named_not_guessed(house, monkeypatch):
    root, people, runs = house
    monkeypatch.setattr(grants, "_ask", lambda program, *argv: (None, "didn't answer"))
    data = grants.report(book=people, rules=RuleBook(), roster=Roster(root), runs=runs,
                         house_rung="ask", owner="mahen", samay="samay", prahari=None)
    assert data["asked"] == {"samay": "didn't answer", "prahari": "not switched on"}
    assert data["schedules"] == []

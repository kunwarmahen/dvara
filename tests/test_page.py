"""`dvara page`: the owner's view of the door -- and what it keeps off it.

The bias is A PAGE THAT SHOWS ONE PERSON WHAT ANOTHER SAID. The owner may
see that Priya's agent ran, what it cost and which tools it called; what
Priya typed and what the agent told her are hers. So the tests put words
in somebody else's runs and look for them in every answer, and a Telegram
id in the actors file and look for that too.

The other bias is A PAGE ANYONE ON THE MACHINE CAN READ: no token, the
wrong one, and the door's own token offered instead of the page's.

And the money rule from money.py: a turn with no price is counted, never
added as $0.00.
"""

from __future__ import annotations

import json
import stat
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from yantra import Usage

from dvara.cli import main
from dvara.errors import ConfigProblem
from dvara.page import ENV_TOKEN, TOKEN_FILE, Api, PageServer, page_token
from dvara.runs import Run, RunStore, ToolStep

GOOD = "the-page-token-long-enough"
NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)

ACTORS = """\
[actor.owner]
permissions = "ask"

[actor.priya]
agents = ["greeter"]
max_usd_per_day = 0.50
setu = "own"
[[actor.priya.channel]]
kind = "telegram"
id   = 8675309
"""


def _run(actor, message, reply, *, cost=0.10, when=NOW, tools=()):
    return Run(actor=actor, agent="greeter", thread="t", message=message, reply=reply,
               started_at=when, ended_at=when, model="m", usage=Usage(10, 5, 0, 0),
               cost_usd=cost, stop_reason="end_turn", tools=list(tools))


@pytest.fixture
def door(tmp_path, agents_root):
    actors = tmp_path / "actors.toml"
    actors.write_text(ACTORS)
    state = tmp_path / "state"
    state.mkdir()
    store = RunStore(state / "runs.sqlite3")
    store.record(_run("priya", "my bank pin is 4321", "noted, Priya",
                      tools=[ToolStep("send_message", "user")]))
    store.record(_run("priya", "unpriced turn", "ok", cost=None))
    store.record(_run("priya", "yesterday", "ok", when=NOW - timedelta(days=1)))
    store.record(_run("owner", "check the garden", "all watered"))
    store.close()
    return {"root": agents_root, "actors": actors, "state": state}


@pytest.fixture
def api(door):
    made = Api(**door, owner="owner", now=lambda: NOW)
    yield made
    made.close()


@pytest.fixture
def served(api):
    server = PageServer(api, GOOD, port=0)
    server.start()
    yield server
    server.stop()


def get(server, path, token=GOOD):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.get(server.url.rstrip("/") + path, headers=headers, timeout=5)


def test_somebody_elses_words_are_never_on_the_page(served):
    text = "".join(get(served, p).text for p in
                   ("/api/status", "/api/people", "/api/agents", "/api/runs",
                    "/api/runs?actor=priya"))
    assert "4321" not in text and "noted, Priya" not in text


def test_the_owners_own_words_are(api):
    mine = api.recent("owner", None, 10)[0]
    assert mine["message"] == "check the garden" and mine["reply"] == "all watered"


def test_somebody_elses_run_keeps_its_shape(api):
    theirs = api.recent("priya", None, 10)
    assert {r["message"] for r in theirs} == {None}
    first = next(r for r in theirs if r["tools"])
    assert first["tools"] == [{"name": "send_message", "refusal": "user"}]
    assert first["cost_usd"] == 0.10


def test_a_channel_is_shown_by_kind_never_by_its_id(served):
    text = get(served, "/api/people").text
    assert "8675309" not in text
    priya = next(p for p in json.loads(text)["people"] if p["id"] == "priya")
    assert priya["channels"] == ["telegram"] and priya["accounts"] == "own folder"


def test_todays_spend_counts_an_unpriced_turn_without_pricing_it(api):
    priya = next(p for p in api.people() if p["id"] == "priya")
    assert priya["today"]["spent"] == pytest.approx(0.10)
    assert priya["today"]["turns"] == 2 and priya["today"]["unpriced"] == 1
    assert priya["today"]["left"] == pytest.approx(0.40)
    assert priya["week"]["turns"] == 3 and priya["week"]["spent"] == pytest.approx(0.20)


def test_the_owner_is_marked_and_an_unknown_owner_is_refused(api, door):
    assert [p["id"] for p in api.people() if p["owner"]] == ["owner"]
    with pytest.raises(ConfigProblem):
        Api(**door, owner="nobody")


def test_an_agent_says_who_may_use_it(api):
    assert api.agents() == [{"name": "greeter", "people": ["owner", "priya"]}]


def test_every_api_call_without_the_pages_token_is_refused(served):
    for path in ("/api/status", "/api/people", "/api/agents", "/api/runs"):
        assert get(served, path, token=None).status_code == 401
        assert get(served, path, token="the-doors-token-not-this-one").status_code == 401


def test_the_page_itself_needs_no_token_and_holds_no_data(served):
    for path in ("/", "/page.js", "/page.css"):
        res = get(served, path, token=None)
        assert res.status_code == 200 and "garden" not in res.text


def test_no_other_site_may_frame_it_or_run_a_script_in_it(served):
    policy = get(served, "/", token=None).headers["content-security-policy"]
    assert "frame-ancestors 'self'" in policy and "unsafe-inline" not in policy
    assert "access-control-allow-origin" not in get(served, "/api/status").headers


def test_this_page_only_reads(served):
    res = httpx.post(served.url + "api/people",
                     headers={"Authorization": f"Bearer {GOOD}"}, timeout=5)
    assert res.status_code == 405


def test_the_status_says_the_door_is_not_running(served):
    data = get(served, "/api/status").json()
    assert data["serving"] is False and data["owner"] == "owner" and data["people"] == 2


def test_the_token_is_made_once_and_kept_for_you_alone(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_TOKEN, raising=False)
    first = page_token(tmp_path)
    assert page_token(tmp_path) == first and len(first) >= 16
    assert stat.S_IMODE((tmp_path / TOKEN_FILE).stat().st_mode) == 0o600


def test_a_short_token_from_the_environment_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_TOKEN, "short")
    with pytest.raises(ConfigProblem):
        page_token(tmp_path)


def test_the_command_refuses_an_owner_not_in_the_file(door, capsys):
    code = main(["--root", str(door["root"]), "--actors", str(door["actors"]),
                 "--state", str(door["state"]), "page", "--as", "nobody", "--port", "0"])
    assert code == 2 and "nobody" in capsys.readouterr().err

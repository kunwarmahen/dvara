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

ANSWERING is the page's one write, and its bias is AN ANSWER IN SOMEBODY
ELSE'S NAME. The page answers through the running door as the owner; the
tests have the door hold a question for somebody else, send a body that
names somebody else, and send "yes" where only true approves -- and run
one answer through dvara's real HTTP app, with a real turn waiting on it.
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
from dvara.page import ENV_TOKEN, TOKEN_FILE, Api, Door, PageServer, page_token
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
    state = tmp_path / "page-state"
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


# ---- answering, through the door -------------------------------------------


class FakeDoor:
    """The door's /asks and /holds, recording what the page sent it."""

    def __init__(self):
        self.sent = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer door-token":
            return httpx.Response(401, json={"detail": "unauthorized"})
        path = request.url.path
        if request.method == "GET" and path == "/asks":
            return httpx.Response(200, json={"asks": [
                {"id": "a1", "actor": "owner", "agent": "scribe", "tool": "write_file",
                 "summary": "write notes.txt", "asked_at": "2026-10-07T09:00:00+00:00"},
                {"id": "a2", "actor": "priya", "agent": "greeter", "tool": "send",
                 "summary": "send priya's secret", "asked_at": "2026-10-07T09:00:00+00:00"},
            ]})
        if request.method == "GET" and path == "/holds":
            return httpx.Response(200, json={"holds": []})
        self.sent.append((path, json.loads(request.content)))
        if path == "/holds/h1":
            return httpx.Response(200, json={"text": "done, as you said", "ok": True})
        return httpx.Response(200, json={"answered": True, "approved": True})


@pytest.fixture
def fake(door):
    seen = FakeDoor()
    made = Api(**door, owner="owner", now=lambda: NOW,
               door=Door("owner", "http://door", "door-token",
                         transport=httpx.MockTransport(seen)))
    made.seen = seen
    yield made
    made.close()


def test_only_the_owners_questions_reach_the_page(fake):
    waiting = fake.handle("GET", "/api/waiting", {})[1]
    assert [a["id"] for a in waiting["asks"]] == ["a1"]
    assert "priya" not in json.dumps(waiting)


def test_an_answer_is_sent_as_the_owner_whatever_the_browser_says(fake):
    fake.handle("POST", "/api/asks/a1", {}, {"approve": True, "actor": "priya"})
    assert fake.seen.sent == [("/asks/a1", {"actor": "owner", "approve": True})]


def test_only_a_json_boolean_approves(fake):
    from dvara.page import ApiError
    for said in ("yes", 1, None):
        with pytest.raises(ApiError) as caught:
            fake.handle("POST", "/api/asks/a1", {}, {"approve": said})
        assert caught.value.code == 400
    assert fake.seen.sent == []


def test_a_held_turn_carries_on_and_its_reply_comes_back(fake):
    code, reply = fake.handle("POST", "/api/holds/h1", {},
                              {"answers": {"c1": True, "c2": "not that file"}})
    assert code == 200 and reply["text"] == "done, as you said"
    assert fake.seen.sent == [("/holds/h1", {"actor": "owner",
                                             "answers": {"c1": True, "c2": "not that file"}})]


def test_with_no_door_running_there_is_nothing_to_answer(door, monkeypatch):
    from dvara.page import ApiError
    monkeypatch.delenv("DVARA_URL", raising=False)
    api = Api(**door, owner="owner", now=lambda: NOW)
    try:
        waiting = api.handle("GET", "/api/waiting", {})[1]
        assert waiting["door"]["reachable"] is False and "isn't running" in waiting["door"]["why"]
        with pytest.raises(ApiError) as caught:
            api.handle("POST", "/api/asks/a1", {}, {"approve": True})
        assert caught.value.code == 409
    finally:
        api.close()


def test_without_the_doors_token_the_page_says_what_to_set(door):
    api = Api(**door, owner="owner", door=Door("owner", "http://door", None))
    try:
        assert "DVARA_TOKEN" in api.handle("GET", "/api/waiting", {})[1]["door"]["why"]
    finally:
        api.close()


def test_a_wrong_door_token_is_said_not_shown_as_nothing_waiting(door):
    seen = FakeDoor()
    api = Api(**door, owner="owner", door=Door("owner", "http://door", "not-the-token",
                                                 transport=httpx.MockTransport(seen)))
    try:
        why = api.handle("GET", "/api/waiting", {})[1]["door"]["why"]
        assert "refused" in why
    finally:
        api.close()


def test_an_answer_from_another_site_is_refused(served):
    res = httpx.post(served.url + "api/asks/a1", json={"approve": True},
                     headers={"Authorization": f"Bearer {GOOD}",
                              "Origin": "https://evil.example"}, timeout=5)
    assert res.status_code == 403


def test_the_doors_refusal_reaches_the_page_as_its_own_status(door):
    from dvara.page import ApiError

    def refuses(request):
        return httpx.Response(403, json={"detail": "that question was put to somebody else"})
    api = Api(**door, owner="owner", door=Door("owner", "http://door", "t",
                                                 transport=httpx.MockTransport(refuses)))
    try:
        with pytest.raises(ApiError) as caught:
            api.handle("POST", "/api/asks/a1", {}, {"approve": True})
        assert caught.value.code == 403 and "somebody else" in caught.value.detail
    finally:
        api.close()


fastapi = pytest.importorskip("fastapi")
from tests.test_http import TOKEN as DOOR_TOKEN  # noqa: E402
from tests.test_http import asking  # noqa: E402,F401,F811  (the fixture)


def test_an_answer_from_the_page_releases_a_real_waiting_turn(asking, door):  # noqa: F811
    """Through dvara's own HTTP app, with a turn parked on a real question."""
    api = Api(**door, owner="owner",
              door=Door("owner", "http://testserver", DOOR_TOKEN,
                        transport=asking._transport))
    try:
        waiting = api.handle("GET", "/api/waiting", {})[1]
        assert [a["tool"] for a in waiting["asks"]] == ["write_file"]
        ask = waiting["asks"][0]
        assert api.handle("POST", f"/api/asks/{ask['id']}", {},
                          {"approve": True})[1]["answered"] is True
        asking.turn.join(timeout=5)
        assert asking.done and asking.done[0].ok
    finally:
        api.close()


def test_the_pages_script_parses():
    # The Python tests never run page.js; a redeclared name in it broke the
    # whole page while every test here passed.
    import shutil
    import subprocess
    from importlib.resources import files
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = files("dvara").joinpath("static", "page.js")
    done = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# ---- files and schedules ----------------------------------------------------------------
#
# The same bias, for files: the owner may see that Priya has a 4 KB
# "diary.txt" with her agent -- whose disk it fills -- but not what it says.

SAMAY = """\
#!{python}
import json, sys
if sys.argv[1] == "status":
    print(json.dumps({{"serving": True, "url": "http://127.0.0.1:8780/"}}))
elif sys.argv[1] == "list":
    print(json.dumps([
        {{"id": "s1", "owner": "priya", "agent": "greeter", "prompt": "read my diary aloud",
         "sentence": "every day at 7:00", "state": "active", "paused_because": "",
         "next_at": "2026-10-07T11:00:00+00:00",
         "last_run": {{"outcome": "ok", "ended_at": "2026-10-06T11:00:05+00:00"}}}},
        {{"id": "s2", "owner": "owner", "agent": "greeter", "prompt": "water the garden",
         "sentence": "every 3 hours", "state": "active", "paused_because": "",
         "next_at": "2026-10-06T18:00:00+00:00", "last_run": None}},
        {{"id": "s3", "owner": "stranger", "agent": "x", "prompt": "not served here",
         "sentence": "hourly", "state": "active", "next_at": None, "last_run": None}}]))
"""


@pytest.fixture
def folders(door):
    work = door["state"] / "work"
    (work / "priya" / "greeter").mkdir(parents=True)
    (work / "priya" / "greeter" / "diary.txt").write_text("dear diary, my secret")
    (work / "owner" / "greeter" / "notes").mkdir(parents=True)
    (work / "owner" / "greeter" / "notes" / "garden.md").write_text("tomatoes: watered")
    (work / "owner" / "greeter" / "picture.bin").write_bytes(b"\xff\xd8\xff\x00")
    (work / "owner" / "greeter" / ".yantra").mkdir()
    (work / "owner" / "greeter" / ".yantra" / "mcp.json").write_text("{}")
    (door["state"] / "outside.txt").write_text("not in any folder")
    return work


@pytest.fixture
def samay(tmp_path):
    import sys
    program = tmp_path / "samay"
    program.write_text(SAMAY.format(python=sys.executable))
    program.chmod(0o755)
    return str(program)


def test_every_folder_is_listed_by_name_size_and_date(api, folders):
    found = {(f["person"], f["agent"]): f for f in api.folders()}
    priya = found[("priya", "greeter")]
    assert [r["path"] for r in priya["files"]] == ["diary.txt"]
    assert priya["files"][0]["size"] == len("dear diary, my secret")
    assert priya["owner"] is False
    assert "dear diary" not in json.dumps(api.folders())


def test_the_agents_own_bookkeeping_is_not_listed(api, folders):
    mine = next(f for f in api.folders() if f["person"] == "owner")
    assert ".yantra/mcp.json" not in [r["path"] for r in mine["files"]]
    assert mine["count"] == 2


def test_the_owner_opens_their_own_file(api, folders):
    f = api.handle("GET", "/api/file", {"agent": ["greeter"], "path": ["notes/garden.md"]})[1]
    assert f["text"] == "tomatoes: watered" and f["binary"] is False


def test_a_file_that_is_not_text_is_said_not_shown(api, folders):
    f = api.open_file("greeter", "picture.bin")
    assert f["binary"] is True and f["text"] is None


@pytest.mark.parametrize("agent, path", [
    ("greeter", "../../priya/greeter/diary.txt"),       # somebody else's, by walking
    ("../priya/greeter", "diary.txt"),                  # by naming their folder
    ("greeter", "../../../outside.txt"),
    ("greeter", ".yantra/mcp.json"),
    ("greeter", "nothing.txt"),
    ("", "diary.txt"),
])
def test_nobody_elses_file_opens_and_every_refusal_reads_the_same(api, folders,
                                                                   agent, path):
    with pytest.raises(Exception) as caught:
        api.open_file(agent, path)
    assert caught.value.code == 404 and caught.value.detail == "no such file"


def test_schedules_are_samays_sentence_with_words_only_for_the_owner(door, folders,
                                                                     samay):
    made = Api(**door, owner="owner", now=lambda: NOW, samay=samay)
    data = made.schedules()
    made.close()
    assert data["samay"] == {"found": True, "why": None, "page": "http://127.0.0.1:8780/"}
    by = {s["id"]: s for s in data["schedules"]}
    assert set(by) == {"s1", "s2"}                    # nobody this door does not serve
    assert by["s1"]["sentence"] == "every day at 7:00"
    assert by["s1"]["prompt"] is None and "diary" not in json.dumps(data)
    assert by["s2"]["prompt"] == "water the garden"
    assert by["s1"]["last"] == {"outcome": "ok", "at": "2026-10-06T11:00:05+00:00"}
    assert data["schedules"][0]["person"] == "owner"   # yours first


def test_no_samay_is_said_on_the_page_not_an_error(api, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("DVARA_SAMAY", raising=False)
    data = api.schedules()
    assert data["samay"]["found"] is False and "--samay" in data["samay"]["why"]
    assert data["schedules"] == []

"""Bias: a page that cannot say which way a turn came in.

Telegram, the web page, Samay and the terminal all end in the same
``deliver``, so a run looked the same whichever door it used. Each now
says, the page can be filtered by it, and an old store fills in what its
threads already recorded -- and nothing it would have to guess.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import UTC, datetime

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.actors import Channel  # noqa: E402
from dvara.http import create_app  # noqa: E402
from dvara.page import Api  # noqa: E402
from dvara.runs import Run, RunStore  # noqa: E402
from tests.conftest import says  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def last(service) -> Run:
    return service.runs.recent(limit=1)[0]


def test_a_channel_turn_is_marked_with_the_channels_kind(make_service):
    from dvara.actors import ActorBook
    book = ActorBook.from_dict({"actor": {"owner": {
        "channel": [{"kind": "telegram", "id": "8675309"}]}}})
    service = make_service([says("hi")], actors=book)
    asyncio.run(service.deliver(via=Channel("telegram", "8675309"), agent="greeter",
                                thread="chat7", text="hello"))
    assert last(service).came_by == "telegram"


def test_a_caller_naming_nobody_leaves_it_empty(make_service):
    service = make_service([says("hi")])
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="hello"))
    assert last(service).came_by is None


@pytest.mark.parametrize(("extra", "want"), [
    ({}, "http"),
    ({"came_by": "samay", "unattended": True}, "samay"),
])
def test_http_says_http_unless_the_caller_names_itself(make_service, extra, want):
    service = make_service([says("Hello.")])
    with TestClient(create_app(service, token=TOKEN)) as client:
        reply = client.post("/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "thread": "t", "text": "hi",
            **extra})
        assert reply.status_code == 200
        assert last(service).came_by == want


def test_http_refuses_a_came_by_that_is_not_a_word(make_service):
    service = make_service([says("Hello.")])
    with TestClient(create_app(service, token=TOKEN)) as client:
        reply = client.post("/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "thread": "t", "text": "hi",
            "came_by": "<b>Samay</b>"})
    assert reply.status_code == 400


def test_a_turn_from_the_web_page_says_web(make_service):
    service = make_service([says("Hello from the page.")], web=True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "text": "hi"})
        for _ in range(200):
            if service.runs.recent(limit=1):
                break
            time.sleep(0.02)
        assert last(service).came_by == "web"


def test_the_terminal_says_cli(tmp_path, agents_root, monkeypatch):
    from dvara.cli import main
    from dvara.service import Reply, Service

    seen = {}

    async def deliver(self, **kwargs):
        seen.update(kwargs)
        return Reply(text="ok", run_id="abc", agent="greeter", stop_reason="end_turn")

    monkeypatch.setattr(Service, "deliver", deliver)
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n")
    main(["--root", str(agents_root), "--actors", str(actors),
          "--state", str(tmp_path / "state"),
          "say", "--actor", "owner", "--agent", "greeter", "hi"])
    assert seen["came_by"] == "cli"


def _run(came_by, thread="t", unattended=False):
    when = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    return Run(actor="owner", agent="greeter", thread=thread, message="m",
               started_at=when, ended_at=when, stop_reason="end_turn",
               came_by=came_by, unattended=unattended)


def test_runs_filter_by_the_way_they_came(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    for way in ("telegram", "web", "samay", "cli"):
        store.record(_run(way))
    assert [r.came_by for r in store.recent(came_by="samay")] == ["samay"]
    assert len(store.recent()) == 4
    store.close()


def test_an_old_store_fills_in_only_what_its_threads_recorded(tmp_path):
    path = tmp_path / "runs.sqlite3"
    # the shape on somebody's disk the day before the column came
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE runs (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
        "agent TEXT NOT NULL, thread TEXT NOT NULL, started_at TEXT NOT NULL, "
        "ended_at TEXT NOT NULL, message TEXT NOT NULL, reply TEXT NOT NULL, "
        "model TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0, "
        "output_tokens INTEGER NOT NULL DEFAULT 0, "
        "cache_read_tokens INTEGER NOT NULL DEFAULT 0, "
        "cache_write_tokens INTEGER NOT NULL DEFAULT 0, cost_usd REAL, "
        "stop_reason TEXT NOT NULL, detail TEXT, tools TEXT, answered_from TEXT, "
        "agent_version TEXT, waited_seconds REAL, resumes TEXT, unattended INTEGER)")
    for i, (thread, unattended) in enumerate([
            ("telegram:42", 0), ("web:chat", 0), ("samay-ab12-1760000000", 1),
            ("samay-by-hand", 0), ("t", 0)]):
        db.execute(
            "INSERT INTO runs (id, actor, agent, thread, started_at, ended_at, "
            "message, reply, model, stop_reason, unattended) "
            "VALUES (?, 'owner', 'greeter', ?, '2026-01-01T00:00:00+00:00', "
            "'2026-01-01T00:00:01+00:00', 'm', 'r', 'x', 'end_turn', ?)",
            (f"old{i}", thread, unattended))
    db.commit()
    db.close()

    store = RunStore(path)
    got = {r.thread: r.came_by for r in store.recent(limit=10)}
    assert got == {"telegram:42": "telegram", "web:chat": "web",
                   "samay-ab12-1760000000": "samay",
                   # typed by a person, or nobody knows: left empty
                   "samay-by-hand": None, "t": None}
    store.close()


def test_the_page_shows_and_filters_by_it(tmp_path, agents_root):
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n")
    state = tmp_path / "state"
    state.mkdir()
    store = RunStore(state / "runs.sqlite3")
    store.record(_run("telegram"))
    store.record(_run("samay", thread="samay-x-1", unattended=True))
    store.close()
    api = Api(root=agents_root, actors=actors, state=state, owner="owner")
    try:
        assert {r["came_by"] for r in api.recent(None, None, 10)} == {"telegram", "samay"}
        status, body = api.handle("GET", "/api/runs", {"came_by": ["samay"]})
        assert status == 200 and [r["came_by"] for r in body["runs"]] == ["samay"]
    finally:
        api.close()

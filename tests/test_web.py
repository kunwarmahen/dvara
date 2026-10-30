"""Bias: a page's chat that loses what it was told, or tells the wrong person.

The web channel keeps lines, so the failures worth a test are the ones
where a line goes missing or goes astray: an answer that never comes
back because the page asked too early, a schedule's notice that reaches
nobody because they have no Telegram, one person's lines shown to
another, a page's conversation that quietly continues Telegram's, and a
held turn answered from the page that runs and leaves no line.
"""

from __future__ import annotations

import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dvara.http import create_app  # noqa: E402
from dvara.web import THREAD  # noqa: E402

from tests.conftest import says  # noqa: E402

TOKEN = "a-token-long-enough-to-be-real"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def settled(client, actor: str = "owner", after: int = 0) -> dict:
    """The page's look once nothing is running any more."""
    for _ in range(200):
        seen = client.get(f"/web?actor={actor}&after={after}", headers=AUTH).json()
        if not seen["busy"]:
            return seen
        time.sleep(0.02)
    raise AssertionError("the turn never finished")


@pytest.fixture
def page(make_service):
    service = make_service([says("Hello from the page."), says("Again.")], web=True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.service = service
        yield client


def test_a_message_is_answered_as_a_later_line(page):
    said = page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "hi"}).json()
    assert said["line"]["who"] == "you" and said["line"]["text"] == "hi"
    seen = settled(page)
    assert [(ln["who"], ln["text"]) for ln in seen["lines"]] == [
        ("you", "hi"), ("agent", "Hello from the page.")]
    assert seen["agents"] == ["greeter"]


def test_a_look_after_a_line_shows_only_what_came_since(page):
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "hi"})
    first = settled(page)["lines"][0]["id"]
    later = settled(page, after=first)["lines"]
    assert [ln["who"] for ln in later] == ["agent"]


def test_the_page_runs_its_own_conversation_not_telegrams(page):
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "hi"})
    settled(page)
    assert {r.thread for r in page.service.runs.recent(limit=5)} == {THREAD}


def test_a_notice_waits_on_the_page_for_a_person_with_no_telegram(page):
    sent = page.post("/notify", headers=AUTH,
                     json={"actor": "guest", "text": "2 new mails"}).json()
    assert sent["sent"] == ["web"] and not sent["nowhere"]
    lines = page.get("/web?actor=guest", headers=AUTH).json()["lines"]
    assert [(ln["who"], ln["text"]) for ln in lines] == [("notice", "2 new mails")]


def test_notices_are_listed_by_themselves_newest_first_even_after_new(page):
    for text in ("2 new mails", "the parcel is out for delivery"):
        page.post("/notify", headers=AUTH, json={"actor": "owner", "text": text})
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "/new"})
    settled(page)
    got = page.get("/web/notices?actor=owner", headers=AUTH).json()["notices"]
    assert [n["text"] for n in got] == ["the parcel is out for delivery", "2 new mails"]
    assert all(n["who"] == "notice" for n in got)
    assert page.get("/web/notices?actor=guest", headers=AUTH).json()["notices"] == []
    assert page.get("/web/notices?actor=owner").status_code == 401


def test_one_persons_lines_are_never_anothers(page):
    page.post("/notify", headers=AUTH, json={"actor": "guest", "text": "yours"})
    assert page.get("/web?actor=owner", headers=AUTH).json()["lines"] == []


def test_an_agent_the_person_may_not_use_is_refused_before_any_line(page):
    response = page.post("/web/message", headers=AUTH, json={
        "actor": "guest", "agent": "nope", "text": "hi"})
    assert response.status_code == 400
    assert page.get("/web?actor=guest", headers=AUTH).json()["lines"] == []


def test_a_stranger_is_a_404_and_no_token_is_a_401(page):
    assert page.get("/web?actor=stranger", headers=AUTH).status_code == 404
    assert page.get("/web?actor=owner").status_code == 401


def test_without_web_there_is_no_web_and_nowhere_is_still_nowhere(make_service):
    service = make_service()
    with TestClient(create_app(service, token=TOKEN)) as client:
        assert client.get("/web?actor=owner", headers=AUTH).status_code == 404
        sent = client.post("/notify", headers=AUTH,
                           json={"actor": "owner", "text": "hi"}).json()
        assert sent["nowhere"]


def test_lines_survive_a_restart(make_service, tmp_path):
    first = make_service(web=True)
    with TestClient(create_app(first, token=TOKEN)) as client:
        client.post("/notify", headers=AUTH, json={"actor": "owner", "text": "kept"})
    again = make_service(web=True)
    with TestClient(create_app(again, token=TOKEN)) as client:
        lines = client.get("/web?actor=owner", headers=AUTH).json()["lines"]
    assert [ln["text"] for ln in lines] == ["kept"]


def test_a_person_keeps_only_their_newest_lines(tmp_path):
    from dvara.web import WebBook
    book = WebBook(tmp_path / "web.sqlite3", keep=3)
    for n in range(5):
        book.add("owner", "notice", f"n{n}")
    book.add("guest", "notice", "g")
    assert [ln.text for ln in book.after("owner")] == ["n2", "n3", "n4"]
    assert [ln.text for ln in book.after("guest")] == ["g"]


def test_an_answer_that_says_connect_carries_the_words_for_buttons(make_service):
    service = make_service([says("Send /connect gmail, then ask again.")], web=True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "text": "any mail?"})
        mine, answer = settled(client)["lines"]
    assert answer["taps"] == [{"word": "/connect gmail", "label": "Connect gmail"}]
    assert "taps" not in mine                              # your own line has none


def test_a_file_sent_from_the_page_is_kept_and_named(make_service):
    import base64

    service = make_service([says("A receipt for 12.50.")], web=True)
    png = base64.b64encode(b"\x89PNG not really").decode()
    with TestClient(create_app(service, token=TOKEN)) as client:
        said = client.post("/web/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "text": "",
            "files": [{"name": "../receipt.png", "data": png}]}).json()
        assert said["line"]["sent"] == ["receipt.png"]
        assert settled(client)["lines"][-1]["text"] == "A receipt for 12.50."
        run = service.runs.recent(limit=1)[0]
        assert "from-you/receipt.png (a picture)" in run.message
        assert [p.name for p in service.state.rglob("from-you/*")] == ["receipt.png"]


def test_a_file_that_is_not_base64_is_refused_before_any_line(page):
    said = page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "hi",
        "files": [{"name": "a.txt", "data": "not base64!"}]})
    assert said.status_code == 400 and "base64" in said.json()["detail"]
    assert settled(page)["lines"] == []


# ---- a held turn, answered from the page ----------------------------------

def test_a_held_turn_answered_on_the_page_leaves_its_answer_as_a_line(
        make_service, agents_root):
    from tests.test_holds_channels import holding
    from tests.test_what_decided_it import scribe, two_calls
    scribe(agents_root)
    service = make_service([two_calls(), says("wrote a.")], asks=holding(), web=True)
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH, json={
            "actor": "owner", "agent": "scribe", "text": "write both"})
        seen = settled(client)
        held = seen["holds"][0]
        assert seen["lines"][-1]["held"] == held["id"]
        assert client.post(f"/web/holds/{held['id']}", headers=AUTH, json={
            "actor": "guest", "answers": {"call-a": True}}).status_code == 403
        assert client.post(f"/web/holds/{held['id']}", headers=AUTH, json={
            "actor": "owner",
            "answers": {"call-a": True, "call-b": "not b"}}).json() == {"started": True}
        after = settled(client)
        assert after["lines"][-1]["text"] == "wrote a." and after["holds"] == []


def test_the_accounts_page_button_says_why_when_there_is_no_link(page):
    got = page.post("/web/accounts-page", json={"actor": "owner"}, headers=AUTH).json()
    assert got["url"] is None and "No accounts are set up for you" in got["said"]
    assert page.post("/web/accounts-page", json={"actor": "nobody"},
                     headers=AUTH).status_code == 404


def test_new_starts_the_page_over_and_keeps_the_lines_before(page):
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "List my profiles"})
    settled(page)
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "/new"})
    seen = settled(page)
    assert [ln["who"] for ln in seen["lines"]] == ["agent"]
    assert seen["lines"][0].get("fresh") and seen["lines"][0]["text"].startswith("Starting fresh")
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "hi"})
    seen = settled(page)
    assert [ln["text"] for ln in seen["lines"]][1:] == ["hi", "Again."]
    # the lines before /new are still kept, only not shown
    kept = page.service.web.book._db.execute(
        "SELECT COUNT(*) FROM lines WHERE actor = 'owner'").fetchone()[0]
    assert kept == 6


def test_a_new_word_that_isnt_new_marks_nothing(page):
    page.post("/web/message", headers=AUTH, json={
        "actor": "owner", "agent": "greeter", "text": "/newsletter please"})
    seen = settled(page)
    assert not any(ln.get("fresh") for ln in seen["lines"])


# ---- the bell's read mark, and a voice note's words on its own line --------

def test_notices_read_on_one_page_are_read_on_every_page(page):
    for text in ("2 new mails", "the parcel is out"):
        page.post("/notify", headers=AUTH, json={"actor": "owner", "text": text})
    got = page.get("/web/notices?actor=owner", headers=AUTH).json()
    assert got["read"] == 0
    newest = got["notices"][0]["id"]
    marked = page.post("/web/notices/read", headers=AUTH,
                       json={"actor": "owner", "upto": newest}).json()
    assert marked["read"] == newest
    # a page a step behind can't move it back
    page.post("/web/notices/read", headers=AUTH, json={"actor": "owner", "upto": 1})
    assert page.get("/web/notices?actor=owner", headers=AUTH).json()["read"] == newest
    assert page.get("/web/notices?actor=guest", headers=AUTH).json()["read"] == 0
    assert page.post("/web/notices/read", headers=AUTH,
                     json={"actor": "owner", "upto": "all"}).status_code == 400
    assert page.post("/web/notices/read", json={"actor": "owner", "upto": 1}).status_code == 401


def test_the_read_mark_survives_a_restart(make_service):
    first = make_service(web=True)
    with TestClient(create_app(first, token=TOKEN)) as client:
        client.post("/notify", headers=AUTH, json={"actor": "owner", "text": "kept"})
        n = client.get("/web/notices?actor=owner", headers=AUTH).json()["notices"][0]["id"]
        client.post("/web/notices/read", headers=AUTH, json={"actor": "owner", "upto": n})
    again = make_service(web=True)
    with TestClient(create_app(again, token=TOKEN)) as client:
        assert client.get("/web/notices?actor=owner", headers=AUTH).json()["read"] == n


def test_a_voice_note_from_the_page_shows_its_words_on_your_own_line(make_service,
                                                                      monkeypatch):
    import base64

    from dvara import heard

    monkeypatch.setattr(heard, "_hear", lambda path: "what's the weather outside")
    service = make_service([says("Clear and 68°F.")], web=True)
    note = base64.b64encode(b"not really webm").decode()
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH, json={
            "actor": "owner", "agent": "greeter", "text": "",
            "files": [{"name": "voice-note.webm", "data": note}]})
        lines = settled(client)["lines"]
        mine, answer = lines
        assert mine["who"] == "you" and mine["heard"] == "what's the weather outside"
        assert answer["text"] == "Clear and 68°F."

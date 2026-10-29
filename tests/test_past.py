"""Past conversations: every one kept as it goes, found, opened, deleted (past.py).

The bias is A CONVERSATION THAT COMES BACK WRONG, OR NOT AT ALL, OR TO
SOMEBODY ELSE, OR THAT WON'T GO. Every conversation is in the list
whether or not ``/new`` ended it; going back puts exactly it in front of
the model and grows its own row rather than a copy; one person never
sees another's; a delete needs the word ``sure`` and then leaves nothing;
a schedule's run is not a conversation; and nothing here is a turn.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time

from dvara import past
from dvara.keys import session_key
from tests.conftest import says


def say(service, text, *, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter",
                                       thread=thread, text=text))


def shown(service, n=-1):
    return [block.text for m in service.scripted.requests[n]["messages"]
            if m.role == "user" for block in m.content
            if getattr(block, "text", None)]


def test_a_conversation_is_kept_without_new(make_service):
    service = make_service([says("The trip is on Friday.")])
    say(service, "when is the school trip?")
    listed = say(service, "/chats")
    assert listed.run_id is None
    assert "1. when is the school trip? (this one) —" in listed.text
    assert "1 message" in listed.text


def test_new_starts_a_second_conversation_and_keeps_the_first(make_service):
    service = make_service([says("Friday."), says("Hello.")])
    say(service, "when is the school trip?")
    say(service, "/new")
    say(service, "hi")
    titles = [r.title for r in service.past.listed("owner", "greeter")]
    assert titles == ["hi", "when is the school trip?"]


def test_going_back_shows_the_model_that_conversation_and_grows_its_row(make_service):
    service = make_service([says("Friday."), says("Hello."), says("Bring a packed lunch.")])
    say(service, "when is the school trip?")
    say(service, "/new")
    say(service, "hi")
    back = say(service, "/chats 2")
    assert back.text.startswith("Back in: when is the school trip?")
    assert back.text.endswith("Where we left it:\nYou: when is the school trip?\n"
                              "greeter: Friday.")
    assert back.transcript == ({"who": "you", "text": "when is the school trip?"},
                               {"who": "agent", "text": "Friday."})
    say(service, "what should he bring?")
    assert shown(service) == ["when is the school trip?", "what should he bring?"]
    rows = service.past.listed("owner", "greeter")
    assert [(r.title, r.turns) for r in rows] == [("when is the school trip?", 2),
                                                 ("hi", 1)]


def test_going_back_into_the_one_open_is_said(make_service):
    service = make_service([says("x")])
    say(service, "a")
    assert say(service, "/chats 1").text == "That's the conversation we're in now."


def test_words_find_a_conversation_and_keep_its_number(make_service):
    service = make_service([says("Lisbon in May."), says("1.5 bar.")])
    say(service, "where should we go?")
    say(service, "/new")
    say(service, "boiler pressure?")
    found = say(service, "/chats lisbon")
    assert "2. where should we go?" in found.text
    assert "*Lisbon*" in found.text
    assert "boiler" not in found.text
    assert "None of your conversations" in say(service, "/chats zebra").text


def test_a_number_that_is_not_there_is_said(make_service):
    service = make_service([says("x")])
    say(service, "a")
    assert "no conversation 7" in say(service, "/chats 7").text


def test_delete_asks_first_and_sure_deletes_for_good(make_service, tmp_path):
    service = make_service([says("noted"), says("hi")])
    say(service, "my zebracorn plan")
    say(service, "/new")
    say(service, "hello")
    asked = say(service, "/chats delete 2")
    assert "Delete “my zebracorn plan” for good?" in asked.text
    assert len(service.past.listed("owner", "greeter")) == 2
    done = say(service, "/chats delete 2 sure")
    assert done.text == "Deleted “my zebracorn plan” for good."
    assert [r.title for r in service.past.listed("owner", "greeter")] == ["hello"]
    service.past.close()
    for f in (tmp_path / "state" / "past").iterdir():
        assert b"zebracorn" not in f.read_bytes()


def test_the_conversation_open_now_is_not_deleted(make_service):
    service = make_service([says("x")])
    say(service, "a")
    assert "Send /new first" in say(service, "/chats delete 1 sure").text
    assert len(service.past.listed("owner", "greeter")) == 1


def test_one_persons_conversations_are_never_anothers(make_service, tmp_path):
    service = make_service([says("x")])
    say(service, "my secret plan")
    theirs = say(service, "/chats", actor="guest")
    assert "secret" not in theirs.text and "no conversations" in theirs.text
    assert service.past.listed("guest") == []
    assert [f.name for f in (tmp_path / "state" / "past").glob("*.sqlite")] == ["owner.sqlite"]


def test_nothing_said_is_nothing_kept(make_service):
    service = make_service([])
    say(service, "/new")
    assert service.past.listed("owner", "greeter") == []


def test_a_scheduled_run_is_not_a_conversation(make_service, monkeypatch):
    monkeypatch.setenv("YANTRA_UNATTENDED", "1")
    service = make_service([says("all quiet")])
    say(service, "check the site")
    assert service.past.listed("owner") == []


def test_what_new_kept_before_comes_over_once(tmp_path):
    old = tmp_path / "past.sqlite3"
    db = sqlite3.connect(old)
    db.execute("CREATE TABLE past (id INTEGER PRIMARY KEY, actor TEXT, agent TEXT, "
               "came TEXT, title TEXT, turns INTEGER, ended TEXT, payload TEXT)")
    db.execute("INSERT INTO past (actor, agent, came, title, turns, ended, payload) "
               "VALUES (?,?,?,?,?,?,?)",
               ("o", "greeter", "Telegram", "old trip", 1, "2026-09-01T10:00:00+00:00",
                json.dumps({"history": [{"role": "user", "content": [
                    {"kind": "text", "text": "old trip"}]}]})))
    db.commit()
    db.close()
    book = past.PastBook(tmp_path / "past")
    assert book.bring_in(old) == 1 and not old.exists()
    [row] = book.listed("o", "greeter")
    assert (row.title, row.road, row.updated_at) == ("old trip", "Telegram",
                                                     "2026-09-01T10:00:00+00:00")
    assert book.bring_in(old) == 0
    book.close()


def test_a_persons_file_is_never_a_step_up(tmp_path):
    book = past.PastBook(tmp_path / "past")
    assert book._path("..").parent == tmp_path / "past"
    assert not book._path(".x").name.startswith(".")
    book.close()


def test_one_still_open_in_another_chat_is_not_opened_twice(make_service):
    service = make_service([says("Friday."), says("hi")])
    say(service, "trip?", thread="telegram:1")
    said = say(service, "/chats 1", thread="web:chat")
    assert said.text.startswith("That conversation is still going on Telegram.")


def test_export_sends_a_file_of_words_and_tool_names(make_service):
    service = make_service([says("The trip is on Friday.")])
    say(service, "when is the school trip?")
    sent = say(service, "/chats export 1")
    assert sent.run_id is None and sent.stop_reason == "files"
    [made] = sent.files
    assert made.parent.name == "shared" and made.name.endswith("-when-is-the-school-trip.md")
    text = made.read_text()
    assert "**You**\n\nwhen is the school trip?" in text
    assert "**greeter**\n\nThe trip is on Friday." in text
    assert "never what they returned" in sent.text


def test_export_of_a_number_not_there_is_said(make_service):
    service = make_service([says("x")])
    say(service, "a")
    sent = say(service, "/chats export 9")
    assert "no conversation 9" in sent.text and not sent.files


def test_export_is_only_the_word_with_a_number():
    assert past.export_pick("/chats export 2") == 2
    assert past.export_pick("/chats export") is None
    assert past.export_pick("/chats exports 2") is None
    assert past.export_pick("export 2") is None


def test_the_session_it_replaces_is_its_own_key(make_service):
    service = make_service([says("Friday."), says("hi")])
    say(service, "trip?")
    say(service, "/new")
    say(service, "hello")
    say(service, "/chats 2")
    assert service.sessions.load_latest(session_key("owner", "greeter", "chat"))


def test_the_transcript_is_words_never_a_tools_output():
    payload = {"history": [
        {"role": "user", "content": [{"kind": "text", "text": "check the site"}]},
        {"role": "assistant", "content": [{"kind": "text", "text": "Looking."},
                                          {"kind": "tool_call", "name": "web_fetch"}]},
        {"role": "user", "content": [{"kind": "tool_result", "content": "<html>secret"}]},
        {"role": "assistant", "content": [{"kind": "text", "text": "It's up."}]}]}
    assert past.transcript(payload) == [{"who": "you", "text": "check the site"},
                                        {"who": "agent", "text": "It's up."}]


def finish(client, auth, text):
    client.post("/web/message", headers=auth,
                json={"actor": "owner", "agent": "greeter", "text": text})
    for _ in range(200):
        seen = client.get("/web?actor=owner", headers=auth).json()
        if not seen["busy"]:
            return seen
        time.sleep(0.02)
    return seen


def test_the_page_gets_the_whole_conversation_on_its_line(make_service):
    from fastapi.testclient import TestClient

    from dvara.http import create_app

    service = make_service([says("Friday."), says("Hi.")], web=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        for text in ("when is the trip?", "/new", "hello"):
            finish(client, auth, text)
        seen = finish(client, auth, "/chats 2")
        last = seen["lines"][-1]
    assert last["transcript"] == [{"who": "you", "text": "when is the trip?"},
                                  {"who": "agent", "text": "Friday."}]


def test_the_page_lists_searches_reads_and_deletes(make_service):
    from fastapi.testclient import TestClient

    from dvara.http import create_app

    service = make_service([says("Lisbon in May."), says("1.5 bar.")], web=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        finish(client, auth, "where should we go?")
        finish(client, auth, "/new")
        finish(client, auth, "boiler pressure?")
        listed = client.get("/web/chats", headers=auth,
                            params={"actor": "owner"}).json()
        assert [r["title"] for r in listed["rows"]] == ["boiler pressure?",
                                                         "where should we go?"]
        assert listed["rows"][0]["open"] and not listed["rows"][1]["open"]
        assert listed["rows"][1]["agent"] == "greeter"
        found = client.get("/web/chats", headers=auth,
                           params={"actor": "owner", "q": "lisbon"}).json()["rows"]
        assert [r["title"] for r in found] == ["where should we go?"]
        old = found[0]["id"]
        read = client.get(f"/web/chats/{old}", headers=auth,
                          params={"actor": "owner"}).json()
        assert read["transcript"][1] == {"who": "agent", "text": "Lisbon in May."}
        assert client.get(f"/web/chats/{old}", headers=auth,
                          params={"actor": "guest"}).status_code == 404
        got = client.get(f"/web/chats/{old}/export", headers=auth,
                         params={"actor": "owner"})
        assert got.status_code == 200 and got.headers["content-type"].startswith("text/markdown")
        assert "**greeter**\n\nLisbon in May." in got.text
        assert "where-should-we-go.md" in got.headers["content-disposition"]
        assert client.get(f"/web/chats/{old}/export", headers=auth,
                          params={"actor": "guest"}).status_code == 404
        now = listed["rows"][0]["id"]
        assert client.request("DELETE", f"/web/chats/{now}", headers=auth,
                              params={"actor": "owner"}).status_code == 409
        assert client.request("DELETE", f"/web/chats/{old}", headers=auth,
                              params={"actor": "owner"}).status_code == 200
        assert client.get(f"/web/chats/{old}", headers=auth,
                          params={"actor": "owner"}).status_code == 404


def test_the_page_carries_one_on(make_service):
    from fastapi.testclient import TestClient

    from dvara.http import create_app

    service = make_service([says("Lisbon."), says("hi"), says("Book flights.")], web=True)
    token = "a-token-long-enough-to-be-real"
    auth = {"Authorization": f"Bearer {token}"}
    with TestClient(create_app(service, token=token)) as client:
        finish(client, auth, "where should we go?")
        finish(client, auth, "/new")
        finish(client, auth, "hello")
        old = client.get("/web/chats", headers=auth, params={
            "actor": "owner", "q": "where"}).json()["rows"][0]["id"]
        seen = finish(client, auth, f"/chats open {old}")
        assert seen["lines"][-1]["transcript"][0]["text"] == "where should we go?"
        finish(client, auth, "and then?")
    rows = service.past.listed("owner", "greeter")
    assert [(r.title, r.turns) for r in rows][0] == ("where should we go?", 2)


# ---- kept as a test (Yantra's kept_tests.py) ----------------------------------


def test_keep_test_keeps_this_one_in_the_persons_own_tests(make_service, tmp_path,
                                                           monkeypatch):
    from yantra.eval_suite import load_cases
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([says("The trip is on Friday.")])
    say(service, "when is the school trip?")
    kept = say(service, "/keep test Friday, trip")
    assert kept.run_id is None
    assert kept.text.startswith("Kept “when is the school trip?” as a test")
    assert "say Friday, trip" in kept.text and "nothing real runs" in kept.text
    suite = tmp_path / "tests" / "people" / "owner" / "greeter"
    [case] = load_cases(suite)
    assert case.answer_contains == ["Friday", "trip"]
    about = json.loads((suite / "agent.json").read_text())
    assert about["person"] == "owner" and about["package"].endswith("greeter")


def test_chats_test_n_keeps_one_from_the_list(make_service, tmp_path, monkeypatch):
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([says("Friday."), says("Hello.")])
    say(service, "when is the school trip?")
    say(service, "/new")
    say(service, "hi")
    kept = say(service, "/chats test 2")
    assert "“when is the school trip?”" in kept.text
    assert "no conversation 9" in say(service, "/chats test 9").text


def test_nothing_to_keep_yet_is_said(make_service, tmp_path, monkeypatch):
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([])
    assert "nothing to keep yet" in say(service, "/keep test").text


def test_one_persons_tests_are_never_anothers(make_service, tmp_path, monkeypatch):
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([says("Friday.")])
    say(service, "when is the trip?")
    theirs = say(service, "/chats test 1", actor="guest")
    assert "no conversation 1" in theirs.text
    assert not (tmp_path / "tests").exists()


def test_keep_test_is_only_those_words():
    assert past.keep_test_words("/keep test May 20, refund") == "May 20, refund"
    assert past.keep_test_words("/keep test") == ""
    assert past.keep_test_words("/keep") is None
    assert past.keep_test_words("/keep tests") is None
    assert past.test_pick("/chats test 3 refund") == (3, "refund")
    assert past.test_pick("/chats test") is None


def test_tests_lists_and_takes_one_back(make_service, tmp_path, monkeypatch):
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([says("The trip is on Friday.")])
    say(service, "when is the school trip?")
    say(service, "/keep test Friday")
    listed = say(service, "/tests")
    assert listed.run_id is None
    assert "1. when is the school trip? — not run yet (must say Friday)" in listed.text
    assert "no kept test 4" in say(service, "/tests delete 4").text
    gone = say(service, "/tests delete 1")
    assert "Taken back" in gone.text and "still in /chats" in gone.text
    assert "haven't kept any" in say(service, "/tests").text
    assert service.past.listed("owner", "greeter")          # the conversation stays


def test_chats_test_n_turn_k_keeps_that_turn(make_service, tmp_path, monkeypatch):
    from yantra.eval_suite import load_cases
    monkeypatch.setenv("YANTRA_TESTS", str(tmp_path / "tests"))
    service = make_service([says("Friday."), says("Bring lunch.")])
    say(service, "when is the trip?")
    say(service, "what should she bring?")
    kept = say(service, "/chats test 1 turn 1 Friday")
    assert "“when is the trip?”" in kept.text or "Kept" in kept.text
    [case] = load_cases(tmp_path / "tests" / "people" / "owner" / "greeter")
    assert case.user_message == "when is the trip?" and case.answer_contains == ["Friday"]
    assert "has 2 turns, not 7" in say(service, "/chats test 1 turn 7").text


def test_a_question_is_in_the_history_while_it_is_still_being_answered(make_service):
    """A long job -- a flight search that waits on a yes -- was only in the
    list once it ended. The question is there as soon as it's asked."""
    service = make_service([says("Flights found.")])
    seen_mid_turn = []
    asked = service.scripted._next

    def while_working(**kwargs):
        seen_mid_turn.append([(r.title, r.turns)
                              for r in service.past.listed("owner", "greeter")])
        return asked(**kwargs)

    service.scripted._next = while_working
    say(service, "find me a flight to Phoenix on Sunday")
    assert seen_mid_turn == [[("find me a flight to Phoenix on Sunday", 1)]]
    assert [r.title for r in service.past.listed("owner", "greeter")] == [
        "find me a flight to Phoenix on Sunday"]                 # one row, not two

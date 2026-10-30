"""A run, step by step (runsteps.py), from the ledger, the door and the chat.

The bias these tests encode: A PERSON'S WORDS ON THE OWNER'S SCREEN. The
owner's page has always kept what somebody typed and what their agent
said to that person alone; a step-by-step view is a much larger body of
the same thing (what the tools were given, what they read, the phone's
screen). So the owner sees anybody else's run as its shape only, and a
file for a bug report is made of their own runs only. The other bias is
a run that finds SOMEBODY ELSE'S steps: each run opens its own turn,
found by its run id, never by position.
"""

from __future__ import annotations

import asyncio

import pytest

from dvara import runsteps
from dvara.actors import ActorBook
from dvara.page import Api, ApiError
from tests.conftest import calls, says


def people():
    return ActorBook.from_dict({"actor": {"owner": {}, "guest": {"agents": ["greeter"]}}})


def say(service, text, actor="owner", thread="chat"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter", thread=thread,
                                       text=text))


def page(tmp_path, agents_root):
    actors = tmp_path / "actors.toml"
    actors.write_text('[actor.owner]\n[actor.guest]\nagents = ["greeter"]\n')
    return Api(root=agents_root, actors=actors, state=tmp_path / "state", owner="owner")


def test_each_run_opens_its_own_turn(make_service):
    service = make_service([calls("read_file", {"path": "a.txt"}), says("first"),
                            says("second")], actors=people())
    first = say(service, "read a.txt")
    second = say(service, "and now?")

    one = service.run_steps(first.run_id)
    two = service.run_steps(second.run_id)

    assert [s["tool"] for s in one["steps"]] == ["read_file"]
    assert one["steps"][0]["arguments"] == {"path": "a.txt"} and one["answer"] == "first"
    assert two["steps"] == [] and two["answer"] == "second"


def test_the_owner_sees_anybody_elses_run_as_its_shape(make_service, tmp_path,
                                                       agents_root):
    service = make_service([calls("read_file", {"path": "diary.txt"}), says("done")],
                           actors=people())
    theirs = say(service, "read my diary", actor="guest")
    api = page(tmp_path, agents_root)

    view = api.run_steps(theirs.run_id)

    assert view["message"] is None and view["answer"] is None
    assert view["steps"][0]["tool"] == "read_file"
    assert view["steps"][0]["arguments"] is None and view["steps"][0]["result"] is None
    with pytest.raises(ApiError, match="only your own runs"):
        api.run_steps(theirs.run_id, markdown=True)


def test_the_owners_own_run_comes_whole_and_as_a_file(make_service, tmp_path,
                                                      agents_root):
    service = make_service([calls("read_file", {"path": "a.txt"}), says("done")],
                           actors=people())
    mine = say(service, "read a.txt")
    api = page(tmp_path, agents_root)

    assert api.run_steps(mine.run_id)["steps"][0]["arguments"] == {"path": "a.txt"}
    got = api.run_steps(mine.run_id, markdown=True)
    assert got["markdown"].startswith("> This file holds") and got["name"].endswith(".md")


def test_a_run_whose_conversation_is_gone_says_so(make_service):
    service = make_service([says("hi")], actors=people())
    run = say(service, "hello")
    service.sessions.forget("owner/greeter/chat")

    with pytest.raises(runsteps.NoSteps, match="no longer kept"):
        service.run_steps(run.run_id)


def test_a_person_asks_for_their_own_last_turn_in_the_chat(make_service):
    service = make_service([calls("read_file", {"path": "a.txt"}), says("done")],
                           actors=people())
    say(service, "read a.txt")

    reply = say(service, "/steps")

    assert "1. read_file" in reply.text and reply.run_id is None
    assert len(service.scripted.requests) == 2          # no model asked for it


# ---- the home page's chat: an answer's own steps, by its line ---------------------

def test_a_page_answer_opens_its_own_steps_and_nobody_elses(make_service):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from dvara.http import create_app
    from tests.test_web import AUTH, TOKEN, settled

    service = make_service([calls("read_file", {"path": "a.txt"}), says("done")],
                           web=True, actors=people())
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH,
                    json={"actor": "owner", "agent": "greeter", "text": "read a.txt"})
        seen = settled(client, "owner")
        mine, answer = seen["lines"][0], seen["lines"][-1]
        assert answer["steps"] is True and "steps" not in mine and "run" not in answer
        got = client.get(f"/web/steps?actor=owner&line={answer['id']}", headers=AUTH)
        assert got.status_code == 200
        view = got.json()
        assert [s["tool"] for s in view["steps"]] == ["read_file"]
        assert view["said"][0].startswith("1. read_file")
        made = client.get(f"/web/steps/export?actor=owner&line={answer['id']}",
                          headers=AUTH)
        assert made.status_code == 200 and "## 1. read_file" in made.text
        assert "attachment" in made.headers["content-disposition"]
        # their own words have no steps, and the line is nobody else's to open
        assert client.get(f"/web/steps?actor=owner&line={mine['id']}",
                          headers=AUTH).status_code == 404
        assert client.get(f"/web/steps?actor=guest&line={answer['id']}",
                          headers=AUTH).status_code == 404


def test_an_answers_steps_outlive_new_from_the_kept_conversation(make_service):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from dvara.http import create_app
    from tests.test_web import AUTH, TOKEN, settled

    service = make_service([calls("read_file", {"path": "a.txt"}), says("done")],
                           web=True, actors=people())
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH,
                    json={"actor": "owner", "agent": "greeter", "text": "read a.txt"})
        answer = settled(client, "owner")["lines"][-1]
        client.post("/web/message", headers=AUTH,
                    json={"actor": "owner", "agent": "greeter", "text": "/new"})
        settled(client, "owner")
        # its chat moved on; the list still has the conversation, and so does Steps
        got = client.get(f"/web/steps?actor=owner&line={answer['id']}", headers=AUTH)
        assert got.status_code == 200
        step = got.json()["steps"][0]
        assert step["tool"] == "read_file" and step["arguments"] == {"path": "a.txt"}

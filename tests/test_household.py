"""Bias: a fact for everyone that anyone can write, or that nobody sees.

The household's facts are read by every agent in the house, so the two
failures worth testing are opposite ones:

* a guest's ``/remember for everyone`` landing in every agent's prompt
  without the owner's yes (a guest writing the house's instructions);
* a kept fact that a turn never gets: only agents that remember, only
  the owner's own, or only until somebody restarts.

Plus what makes a chat word usable: numbers that pick what was listed,
and a refusal that says what to do instead of cutting a fact short.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from dvara import cli, household
from dvara.actors import ActorBook
from dvara.household import Household, HouseholdProblem

from tests.conftest import says

PEOPLE = ActorBook.from_dict({"actor": {"owner": {}, "guest": {}}})


def say(service, actor, text):
    return asyncio.run(service.deliver(actor=actor, agent="greeter",
                                       thread="t", text=text)).text


def test_the_words_after_for_everyone_are_the_fact():
    assert household.for_everyone("/remember for everyone: bins go out Tuesday") == \
        "bins go out Tuesday"
    assert household.for_everyone("/remember 1 3") is None
    assert household.for_everyone("remember for everyone x") is None


def test_the_owner_keeps_a_fact_and_every_turn_is_told_it(make_service):
    service = make_service([says("noted"), says("Tuesday")], actors=PEOPLE, owner="owner")
    assert "Kept for everyone" in say(service, "owner",
                                      "/remember for everyone the bins go out Tuesday")
    say(service, "guest", "when do bins go out?")
    system = service.scripted.requests[-1].get("system")
    assert "bins go out Tuesday" in system and "household" in system.lower()


def test_a_guests_fact_is_offered_not_kept(make_service):
    service = make_service([says("hi")], actors=PEOPLE, owner="owner")
    said = say(service, "guest", "/remember for everyone wifi is on the fridge")
    assert said.startswith("Offered to owner")
    assert service.household.facts() == []
    assert [f.text for f in service.household.offered()] == ["wifi is on the fridge"]
    say(service, "guest", "hello")
    assert "fridge" not in (service.scripted.requests[-1].get("system") or "")


def test_the_owner_answers_an_offer_by_its_number(make_service):
    service = make_service(actors=PEOPLE, owner="owner")
    say(service, "guest", "/remember for everyone wifi is on the fridge")
    assert "Offered, waiting on you" in say(service, "owner", "/household")
    assert "Kept" in say(service, "owner", "/household yes 1")
    assert [f.text for f in service.household.facts()] == ["wifi is on the fridge"]
    assert "Only owner" in say(service, "guest", "/household forget 1")
    assert "Forgotten" in say(service, "owner", "/household forget 1")


def test_with_no_owner_an_offer_has_nobody_to_go_to(make_service):
    service = make_service(actors=PEOPLE)
    assert "nobody to offer it to" in say(service, "guest", "/remember for everyone x")


def test_a_fact_too_long_is_refused_whole(tmp_path):
    with pytest.raises(HouseholdProblem, match="characters"):
        Household(tmp_path).add("x" * (household.LONGEST + 1), "owner")
    assert Household(tmp_path).facts() == []


def test_the_same_fact_twice_is_one(tmp_path):
    house = Household(tmp_path)
    house.add("Bins Tuesday", "owner")
    with pytest.raises(HouseholdProblem, match="already"):
        house.offer("bins tuesday", "guest")


def test_the_file_is_the_owners_alone(tmp_path):
    Household(tmp_path).add("a", "owner")
    assert (tmp_path / household.FILE).stat().st_mode & 0o777 == 0o600


def test_the_page_changes_it_through_settings(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO('{"add": "bins Tuesday"}'))
    assert cli.main(["--state", str(state), "--owner", "owner",
                     "settings", "household"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [f["text"] for f in out["household"]["facts"]] == ["bins Tuesday"]
    assert out["household"]["facts"][0]["by"] == "owner"

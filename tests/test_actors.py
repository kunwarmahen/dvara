"""Bias: a misspelled ceiling that quietly means "no ceiling".

The actors file is the only thing standing between a stranger and an
agent, and every failure here is silent by nature: a typo'd key, an empty
whitelist read as "everything", a negative allowance accepted. Each test
is one of those made loud.
"""

from __future__ import annotations

import pytest

from dvara.actors import Actor, ActorBook
from dvara.errors import ConfigProblem, Refused


def book(**actors) -> ActorBook:
    return ActorBook.from_dict({"actor": actors})


def test_an_actor_with_no_agents_key_may_reach_every_agent():
    assert book(owner={}).get("owner").may_use("anything")


def test_an_agents_list_is_a_complete_whitelist():
    guest = book(guest={"agents": ["greeter"]}).get("guest")
    assert guest.may_use("greeter")
    assert not guest.may_use("researcher")


def test_an_unknown_actor_learns_nothing_about_who_else_exists():
    with pytest.raises(Refused) as caught:
        book(owner={}, guest={}).get("stranger")
    assert "owner" not in str(caught.value)
    assert "guest" not in str(caught.value)


def test_reaching_an_agent_you_do_not_have_is_refused_by_name():
    with pytest.raises(Refused) as caught:
        book(guest={"agents": ["greeter"]}).may("guest", "researcher")
    assert "researcher" in str(caught.value)


def test_a_misspelled_key_is_an_error_rather_than_no_ceiling():
    with pytest.raises(ConfigProblem) as caught:
        book(guest={"max_usd_per_days": 1.0})
    assert "max_usd_per_days" in str(caught.value)


def test_an_empty_agents_list_is_an_error_not_a_silent_lockout():
    with pytest.raises(ConfigProblem):
        book(guest={"agents": []})


@pytest.mark.parametrize("value", [0, -1.0, "0.50", True])
def test_a_ceiling_that_could_never_serve_anyone_is_an_error(value):
    with pytest.raises(ConfigProblem):
        book(guest={"max_usd_per_turn": value})


def test_a_file_with_no_actors_serves_nobody_and_says_so():
    with pytest.raises(ConfigProblem):
        ActorBook.from_dict({})


def test_the_file_round_trips_from_disk(tmp_path):
    path = tmp_path / "actors.toml"
    path.write_text('[actor.mahen]\nmax_usd_per_day = 2.0\n', encoding="utf-8")
    assert ActorBook.from_toml(path).get("mahen") == \
        Actor(id="mahen", agents=None, max_usd_per_turn=None,
              max_usd_per_day=2.0)


def test_a_missing_file_is_the_owners_problem(tmp_path):
    with pytest.raises(ConfigProblem):
        ActorBook.from_toml(tmp_path / "nope.toml")


def test_the_shipped_example_parses():
    # An example that does not load is documentation that lies.
    from tests.conftest import EXAMPLES
    people = ActorBook.from_toml(EXAMPLES / "actors.toml")
    assert people.ids() == ["guest", "owner"]

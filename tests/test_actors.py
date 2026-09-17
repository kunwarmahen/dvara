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


# ---- the permissions rung ---------------------------------------------------

def test_an_actor_with_no_permissions_key_has_no_opinion():
    # The same convention as max_usd_per_turn: absent is not a ceiling.
    assert book(owner={}).get("owner").permissions is None


def test_a_rung_is_carried_through_to_the_gate():
    quiet = book(guest={"permissions": "read_only"}).get("guest")
    assert quiet.permissions == "read_only"


def test_a_misspelled_rung_is_an_error_rather_than_the_tightest():
    # At RUNTIME an unknown mode reads as the tightest, which is right for
    # a package somebody else wrote. In the owner's own file it is a typo
    # and the owner is standing right here to be told about it.
    with pytest.raises(ConfigProblem, match="permissions must be one of"):
        book(guest={"permissions": "read-only"})
    with pytest.raises(ConfigProblem, match="permissions must be one of"):
        book(guest={"permissions": True})


# ---- one person, several channels ------------------------------------------

def channelled(**actors) -> ActorBook:
    """An actors file where somebody is reachable somewhere."""
    return ActorBook.from_dict({"actor": actors})


def test_a_channel_identity_resolves_to_the_actor_the_owner_assigned():
    book_ = channelled(mahen={"channel": [{"kind": "telegram", "id": 8675309}]})
    assert book_.resolve("telegram", 8675309).id == "mahen"
    # The adapter will have a string in hand, and TOML had a number.
    # Either way it is the same person, because both sides are text.
    assert book_.resolve("telegram", "8675309").id == "mahen"


def test_two_channels_are_one_actor_with_one_allowance_and_one_queue():
    book_ = channelled(mahen={
        "max_usd_per_day": 2.0,
        "channel": [{"kind": "telegram", "id": "1"},
                    {"kind": "signal", "id": "+1555"}],
    })
    by_telegram = book_.resolve("telegram", "1")
    by_signal = book_.resolve("signal", "+1555")
    assert by_telegram is by_signal
    # The argument for the whole table: the owner wrote one ceiling and
    # there is one ceiling, rather than one per channel installed.
    assert by_telegram.max_usd_per_day == 2.0


def test_an_unmapped_channel_identity_is_refused_like_an_unknown_actor():
    book_ = channelled(mahen={"channel": [{"kind": "telegram", "id": "1"}]})
    with pytest.raises(Refused) as caught:
        book_.resolve("telegram", "2")
    assert "mahen" not in str(caught.value)


def test_a_channel_identity_is_not_an_actor_id():
    """The two namespaces do not leak into each other in either direction."""
    book_ = channelled(mahen={"channel": [{"kind": "telegram", "id": "1"}]})
    with pytest.raises(Refused):
        book_.get("1")
    with pytest.raises(Refused):
        book_.resolve("telegram", "mahen")


def test_one_channel_identity_claimed_by_two_people_is_an_error():
    with pytest.raises(ConfigProblem) as caught:
        channelled(mahen={"channel": [{"kind": "telegram", "id": "1"}]},
                   guest={"channel": [{"kind": "telegram", "id": "1"}]})
    # Naming both is the point: the owner has to know which two lines.
    assert "mahen" in str(caught.value)
    assert "guest" in str(caught.value)


def test_the_same_native_id_on_two_channels_is_two_different_people():
    """Kinds are separate namespaces, so no coincidence joins them."""
    book_ = channelled(mahen={"channel": [{"kind": "telegram", "id": "1"}]},
                       guest={"channel": [{"kind": "signal", "id": "1"}]})
    assert book_.resolve("telegram", "1").id == "mahen"
    assert book_.resolve("signal", "1").id == "guest"


def test_a_person_listed_twice_on_one_channel_is_an_error():
    with pytest.raises(ConfigProblem) as caught:
        channelled(mahen={"channel": [{"kind": "telegram", "id": "1"},
                                      {"kind": "telegram", "id": "1"}]})
    assert "once per line" in str(caught.value)


@pytest.mark.parametrize("kind", ["Telegram", "tele gram", "tele/gram",
                                  "2fast", "", 7])
def test_a_channel_kind_that_is_not_a_token_is_an_error(kind):
    with pytest.raises(ConfigProblem):
        channelled(mahen={"channel": [{"kind": kind, "id": "1"}]})


@pytest.mark.parametrize("native", [None, "", "  ", True, [], {"id": 1}])
def test_a_channel_with_no_usable_id_is_an_error(native):
    with pytest.raises(ConfigProblem):
        channelled(mahen={"channel": [{"kind": "telegram", "id": native}]})


def test_a_misspelled_channel_key_is_an_error_not_a_silent_omission():
    with pytest.raises(ConfigProblem) as caught:
        channelled(mahen={"channel": [{"kind": "telegram", "chat_id": "1"}]})
    assert "chat_id" in str(caught.value)


def test_a_channel_written_as_a_table_rather_than_a_list_is_an_error():
    with pytest.raises(ConfigProblem) as caught:
        channelled(mahen={"channel": {"kind": "telegram", "id": "1"}})
    assert "[[actor.mahen.channel]]" in str(caught.value)


def test_an_actor_with_no_channels_is_ordinary():
    owner = channelled(owner={}).get("owner")
    assert owner.channels == ()
    assert owner.reach() == ()


def test_reach_is_what_a_desk_needs_and_nothing_it_does_not():
    mahen = channelled(mahen={"channel": [{"kind": "telegram", "id": 1},
                              {"kind": "signal", "id": "+1555"}]}).get("mahen")
    assert mahen.reach() == (("telegram", "1"), ("signal", "+1555"))


def test_channels_survive_a_real_toml_file(tmp_path):
    path = tmp_path / "actors.toml"
    path.write_text(
        "[actor.mahen]\n"
        "max_usd_per_day = 2.0\n\n"
        "[[actor.mahen.channel]]\n"
        "kind = \"telegram\"\n"
        "id   = 8675309\n",
        encoding="utf-8")
    assert ActorBook.from_toml(path).resolve("telegram", 8675309).id == "mahen"


# ---- what follows the answer ------------------------------------------------

def test_no_receipt_key_is_the_quiet_default():
    assert book(owner={}).get("owner").receipt is None


def test_the_owner_may_ask_for_what_a_turn_cost():
    assert book(owner={"receipt": "cost"}).get("owner").receipt == "cost"


def test_a_person_on_an_allowance_may_ask_for_what_is_left():
    guest = book(guest={"max_usd_per_day": 0.10,
                        "receipt": "remaining"}).get("guest")
    assert guest.receipt == "remaining"


def test_asking_what_is_left_of_an_allowance_nobody_set_is_an_error():
    """A key that silently does nothing is worse than one that complains."""
    with pytest.raises(ConfigProblem) as caught:
        book(guest={"receipt": "remaining"})
    assert "max_usd_per_day" in str(caught.value)


@pytest.mark.parametrize("value", ["Cost", "yes", True, 1, "", "spent"])
def test_a_receipt_that_is_not_one_of_the_two_is_an_error(value):
    with pytest.raises(ConfigProblem):
        book(owner={"receipt": value})

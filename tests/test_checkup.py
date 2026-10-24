"""Bias: a person's check that shows them somebody else's trouble, or hides theirs.

``/doctor`` answers one person about what is theirs. The ways it goes
wrong are the two a shared house makes easy:

* a line about somebody else -- the owner's failed schedule, a guest's
  paused watch, a sign-in in an account narrowed away -- told to a
  person who can do nothing about it (and shouldn't see it);
* trouble of theirs left green: a sign-in the site ended, Samay not
  running when they have schedules, a day's allowance spent;

plus the fix being words they can't use (``setu connect`` at a
terminal, ``/connect`` on a folder the owner looks after).
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap
from datetime import UTC, datetime, timedelta

from dvara import checkup
from dvara.actors import ActorBook


NOW = datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def levels(lines):
    return [(line.level, line.about) for line in lines]


# ---- each part, from what its program said ------------------------------------------

def test_an_ended_sign_in_is_red_and_its_fix_is_a_chat_word():
    data = {"connections": [{"ref": "gmail:personal", "connector": "gmail",
                             "account": "personal", "expired": True},
                            {"ref": "gmail:work", "connector": "gmail", "account": "work"}]}
    lines = checkup.accounts(data, narrowed=None, own=True, owner="mahen",
                             now=NOW.timestamp())
    assert levels(lines) == [("red", "accounts")]
    assert lines[0].fix == "/connect gmail as personal"


def test_a_folder_the_owner_looks_after_says_ask_them():
    data = {"connections": [{"ref": "gmail:home", "connector": "gmail",
                             "account": "home", "expired": True}]}
    lines = checkup.accounts(data, narrowed=None, own=False, owner="mahen",
                             now=NOW.timestamp())
    assert lines[0].fix == "ask mahen to sign it in again"


def test_an_account_narrowed_away_is_not_theirs_to_hear_about():
    data = {"connections": [{"ref": "gmail:owner", "expired": True},
                            {"ref": "gmail:kid"}]}
    lines = checkup.accounts(data, narrowed=("gmail:kid",), own=False, owner="mahen",
                             now=NOW.timestamp())
    assert levels(lines) == [("green", "accounts")] and "1 account" in lines[0].said


def test_a_google_sign_in_in_its_last_days_is_amber_and_a_locked_folder_too():
    data = {"connections": [{"ref": "gmail:me", "connector": "gmail", "account": "me",
                             "ends": iso(NOW + timedelta(days=1))}],
            "lock": {"locked": True, "open": False}}
    lines = checkup.accounts(data, narrowed=None, own=True, owner=None,
                             now=NOW.timestamp())
    assert levels(lines) == [("amber", "accounts"), ("amber", "accounts")]
    assert "Google ends this sign-in" in lines[0].said and lines[1].fix == "/unlock"


SCHEDULES = [{"id": "s1", "owner": "kid", "prompt": "morning brief", "state": "active"},
             {"id": "s2", "owner": "mahen", "prompt": "the owner's", "state": "active"}]


def test_a_failed_run_of_theirs_is_amber_and_the_owners_is_not_shown():
    runs = [{"schedule": "s1", "outcome": "failed", "detail": "the model said no",
             "ended_at": iso(NOW - timedelta(hours=2))},
            {"schedule": "s2", "outcome": "failed", "ended_at": iso(NOW)},
            {"schedule": "s1", "outcome": "failed",
             "ended_at": iso(NOW - timedelta(days=3))}]
    lines = checkup.schedules({"serving": True}, SCHEDULES, runs, person={"kid"},
                              since=NOW - timedelta(days=1))
    assert levels(lines) == [("amber", "schedules")]
    assert "morning brief" in lines[0].said and "the model said no" in lines[0].said
    assert not any("owner's" in line.said for line in lines)


def test_samay_not_running_is_red_for_someone_with_schedules_and_nothing_without():
    stopped = checkup.schedules({"serving": False}, SCHEDULES, [], person={"kid"},
                                since=NOW)
    assert levels(stopped) == [("red", "schedules")]
    assert checkup.schedules({"serving": False}, SCHEDULES, [], person={"guest"},
                             since=NOW) == []


def test_a_paused_watch_and_a_broken_look_are_amber_and_only_theirs():
    listed = [{"id": "w1", "owner": "kid", "name": "price", "state": "paused",
               "paused_because": "3 broken looks in a row"},
              {"id": "w2", "owner": "kid", "name": "mail", "state": "active",
               "last_look": {"outcome": "failed", "detail": "no account"}},
              {"id": "w3", "owner": "mahen", "name": "the owner's", "state": "paused",
               "paused_because": "x"}]
    lines = checkup.watches({"serving": True}, listed, person={"kid"})
    assert levels(lines) == [("amber", "watches"), ("amber", "watches")]
    assert not any("owner's" in line.said for line in lines)
    # Prahari stopped: said in red, and what's wrong under it still said
    stopped = checkup.watches({"serving": False}, listed, person={"kid"})
    assert [line.level for line in stopped] == ["red", "amber", "amber"]


def test_a_phone_of_theirs_not_connected_is_amber_by_name():
    data = {"named": [{"name": "nexus", "where": "ABC", "kind": "Android"},
                      {"name": "iphone", "where": "XYZ", "kind": "iPhone"}],
            "phones": [{"serial": "ABC", "state": "device"}]}
    lines = checkup.phones(data, mine=("iphone",))
    assert levels(lines) == [("amber", "phone")] and "iphone" in lines[0].said
    both = checkup.phones(data, mine=())
    assert levels(both) == [("green", "phone"), ("amber", "phone")]


def test_an_allowance_spent_is_red_nearly_spent_amber():
    who = ActorBook.from_dict({"actor": {"kid": {"max_usd_per_day": 1.0,
                                                 "max_turns_per_day": 10}}}).get("kid")
    reset = NOW + timedelta(hours=3)
    spent = checkup.limits(who, spent=1.0, sent=2, now=NOW, reset=reset)
    assert levels(spent)[0] == ("red", "limits") and "spent" in spent[0].said
    nearly = checkup.limits(who, spent=0.85, sent=10, now=NOW, reset=reset)
    assert levels(nearly) == [("amber", "limits"), ("red", "limits")]


def test_the_answer_counts_and_the_owner_hears_where_the_house_is():
    lines = [checkup.Line("red", "accounts", "x ended", "/connect x"),
             checkup.Line("green", "limits", "fine")]
    said = checkup.said(lines, is_owner=True)
    assert said.splitlines()[0] == "Your check: 1 red"
    assert "→ /connect x" in said and "sarathi doctor" in said
    assert "sarathi doctor" not in checkup.said(lines, is_owner=False)
    assert checkup.said([], is_owner=False).startswith("Your check: Nothing of yours")


# ---- through the service -------------------------------------------------------------

FAKE_SAMAY = """\
    import json, sys
    args = sys.argv[1:]
    if args == ["list", "--json"]:
        print({schedules!r})
    elif args == ["status", "--json"]:
        print(json.dumps({{"serving": True}}))
    elif args[:1] == ["runs"]:
        print({runs!r})
    else:
        sys.exit("unexpected " + " ".join(args))
"""


def test_doctor_in_the_chat_is_their_own_lines_and_not_a_turn(make_service, tmp_path):
    runs = [{"schedule": "s1", "outcome": "timed_out", "ended_at": iso(NOW)},
            {"schedule": "s2", "outcome": "failed", "ended_at": iso(NOW)}]
    samay = tmp_path / "samay"
    samay.write_text(f"#!{sys.executable}\n" + textwrap.dedent(FAKE_SAMAY).format(
        schedules=json.dumps(SCHEDULES), runs=json.dumps(runs)))
    samay.chmod(0o755)
    book = ActorBook.from_dict({"actor": {"mahen": {}, "kid": {"max_usd_per_day": 1.0}}})
    service = make_service([], actors=book, samay=str(samay), owner="mahen")  # no model
    reply = asyncio.run(service.deliver(actor="kid", agent="greeter", thread="t",
                                        text="/doctor"))
    assert reply.stop_reason == "doctor" and reply.run_id is None
    assert "morning brief" in reply.text and "ran out of time" in reply.text
    assert "owner's" not in reply.text and "sarathi doctor" not in reply.text
    assert "$0.00 of your $1.00 today" in reply.text
    mine = asyncio.run(service.deliver(actor="mahen", agent="greeter", thread="t",
                                       text="/doctor"))
    assert "the owner's" in mine.text and "sarathi doctor" in mine.text
    assert json.dumps(service.scripted.requests) == "[]"


def test_the_owner_is_told_how_to_start_it_a_person_whom_to_tell():
    listed = [{"id": "w1", "owner": "local", "name": "BTC", "state": "active"}]
    owner = checkup.watches({"serving": False}, listed, person={"mahen", "local"},
                            start=checkup.OWNER_STARTS)
    assert owner[0].fix.startswith("`sarathi up`")
    assert checkup.watches({"serving": False}, listed, person={"kid"}) == []


def test_the_owner_of_a_shared_folder_is_given_the_computers_words():
    data = {"connections": [{"ref": "gmail:personal", "connector": "gmail",
                             "account": "personal", "expired": True}]}
    lines = checkup.accounts(data, narrowed=None, own=False, owner="mahen",
                             now=NOW.timestamp(), is_owner=True)
    assert lines[0].fix.startswith("setu connect gmail --as personal")

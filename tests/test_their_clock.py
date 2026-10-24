"""Bias: a person abroad on the house's clock.

One machine serves a household, and the household isn't always in one
place: a child at university, a parent on holiday. With one clock for
everyone, three things are quietly wrong for that person, and each test
here catches one:

* their agent is told this machine's time, so "remind me in an hour" and
  "what's today?" are counted from somebody else's day;
* their schedule "every day at 7" runs at 7 on this machine's clock;
* their hours ("07:00-21:00") open and close on this machine's clock.

And the owner's typo: a zone that isn't one, quietly read as this
machine's, is a bedtime hours out. It's an error at load, like every
other key in the file.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from dvara import settings
from dvara.actors import ActorBook
from dvara.errors import ConfigProblem
from dvara.limits import now_for

from tests.conftest import says, write_package
from tests.test_schedules import logged, samay  # noqa: F401 -- a fixture

#: Far from anywhere this test is likely to run, and a quarter-hour off.
AWAY = "Pacific/Chatham"


def offset(zone: str) -> str:
    seconds = int(datetime.now(ZoneInfo(zone)).utcoffset().total_seconds())
    sign = "-" if seconds < 0 else "+"
    seconds = abs(seconds)
    return f"UTC{sign}{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"


def deliver(service, actor="away", text="what time is it?"):
    return asyncio.run(service.deliver(actor=actor, agent="clocked", thread="t",
                                       text=text))


@pytest.fixture
def clocked(agents_root):
    write_package(agents_root, "clocked",
                  body='[agent]\nname = "clocked"\nprompt = "prompt.md"\n'
                       '[env]\ncontext = "local"\n')
    return agents_root


def told(service) -> str:
    request = service.scripted.requests[-1]
    return str(request.get("messages")) + str(request.get("system") or "")


def test_their_agent_is_told_the_time_on_their_clock(make_service, clocked):
    book = ActorBook.from_dict({"actor": {"owner": {}, "away": {"zone": AWAY}}})
    service = make_service([says("it is late here")], actors=book)
    assert deliver(service).ok
    assert offset(AWAY) in told(service)


def test_someone_without_a_zone_keeps_this_machines(make_service, clocked):
    book = ActorBook.from_dict({"actor": {"owner": {}, "away": {}}})
    service = make_service([says("ok")], actors=book)
    assert deliver(service).ok
    seconds = int(datetime.now().astimezone().utcoffset().total_seconds())
    sign = "-" if seconds < 0 else "+"
    here = f"UTC{sign}{abs(seconds) // 3600:02d}:{abs(seconds) % 3600 // 60:02d}"
    assert here in told(service)


def test_their_hours_open_on_their_clock_not_this_machines(make_service, clocked):
    # A window open right now where they are, and closed right now here
    # (unless here is there, which this zone was chosen to make unlikely).
    theirs = now_for(AWAY)
    window = f"{theirs:%H:%M}-{theirs + timedelta(hours=1):%H:%M}"
    here = datetime.now().astimezone()
    if theirs.strftime("%H") == here.strftime("%H"):
        pytest.skip("this machine keeps the far zone's hour")
    away = ActorBook.from_dict({"actor": {"owner": {}, "away": {"hours": window,
                                                                "zone": AWAY}}})
    assert deliver(make_service([says("open")], actors=away)).ok
    home = ActorBook.from_dict({"actor": {"owner": {}, "away": {"hours": window}}})
    refused = deliver(make_service([], actors=home))
    assert refused.stop_reason == "refused" and window in refused.text


def test_now_for_no_zone_is_this_machines_clock():
    assert now_for(None).utcoffset() == datetime.now().astimezone().utcoffset()
    assert now_for(AWAY).tzinfo == ZoneInfo(AWAY)


@pytest.mark.parametrize("bad", ["Europe/Londn", "IST", "+05:30", 5, ""])
def test_a_zone_that_isnt_one_is_an_error_at_load(bad):
    with pytest.raises(ConfigProblem, match="zone must be a time zone's name"):
        ActorBook.from_dict({"actor": {"away": {"zone": bad}}})


def test_utc_is_a_zone():
    book = ActorBook.from_dict({"actor": {"away": {"zone": "UTC"}}})
    assert book.get("away").zone == "UTC"


def test_the_page_reads_and_writes_their_zone(tmp_path):
    actors = tmp_path / "actors.toml"
    actors.write_text("[actor.owner]\n\n[actor.away]\n", encoding="utf-8")
    shown = settings.set_person(actors, "away", {"zone": "Asia/Kolkata"})
    assert shown["zone"] == "Asia/Kolkata"
    assert 'zone = "Asia/Kolkata"' in actors.read_text(encoding="utf-8")
    with pytest.raises(ConfigProblem, match="zone"):
        settings.set_person(actors, "away", {"zone": "Asia/Kolkatta"})
    assert settings.set_person(actors, "away", {"zone": None})["zone"] is None


def test_their_schedules_are_made_on_their_clock(make_service, samay):  # noqa: F811
    book = ActorBook.from_dict({"actor": {"owner": {}, "away": {"zone": AWAY}}})
    service = make_service([says("ok"), says("ok")], actors=book, samay=str(samay[0]))
    asyncio.run(service.deliver(actor="away", agent="greeter", thread="t", text="hi"))
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t", text="hi"))
    assert [z for kind, z in (e for e in logged(samay[1]) if e[0] == "zone")] == [AWAY, ""]

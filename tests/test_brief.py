"""``/brief``: the house's own account of a person's last day.

The bias these tests encode: A BRIEF THAT LEAVES OUT WHAT NOBODY SAW, OR
PUTS IN WHAT ISN'T THEIRS. A watch's run at 3 am missing because it was
untyped; yesterday's due times listed as today's; somebody else's
schedule or run in it; a schedule's own scheduled /brief refused because
nobody typed it; a quiet day that says nothing at all, which looks like
the house being down. And a model asked for it, which costs money for
words the ledger already has.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone, UTC

from dvara import brief
from dvara.runs import Run

NOW = datetime(2026, 11, 18, 7, 30, tzinfo=timezone(timedelta(hours=-5)))


def run(**kw) -> Run:
    base = dict(actor="owner", agent="minder", thread="chat", message="hi",
                started_at=NOW - timedelta(hours=1), stop_reason="end_turn")
    return Run(**{**base, **kw})


WATCHED = run(thread="prahari-43dff0b2-1", unattended=True, came_by="prahari",
              started_at=NOW - timedelta(hours=5),
              message='(Prahari, watching for the person: "Heat below 70°F" -- (every '
                      'hour).)\n\nSet the guest room to heat.', cost_usd=0.0)
SCHEDULED = run(thread="samay-713aefd8-c1", unattended=True, came_by="samay",
                started_at=NOW - timedelta(minutes=30), stop_reason="held",
                message="(A scheduled run.)\n\nWrite my morning brief.")


def compose(**kw):
    kw.setdefault("runs", [SCHEDULED, WATCHED])
    kw.setdefault("schedules", [])
    kw.setdefault("watches", [])
    return brief.compose(now=NOW, **kw)


class TestWhatRanUnseen:
    def test_a_watchs_and_a_schedules_runs_are_listed_with_how_they_ended(self):
        said = compose()
        assert ('02:30 Your watch "Heat below 70°F" (Prahari): "Set the guest room to heat."'
                ' — done (/why 2)') in said
        assert '07:00 Your schedule 713aefd8 (Samay): "Write my morning brief." — waiting ' \
               'for your yes (/why 1)' in said

    def test_a_typed_turn_and_an_older_run_are_not_unseen(self):
        said = compose(runs=[run(message="what's the weather"),
                             run(thread="samay-1-2", unattended=True,
                                 started_at=NOW - timedelta(days=2))])
        assert "What ran that nobody typed:\n- nothing" in said

    def test_model_use_counts_the_day_and_says_when_nothing_was_billed(self):
        assert "Model use: 2 turns, nothing billed." in compose()
        assert "Model use: 1 turn, $0.42." in compose(runs=[run(cost_usd=0.42)])


class TestToday:
    def test_only_what_is_still_due_today_in_their_zone_and_paused_ones_named(self):
        later = (NOW + timedelta(hours=2)).astimezone(UTC).isoformat()
        earlier = (NOW - timedelta(hours=2)).astimezone(UTC).isoformat()
        tomorrow = (NOW + timedelta(days=1)).astimezone(UTC).isoformat()
        said = compose(schedules=[
            {"prompt": "Water the plants", "state": "active", "upcoming": [later, tomorrow]},
            {"prompt": "Gone already", "state": "active", "upcoming": [earlier]},
            {"prompt": "Check flights", "state": "paused", "paused_because": "3 failures",
             "upcoming": []}])
        assert "- 09:30 Water the plants" in said and "Gone already" not in said
        assert "- paused: Check flights (3 failures)" in said

    def test_a_program_that_couldnt_be_read_is_said_not_skipped(self):
        said = compose(schedules=None, schedules_why="Samay didn't answer",
                       watches=None, watches_why="watches aren't switched on here")
        assert "Due today:\n- Samay didn't answer" in said
        assert "Watches: watches aren't switched on here" in said

    def test_watches_say_how_many_look_which_fired_and_which_stopped(self):
        said = compose(watches=[
            {"name": "Heat below 70°F", "state": "active", "fired_today": 2},
            {"name": "ALAB under $50", "state": "active", "fired_today": 0},
            {"name": "Porch package", "state": "paused",
             "paused_because": "the camera hasn't sent a new picture since Mon"}])
        assert "Watches: 2 looking, 1 saw what they wait for" in said
        assert "- Heat below 70°F: saw it 2 times" in said
        assert "- paused: Porch package (the camera hasn't sent a new picture" in said


class TestTheWords:
    def test_every_morning_reads_a_time_off_and_nonsense(self):
        assert brief.morning_word("/brief every morning") == ("on", None)
        assert brief.morning_word("/brief every morning 6:45") == ("on", "06:45")
        assert brief.morning_word("/brief every morning off") == ("off", None)
        assert brief.morning_word("/brief every morning soonish") == ("bad", "soonish")
        assert brief.morning_word("/brief") is None


class TestThroughTheService:
    def test_brief_is_theirs_and_asks_no_model(self, make_service):
        service = make_service([])
        service.runs.record(run(actor="owner", thread="samay-aa-1", unattended=True,
                                started_at=datetime.now(UTC) - timedelta(hours=1),
                                message="(x)\n\nMine, overnight"))
        service.runs.record(run(actor="guest", thread="samay-bb-1", unattended=True,
                                started_at=datetime.now(UTC) - timedelta(hours=1),
                                message="(x)\n\nThe guest's"))
        said = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                           text="/brief")).text
        assert "Mine, overnight" in said and "The guest's" not in said
        assert "schedules aren't switched on here" in said
        assert service.scripted.requests == []

    def test_a_scheduled_brief_is_answered_not_refused(self, make_service):
        service = make_service([])
        reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="t",
                                            text="/brief", unattended=True))
        assert reply.stop_reason == "brief" and "Your house, the last 24 hours" in reply.text
        assert "/brief every morning" not in reply.text

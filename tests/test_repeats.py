"""The same ask, day after day, offered as a schedule (repeats.py).

The bias these tests encode: AN OFFER THAT NAGS, OR ONE THAT'S WRONG. A
retry counted as a habit; a schedule's own run counted as the person
asking; the same ask in other words missed while two different asks are
merged; the schedule set for 2 am because one late ask pulled an
average; an offer made again after "no"; and anything that holds the
answer open or asks a model.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone

from dvara import repeats
from dvara.runs import Run

from tests.conftest import says

TZ = timezone(timedelta(hours=-5))
NOW = datetime(2026, 11, 18, 19, 42, tzinfo=TZ)        # a Wednesday


def ask(text, days_ago, hour=19, minute=40, **kw) -> Run:
    base = dict(actor="owner", agent="greeter", thread="chat", message=text,
                started_at=(NOW - timedelta(days=days_ago)).replace(hour=hour, minute=minute),
                stop_reason="end_turn")
    return Run(**{**base, **kw})


class TestTheSameAsk:
    def test_other_words_for_the_same_ask_match(self):
        assert repeats.same(repeats.marks("what's the guest room temp"),
                            repeats.marks("Guest room temperature?"))

    def test_different_asks_do_not(self):
        assert not repeats.same(repeats.marks("guest room temperature"),
                                repeats.marks("turn off the guest room light"))


class TestAHabit:
    def test_three_days_is_a_habit_at_the_time_they_ask(self):
        found = repeats.habit("guest room temperature?", "greeter",
                              [ask("what's the guest room temp", 1, minute=35),
                               ask("guest room temp please", 3, minute=50)], NOW)
        assert found is not None and found.days == 3 and found.at == "19:40"
        assert found.words == "guest room temperature?" and not found.weekdays

    def test_three_times_in_one_day_is_a_retry_not_a_habit(self):
        runs = [ask("guest room temperature", 0, minute=m) for m in (10, 20, 30)]
        assert repeats.habit("guest room temperature", "greeter", runs, NOW) is None

    def test_a_schedules_run_and_a_failed_turn_are_not_asks(self):
        runs = [ask("guest room temperature", 1, unattended=True),
                ask("guest room temperature", 2, stop_reason="error")]
        assert repeats.habit("guest room temperature", "greeter", runs, NOW) is None

    def test_older_than_thirty_days_or_another_agents_dont_count(self):
        runs = [ask("guest room temperature", 40), ask("guest room temperature", 2,
                                                       agent="minder")]
        assert repeats.habit("guest room temperature", "greeter", runs, NOW) is None

    def test_one_late_ask_doesnt_drag_the_time(self):
        runs = [ask("portfolio value today", d, hour=7, minute=30) for d in (1, 2)]
        runs.append(ask("portfolio value today", 3, hour=23, minute=55))
        found = repeats.habit("portfolio value today", "greeter", runs,
                              NOW.replace(hour=7, minute=35))
        assert found.at == "07:35"         # the middle of 07:30, 07:30, 07:35, 23:55

    def test_asked_only_on_weekdays_is_a_weekday_schedule(self):
        runs = [ask("portfolio value", d, hour=7) for d in (1, 2)]   # Tue, Mon
        found = repeats.habit("portfolio value", "greeter", runs, NOW.replace(hour=7))
        assert found.weekdays and found.when() == "at 07:40 on weekdays"

    def test_a_word_or_two_is_no_habit(self):
        runs = [ask("thanks", d) for d in (1, 2)]
        assert repeats.habit("thanks", "greeter", runs, NOW) is None


class TestTheOffer:
    def test_offered_once_and_never_after_no(self, tmp_path):
        offers = repeats.Offers(tmp_path)
        found = repeats.habit("guest room temperature", "greeter",
                              [ask("guest room temp", d) for d in (1, 2)], NOW)
        assert not offers.known("owner", found)
        assert offers.offer("owner", found) == 1 and offers.known("owner", found)
        assert offers.take("owner", 1, decline=True).words == "guest room temperature"
        assert offers.waiting("owner") == [] and offers.known("owner", found)
        assert not offers.known("priya", found)               # theirs, not everyone's


def deliver(service, text, actor="owner"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter", thread="chat",
                                       text=text))


class TestThroughTheService:
    def seed(self, service, words="guest room temperature"):
        for d in (1, 2):
            service.runs.record(Run(actor="owner", agent="greeter", thread="chat",
                                    message=words, stop_reason="end_turn",
                                    started_at=datetime.now(UTC) - timedelta(days=d)))

    def test_the_third_day_gets_one_line_under_the_answer_and_no_more(self, make_service,
                                                                     tmp_path):
        service = make_service([says("It's 68°F."), says("It's 67°F.")], samay="samay")
        self.seed(service)
        first = deliver(service, "guest room temperature?").text
        assert first.startswith("It's 68°F.") and "/repeats yes 1 makes it a schedule" in first
        again = deliver(service, "guest room temperature?").text
        assert "/repeats" not in again                        # offered once

    def test_without_schedules_there_is_no_offer(self, make_service):
        service = make_service([says("It's 68°F.")])
        self.seed(service)
        assert "/repeats" not in deliver(service, "guest room temperature?").text

    def test_yes_makes_a_samay_schedule_as_them_at_their_time(self, make_service, tmp_path):
        log = tmp_path / "samay-args.json"
        fake = tmp_path / "samay"
        fake.write_text("#!/usr/bin/env python3\nimport json, sys\n"
                        f"open({str(log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                        "print(json.dumps({'id': 'abc', 'sentence': 'every day at 19:40'}))\n")
        fake.chmod(0o755)
        service = make_service([says("It's 68°F.")], samay=str(fake))
        self.seed(service)
        deliver(service, "guest room temperature?")
        said = deliver(service, "/repeats yes 1").text
        assert said.startswith('Done: "guest room temperature?" every day at 19:40.')
        argv = json.loads(log.read_text())
        assert argv[:2] == ["add", "guest room temperature?"]
        assert argv[argv.index("--as") + 1] == "owner"
        assert argv[argv.index("--runner") + 1] == "dvara"
        assert argv[argv.index("--notify") + 1] == "always"
        assert "Nothing I've noticed" in deliver(service, "/repeats").text   # list empty now
        assert service.repeats.waiting("owner") == []

    def test_no_drops_it_for_good_and_asks_no_model(self, make_service):
        service = make_service([says("It's 68°F.")], samay="samay")
        self.seed(service)
        deliver(service, "guest room temperature?")
        assert deliver(service, "/repeats no 1").text.startswith("I won't offer")
        assert len(service.scripted.requests) == 1           # only the real question

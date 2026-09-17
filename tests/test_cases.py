"""Bias: a loop that closes itself, and a case nobody can act on later.

Two failures, and they pull in opposite directions.

A SERVICE THAT EDITS THE PACKAGE IT RUNS. Note 01 refused to let a
running agent write into the folder the owner reviews and commits, and a
failure loop is the obvious place for that rule to quietly lapse. So the
default is stdout, `--write` is a flag a person types, and the append is
tested for the things that make an edit safe: the existing suite parses
first, and the same run cannot be written down twice.

A CASE THAT MEANS NOTHING IN SIX MONTHS. `trace-a8ba6c09` with a blank
description is a row in a gate that nobody dares delete and nobody can
explain. So a turn that ended normally is refused unless somebody says
what was wrong with it, and every generated description is asserted to
carry the run id and the date.

The third strand is the round trip itself, and it is the one worth
keeping honest: these tests parse the rendered case back with Yantra's
own loader rather than matching on the text. A block that looks right and
does not load is the only failure that would reach a package.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from yantra import Usage, load_cases

from dvara.cases import append, case_from_run, suite_file
from dvara.errors import ConfigProblem, Refused
from dvara.runs import Run

from tests.conftest import write_package


def run(*, reason="error", detail="ToolError: boom", message="do the thing",
        tokens=(1000, 500), agent="scribe", id="a8ba6c09f2d9") -> Run:
    return Run(actor="owner", agent=agent, thread="t",
               message=message,
               started_at=datetime(2026, 9, 17, 9, 30, tzinfo=UTC),
               reply="", model="qwen3.8:latest",
               usage=Usage(tokens[0], tokens[1], 0, 0),
               stop_reason=reason, detail=detail, id=id)


def loaded(package):
    """The package's suite, read back by the loader that will grade it."""
    return load_cases(package)


# ---- which runs become cases ------------------------------------------------


class TestWhatIsEligible:
    @pytest.mark.parametrize("reason", ["error", "max_iterations",
                                        "over_budget"])
    def test_a_turn_that_stopped_badly_describes_itself(self, reason):
        case = case_from_run(run(reason=reason))
        assert case.id == "trace-a8ba6c09"
        assert case.user_message == "do the thing"
        assert case.description.strip()

    def test_a_refused_run_is_never_a_case(self):
        """No agent ran. The row is about this service's configuration and
        would mean nothing in somebody else's copy of the package."""
        with pytest.raises(Refused, match="before any agent ran"):
            case_from_run(run(reason="refused", detail=None))

    def test_a_turn_that_ended_normally_needs_a_person_to_say_why(self):
        with pytest.raises(Refused, match="--because"):
            case_from_run(run(reason="end_turn", detail=None))

    def test_a_cancelled_turn_needs_one_too(self):
        """The caller hung up. Whether that was because it was going wrong
        is not something the service saw."""
        with pytest.raises(Refused, match="--because"):
            case_from_run(run(reason="cancelled", detail=None))

    def test_because_is_enough_to_pin_a_green_turn(self):
        case = case_from_run(run(reason="end_turn", detail=None),
                             because="it cited a file that does not exist")
        assert case.description.startswith("it cited a file that does not "
                                           "exist")

    def test_because_overrides_the_services_own_verdict(self):
        """The owner was there. What they say happened wins over a stop
        reason, which is a log line."""
        case = case_from_run(run(), because="it should have asked me first")
        assert case.description.startswith("it should have asked me first")
        assert "ToolError" not in case.description

    def test_an_empty_message_has_nothing_to_replay(self):
        with pytest.raises(Refused, match="no message"):
            case_from_run(run(message="   "))


class TestWhatTheCaseSays:
    def test_the_description_carries_the_run_id_and_the_date(self):
        """What somebody needs six months later to find the turn this came
        from."""
        description = case_from_run(run()).description
        assert "a8ba6c09f2d9" in description
        assert "2026-09-17" in description

    def test_the_description_never_names_the_actor(self):
        """A package is a thing you hand to somebody. The people this
        service serves are not part of it."""
        assert "owner" not in case_from_run(run()).description

    def test_the_ceiling_is_what_the_failure_spent_plus_half(self):
        assert case_from_run(run(tokens=(1000, 500))).max_tokens == 2250

    def test_a_run_that_never_reached_a_model_gets_no_ceiling(self):
        """Leaving the package's own in force, which is the honest answer
        when there is no evidence about cost."""
        assert case_from_run(run(tokens=(0, 0))).max_tokens is None

    def test_the_iteration_cap_is_left_to_the_package(self):
        """Even for a turn that died on one: the package's cap is part of
        what is under test, and raising it would grade a different agent."""
        assert case_from_run(run(reason="max_iterations")).max_iterations is None

    def test_a_crash_message_with_quotes_survives_the_round_trip(self, tmp_path):
        """The reason the writer lives in Yantra beside the parser."""
        package = write_package(tmp_path, "scribe")
        append(package, case_from_run(run(
            detail='KeyError: "path"\nduring the retry as well')))
        (back,) = loaded(package)
        assert 'KeyError: "path"' in back.description


# ---- putting it in the package ----------------------------------------------


class TestAppending:
    def test_a_package_with_no_gate_gets_one(self, tmp_path):
        package = write_package(tmp_path, "scribe")
        path = append(package, case_from_run(run()))
        assert path == suite_file(package)
        assert [c.id for c in loaded(package)] == ["trace-a8ba6c09"]
        assert "acceptance gate" in path.read_text(), "no header for a reader"

    def test_a_second_case_lands_beside_the_first(self, tmp_path):
        package = write_package(tmp_path, "scribe")
        append(package, case_from_run(run()))
        append(package, case_from_run(run(id="bbbbbbbbbbbb",
                                          reason="end_turn", detail=None),
                                      because="wrong answer"))
        assert [c.id for c in loaded(package)] == ["trace-a8ba6c09",
                                                   "trace-bbbbbbbb"]

    def test_the_cases_an_author_wrote_by_hand_survive(self, tmp_path):
        package = write_package(tmp_path, "scribe")
        handwritten = suite_file(package)
        handwritten.parent.mkdir(parents=True)
        handwritten.write_text('[[case]]\nid = "cannot-write"\n'
                               'lacks_tools = ["bash"]\n', encoding="utf-8")
        append(package, case_from_run(run()))
        ids = [c.id for c in loaded(package)]
        assert ids == ["cannot-write", "trace-a8ba6c09"]

    def test_the_same_run_cannot_be_written_down_twice(self, tmp_path):
        package = write_package(tmp_path, "scribe")
        append(package, case_from_run(run()))
        with pytest.raises(Refused, match="already has a case"):
            append(package, case_from_run(run()))

    def test_a_suite_that_does_not_parse_is_left_alone(self, tmp_path):
        """Breaking every case in a file to add one, at the moment somebody
        was trying to make the package more trustworthy."""
        package = write_package(tmp_path, "scribe")
        broken = suite_file(package)
        broken.parent.mkdir(parents=True)
        broken.write_text("[[case]\n", encoding="utf-8")
        with pytest.raises(ConfigProblem, match="does not parse"):
            append(package, case_from_run(run()))
        assert broken.read_text() == "[[case]\n"

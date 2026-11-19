"""``/why``: what started a run, what let each step happen, what it went by.

The bias these tests encode: AN ANSWER TO "WHY DID YOU DO THAT?" THAT IS
WRONG, OR SOMEBODY ELSE'S. A schedule's run told as "you asked"; a call
a rule let through told as the person's yes; a refused call told as
done; another person's run shown because it was the newest; and the
words a run went by lost because the store keeps no use. Each would make
the answer worse than none.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from dvara import why
from dvara.runs import Run, ToolStep

from tests.conftest import says


def run(**kw) -> Run:
    base = dict(actor="owner", agent="greeter", thread="chat", message="turn the heat on",
                started_at=datetime.now(UTC), stop_reason="end_turn", came_by="telegram")
    return Run(**{**base, **kw})


def say(service, text, actor="owner"):
    return asyncio.run(service.deliver(actor=actor, agent="greeter", thread="chat",
                                       text=text)).text


class TestWhoStartedIt:
    def test_a_typed_turn_says_the_channel(self):
        assert why.started_by(run()) == "You asked, on Telegram."

    def test_a_schedule_a_watch_a_routine_and_the_puck_are_named(self):
        assert "schedule 713aefd8 (Samay)" in why.started_by(
            run(thread="samay-713aefd8-c1f43f1f", came_by="samay", unattended=True))
        watched = run(thread="prahari-43dff0b2-1794433093", came_by="prahari",
                      unattended=True, message='(Prahari, watching for the person: '
                      '"Guestroom heat when below 70°F" -- senses …)\n\nTurn the heat on.')
        assert 'watch "Guestroom heat when below 70°F" (Prahari)' in why.started_by(watched)
        assert "routine cold-night (Vidhi)" in why.started_by(
            run(thread="vidhi-cold-night-r1", unattended=True))
        assert why.started_by(run(thread="vaani:kitchen", came_by="vaani")) == \
            "You asked out loud, at the kitchen puck."

    def test_a_framing_with_brackets_inside_is_skipped_whole(self):
        framed = run(message='(Prahari, watching for the person: "Heat below 70°F" -- '
                             'senses outside-temp (every hour); tells you when.)\n\n'
                             'Set the guest room to heat.')
        assert why.asked(framed) == "Set the guest room to heat."

    def test_what_was_asked_drops_a_programs_framing(self):
        framed = run(message="(A scheduled run -- at 07:30. Nobody is watching.)\n\n"
                             "Write my morning brief.\n\n(Last run, Tue: Calendar)")
        assert why.asked(framed) == "Write my morning brief."


class TestWhatLetEachStepHappen:
    def test_each_kind_of_yes_and_the_rung_are_told_apart(self):
        said = why.explain(run(tools=[
            ToolStep("mcp__homeassistant-home__get_state"),
            ToolStep("mcp__homeassistant-home__call_service", decided_by="asked:telegram"),
            ToolStep("write_file", decided_by="rule:notes-ok"),
            ToolStep("send_file", decided_by="ahead"),
            ToolStep("web_fetch", decided_by="for_turn"),
            ToolStep("buy", refusal="timeout")]), rung="ask")
        assert "1. get_state (homeassistant-home): it only looks" in said
        assert "2. call_service (homeassistant-home): you said yes on telegram" in said
        assert "3. write_file: your standing rule notes-ok allows it" in said
        assert "4. send_file: the grant you gave the schedule" in said
        assert "5. web_fetch: your yes for the whole task" in said
        assert "6. buy: refused: nobody answered in time" in said

    def test_on_yolo_a_change_nobody_was_asked_about_is_not_called_a_look(self):
        said = why.explain(run(tools=[ToolStep("write_file")]), rung="yolo")
        assert "ran unasked: this agent may act without asking" in said
        assert "only looks" not in said

    def test_the_same_step_in_a_row_is_one_line(self):
        said = why.explain(run(tools=[ToolStep("list_available_tools")] * 3
                               + [ToolStep("web_fetch")]), rung="ask")
        assert "1. list_available_tools ×3: it only looks" in said and "2. web_fetch" in said

    def test_what_it_went_by_and_kept_are_said_as_judgements(self):
        said = why.explain(run(leaned_on=["Lives in Cary"], kept=["Has a cat"],
                               cost_usd=0.031, model="qwen3.8"))
        assert "What it seems to have gone by about you:\n- Lives in Cary" in said
        assert "What it kept about you:\n- Has a cat" in said
        assert said.endswith("It finished, costing $0.03 (qwen3.8).")


class TestTheirsOnly:
    def test_why_shows_their_own_newest_run_and_no_one_elses(self, make_service):
        service = make_service([])
        now = datetime.now(UTC)
        service.runs.record(run(message="mine, older", started_at=now - timedelta(hours=2)))
        service.runs.record(run(message="mine, newest", started_at=now - timedelta(hours=1)))
        service.runs.record(run(actor="guest", message="the guest's", started_at=now))
        assert 'Why: "mine, newest"' in say(service, "/why")
        assert 'Why: "mine, older"' in say(service, "/why 2")
        assert "nothing 3 back" in say(service, "/why 3")
        assert service.scripted.requests == []          # no model was asked

    def test_a_word_after_why_that_isnt_a_number_says_how(self, make_service):
        assert "Send /why for the last" in say(make_service([]), "/why me")

    def test_with_nothing_done_yet_it_says_so(self, make_service):
        assert say(make_service([]), "/why") == "I haven't done anything for you here yet."


def test_a_turn_keeps_what_its_answer_leaned_on(make_service, agents_root, monkeypatch,
                                                tmp_path):
    # the run row carries Yantra's Memory.leaned, read back by /why
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    (agents_root / "greeter" / "agent.toml").write_text(
        '[agent]\nname = "greeter"\nprompt = "prompt.md"\n[memory]\nvia = "local"\n')
    from yantra.memory.local import LocalStore
    LocalStore().remember("owner", "Lives near RDU", {})
    service = make_service([says("From RDU, as before.")])
    say(service, "flights to Denver?")
    assert service.runs.recent(actor="owner")[0].leaned_on == ["Lives near RDU"]
    assert "- Lives near RDU" in say(service, "/why")

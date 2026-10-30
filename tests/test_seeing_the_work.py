"""Seeing the work: a turn watched, skills offered and kept, tools and schedules.

Designed against:

* **A watcher shown what a tool READ.** A step is the tool and its own
  one-line summary; the output (an inbox, a page) never reaches a channel.
* **A watcher that breaks costing the answer.** It is dropped; the turn
  answers.
* **A look that holds up the answer, or asks from behind it.** The reply
  comes back first; a test that would need a yes is refused unasked.
* **One person's kept skill changing the agent for another.** It is saved
  in the keeper's own folder, and only they see it.
* **A schedule's run offering skills to nobody.** Unattended turns are
  counted, never looked at.
* **``/tools`` starting every server to answer.** It reads what the last
  turn was given.
* **``/watches every`` reaching somebody else's watch.** A number or an id
  is looked up among the person's own; the owner's also counts what was
  made at the computer (``local``), nobody else's does.
"""

from __future__ import annotations

import asyncio
import json
import stat

import pytest
from yantra import PermissionRequest
from yantra.types import Usage

from dvara import gate as gates
from dvara.actors import ActorBook
from dvara.gate import Policy
from tests.conftest import calls, says, write_package

SCRIPT = """\
import sys
print("greeted", sys.argv[1])
"""

DRAFT = f"""VERDICT: save
NAME: greet-someone
DESCRIPTION: Greet someone by name through the greeting script. Use when
SCOPE: user
INPUTS: who (the name the person gives)
NEEDS: none
SCRIPT: scripts/greet.py
TEST: python3 "$SKILL_DIR/scripts/greet.py" world
=== INSTRUCTIONS ===
# Greet someone

1. Run python3 scripts/greet.py WHO from this skill's folder.
=== SCRIPT ===
{SCRIPT}=== END ===
"""

PEOPLE = ActorBook.from_dict({"actor": {"owner": {}, "maya": {}}})


def draft():
    return says(DRAFT, usage=Usage(900, 300))


def solved_turn() -> list:
    """Four working calls and an answer: a turn worth a look."""
    return [*(calls("bash", {"command": f"echo step {i}"}, call_id=f"c{i}",
                    usage=Usage(1000, 50)) for i in range(1, 5)),
            says("Greeted world.", usage=Usage(1000, 20))]


@pytest.fixture
def helper(agents_root):
    write_package(agents_root, "helper", body=(
        '[agent]\nname = "helper"\nprompt = "prompt.md"\n'
        '[permissions]\nmode = "yolo"\n[skills]\nenabled = true\n'))
    return "helper"


def run(service, *coros):
    async def go():
        out = [await c for c in coros]
        while service.learning._jobs:
            await asyncio.gather(*list(service.learning._jobs))
        return out
    return asyncio.run(go())


def say(service, text, *, actor="owner", agent="helper", watch=None):
    return service.deliver(actor=actor, agent=agent, thread="chat", text=text, watch=watch)


# ---- watching a turn ---------------------------------------------------------------


class TestWatching:
    def test_steps_are_lines_and_the_output_never_shows(self, make_service, helper):
        service = make_service([calls("bash", {"command": "echo the-secret-inbox"}),
                                says("All done.")], policy=Policy(mode="yolo"),
                               actors=PEOPLE)
        seen = []
        reply, = run(service, say(service, "go", watch=seen.append))
        assert reply.text == "All done."
        steps = [e for e in seen if e["kind"] == "step"]
        assert len(steps) == 1 and steps[0]["tool"] == "bash" and steps[0]["ok"]
        assert "echo the-secret-inbox" in steps[0]["said"]       # what it did
        assert not any("the-secret-inbox\n" in json.dumps(e) for e in seen)
        assert "".join(e["text"] for e in seen if e["kind"] == "text") == "All done."
        assert {"kind": "using", "tool": "bash"} in seen

    def test_a_watcher_that_breaks_costs_nothing(self, make_service, helper):
        service = make_service([says("Still here.")], actors=PEOPLE)

        def broken(event):
            raise RuntimeError("the page went away")

        reply, = run(service, say(service, "hi", watch=broken))
        assert reply.ok and reply.text == "Still here."

    def test_the_web_channel_shows_a_turn_while_it_runs(self, make_service, helper):
        service = make_service([calls("bash", {"command": "echo hi"}), says("Done.")],
                               policy=Policy(mode="yolo"), actors=PEOPLE, web=True)
        looks = []

        async def go():
            service.web.say("owner", "helper", "go")
            for _ in range(200):
                await asyncio.sleep(0)
                looks.append(service.web.look("owner"))
                if not service.web._busy:
                    break
            while service.learning._jobs:
                await asyncio.gather(*list(service.learning._jobs))

        asyncio.run(go())
        live = [lv for lk in looks for lv in lk["live"]]
        assert live and live[0]["agent"] == "helper"
        assert any("step" in i for lv in live for i in lv["items"])
        assert looks[-1]["live"] == []                     # gone once answered
        assert looks[-1]["lines"][-1]["text"] == "Done."


# ---- skills -------------------------------------------------------------------------


class TestSkills:
    def test_a_solved_turn_is_offered_behind_the_answer(self, make_service, helper):
        service = make_service([*solved_turn(), draft()], policy=Policy(mode="yolo"),
                               actors=PEOPLE, web=True)
        reply, = run(service, say(service, "greet world"))
        assert reply.text == "Greeted world."                 # the answer came first
        line = service.web.look("owner")["lines"][-1]
        assert line["who"] == "notice" and line["offer"]["name"] == "greet-someone"
        assert line["offer"]["test"] == "passed"
        assert f"/skills keep {line['offer']['id']}" in line["text"]
        looked = [r for r in service.runs.recent(limit=5) if r.stop_reason == "looked_for_skill"]
        assert looked and looked[0].usage.input_tokens > 0  # on their allowance

    def test_kept_it_lives_in_their_folder_and_only_they_see_it(self, make_service, helper):
        service = make_service([*solved_turn(), draft()], policy=Policy(mode="yolo"),
                               actors=PEOPLE)
        run(service, say(service, "greet world"))
        listed, = run(service, say(service, "/skills"))
        assert "1. greet-someone" in listed.text and listed.stop_reason == "skills"
        kept, = run(service, say(service, "/skills keep 1"))
        assert kept.text.startswith("Kept greet-someone")
        folder = service._workspace("owner/helper/chat")
        assert (folder / ".yantra/skills/learned/greet-someone/SKILL.md").is_file()
        mine, = run(service, say(service, "/skills"))
        assert "Yours:" in mine.text and "• greet-someone" in mine.text
        theirs, = run(service, say(service, "/skills", actor="maya"))
        assert "greet-someone" not in theirs.text

    def test_dropped_is_gone_with_its_files(self, make_service, helper):
        service = make_service([*solved_turn(), draft()], policy=Policy(mode="yolo"),
                               actors=PEOPLE)
        run(service, say(service, "greet world"))
        dropped, = run(service, say(service, "/skills drop 1"))
        assert dropped.text.startswith("Dropped greet-someone")
        folder = service._workspace("owner/helper/chat")
        assert not (folder / ".yantra/learning/greet-someone").exists()
        assert "Nothing is waiting" in run(service, say(service, "/skills keep 1"))[0].text

    def test_a_schedules_run_is_never_looked_at(self, make_service, helper):
        service = make_service(solved_turn(), policy=Policy(mode="yolo"), actors=PEOPLE)
        reply, = run(service, service.deliver(actor="owner", agent="helper", thread="s1",
                                              text="greet world", unattended=True))
        assert reply.ok and service.scripted.script == []   # no write-up was asked for

    def test_learning_off_looks_at_nothing(self, make_service, helper, monkeypatch):
        monkeypatch.setenv("YANTRA_LEARN", "off")
        service = make_service(solved_turn(), policy=Policy(mode="yolo"), actors=PEOPLE)
        assert run(service, say(service, "greet world"))[0].ok

    def test_learn_asks_for_one_now_even_after_a_short_job(self, make_service, helper):
        short = [calls("bash", {"command": "echo hi"}, call_id="c1"), says("Hi.")]
        service = make_service([*short, draft()], policy=Policy(mode="yolo"),
                               actors=PEOPLE, web=True)
        run(service, say(service, "greet world"))
        assert len(service.scripted.script) == 1      # the draft: no look by itself
        asked, = run(service, say(service, "/learn"))
        assert asked.text.startswith("Looking at how I did that")
        line = service.web.look("owner")["lines"][-1]
        assert line["who"] == "notice" and line["offer"]["name"] == "greet-someone"

    def test_learn_before_any_job_says_do_it_first(self, make_service, helper):
        service = make_service([], actors=PEOPLE)
        reply, = run(service, say(service, "/learn"))
        assert "Ask me to do the job first" in reply.text

    def test_learn_with_nothing_to_keep_says_why(self, make_service, helper):
        service = make_service([says("Hello.")], policy=Policy(mode="yolo"),
                               actors=PEOPLE, web=True)
        run(service, say(service, "hi"))
        run(service, say(service, "/learn"))
        line = service.web.look("owner")["lines"][-1]
        assert line["who"] == "notice" and line["text"].startswith("Nothing to keep")

    def test_an_agent_without_skills_says_so(self, make_service):
        service = make_service([], actors=PEOPLE)
        reply, = run(service, say(service, "/skills", agent="greeter"))
        assert "doesn't use skills" in reply.text

    def test_from_behind_nobody_is_asked(self):
        token = gates.NOBODY_ASKED.set(True)
        try:
            request = PermissionRequest(tool_name="bash", arguments={}, summary="ls",
                                        read_only=False, call_id="t")
            approved = asyncio.run(gates.put(object(), request, actor="owner",
                                             agent="helper", thread="chat"))
        finally:
            gates.NOBODY_ASKED.reset(token)
        assert approved is False and request.code == "unattended"


# ---- tools and schedules ---------------------------------------------------------------


class TestToolsAndSchedules:
    def test_tools_are_what_the_last_turn_was_given(self, make_service, helper):
        service = make_service([says("hi")], actors=PEOPLE)
        before, = run(service, say(service, "/tools"))
        assert "once you've sent it a message" in before.text
        run(service, say(service, "hello"))
        after, = run(service, say(service, "/tools"))
        assert after.stop_reason == "seen" and "built in:" in after.text
        assert "• bash" in after.text

    def test_schedules_off_says_so(self, make_service):
        service = make_service([], actors=PEOPLE)
        reply, = run(service, say(service, "/schedules", agent="greeter"))
        assert reply.text == "Schedules aren't switched on here."

    def test_only_your_own_schedules(self, make_service, tmp_path):
        cards = [{"id": "s1", "owner": "owner", "agent": "greeter", "prompt": "the weather",
                  "sentence": "every day at 08:00", "state": "active",
                  "last_run": {"outcome": "ok", "ended_at": "2026-10-14T08:00:05+00:00"}},
                 {"id": "s2", "owner": "maya", "agent": "greeter", "prompt": "maya's own",
                  "sentence": "every day at 09:00", "state": "active"}]
        (tmp_path / "cards.json").write_text(json.dumps(cards))
        samay = tmp_path / "samay"
        samay.write_text(f"#!/bin/sh\nif [ \"$1\" = list ]; then cat {tmp_path}/cards.json; "
                         "else echo '{}'; fi\n")
        samay.chmod(samay.stat().st_mode | stat.S_IEXEC)
        service = make_service([], actors=PEOPLE, samay=str(samay))
        reply, = run(service, say(service, "/schedules", agent="greeter"))
        assert "the weather" in reply.text and "every day at 08:00" in reply.text
        assert "Last time: ok" in reply.text and "maya's own" not in reply.text


def fake_prahari(tmp_path, cards) -> str:
    """A prahari that lists ``cards``, and on ``edit ID --every X`` writes
    down what it was asked and answers like Prahari (``1m`` too often)."""
    (tmp_path / "watches.json").write_text(json.dumps(cards))
    program = tmp_path / "prahari"
    program.write_text(
        "#!/bin/sh\n"
        f"if [ \"$1\" = list ]; then cat {tmp_path}/watches.json; exit 0; fi\n"
        f"echo \"$@\" >> {tmp_path}/asked\n"
        "if [ \"$4\" = 1m ]; then echo 'error: nothing is looked at more often than "
        "every 5 minutes; '\\''1m'\\'' is too often' >&2; exit 1; fi\n"
        "echo '{\"name\": \"ALAB under $50\", "
        "\"sentence\": \"every 6 hours, looks with web_fetch\"}'\n")
    program.chmod(program.stat().st_mode | stat.S_IEXEC)
    return str(program)


WATCH_CARDS = [
    {"id": "w1aa", "owner": "maya", "name": "ALAB under $50", "every": "3h",
     "asked": "tell me if ALAB gets cheap",
     "sentence": "every 3 hours, looks with web_fetch", "state": "active",
     "last_look": {"outcome": "quiet", "ended_at": "2026-10-14T08:00:05+00:00"}},
    {"id": "w2bb", "owner": "maya", "name": "Mum on WhatsApp", "every": "",
     "listen": "whatsapp", "sentence": "hears whatsapp at the inlet", "state": "active"},
    {"id": "w3cc", "owner": "owner", "name": "the owner's own", "every": "1h",
     "sentence": "every hour, looks with web_fetch", "state": "active"},
    {"id": "w4dd", "owner": "local", "name": "made at the computer", "every": "1d",
     "sentence": "every day, looks with web_fetch", "state": "paused",
     "paused_because": "broke twice"},
]


class TestWatches:
    def test_watches_off_says_so(self, make_service):
        service = make_service([], actors=PEOPLE)
        reply, = run(service, say(service, "/watches", agent="greeter"))
        assert reply.text == "Watches aren't switched on here."

    def test_only_your_own_watches_numbered(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS),
                               owner="owner")
        reply, = run(service, say(service, "/watches", actor="maya", agent="greeter"))
        assert reply.stop_reason == "seen"
        assert "1. ALAB under $50" in reply.text and "2. Mum on WhatsApp" in reply.text
        assert "Last look: quiet" in reply.text
        # what it is for, in their words, under its name; none for one made without
        assert ('1. ALAB under $50 (id w1aa)\n  You asked: "tell me if ALAB gets cheap"\n'
                '  every 3 hours') in reply.text
        assert reply.text.count("You asked") == 1
        assert "owner's own" not in reply.text and "the computer" not in reply.text

    def test_the_owner_also_sees_what_was_made_at_the_computer(self, make_service,
                                                                  tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS),
                               owner="owner")
        reply, = run(service, say(service, "/watches", agent="greeter"))
        assert "1. the owner's own" in reply.text
        assert "2. made at the computer" in reply.text and "paused: broke twice" in reply.text
        assert "ALAB" not in reply.text

    def test_every_changes_how_often_by_number(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS))
        reply, = run(service, say(service, "/watches every 1 6h", actor="maya",
                                  agent="greeter"))
        assert reply.text == "Done. \"ALAB under $50\": every 6 hours, looks with web_fetch."
        assert (tmp_path / "asked").read_text().split() == [
            "edit", "w1aa", "--every", "6h", "--json"]

    def test_a_number_from_someone_elses_list_finds_nothing(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS))
        for which in ("3", "w3cc"):
            reply, = run(service, say(service, f"/watches every {which} 6h", actor="maya",
                                      agent="greeter"))
            assert reply.text.startswith(f"You have no watch {which}.")
        assert not (tmp_path / "asked").exists()

    def test_a_watch_that_listens_has_no_how_often(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS))
        reply, = run(service, say(service, "/watches every 2 6h", actor="maya",
                                  agent="greeter"))
        assert "doesn't look on a clock" in reply.text
        assert not (tmp_path / "asked").exists()

    def test_prahari_saying_no_is_passed_on(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS))
        reply, = run(service, say(service, "/watches every w1 1m", actor="maya",
                                  agent="greeter"))
        assert reply.text == ("Prahari said: nothing is looked at more often than "
                              "every 5 minutes; '1m' is too often")

    def test_the_only_watch_needs_no_number(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE,
                               prahari=fake_prahari(tmp_path, WATCH_CARDS[2:3]))
        reply, = run(service, say(service, "/watches every 6h", agent="greeter"))
        assert reply.text.startswith("Done.")
        assert "w3cc" in (tmp_path / "asked").read_text()

    def test_a_word_it_doesnt_know_says_how(self, make_service, tmp_path):
        service = make_service([], actors=PEOPLE, prahari=fake_prahari(tmp_path, WATCH_CARDS))
        reply, = run(service, say(service, "/watches pause 1", actor="maya", agent="greeter"))
        assert "/watches every NUMBER 6h" in reply.text


class TestWhichSkills:
    """Only the package's skills and the person's own: never the
    computer's (~/.yantra/skills, where the owner's page keeps what the
    owner learned), the owner's own chat included."""

    @staticmethod
    def skill(root, name):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Does {name}. Use when asked.\n---\n\n1. Do it.\n")

    def test_the_computers_skills_reach_nobody(self, make_service, helper, agents_root,
                                                tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        self.skill(tmp_path / "home" / ".yantra" / "skills" / "learned", "owners-linkedin")
        self.skill(agents_root / "helper" / "skills", "check-the-orders")
        service = make_service([], actors=PEOPLE)
        for person in ("owner", "maya"):
            listed, = run(service, say(service, "/skills", actor=person))
            assert "check-the-orders" in listed.text
            assert "owners-linkedin" not in listed.text

"""A lesson through Dvara: a job taught one step per message, kept as one skill.

Designed against:

* **The walk learned as its last step.** Each message is its own turn,
  and the agent is built anew for each; the lesson is kept on disk and
  every turn since ``/learn start`` reaches the write-up.
* **A step offered as a skill of its own.** While a lesson is open, no
  look runs after a turn.
* **The agent running ahead.** The lesson's opening is the turn the
  agent hears first, so it knows it is being taught.
* **One person's lesson in another's.** It is kept per person per agent.
* **A page that can't see it.** Sarathi's home chat draws a lesson bar
  from the web look, so the look names each open lesson -- and only the
  person's own.
* **A word that isn't there.** ``/learn clear`` drops it, like ``stop``.
"""

from __future__ import annotations

import asyncio

import pytest
from yantra.types import Usage

from dvara.actors import ActorBook
from dvara.gate import Policy
from tests.conftest import calls, says, write_package

PEOPLE = ActorBook.from_dict({"actor": {"owner": {}, "maya": {}}})

DRAFT = """VERDICT: save
NAME: send-a-whatsapp-message
DESCRIPTION: Send someone a WhatsApp message on the phone. Use when asked to message someone.
SCOPE: user
INPUTS: who, message
NEEDS: the phone
SCRIPT: none
TEST: none
=== INSTRUCTIONS ===
# Send a WhatsApp message

1. Open WhatsApp. The Chats list shows.
2. Tap the chat named WHO.
=== END ===
"""


@pytest.fixture
def helper(agents_root):
    write_package(agents_root, "helper", body=(
        '[agent]\nname = "helper"\nprompt = "prompt.md"\n'
        '[permissions]\nmode = "yolo"\n[skills]\nenabled = true\n'))
    return "helper"


def run(service, *coros):
    async def go():
        out = []
        for c in coros:
            out.append(await c)
        while service.learning._jobs:
            await asyncio.gather(*list(service.learning._jobs))
        return out
    return asyncio.run(go())


def say(service, text, *, actor="owner"):
    return service.deliver(actor=actor, agent="helper", thread="chat", text=text)


def walk() -> list:
    """The opening's answer, then two taught steps of one call each."""
    return [says("Ready. What's first?"),
            calls("bash", {"command": "echo opened whatsapp"}, call_id="c1"),
            says("WhatsApp is open. Next?"),
            calls("bash", {"command": "echo tapped mom"}, call_id="c2"),
            says("Mom's chat is open. Next?")]


class TestALesson:
    def test_start_runs_the_opening_as_the_turn(self, make_service, helper):
        service = make_service(walk()[:1], policy=Policy(mode="yolo"), actors=PEOPLE)
        reply, = run(service, say(service, "/learn start send a WhatsApp message"))
        assert reply.text == "Ready. What's first?"
        heard = service.scripted.requests[0]["messages"][-1].text()
        assert "teach you how to send a WhatsApp message" in heard
        assert service.learning.lesson("owner", "helper").told() == 0

    def test_done_writes_the_whole_walk_and_nothing_is_offered_halfway(
            self, make_service, helper):
        service = make_service([*walk(), says(DRAFT, usage=Usage(900, 300))],
                               policy=Policy(mode="yolo"), actors=PEOPLE, web=True)
        run(service, say(service, "/learn start send a WhatsApp message"),
            say(service, "open WhatsApp"), say(service, "tap Mom"))
        assert len(service.scripted.script) == 1          # no look ran after a step
        assert service.learning.lesson("owner", "helper").told() == 2
        done, = run(service, say(service, "/learn done"))
        assert done.text.startswith("Writing down what you taught me (2 step(s))")
        prompt = service.scripted.requests[-1]["messages"][0].text()
        assert "PERSON: open WhatsApp" in prompt and "PERSON: tap Mom" in prompt
        assert "echo opened whatsapp" in prompt and "echo tapped mom" in prompt
        line = service.web.look("owner")["lines"][-1]
        assert line["offer"]["name"] == "send-a-whatsapp-message"
        assert service.learning.lesson("owner", "helper") is None

    def test_a_second_start_over_steps_says_how_far_the_first_got(self, make_service, helper):
        service = make_service(walk()[:3], policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"), say(service, "open WhatsApp"))
        again, = run(service, say(service, "/learn start y"))
        assert again.text.startswith("You're teaching me how to x")
        assert "/learn stop, then start again" in again.text

    def test_stop_drops_it_and_done_then_has_nothing(self, make_service, helper):
        service = make_service(walk()[:1], policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"))
        stopped, = run(service, say(service, "/learn stop"))
        done, = run(service, say(service, "/learn done"))
        assert stopped.text == "Dropped the lesson; nothing was kept."
        assert done.text.startswith("No lesson is open")

    def test_clear_drops_it_too(self, make_service, helper):
        service = make_service(walk()[:1], policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"))
        cleared, = run(service, say(service, "/learn clear"))
        assert cleared.text == "Dropped the lesson; nothing was kept."
        assert service.learning.lesson("owner", "helper") is None

    def test_the_web_look_shows_a_persons_open_lesson(self, make_service, helper):
        service = make_service(walk()[:3], policy=Policy(mode="yolo"), actors=PEOPLE,
                               web=True)
        assert service.web.look("owner")["lessons"] == []
        run(service, say(service, "/learn watch check my battery"),
            say(service, "open WhatsApp"))
        lesson, = service.web.look("owner")["lessons"]
        assert lesson["agent"] == "helper" and lesson["task"] == "check my battery"
        assert lesson["watching"] and lesson["told"] == 1
        assert service.web.look("maya")["lessons"] == []

    def test_a_lesson_is_one_persons(self, make_service, helper):
        service = make_service([*walk()[:1], says("Hi Maya.")],
                               policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"), say(service, "hi", actor="maya"))
        assert service.learning.lesson("maya", "helper") is None
        assert service.learning.lesson("owner", "helper").told() == 0

    def test_a_word_it_does_not_know_shows_how(self, make_service, helper):
        service = make_service([], actors=PEOPLE)
        reply, = run(service, say(service, "/learn begin"))
        assert "TELL: /learn start" in reply.text and "SHOW: /learn watch" in reply.text


class TestTheMixUps:
    """From a real run on Telegram: a second start answered with the first's
    status (0 steps); steps done by hand in a start lesson; /new leaving the
    lesson open with its opening gone."""

    def test_a_start_over_an_empty_lesson_replaces_it(self, make_service, helper):
        service = make_service([says("Ready."), says("Ready.")],
                               policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start coinbase current portfolio value"))
        again, = run(service, say(service, "/learn start check my Coinbase value"))
        assert again.text == "Ready."
        assert service.learning.lesson("owner", "helper").task == "check my Coinbase value"

    def test_done_with_nothing_taught_says_how_and_keeps_it(self, make_service, helper):
        service = make_service([says("Ready.")], policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"))
        done, = run(service, say(service, "/learn done"))
        assert "haven't shown me any steps" in done.text and "/learn watch" in done.text
        assert service.learning.lesson("owner", "helper") is not None
        assert service.scripted.script == []          # no write-up was asked for

    def test_new_drops_the_lesson_and_says_so(self, make_service, helper):
        service = make_service([says("Ready.")], policy=Policy(mode="yolo"), actors=PEOPLE)
        run(service, say(service, "/learn start x"))
        fresh, = run(service, say(service, "/new"))
        assert "lesson you'd started was dropped" in fresh.text
        assert service.learning.lesson("owner", "helper") is None

"""An answer read aloud (spoken.py).

The bias is A VOICE THAT GETS IN THE WAY: an answer read to someone who
chose silence, a voice note sent INSTEAD of the words (or before them,
so the person waits on it), code and web addresses read out letter by
letter, and a machine with no voice that loses the answer rather than
the voice. Piper is stood in for except in the one test that needs the
real thing, which is skipped where Piper or a voice isn't installed.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from dvara import heard, spoken
from dvara.actors import ActorBook
from dvara.errors import ConfigProblem
from tests.conftest import says
from tests.test_telegram import KNOWN, FakeTelegram, actors, make_bot, message  # noqa: F401


class Patient(FakeTelegram):
    """Polls that take a moment: hearing and speaking run off the loop."""

    def _handle(self, request):
        if request.url.path.endswith("/getUpdates"):
            time.sleep(0.01)
        return super()._handle(request)


@pytest.fixture
def voiced(monkeypatch):
    """A machine that can speak, where speaking writes a small file."""
    made: list[tuple[str, bool]] = []

    def make(text, out, *, telegram=False):
        made.append((text, telegram))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"OggS voice" if telegram else b"RIFF voice")
        return out

    monkeypatch.setattr(spoken, "make", make)
    monkeypatch.setattr(spoken, "can_speak", lambda: None)
    return made


def people(speak: str | None = None) -> ActorBook:
    body = {"channel": [{"kind": "telegram", "id": KNOWN}]}
    if speak is not None:
        body["speak"] = speak
    return ActorBook.from_dict({"actor": {"mahen": body}})


# ---- what is read -------------------------------------------------------------

def test_code_links_and_tables_are_not_read_out():
    said = spoken.aloud("**Done.** See [the order](https://amazon.com/x/123).\n\n"
                        "```\nrm -rf /tmp/x\n```\n"
                        "| item | price |\n|---|---|\n| tea | 4 |\n"
                        "- first thing\n- second thing\nMore at https://example.com/a?b=c")
    assert "https" not in said and "rm -rf" not in said and "|" not in said
    assert "**" not in said and "- first" not in said
    assert "See the order." in said and "(some code, in the message)" in said
    assert said.count("(a table, in the message)") == 1
    assert "first thing. second thing." in said and "More at a link" in said


def test_a_long_answer_stops_at_a_sentence_and_says_the_rest_is_written():
    said = spoken.aloud(" ".join(f"Sentence number {n} is here." for n in range(200)),
                        longest=200)
    assert said.endswith(spoken.REST)
    assert len(said) <= 200 + len(spoken.REST) + 1
    assert said[: -len(spoken.REST)].rstrip().endswith("here.")


def test_each_choice_reads_aloud_only_when_it_says():
    assert not spoken.wanted("off", spoke=True)
    assert spoken.wanted("when-spoken", spoke=True)
    assert not spoken.wanted("when-spoken", spoke=False)
    assert spoken.wanted("always", spoke=False)
    assert spoken.wanted(None, spoke=True) and not spoken.wanted(None, spoke=False)


# ---- who chose what -----------------------------------------------------------

def test_a_misspelled_choice_in_the_actors_file_is_an_error():
    with pytest.raises(ConfigProblem, match="speak must be one of off, when-spoken, always"):
        people("allways")
    assert people("always").get("mahen").speak == "always"


def test_their_own_voice_word_wins_over_the_file_and_can_be_taken_back(tmp_path):
    choices = spoken.Choices(tmp_path)
    assert choices.choice("mahen", "always") == "always"
    said = spoken.voice_words(choices, "mahen", "always", "/voice off")
    assert said == "From now on, I don't read answers aloud."
    assert choices.choice("mahen", "always") == "off"
    assert spoken.Choices(tmp_path).get("mahen") == "off"         # kept on disk
    said = spoken.voice_words(choices, "mahen", "always", "/voice default")
    assert said.startswith("Back to what's set for you") and "every answer" in said
    assert "/voice off" in spoken.voice_words(choices, "mahen", None, "/voice loudly")


def test_voice_says_when_this_machine_cannot_speak(tmp_path, monkeypatch):
    monkeypatch.setattr(spoken, "piper", lambda: None)
    said = spoken.voice_words(spoken.Choices(tmp_path), "mahen", None, "/voice")
    assert "when you send me a voice note" in said and "Piper isn't installed" in said


def test_off_in_the_environment_is_off_whatever_is_installed(monkeypatch):
    monkeypatch.setenv(spoken.ENV, "off")
    assert spoken.voice_file() is None and spoken.can_speak() == f"{spoken.ENV} is off"


# ---- on Telegram --------------------------------------------------------------

def test_a_voice_note_is_answered_with_words_then_a_voice_note(make_bot, monkeypatch,  # noqa: F811
                                                               voiced):
    monkeypatch.setattr(heard, "_hear", lambda path: "when do the bins go out")
    fake = Patient([message(None, voice={"file_id": "v1", "file_size": 2000})])
    bot = make_bot(fake, script=[says("The bins go out on **Tuesday**.")])
    asyncio.run(bot.run())
    order = [m for m, _ in fake.calls if m in ("sendMessage", "sendVoice")]
    assert order == ["sendMessage", "sendMessage", "sendVoice"]     # heard, answer, voice
    assert voiced == [("The bins go out on **Tuesday**.", True)]
    assert "OggS voice" in fake.of("sendVoice")[0]["multipart"]


def test_a_typed_message_gets_no_voice_by_default(make_bot, voiced):  # noqa: F811
    fake = Patient([message("when do the bins go out")])
    bot = make_bot(fake, script=[says("Tuesday.")])
    asyncio.run(bot.run())
    assert fake.texts() == ["Tuesday."] and not fake.of("sendVoice") and not voiced


def test_always_reads_a_typed_answer_and_off_reads_nothing(make_bot, make_service,  # noqa: F811
                                                           monkeypatch, voiced):
    fake = Patient([message("hi")])
    bot = make_bot(fake, service=make_service([says("Hello.")], actors=people("always")))
    asyncio.run(bot.run())
    assert len(fake.of("sendVoice")) == 1

    monkeypatch.setattr(heard, "_hear", lambda path: "hi")
    fake = Patient([message(None, voice={"file_id": "v2", "file_size": 2000})])
    bot = make_bot(fake, service=make_service([says("Hello.")], actors=people("off")))
    asyncio.run(bot.run())
    assert not fake.of("sendVoice") and fake.texts()[-1] == "Hello."


def test_no_voice_here_still_sends_the_words_and_tells_the_owner(make_bot, make_service,  # noqa: F811
                                                                 monkeypatch, capsys):
    monkeypatch.setattr(spoken, "piper", lambda: None)
    fake = Patient([message("hi")])
    bot = make_bot(fake, service=make_service([says("Hello.")], actors=people("always")))
    asyncio.run(bot.run())
    assert fake.texts() == ["Hello."] and not fake.of("sendVoice")
    assert "wasn't read aloud -- Piper isn't installed" in capsys.readouterr().err


def test_the_voice_word_is_not_a_turn(make_bot, make_service):  # noqa: F811
    fake = Patient([message("/voice always")])
    service = make_service([says("never asked")], actors=people())
    bot = make_bot(fake, service=service)
    asyncio.run(bot.run())
    assert "every answer" in fake.texts()[0]
    assert service.voices.get("mahen") == "always" and not service.runs.recent(limit=1)


# ---- on a page ------------------------------------------------------------------

def test_a_page_answer_is_read_aloud_when_asked_and_made_once(make_service, voiced):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from dvara.http import create_app
    from tests.test_web import AUTH, TOKEN, settled

    service = make_service([says("Tuesday, see https://council.example/bins.")],
                           web=True, actors=people("always"))
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH,
                    json={"actor": "mahen", "agent": "greeter", "text": "bins?"})
        seen = settled(client, "mahen")
        answer = seen["lines"][-1]
        assert seen["voice"] is True and answer["speak"] is True
        for _ in range(2):
            got = client.get(f"/web/spoken?actor=mahen&line={answer['id']}", headers=AUTH)
            assert got.status_code == 200 and got.content == b"RIFF voice"
        assert len(voiced) == 1                                   # kept, not made again
        mine = seen["lines"][0]["id"]
        assert client.get(f"/web/spoken?actor=mahen&line={mine}",
                          headers=AUTH).status_code == 404        # their own words


def test_a_page_with_no_voice_says_why(make_service, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from dvara.http import create_app
    from tests.test_web import AUTH, TOKEN, settled

    monkeypatch.setattr(spoken, "piper", lambda: None)
    service = make_service([says("Hello.")], web=True, actors=people())
    with TestClient(create_app(service, token=TOKEN)) as client:
        client.post("/web/message", headers=AUTH,
                    json={"actor": "mahen", "agent": "greeter", "text": "hi"})
        seen = settled(client, "mahen")
        assert seen["voice"] is False and "speak" not in seen["lines"][-1]
        got = client.get(f"/web/spoken?actor=mahen&line={seen['lines'][-1]['id']}",
                         headers=AUTH)
        assert got.status_code == 503 and "Piper isn't installed" in got.json()["detail"]


# ---- the real thing, where it's installed ---------------------------------------

@pytest.mark.skipif(spoken.can_speak() is not None,
                    reason="Piper and a voice aren't installed here")
def test_piper_really_makes_a_wav_and_a_telegram_voice_note(tmp_path):
    wav = spoken.make("The bins go out on Tuesday.", tmp_path / "a.wav")
    assert wav.read_bytes()[:4] == b"RIFF"
    ogg = spoken.make("The bins go out on Tuesday.", tmp_path / "a.ogg", telegram=True)
    assert ogg.read_bytes()[:4] == b"OggS"


def test_the_home_page_sets_it_and_blank_is_the_default(tmp_path):
    from dvara import settings

    path = tmp_path / "actors.toml"
    path.write_text("[actor.priya]\n")
    assert settings.set_person(path, "priya", {"speak": "always"})["speak"] == "always"
    assert 'speak = "always"' in path.read_text()
    assert settings.set_person(path, "priya", {"speak": None})["speak"] is None
    assert "speak" not in path.read_text()
    with pytest.raises(ConfigProblem, match="speak must be one of"):
        settings.set_person(path, "priya", {"speak": "loud"})


def test_a_backup_leaves_the_voices_made_for_the_page_out(tmp_path):
    from dvara import keeps
    from dvara.web import VOICE_CACHE

    state = next(k for k in keeps.report(tmp_path, tmp_path / "a.toml", tmp_path,
                                         tmp_path / "p.toml")["keeps"] if k["id"] == "state")
    assert VOICE_CACHE in state["leave_out"]

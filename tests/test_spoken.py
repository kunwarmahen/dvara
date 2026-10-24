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
import json
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


def a_voice(folder, name, family, language):
    """A voice file and its card, as Piper's catalogue ships them."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.onnx").write_bytes(b"not really a model")
    (folder / f"{name}.onnx.json").write_text(json.dumps(
        {"language": {"code": name.split("-")[0], "family": family,
                      "name_english": language}}))


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    """Only the voices a test puts here: English and Hindi to begin with,
    never what this machine happens to have installed."""
    folder = tmp_path / "voices"
    a_voice(folder, "en_US-lessac-medium", "en", "English")
    a_voice(folder, "hi_IN-pratham-medium", "hi", "Hindi")
    monkeypatch.setattr(spoken, "VOICES", ())
    monkeypatch.setenv("PIPER_VOICES", str(folder))
    monkeypatch.delenv(spoken.ENV, raising=False)
    return folder


class Made(list):
    """What was read aloud, (text, for Telegram), and in which voices."""

    def __init__(self) -> None:
        super().__init__()
        self.voices: list[str] = []


@pytest.fixture
def voiced(monkeypatch, shelf):
    """A machine that can speak, where speaking writes a small file and
    keeps which voice it would have used."""
    made = Made()

    def make(text, out, *, telegram=False, voice=None):
        made.append((text, telegram))
        chosen = voice if isinstance(voice, spoken.Voice) else spoken.pick(
            spoken.aloud(text), voice)
        made.voices.append(chosen.name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"OggS voice" if telegram else b"RIFF voice")
        return out

    monkeypatch.setattr(spoken, "make", make)
    monkeypatch.setattr(spoken, "piper", lambda: ["piper"])
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


# ---- whose voice, and the answer's language -------------------------------------

def test_the_answers_language_is_told_by_its_script_or_its_small_words():
    assert spoken.languages_of("कूड़ा मंगलवार को जाता है।")[0] == "hi"
    assert spoken.languages_of("The bins go out on Tuesday, and that is it.") == ("en",)
    assert spoken.languages_of("Der Müll wird am Dienstag abgeholt, das ist gut.") == ("de",)
    assert spoken.languages_of("Привет, как дела?")[0] == "ru"
    # an English name inside a Hindi answer doesn't make it English
    assert spoken.languages_of("आपका Wi-Fi पासवर्ड फ्रिज पर लिखा है।")[0] == "hi"
    assert spoken.languages_of("OK.") is None and spoken.languages_of("Tuesday") is None


def test_the_house_voice_is_english_and_each_voice_knows_its_language(shelf):
    every = spoken.voices()
    assert [v.name for v in every] == ["en_US-lessac-medium", "hi_IN-pratham-medium"]
    assert every[1].said() == "hi_IN-pratham-medium (Hindi)"


def test_dvara_voice_names_the_houses_own(shelf, monkeypatch):
    monkeypatch.setenv(spoken.ENV, "hi_IN-pratham-medium")
    assert spoken.voices()[0].name == "hi_IN-pratham-medium"
    assert spoken.pick("Tuesday").name == "hi_IN-pratham-medium"   # can't tell: theirs


def test_a_voice_reads_its_own_language_and_another_reads_the_rest(shelf):
    hindi = "कूड़ा मंगलवार को जाता है।"
    english = "The bins go out on Tuesday, and that is all."
    assert spoken.pick(hindi).name == "hi_IN-pratham-medium"
    assert spoken.pick(english, "hi_IN-pratham-medium").name == "en_US-lessac-medium"
    assert spoken.pick(hindi, "hi_IN-pratham-medium").name == "hi_IN-pratham-medium"
    assert spoken.pick(english, "no-such-voice").name == "en_US-lessac-medium"


def test_a_language_with_no_voice_here_is_not_read_in_the_wrong_one(shelf):
    with pytest.raises(spoken.Unspoken, match="in German and there's no German voice"):
        spoken.pick("Der Müll wird am Dienstag abgeholt, das ist gut.")
    a_voice(shelf, "de_DE-thorsten-medium", "de", "German")
    assert spoken.pick("Der Müll wird am Dienstag abgeholt, das ist gut.").family == "de"


def test_their_own_voice_is_chosen_by_number_or_name_and_kept_beside_when(shelf, tmp_path):
    choices = spoken.Choices(tmp_path)
    choices.set("mahen", "always")
    listed = spoken.voice_words(choices, "mahen", None, "/voice")
    assert "in en_US-lessac-medium (English)" in listed
    assert "2. hi_IN-pratham-medium (Hindi)" in listed and "/voice use N" in listed
    said = spoken.voice_words(choices, "mahen", None, "/voice use 2")
    assert said.startswith("From now on, I read to you in hi_IN-pratham-medium (Hindi)")
    assert choices.voice("mahen", None) == "hi_IN-pratham-medium"
    assert choices.choice("mahen", None) == "always"                 # when is kept
    assert "no voice 'klingon'" in spoken.voice_words(choices, "mahen", None,
                                                      "/voice use klingon")
    said = spoken.voice_words(choices, "mahen", None, "/voice use default",
                              voice="hi_IN-pratham-medium")       # the actors file's
    assert said.startswith("Back to the usual voice: in hi_IN-pratham-medium")
    assert choices.own_voice("mahen") is None


def test_a_choice_kept_the_first_way_still_reads(tmp_path):
    (tmp_path / spoken.FILE).write_text('{"mahen": "always"}')
    choices = spoken.Choices(tmp_path)
    assert choices.get("mahen") == "always"
    choices.set_voice("mahen", "hi_IN-pratham-medium")
    assert choices.get("mahen") == "always" and choices.own_voice("mahen")


def test_a_voice_in_the_actors_file_is_a_name(tmp_path):
    with pytest.raises(ConfigProblem, match="voice must be a voice's name"):
        ActorBook.from_dict({"actor": {"mahen": {"voice": "../../etc/passwd"}}})
    book = ActorBook.from_dict({"actor": {"mahen": {"voice": "hi_IN-pratham-medium"}}})
    assert book.get("mahen").voice == "hi_IN-pratham-medium"


def test_settings_list_the_voices_here_and_keep_a_persons(shelf, tmp_path):
    from dvara import settings

    path = tmp_path / "actors.toml"
    path.write_text("[actor.priya]\n")
    got = settings.set_person(path, "priya", {"voice": "hi_IN-pratham-medium"})
    assert got["voice"] == "hi_IN-pratham-medium"
    shown = settings.show(root=tmp_path / "agents", actors=path, policy=tmp_path / "p.toml")
    assert {"name": "hi_IN-pratham-medium", "language": "Hindi"} in shown["voices"]


def test_a_hindi_answer_on_telegram_is_read_in_the_hindi_voice(make_bot, make_service,  # noqa: F811
                                                               voiced):
    fake = Patient([message("bins?")])
    bot = make_bot(fake, service=make_service([says("कूड़ा मंगलवार को जाता है।")],
                                              actors=people("always")))
    asyncio.run(bot.run())
    assert len(fake.of("sendVoice")) == 1
    assert voiced.voices == ["hi_IN-pratham-medium"]


# ---- what's sent unasked --------------------------------------------------------

def test_a_notice_is_marked_to_be_read_only_for_someone_who_chose_always(make_service):
    seen = []

    async def sender(address, text, extra=None):
        seen.append(extra)

    for choice, wanted in (("always", True), (None, False), ("when-spoken", False)):
        service = make_service(actors=people(choice))
        service.notices.route("telegram", sender)
        asyncio.run(service.notices.send("mahen", [("telegram", str(KNOWN))], "Brief"))
        assert bool((seen[-1] or {}).get("speak")) is wanted, choice
    service.voices.set_voice("mahen", "hi_IN-pratham-medium")
    service.voices.set("mahen", "always")
    asyncio.run(service.notices.send("mahen", [("telegram", str(KNOWN))], "Brief"))
    assert seen[-1] == {"speak": True, "voice": "hi_IN-pratham-medium"}


def test_a_morning_brief_on_telegram_is_its_words_then_a_voice_note(make_bot, voiced):  # noqa: F811
    fake = FakeTelegram()
    bot = make_bot(fake)
    asyncio.run(bot._deliver_notice(str(KNOWN), "Good morning: 2 new mails.",
                                    extra={"speak": True, "voice": None}))
    order = [m for m, _ in fake.calls if m in ("sendMessage", "sendVoice")]
    assert order == ["sendMessage", "sendVoice"]
    asyncio.run(bot._deliver_notice(str(KNOWN), "No voice for this one."))
    assert len(fake.of("sendVoice")) == 1


def test_a_notice_on_the_page_plays_by_itself_for_always(make_service, voiced):
    service = make_service(actors=people("always"), web=True)
    asyncio.run(service.notices.send("mahen", [("web", "mahen")], "Good morning."))
    line = service.web.look("mahen")["lines"][-1]
    assert line["who"] == "notice" and line["speak"] is True

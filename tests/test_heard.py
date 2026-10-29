"""A voice note, heard before the turn (heard.py).

The bias is A GUESS PASSED OFF AS WHAT THEY SAID. What the agent reads
says it came from a voice note; the person is shown what was heard; a
note nothing can hear is said plainly, never made up; and the recording
is kept either way. The hearing model is stood in for: these tests need
no Ollama.
"""

from __future__ import annotations

import asyncio
import time

from dvara import heard
from tests.conftest import says
from tests.test_telegram import KNOWN, FakeTelegram, actors, make_bot, message  # noqa: F401


class Patient(FakeTelegram):
    """Polls that take a moment: hearing runs off the loop."""

    def _handle(self, request):
        if request.url.path.endswith("/getUpdates"):
            time.sleep(0.01)
        return super()._handle(request)


def test_the_agent_reads_that_it_was_a_voice_note():
    assert heard.said("call Ravi on Monday", "", "from-you/v.ogg") == (
        '(a voice note, heard as: "call Ravi on Monday")')
    cannot = heard.said(None, "", "from-you/v.ogg")
    assert "nothing here can listen" in cannot and "from-you/v.ogg" in cannot


def test_a_named_model_is_used_as_named(monkeypatch):
    monkeypatch.setenv(heard.ENV, "gemma4:e4b")
    assert heard.which_model("http://nowhere.invalid") == "gemma4:e4b"


def test_whisper_is_asked_first_and_ollama_is_the_fallback(monkeypatch, tmp_path):
    import httpx
    asked = []

    def post(url, **kw):
        asked.append(url)
        if "transcriptions" in url:
            if "down" in url:
                raise httpx.ConnectError("refused")
            assert kw["files"]["file"][2] == "audio/wav"
            return httpx.Response(200, json={"text": " call  Ravi on Monday "},
                                  request=httpx.Request("POST", url))
        return httpx.Response(200, json={"message": {"content": "from ollama"}},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(heard, "to_wav", lambda path: b"RIFF")
    monkeypatch.setenv(heard.ENV, "gemma4:e4b")
    monkeypatch.setenv(heard.WHISPER, "http://whisper.test:11435")
    assert heard._hear(tmp_path / "v.ogg") == "call Ravi on Monday"
    assert asked == ["http://whisper.test:11435/v1/audio/transcriptions"]
    monkeypatch.setenv(heard.WHISPER, "http://down.test:11435")
    assert heard._hear(tmp_path / "v.ogg") == "from ollama"


def test_without_ffmpeg_it_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(heard.shutil, "which", lambda name: None)
    words, why = asyncio.run(heard.hear(tmp_path / "v.ogg"))
    assert words is None and why  # a model or ffmpeg missing, in words


def test_on_telegram_a_voice_note_is_heard_shown_and_kept(make_bot, monkeypatch):  # noqa: F811
    monkeypatch.setattr(heard, "_hear", lambda path: "remind me to call Ravi on Monday")
    sent = message(None, voice={"file_id": "v1", "duration": 3, "file_size": 2000})
    fake = Patient([sent])
    bot = make_bot(fake, script=[says("I'll remind you on Monday.")])
    asyncio.run(bot.run())
    assert fake.texts() == ['I heard: "remind me to call Ravi on Monday"',
                            "I'll remind you on Monday."]
    run = bot.service.runs.recent(limit=1)[0]
    assert run.message == '(a voice note, heard as: "remind me to call Ravi on Monday")'
    assert list(bot.service.state.rglob("from-you/voice-*.ogg"))


def test_a_note_nothing_can_hear_is_said_plainly(make_bot, monkeypatch):  # noqa: F811
    def deaf(path):
        raise ValueError("no local model here can hear")
    monkeypatch.setattr(heard, "_hear", deaf)
    fake = Patient([message(None, voice={"file_id": "v1", "file_size": 2000})])
    bot = make_bot(fake, script=[says("I can't listen to voice notes here; please type it.")])
    asyncio.run(bot.run())
    assert not any(t.startswith("I heard") for t in fake.texts())
    assert "nothing here can listen" in bot.service.runs.recent(limit=1)[0].message

"""A voice note, turned into words before the turn: what was heard, shown.

A Telegram voice message got "I can read words, pictures and files, not
this". People on a phone talk; typing "remind me Monday at nine to call
Ravi" walking down the stairs is the thing they wanted not to do.

WORDS, BEFORE THE TURN. The agent's model mostly can't hear (most local
ones and every cloud one Yantra speaks to take text and pictures only),
and Yantra's loop has no audio block. So the note is heard first, by a
local model that CAN -- Ollama lists "audio" among its capabilities
(gemma4's small ones do) -- and the turn is the words, with a line that
says they came from a voice note: *"(a voice note, heard as: "…")"*. A
model told so knows a name may be misheard.

WHAT WAS HEARD IS SHOWN. The person sees *I heard: "…"* with the answer
(a line on the page, a message before the answer on Telegram), so a
mishearing is caught by the one person who knows what they said.

WHICH MODEL. A Whisper on this computer first, when ``$DVARA_WHISPER``
gives its address: any server on the OpenAI transcription road
(``faster-whisper-server``, whisper.cpp's), made to write speech down and
faster at it than a model asked to. Otherwise ``$DVARA_HEARING`` names an
Ollama model; otherwise the smallest local one Ollama lists with
"audio". A Whisper that doesn't answer falls back to Ollama's, and the
reason is kept for the line that says nothing could listen. None is
said plainly: the recording is
kept in their folder (``from-you/``), and the agent is told it can't
listen to it -- never a guess at what it said.

Ollama takes WAV, not Telegram's OGG/Opus, so ``ffmpeg`` converts it
(Sarathi's image carries it). Without ffmpeg, the same plain answer.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

#: The model to hear with, by name.
ENV = "DVARA_HEARING"
#: A Whisper server's address (the OpenAI transcription road), tried first.
WHISPER = "DVARA_WHISPER"
#: The Whisper model asked for; a server with one model ignores it.
WHISPER_MODEL = "DVARA_WHISPER_MODEL"
#: How long hearing one note may take, and the longest note heard.
WITHIN = 180.0
LONGEST_SECONDS = 300
ASK = ("Write down this voice note word for word, in the language it is spoken. "
       "Reply with the words only, nothing else.")
CANNOT = ("(a voice note: kept in your folder as {name}, but nothing here can "
          "listen to it -- say so, and ask them to type it)")


def ollama_url() -> str:
    return (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip(
        "/").removesuffix("/v1")


def _models_that_hear(base: str) -> list[str]:
    import httpx

    try:
        tags = httpx.get(f"{base}/api/tags", timeout=10).json().get("models") or []
    except (httpx.HTTPError, ValueError):
        return []
    hearing = []
    for row in sorted(tags, key=lambda m: m.get("size") or 0):
        try:
            shown = httpx.post(f"{base}/api/show", json={"model": row.get("name")},
                               timeout=10).json()
        except (httpx.HTTPError, ValueError):
            continue
        if "audio" in (shown.get("capabilities") or []):
            hearing.append(row["name"])
    return hearing


def which_model(base: str) -> str | None:
    named = os.environ.get(ENV, "").strip()
    if named:
        return named
    found = _models_that_hear(base)
    return found[0] if found else None


def to_wav(path: Path) -> bytes:
    """The note as 16 kHz mono WAV; ValueError in words when it can't be."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ValueError("ffmpeg isn't installed here")
    with tempfile.TemporaryDirectory(prefix="dvara-heard-") as tmp:
        out = Path(tmp) / "note.wav"
        done = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(path),
                               "-t", str(LONGEST_SECONDS), "-ac", "1", "-ar", "16000",
                               str(out)], capture_output=True, text=True, timeout=60)
        if done.returncode != 0 or not out.is_file():
            raise ValueError(f"the recording couldn't be read: "
                             f"{(done.stderr or '').strip()[-200:]}")
        return out.read_bytes()


def _whisper(url: str, wav: bytes) -> str:
    import httpx

    model = os.environ.get(WHISPER_MODEL, "").strip() or "Systran/faster-whisper-small"
    try:
        answer = httpx.post(f"{url.rstrip('/')}/v1/audio/transcriptions", timeout=WITHIN,
                            data={"model": model},
                            files={"file": ("note.wav", wav, "audio/wav")})
        answer.raise_for_status()
        words = str(answer.json().get("text") or "")
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError(f"Whisper at {url} didn't answer: {exc}") from None
    words = " ".join(words.split()).strip()
    if not words:
        raise ValueError("Whisper heard nothing in it")
    return words


def _hear(path: Path) -> str:
    whisper = os.environ.get(WHISPER, "").strip()
    if whisper:
        try:
            return _whisper(whisper, to_wav(path))
        except ValueError as exc:
            if "heard nothing" in str(exc):
                raise
            missed = str(exc)
        try:
            return _hear_ollama(path)
        except ValueError as exc:
            raise ValueError(f"{missed}; and {exc}") from None
    return _hear_ollama(path)


def _hear_ollama(path: Path) -> str:
    import httpx

    base = ollama_url()
    model = which_model(base)
    if model is None:
        raise ValueError("no local model here can hear (Ollama lists none with "
                         "\"audio\"; set DVARA_HEARING to one)")
    wav = base64.b64encode(to_wav(path)).decode()
    try:
        answer = httpx.post(f"{base}/api/chat", timeout=WITHIN, json={
            "model": model, "stream": False, "think": False,
            "messages": [{"role": "user", "content": ASK, "images": [wav]}]})
        words = (answer.json().get("message") or {}).get("content", "")
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError(f"{model} didn't answer: {exc}") from None
    words = " ".join(words.split()).strip().strip('"')
    if not words:
        raise ValueError(f"{model} heard nothing in it")
    return words


async def hear(path: Path) -> tuple[str | None, str]:
    """(the words, or None; why not, when None)."""
    try:
        return await asyncio.to_thread(_hear, path), ""
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)


def said(heard: str | None, text: str, name: str) -> str:
    """The message the agent reads, for a note heard (or not)."""
    line = (f'(a voice note, heard as: "{heard}")' if heard is not None
            else CANNOT.format(name=name))
    return f"{text.strip()}\n\n{line}" if text.strip() else line

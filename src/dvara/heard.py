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

WHICH MODEL. ``$DVARA_HEARING`` names one; otherwise the smallest local
model Ollama lists with "audio". None is said plainly: the recording is
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


def _hear(path: Path) -> str:
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

"""An answer read aloud: a voice note back, made on this machine.

Voice notes came in (heard.py) and words went back. A person who spoke
because their hands were full -- cooking, driving, walking down the
stairs -- then had to stop and read. The answer can come back the way
the question went.

MADE HERE, BY A SMALL VOICE MODEL. Piper reads text aloud on a CPU in
about a second a sentence, from one file of around 60 MB (a "voice":
``en_US-lessac-medium.onnx`` and its ``.onnx.json``). Nothing is sent
anywhere to be spoken, which is the same promise heard.py makes for
hearing: a reader on Ollama with no cloud key gets both directions.
``$DVARA_VOICE`` names a voice file (or ``off``); otherwise the first
one found in ``$PIPER_VOICES``, ``~/.local/share/piper/voices`` or
``/usr/share/piper/voices``. No Piper, or no voice: the words go, as
they always did, and the owner gets one line saying why.

THE WORDS FIRST, THE VOICE AFTER. A voice note takes a second or ten to
make, and an answer read is faster than an answer heard. So the words
are sent as soon as they exist, and the voice note follows them. It is
never instead of them: a misheard name, a link, a number to copy are
all in the message.

WHAT IS READ IS NOT EVERYTHING WRITTEN. A table, a block of code, an
address are things nobody wants read to them. ``aloud`` keeps the
sentences: code becomes "(some code, in the message)", a link is its
words, a bare address is "a link", list marks and emphasis go, and a
long answer stops at a sentence near ``LONGEST`` characters with "The
rest is in the message." A turn that stopped for a reason (a refusal, a
held step) is still read: those are sentences too.

EACH PERSON CHOOSES. Three choices, as the person would say them:

    off           never
    when-spoken   when I sent a voice note (the default)
    always        every answer

The owner sets one for each person in the actors file (``speak =``);
the person can change their own with ``/voice off|when-spoken|always``,
kept in ``<state>/voice.json``, which wins over the file. When-spoken is
the default because it asks for nothing: a person who never speaks to
it never hears it, and one who does is answered in kind.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: A voice file to speak with, or ``off``.
ENV = "DVARA_VOICE"
#: Folders a voice file is looked for in, after ``$PIPER_VOICES``.
VOICES = ("~/.local/share/piper/voices", "/usr/share/piper/voices")
#: Each person's choice, as they'd say it.
CHOICES = ("off", "when-spoken", "always")
DEFAULT = "when-spoken"
#: The person's own choice, kept by the service.
FILE = "voice.json"
#: About how many characters are read before "the rest is in the message"
#: -- a minute and a half or so, at Piper's pace.
LONGEST = 1200
REST = "The rest is in the message."
#: How long making one voice note may take.
WITHIN = 120.0
WORD = "/voice"


class Unspoken(ValueError):
    """Why an answer couldn't be read aloud, in words for the owner."""


# ---- which voice, and whether there is one ---------------------------------------

def voice_file() -> Path | None:
    """The voice to speak with; None when there is none (or it's ``off``)."""
    named = os.environ.get(ENV, "").strip()
    if named.lower() == "off":
        return None
    if named:
        path = Path(named).expanduser()
        return path if path.is_file() else None
    folders = [os.environ.get("PIPER_VOICES", ""), *VOICES]
    for folder in (Path(f).expanduser() for f in folders if f):
        if folder.is_dir():
            for found in sorted(folder.glob("*.onnx")):
                if found.with_name(found.name + ".json").is_file():
                    return found
    return None


def piper() -> list[str] | None:
    """How to run Piper here: its command, or this Python's module."""
    found = shutil.which("piper")
    if found:
        return [found]
    try:
        import piper as _  # noqa: F401 -- only whether it's there
    except ImportError:
        return None
    return [sys.executable, "-m", "piper"]


def can_speak() -> str | None:
    """None when an answer can be read aloud here; otherwise why not."""
    if os.environ.get(ENV, "").strip().lower() == "off":
        return f"{ENV} is off"
    if piper() is None:
        return "Piper isn't installed here (pip install piper-tts)"
    if voice_file() is None:
        named = os.environ.get(ENV, "").strip()
        return (f"{ENV} names {named}, which isn't a file" if named else
                "no Piper voice was found (put one in ~/.local/share/piper/voices, "
                f"or set {ENV} to its .onnx file)")
    return None


# ---- what is read --------------------------------------------------------------

_FENCE = re.compile(r"```.*?(```|\Z)", re.S)
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BARE = re.compile(r"https?://\S+|www\.\S+")
_TABLE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_RULE = re.compile(r"^\s*([-*_]\s*){3,}$", re.M)
_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_MARK = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+", re.M)
_QUOTE = re.compile(r"^\s*>\s?", re.M)
_EMPH = re.compile(r"(\*\*|__|\*|_|`|~~)(?=\S)(.+?)(?<=\S)\1")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def aloud(text: str, *, longest: int = LONGEST) -> str:
    """The words of an answer worth reading out, and no more than that."""
    text = _FENCE.sub(" (some code, in the message). ", text or "")
    text = _TABLE.sub(" (a table, in the message). ", text)
    text = _LINK.sub(r"\1", text)
    text = _BARE.sub("a link", text)
    text = _RULE.sub(" ", text)
    for pattern in (_HEAD, _MARK, _QUOTE):
        text = pattern.sub("", text)
    for _ in range(2):                      # **_both_** marks at once
        text = _EMPH.sub(r"\2", text)
    text = text.replace("`", "")
    # A line that ends without a stop still ends a thought when read.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = " ".join(ln if ln[-1] in ".!?:;," else ln + "." for ln in lines)
    text = re.sub(r"(\(a table, in the message\)\.\s*)+", "(a table, in the message). ", text)
    text = " ".join(text.split())
    if len(text) <= longest:
        return text
    kept = ""
    for sentence in _SENTENCE.split(text):
        if kept and len(kept) + len(sentence) + 1 > longest:
            break
        kept = f"{kept} {sentence}".strip()
    if len(kept) > longest:                 # one sentence longer than all of it
        kept = kept[:longest].rsplit(" ", 1)[0] + "…"
    return f"{kept} {REST}"


# ---- making it --------------------------------------------------------------

def make(text: str, out: Path, *, telegram: bool = False) -> Path:
    """``text`` read aloud into ``out``: WAV, or (``telegram``) OGG Opus,
    the one kind Telegram shows as a voice note. Unspoken in words when
    it can't be."""
    why = can_speak()
    if why is not None:
        raise Unspoken(why)
    words = aloud(text)
    if not words:
        raise Unspoken("there were no words in it to read")
    command, voice = piper(), voice_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dvara-spoken-") as tmp:
        wav = Path(tmp) / "answer.wav"
        try:
            done = subprocess.run([*command, "-m", str(voice), "-f", str(wav)],
                                  input=words, capture_output=True, text=True,
                                  timeout=WITHIN)
        except subprocess.TimeoutExpired:
            raise Unspoken(f"Piper took longer than {WITHIN:.0f}s") from None
        if done.returncode != 0 or not wav.is_file() or wav.stat().st_size == 0:
            raise Unspoken(f"Piper didn't read it: {(done.stderr or '').strip()[-200:]}")
        if not telegram:
            shutil.copyfile(wav, out)
            return out
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise Unspoken("ffmpeg isn't installed here (Telegram wants OGG Opus)")
        done = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav),
                               "-c:a", "libopus", "-b:a", "32k", "-ac", "1", str(out)],
                              capture_output=True, text=True, timeout=WITHIN)
        if done.returncode != 0 or not out.is_file():
            raise Unspoken(f"ffmpeg couldn't make the voice note: "
                           f"{(done.stderr or '').strip()[-200:]}")
    return out


async def speak(text: str, out: Path, *, telegram: bool = False) -> Path:
    return await asyncio.to_thread(make, text, out, telegram=telegram)


# ---- who wants it -------------------------------------------------------------

def wanted(choice: str | None, *, spoke: bool) -> bool:
    """Whether this answer is read aloud, by the person's choice and
    whether they sent a voice note with the message."""
    choice = choice or DEFAULT
    return choice == "always" or (choice == "when-spoken" and spoke)


class Choices:
    """Each person's own choice, where they made one with ``/voice``."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}           # a broken file costs the choice, never the chat
        return data if isinstance(data, dict) else {}

    def get(self, actor: str) -> str | None:
        value = self._read().get(actor)
        return value if value in CHOICES else None

    def set(self, actor: str, choice: str | None) -> None:
        data = self._read()
        if choice is None:
            data.pop(actor, None)
        else:
            data[actor] = choice
        self.path.parent.mkdir(parents=True, exist_ok=True)
        spare = self.path.with_suffix(".tmp")
        fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=1)
        os.replace(spare, self.path)

    def choice(self, actor: str, default: str | None) -> str:
        """What holds for them: their own, else the file's, else DEFAULT."""
        return self.get(actor) or default or DEFAULT


# ---- /voice -------------------------------------------------------------------

_SAID = {"off": "off", "no": "off", "never": "off", "none": "off",
         "when-spoken": "when-spoken", "when": "when-spoken", "spoken": "when-spoken",
         "when-i-speak": "when-spoken", "always": "always", "on": "always",
         "yes": "always", "default": None, "reset": None}
_TOLD = {"off": "I don't read answers aloud",
         "when-spoken": "I read an answer aloud when you send me a voice note",
         "always": "I read every answer aloud"}


def is_word(text: str) -> bool:
    return text.strip().lower().split()[:1] == [WORD]


def voice_words(choices: Choices, actor: str, default: str | None, text: str) -> str:
    """``/voice`` says what holds and whether it can; ``/voice X`` changes it."""
    rest = "-".join(text.strip().lower().split()[1:])
    why = can_speak()
    cannot = (f" (Answers can't be read aloud here just now: {why}.)"
              if why is not None else "")
    if not rest:
        now = choices.choice(actor, default)
        return (f"{_TOLD[now]}.{cannot} Send /voice off, /voice when-spoken "
                f"or /voice always to change it.")
    if rest not in _SAID:
        return "Send /voice off, /voice when-spoken or /voice always."
    picked = _SAID[rest]
    choices.set(actor, picked)
    now = choices.choice(actor, default)
    lead = "Back to what's set for you: " if picked is None else "From now on, "
    return f"{lead}{_TOLD[now]}.{cannot}"

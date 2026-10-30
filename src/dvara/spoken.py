"""An answer read aloud: a voice note back, made on this machine.

Voice notes came in (heard.py) and words went back. A person who spoke
because their hands were full -- cooking, driving, walking down the
stairs -- then had to stop and read. The answer can come back the way
the question went.

MADE HERE, BY A SMALL VOICE MODEL. Piper reads text aloud on a CPU in
about a second a sentence, from one file of around 60 MB (a "voice":
``en_US-lessac-medium.onnx`` and its ``.onnx.json``, which says the
voice's language). Nothing is sent anywhere to be spoken, which is the
same promise heard.py makes for hearing: a reader on Ollama with no
cloud key gets both directions. The voices are every one found in
``$PIPER_VOICES``, ``~/.local/share/piper/voices`` and
``/usr/share/piper/voices``; ``$DVARA_VOICE`` names the house's own (a
name or a file), or is ``off``. No Piper, or no voice: the words go, as
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
rest is in the message."

EACH PERSON CHOOSES WHEN. Three choices, as the person would say them:

    off           never
    when-spoken   when I sent a voice note (the default)
    always        every answer, and what's sent to me unasked

The owner sets one for each person in the actors file (``speak =``);
the person can change their own with ``/voice off|when-spoken|always``,
kept in ``<state>/voice.json``, which wins over the file. When-spoken is
the default because it asks for nothing: a person who never speaks to
it never hears it, and one who does is answered in kind. "Always"
covers notices too -- a schedule's answer, the morning brief -- because
someone who chose to listen rather than read chose it for those as well.

AND WHOSE VOICE. A person may have a voice of their own (``voice =`` in
the actors file, ``/voice use NAME`` in the chat); otherwise the house's.

THE ANSWER'S LANGUAGE PICKS THE VOICE WHEN IT HAS TO. An English voice
reading Hindi reads nothing a person can follow, so the answer's
language is looked at first: by its script (Devanagari, Arabic,
Cyrillic, ...), and for the Latin alphabet by its commonest small words
(the, und, le, el, ...), Hindi typed in Latin letters among them (hai,
kya, nahi). Their own voice reads it when it speaks that
language, or when the language can't be told; otherwise the first voice
here that does. With none here for that language, nothing is read --
never a voice that can't say the words -- and the owner is told which
voice to add.

HINDI IN LATIN LETTERS IS WRITTEN IN DEVANAGARI FIRST. Piper's Hindi
voice reads only Devanagari, so "kal kya hai" goes to it as "कल क्या है"
(romanised.py); read as typed, by either voice, it was heard back as
nonsense.
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
from dataclasses import dataclass
from pathlib import Path

from dvara import romanised

#: The house's voice, by name or file, or ``off``.
ENV = "DVARA_VOICE"
#: Folders voices are looked for in, after ``$PIPER_VOICES``.
VOICES = ("~/.local/share/piper/voices", "/usr/share/piper/voices")
#: Where a voice is fetched from, for the words that say how to add one.
CATALOG = "https://huggingface.co/rhasspy/piper-voices"
#: Each person's choice, as they'd say it.
CHOICES = ("off", "when-spoken", "always")
DEFAULT = "when-spoken"
#: The person's own choices, kept by the service.
FILE = "voice.json"
#: About how many characters are read before "the rest is in the message"
#: -- a minute and a half or so, at Piper's pace.
LONGEST = 1200
REST = "The rest is in the message."
#: How long making one voice note may take.
WITHIN = 120.0
WORD = "/voice"
#: A voice's name: what Piper's catalogue calls it (hi_IN-pratham-medium).
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class Unspoken(ValueError):
    """Why an answer couldn't be read aloud, in words for the owner."""


# ---- the voices here -------------------------------------------------------------

@dataclass(frozen=True)
class Voice:
    name: str           # hi_IN-pratham-medium
    path: Path          # its .onnx
    family: str         # hi
    language: str       # Hindi

    def said(self) -> str:
        """How a person sees it: ``hi_IN-pratham-medium (Hindi)``."""
        return f"{self.name} ({self.language})"


def _voice(path: Path) -> Voice | None:
    card = path.with_name(path.name + ".json")
    if not card.is_file():
        return None
    try:
        lang = json.loads(card.read_text()).get("language") or {}
    except (OSError, ValueError, AttributeError):
        lang = {}
    name = path.name.removesuffix(".onnx")
    family = (lang.get("family") or name.split("_")[0].split("-")[0]).lower()
    return Voice(name=name, path=path, family=family,
                 language=lang.get("name_english") or LANGUAGES.get(family, family))


def voices() -> list[Voice]:
    """Every voice here, the house's first; none when ``$DVARA_VOICE`` is off."""
    named = os.environ.get(ENV, "").strip()
    if named.lower() == "off":
        return []
    found: dict[str, Voice] = {}
    if named and Path(named).expanduser().is_file():
        voice = _voice(Path(named).expanduser())
        if voice is not None:
            found[voice.name] = voice
    folders = [os.environ.get("PIPER_VOICES", ""), *VOICES]
    for folder in (Path(f).expanduser() for f in folders if f):
        if folder.is_dir():
            for path in sorted(folder.glob("*.onnx")):
                voice = _voice(path)
                if voice is not None:
                    found.setdefault(voice.name, voice)
    every = list(found.values())
    house = named and next((v for v in every if named in (v.name, str(v.path))), None)
    if not house:              # English first, as a house with no say needs one
        house = next((v for v in every if v.family == "en"), every[0] if every else None)
    return [house, *[v for v in every if v is not house]] if house else []


def voice_file() -> Path | None:
    """The house's voice file; None when there is none (or it's ``off``)."""
    found = voices()
    return found[0].path if found else None


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
    if not voices():
        return ("no Piper voice was found (put one in ~/.local/share/piper/voices, "
                f"from {CATALOG})")
    return None


# ---- which language, and so which voice -------------------------------------------

#: A family's name, for a voice whose card doesn't say and for the words.
LANGUAGES = {"ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "de": "German",
             "el": "Greek", "en": "English", "es": "Spanish", "fa": "Persian",
             "fr": "French", "he": "Hebrew", "hi": "Hindi", "hy": "Armenian",
             "it": "Italian", "ja": "Japanese", "ka": "Georgian", "kk": "Kazakh",
             "ko": "Korean", "ml": "Malayalam", "mr": "Marathi", "ne": "Nepali",
             "nl": "Dutch", "pt": "Portuguese", "ru": "Russian", "sr": "Serbian",
             "te": "Telugu", "th": "Thai", "uk": "Ukrainian", "ur": "Urdu",
             "zh": "Chinese"}

#: Scripts by their letters' range, and the languages Piper reads in each
#: (in the order to try them). Latin is left out: its words decide.
_SCRIPTS = (
    ((0x0900, 0x097F), ("hi", "mr", "ne")),          # Devanagari
    ((0x0980, 0x09FF), ("bn",)),
    ((0x0C00, 0x0C7F), ("te",)),
    ((0x0D00, 0x0D7F), ("ml",)),
    ((0x0600, 0x06FF), ("ar", "fa", "ur")),
    ((0x0400, 0x04FF), ("ru", "uk", "bg", "sr", "kk")),
    ((0x0370, 0x03FF), ("el",)),
    ((0x0590, 0x05FF), ("he",)),
    ((0x10A0, 0x10FF), ("ka",)),
    ((0x0530, 0x058F), ("hy",)),
    ((0x0E00, 0x0E7F), ("th",)),
    ((0x3040, 0x30FF), ("ja",)),                     # kana before Han
    ((0xAC00, 0xD7AF), ("ko",)),
    ((0x4E00, 0x9FFF), ("zh", "ja")),
)

#: The commonest small words of the Latin-alphabet languages Piper reads.
_WORDS = {
    "en": "the and is you to of it that in for your are with on this have be not was "
          "will can what",
    "de": "der die das und ist nicht ich sie mit ein eine zu den auf für es du wir "
          "auch sind",
    "fr": "le la les et est vous des un une pas que pour dans je il nous sur au "
          "avec sont",
    "es": "el la los las y es que en un una por para no con su se lo del está",
    "it": "il la che di è un una per non con sono del della gli lo si ho",
    "pt": "o a os as e é que de um uma para não com em do da você está",
    "nl": "de het een en is van niet ik je dat op met voor zijn er ook",
    "hi": romanised.VOTES,
}
_VOTES = {lang: set(words.split()) for lang, words in _WORDS.items()}


def languages_of(text: str) -> tuple[str, ...] | None:
    """The languages ``text`` may be in, likeliest first; None when it
    can't be told (Latin letters with no clear words, or no letters)."""
    counts: dict[int, int] = {}
    latin = 0
    for ch in text:
        if not ch.isalpha():
            continue
        code = ord(ch)
        if code < 0x0250:
            latin += 1
            continue
        for n, ((low, high), _) in enumerate(_SCRIPTS):
            if low <= code <= high:
                counts[n] = counts.get(n, 0) + 1
                break
    top = max(counts, key=counts.__getitem__) if counts else None
    if top is not None and counts[top] > latin:
        return _SCRIPTS[top][1]
    words = re.findall(r"[^\W\d_]+", text.lower())
    tally = sorted(((sum(w in _VOTES[lang] for w in words), lang) for lang in _VOTES),
                   reverse=True)
    (best, lang), (second, _) = tally[0], tally[1]
    if best >= 2 and best >= 1.5 * second:
        return (lang,)
    return None


def _latin(text: str) -> bool:
    """Mostly Latin letters: Hindi typed as it is on a phone."""
    letters = [ch for ch in text if ch.isalpha()]
    return sum(ord(ch) < 0x0250 for ch in letters) * 2 > len(letters)


def pick(text: str, preferred: str | None = None) -> Voice:
    """The voice to read ``text`` with: theirs (or the house's) when it
    speaks the answer's language or the language can't be told, else one
    here that does. Unspoken when there's none for it."""
    every = voices()
    if not every:
        raise Unspoken(can_speak() or "no voice here")
    own = next((v for v in every if v.name == preferred), every[0]) if preferred else every[0]
    langs = languages_of(text)
    if langs is None or own.family in langs:
        return own
    for lang in langs:
        for voice in every:
            if voice.family == lang:
                return voice
    name = LANGUAGES.get(langs[0], langs[0])
    raise Unspoken(f"the answer is in {name} and there's no {name} voice here "
                   f"(add one from {CATALOG})")


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
#: Sentence ends: . ! ? and the danda Hindi, Marathi and Nepali end with.
_ENDS = ".!?।॥"
_SENTENCE = re.compile(r"(?<=[.!?।॥])\s+")


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
    text = " ".join(ln if ln[-1] in _ENDS + ":;," else ln + "." for ln in lines)
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

def make(text: str, out: Path, *, telegram: bool = False,
         voice: Voice | str | None = None) -> Path:
    """``text`` read aloud into ``out``: WAV, or (``telegram``) OGG Opus,
    the one kind Telegram shows as a voice note. ``voice`` is the one to
    use, or the person's choice by name (``pick`` decides). Unspoken in
    words when it can't be."""
    why = can_speak()
    if why is not None:
        raise Unspoken(why)
    words = aloud(text)
    if not words:
        raise Unspoken("there were no words in it to read")
    if not isinstance(voice, Voice):
        voice = pick(words, voice)
    if voice.family == "hi" and _latin(words):
        words = romanised.devanagari(words)
    command = piper()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dvara-spoken-") as tmp:
        wav = Path(tmp) / "answer.wav"
        try:
            done = subprocess.run([*command, "-m", str(voice.path), "-f", str(wav)],
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


async def speak(text: str, out: Path, *, telegram: bool = False,
                voice: str | None = None) -> Path:
    return await asyncio.to_thread(make, text, out, telegram=telegram, voice=voice)


# ---- who wants it, in whose voice ------------------------------------------------

def wanted(choice: str | None, *, spoke: bool) -> bool:
    """Whether this answer is read aloud, by the person's choice and
    whether they sent a voice note with the message (never, for a notice)."""
    choice = choice or DEFAULT
    return choice == "always" or (choice == "when-spoken" and spoke)


class Choices:
    """Each person's own choices, where they made one with ``/voice``:
    ``{"mahen": {"speak": "always", "voice": "hi_IN-pratham-medium"}}``."""

    def __init__(self, state: Path) -> None:
        self.path = Path(state) / FILE

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}           # a broken file costs the choice, never the chat
        return data if isinstance(data, dict) else {}

    def _theirs(self, actor: str) -> dict:
        mine = self._read().get(actor)
        # a bare word is how the first of these files kept "when"
        if isinstance(mine, str):
            return {"speak": mine}
        return dict(mine) if isinstance(mine, dict) else {}

    def _write(self, actor: str, key: str, value: str | None) -> None:
        data = self._read()
        mine = self._theirs(actor)
        if value is None:
            mine.pop(key, None)
        else:
            mine[key] = value
        if mine:
            data[actor] = mine
        else:
            data.pop(actor, None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        spare = self.path.with_suffix(".tmp")
        fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=1)
        os.replace(spare, self.path)

    def get(self, actor: str) -> str | None:
        value = self._theirs(actor).get("speak")
        return value if value in CHOICES else None

    def set(self, actor: str, choice: str | None) -> None:
        self._write(actor, "speak", choice)

    def choice(self, actor: str, default: str | None) -> str:
        """When holds for them: their own, else the file's, else DEFAULT."""
        return self.get(actor) or default or DEFAULT

    def own_voice(self, actor: str) -> str | None:
        value = self._theirs(actor).get("voice")
        return value if isinstance(value, str) and NAME.match(value) else None

    def set_voice(self, actor: str, name: str | None) -> None:
        self._write(actor, "voice", name)

    def voice(self, actor: str, default: str | None) -> str | None:
        """Whose voice: their own, else the file's, else None (the house's)."""
        return self.own_voice(actor) or default


# ---- /voice -------------------------------------------------------------------

_SAID = {"off": "off", "no": "off", "never": "off", "none": "off",
         "when-spoken": "when-spoken", "when": "when-spoken", "spoken": "when-spoken",
         "when-i-speak": "when-spoken", "always": "always", "on": "always",
         "yes": "always", "default": None, "reset": None}
_TOLD = {"off": "I don't read answers aloud",
         "when-spoken": "I read an answer aloud when you send me a voice note",
         "always": "I read every answer aloud, and what I send you unasked"}
_HOW = ("Send /voice off, /voice when-spoken or /voice always to change when, "
        "and /voice use N for another voice.")


def is_word(text: str) -> bool:
    return text.strip().lower().split()[:1] == [WORD]


def _whose(choices: Choices, actor: str, voice: str | None, every: list[Voice]) -> str:
    name = choices.voice(actor, voice)
    mine = next((v for v in every if v.name == name), None)
    if mine is not None:
        return f"in {mine.said()}"
    house = f"in {every[0].said()}" if every else "in the house's voice"
    return f"{house} ({name} isn't here)" if name else house


def _listing(every: list[Voice]) -> str:
    if not every:
        return ""
    return " Voices here: " + "; ".join(f"{n}. {v.said()}"
                                       for n, v in enumerate(every, start=1)) + "."


def voice_words(choices: Choices, actor: str, default: str | None, text: str,
                *, voice: str | None = None) -> str:
    """``/voice`` says what holds; ``/voice X`` changes when; ``/voice use
    NAME|N`` changes whose (``/voice use default`` goes back). ``default``
    and ``voice`` are what the actors file says for them."""
    words = text.strip().split()[1:]
    every = voices()
    why = can_speak()
    cannot = (f" (Answers can't be read aloud here just now: {why}.)"
              if why is not None else "")
    if words[:1] and words[0].lower() == "use":
        asked = " ".join(words[1:]).strip()
        if asked.lower() in ("", "default", "reset", "house"):
            choices.set_voice(actor, None)
            return f"Back to the usual voice: {_whose(choices, actor, voice, every)}.{cannot}"
        found = (every[int(asked) - 1] if asked.isdigit() and 0 < int(asked) <= len(every)
                 else next((v for v in every if v.name.lower() == asked.lower()), None))
        if found is None:
            return f"There's no voice {asked!r} here.{_listing(every)} Send /voice use N.{cannot}"
        choices.set_voice(actor, found.name)
        return (f"From now on, I read to you in {found.said()}. An answer in another "
                f"language is read in a voice for it, when there's one here.{cannot}")
    rest = "-".join(w.lower() for w in words)
    if not rest:
        now = choices.choice(actor, default)
        return (f"{_TOLD[now]}, {_whose(choices, actor, voice, every)}.{cannot}"
                f"{_listing(every)} {_HOW}")
    if rest not in _SAID:
        return _HOW
    picked = _SAID[rest]
    choices.set(actor, picked)
    now = choices.choice(actor, default)
    lead = "Back to what's set for you: " if picked is None else "From now on, "
    return f"{lead}{_TOLD[now]}.{cannot}"

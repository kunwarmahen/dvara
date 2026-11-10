"""A person's routines, from any channel: ``/routines``.

Vidhi keeps routines a person drew once (a morning brief, a price check
that asks before it plans). From a chat they are a word away, and none
of these is a turn -- no model, no allowance spent:

    /routines                 their routines, and any question waiting
    /routines 2               how the second one's last runs went
    /routines run 2           start it now
    /routines yes K7Q2MX      answer a run's question (the buttons send this)
    /routines no K7Q2MX
    /routines pick K7Q2MX 2   one of its choices (by number, or its words)
    /routines say K7Q2MX ...  a question that takes a few typed words
    /routines K7Q2MX ...      the same, by the question's code alone
    /routines stop RUN        stop a run that is going or waiting

A QUESTION IS ANSWERED FROM ANY CHANNEL. A run that stopped to ask puts
its question on the person's channels with buttons -- Yes and No, or
its two or three choices -- which send ``/routines yes CODE`` (``pick
CODE N``) as if typed, by the person who pressed. One that takes words
has no buttons: the words are typed after ``/routines say CODE``. On a
phone's ntfy notification the same buttons come marked, never with a
token (push.py). Vidhi takes an answer only for its own person's question
(``vidhi answer --as``), and only once: a second press says what the
first one decided.

THE CODE ALONE IS ENOUGH. ``/routines K7Q2MX blue door`` -- the code
with the verb left out -- answers that question the way its kind takes:
yes or no, a choice, or the words. Before, it was read as a routine's
name, and the person who had just been asked was told they had no such
routine.

THE OWNER'S COMPUTER ROUTINES ARE THE OWNER'S. A routine installed at
the computer is filed under ``local``, and its questions come to the
owner's chat; so for the owner, ``/routines`` lists both, and an answer
that isn't theirs by name is tried as ``local``.

DRAWING ONE IS VIDHI'S PAGE. Nothing here writes a step: what a routine
does is drawn by a person, on Vidhi's own page.
"""

from __future__ import annotations

import re
import shutil

from dvara.seen import ask_json

ROUTINES = "/routines"
LOCAL = "local"
#: Runs shown for one routine.
RUNS_SHOWN = 3
HOW = ("/routines N for how one went, /routines run N to start it. Ask me to set up one "
       "of the ready ones; a new kind is drawn on Vidhi's page.")


#: A run's question code (Vidhi's: six letters and digits).
CODE = re.compile(r"[A-Za-z0-9]{6}")
#: What a yes-or-no question takes, as people type it.
YES_NO = {"yes": "yes", "y": "yes", "yeah": "yes", "yep": "yes", "ok": "yes",
          "okay": "yes", "no": "no", "n": "no", "nope": "no"}
#: A question's own answer words, in the message that asked it.
ASKED = re.compile(r"/routines (yes|pick|say) ([A-Za-z0-9]{6})\b")


def replied_answer(asked: str, text: str) -> str | None:
    """A reply to a run's question, as the words that answer it.

    A REPLY IS AN ANSWER. Pressing reply on the question and typing
    "blue door" (or "yes", or "Cool") answers it: the question's code is
    in the message replied to, in the words it gave to answer it. A
    yes-or-no question takes yes or no only; anything else typed back is
    left as a message to the agent. ``None`` when it isn't an answer."""
    found = ASKED.search(asked or "")
    said = " ".join((text or "").split())
    if not found or not said or said.startswith("/"):
        return None
    verb, code = found.groups()
    if verb == "yes":
        word = YES_NO.get(said.lower().strip(" .!"))
        return f"{ROUTINES} {word} {code}" if word else None
    return f"{ROUTINES} {verb} {code} {said}"


#: What a reply looks like on each channel where one answers.
_REPLY = {"telegram": "Or reply to this message with your answer.",
          "page": "Or press Reply under this and type your answer."}
_REPLY_YES = {"telegram": "Or reply to this message with yes or no.",
              "page": "Or press Reply under this and type yes or no."}


def reply_hint(text: str, channel: str) -> str:
    """The line saying a reply answers, for a routine's question on a
    channel where one does (Telegram, the home page). Empty for any other
    message, and for a channel with no reply (an ntfy notification: there
    the buttons answer, and words go to a chat)."""
    found = ASKED.search(text or "")
    if not found or channel not in _REPLY or (text or "").rstrip().endswith(
            (_REPLY[channel], _REPLY_YES[channel])):
        return ""
    said = _REPLY_YES if found.group(1) == "yes" else _REPLY
    return "\n" + said[channel]


def word_of(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].lower().split("@")[0] == ROUTINES


class Routines:
    def __init__(self, vidhi: str | None = None) -> None:
        self.vidhi = vidhi

    def program(self) -> str | None:
        return self.vidhi or shutil.which("vidhi")

    async def answer(self, actor: str, text: str, *, via: str = "chat",
                     is_owner: bool = False) -> str:
        program = self.program()
        if not program:
            return "Routines aren't set up on this computer (Vidhi isn't here)."
        words = text.strip().split()[1:]
        people = [actor] + ([LOCAL] if is_owner and actor != LOCAL else [])
        verb = words[0].lower() if words else ""
        if verb in ("yes", "no") and len(words) == 2:
            return await self._answer(program, people, words[1], verb, via)
        if verb in ("pick", "say") and len(words) >= 3:
            return await self._answer(program, people, words[1], " ".join(words[2:]), via)
        if verb in ("pick", "say"):
            return (f"/routines {verb} CODE "
                    + ("N (the number of the choice)" if verb == "pick" else "your words"))
        if verb == "run" and len(words) >= 2:
            return await self._start(program, people, words[1], via)
        if verb == "stop" and len(words) == 2:
            return await self._stop(program, people, words[1])
        if words and CODE.fullmatch(words[0]) and not words[0].isdigit():
            question = await self._asked(program, people, words[0])
            if question is not None:
                return await self._by_code(program, people, question, words[1:], via)
        listing = await self._list(program, people)
        if isinstance(listing, str):
            return listing
        if words:
            return await self._runs(program, listing, words[0])
        return await self._overview(program, people, listing)

    # -- seeing ---------------------------------------------------------------------

    async def _list(self, program: str, people: list[str]) -> list[dict] | str:
        found: list[dict] = []
        for person in people:
            cards, trouble = await ask_json([program, "list", f"--as={person}", "--json"])
            if trouble:
                return trouble
            found += [c for c in cards or [] if isinstance(c, dict)]
        return found

    async def _overview(self, program: str, people: list[str], cards: list[dict]) -> str:
        out: list[str] = []
        asks = []
        for person in people:
            open_now, _ = await ask_json([program, "questions", f"--as={person}", "--json"])
            asks += [q for q in open_now or [] if isinstance(q, dict)]
        if asks:
            out.append("Waiting for your answer:")
            for q in asks:
                out.append(f"  {q.get('text')}  ({how_to_answer(q)})")
            out.append("")
        if not cards:
            out.append("You have no routines yet. Ask me for a morning brief, or anything a "
                       "ready one does; a new kind is drawn on Vidhi's page.")
            return "\n".join(out)
        out.append("Your routines:")
        for n, card in enumerate(cards, 1):
            paused = "" if card.get("state") == "active" else f" ({card.get('state')})"
            out.append(f"{n}. {card.get('title')}{paused} — {card.get('cost')}")
        out += ["", HOW]
        return "\n".join(out)

    async def _asked(self, program: str, people: list[str], code: str) -> dict | None:
        """The waiting question with this code, for one of these people."""
        for person in people:
            open_now, _ = await ask_json([program, "questions", f"--as={person}", "--json"])
            for q in open_now or []:
                if isinstance(q, dict) and str(q.get("code", "")).upper() == code.upper():
                    return q
        return None

    async def _by_code(self, program: str, people: list[str], question: dict,
                       rest: list[str], via: str) -> str:
        """A question answered by its code alone, the way its kind takes."""
        code = str(question.get("code"))
        kind = question.get("kind") or "yesno"
        said = " ".join(rest)
        if kind == "yesno":
            word = YES_NO.get(said.lower().strip(" .!"))
            if word:
                return await self._answer(program, people, code, word, via)
        elif said:
            return await self._answer(program, people, code, said, via)
        return f"\"{question.get('text')}\" -- answer it with {how_to_answer(question)}"

    async def _runs(self, program: str, cards: list[dict], which: str) -> str:
        card = _which(cards, which)
        if card is None:
            return f"You have no routine {which}. Send /routines to see them."
        runs, trouble = await ask_json([program, "runs", str(card["name"]),
                                        f"--as={card['owner']}", f"--limit={RUNS_SHOWN}",
                                        "--json"])
        if trouble:
            return trouble
        if not runs:
            return f"{card.get('title')} hasn't run yet. /routines run {which} starts it."
        out = [f"{card.get('title')}, last runs:"]
        for run in runs:
            out.append(f"• {run.get('created_at', '')[:16].replace('T', ' ')} — "
                       f"{run.get('state')}" + (f": {run.get('detail')}"
                                                 if run.get("detail") else ""))
            for step in run.get("steps") or []:
                if step.get("state") in ("pending",):
                    continue
                said = step.get("why") or step.get("detail") or ""
                out.append(f"    {step.get('title')}: {step.get('state')}"
                           + (f" ({said})" if said else ""))
        return "\n".join(out)

    # -- doing ----------------------------------------------------------------------

    async def _start(self, program: str, people: list[str], which: str, via: str) -> str:
        cards = await self._list(program, people)
        if isinstance(cards, str):
            return cards
        card = _which(cards, which)
        if card is None:
            return f"You have no routine {which}. Send /routines to see them."
        run, trouble = await ask_json([program, "start", str(card["name"]),
                                       f"--as={card['owner']}", f"--by=dvara:{via}",
                                       "--json"])
        if trouble:
            return trouble
        return (f"Started {card.get('title')} (run {run.get('id')}). What it finds comes "
                "here; if it has a question, it asks with buttons.")

    async def _answer(self, program: str, people: list[str], code: str, word: str,
                      via: str) -> str:
        trouble = ""
        for person in people:
            said, trouble = await ask_json([program, "answer", code, word,
                                            f"--as={person}", f"--via={via}", "--json"])
            if not trouble:
                question = said.get("question") or {}
                run = said.get("run") or {}
                follow = ("it carries on now" if run.get("state") in ("queued", "running")
                          else f"the run is {run.get('state')}" if run else "")
                kept = str(question.get("answer") or word)
                head = kept.capitalize() if question.get("kind", "yesno") == "yesno" \
                    else f"\"{kept}\""
                return (f"{head} to \"{question.get('text')}\""
                        + (f" — {follow}." if follow else "."))
            if "no question" not in trouble:
                break
        return trouble

    async def _stop(self, program: str, people: list[str], run: str) -> str:
        trouble = ""
        for person in people:
            _, trouble = await ask_json([program, "stop", run, f"--as={person}", "--json"])
            if not trouble:
                return f"Stopped run {run}."
            if "no run" not in trouble:
                break
        return trouble


def how_to_answer(question: dict) -> str:
    """The words that answer a question, as a person types them."""
    code = question.get("code")
    if question.get("kind") == "choice":
        return "  or  ".join(f"/routines pick {code} {n} for {c}"
                             for n, c in enumerate(question.get("choices") or [], 1))
    if question.get("kind") == "words":
        return f"/routines say {code} your words"
    return f"/routines yes {code}  or  /routines no {code}"


def _which(cards: list[dict], which: str) -> dict | None:
    if which.isdigit() and 1 <= int(which) <= len(cards):
        return cards[int(which) - 1]
    return next((c for c in cards if c.get("name") == which), None)

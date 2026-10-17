"""``/phone``: the phone's screen and its last steps, asked for in the chat.

Yantra's page has a phone panel: what is on the screen now, as a picture
and as Sparsh's list, and what was done on it, the agent's steps and the
person's own. Behind this service the person whose phone it is could
only ask the agent ("what's on my phone?"), which spends a turn and
moves its numbers.

THEIRS, AND ONLY THEIRS. The phone on this machine's cable is one
person's, messages and all (``phone = true``, note 30). Anyone else's
``/phone`` gets one sentence and no screen.

A PEEK, NOT A LOOK. Sparsh's ``look --peek`` reads the screen without
becoming the agent's last look, so an agent working the phone keeps its
numbers (Yantra's sparsh_link). The picture is kept in the person's
folder under ``.phone/`` -- a dot folder, so ``/files`` never lists it --
and sent with the words: on Telegram as the file, on the page as one to
open.

The person's word, never a turn: no model, nothing spent.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

WORD = "/phone"
#: Lines of the screen's list shown, and steps.
SCREEN_LINES = 15
STEPS = 5
NOT_YOURS = ("There's no phone here for you: the phone on this computer is "
             "another person's.")


def is_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() == WORD


def _element(e: dict) -> str:
    label = (e.get("label") or "").strip()
    return f"{e.get('n')} {e.get('kind')}" + (f' "{label}"' if label else "")


def _step(entry: dict) -> str:
    at = (entry.get("at") or "")[11:16]
    by = entry.get("by") or "?"
    said = entry.get("said") or entry.get("app") or ""
    text = f"{at} {by}: {entry.get('action')} → {entry.get('outcome')}"
    return f"{text} ({said})" if said else text


def words(screen: dict, steps: list[dict], name: str) -> str:
    out = [f"Your phone ({name}) now shows {screen.get('app') or 'something'}:"]
    if screen.get("note"):
        out.append(screen["note"])
    elements = screen.get("elements") or []
    out += [_element(e) for e in elements[:SCREEN_LINES]]
    if len(elements) > SCREEN_LINES:
        out.append(f"… and {len(elements) - SCREEN_LINES} more")
    if steps:
        out += ["", "Last done on it, newest first:"]
        out += [_step(s) for s in steps[:STEPS]]
    return "\n".join(out)


async def look(sparsh: str | None, folder: Path) -> tuple[str, Path | None]:
    """(what to say, the screenshot kept in their folder or None)."""
    from yantra.sparsh_link import Sparsh, SparshLinkError, load, ready_phones

    try:
        found = await asyncio.to_thread(load, "on", sparsh, False)
    except SparshLinkError as exc:
        return f"I can't reach your phone right now: {exc}", None
    if found is None:
        return "Sparsh isn't on here, so there's no phone to show.", None
    link = Sparsh(mode="on", path=sparsh, data=found[0], program=found[1])
    phones = ready_phones(found[0])
    if not phones:
        return ("No phone is ready: plug it in, or reconnect its Wi-Fi (on the "
                "home page, Settings → Sarathi → Your phone)."), None
    phone = phones[0]
    serial = phone.get("serial") or ""
    try:
        peeked = await asyncio.to_thread(link.peek, serial, True)
        steps = await asyncio.to_thread(link.recent, serial, STEPS)
    except SparshLinkError as exc:
        return f"I can't read your phone's screen right now: {exc}", None
    shot = None
    if peeked.get("shot"):
        shot = Path(folder) / ".phone" / "screen.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        shot.write_bytes(base64.b64decode(peeked["shot"]))
    return words(peeked.get("screen") or {}, steps, phone.get("model") or serial), shot

"""A notice that reaches a phone with no chat open: ntfy, on the house's own server.

The web channel keeps a notice until the person opens the page (web.py),
and Telegram sends one at once -- but only to somebody who has Telegram.
A person who talks to their agents on the home page found a schedule's
answer only when they next looked. ntfy is a small push server and a
phone app: the app keeps a connection to the server and shows what is
posted to a topic it subscribed to.

THE HOUSE'S OWN SERVER. ``dvara serve --ntfy URL`` posts each notice to
an ntfy server the owner runs (Sarathi starts one), so the words never
leave the house. The price: a phone hears it while it can reach that
server -- on the home network, or wherever the owner's own network
reaches (Tailscale). ntfy.sh, the public server, was turned down: every
notice would pass through somebody else's computer.

ONE TOPIC PER PERSON, THAT NOBODY CAN GUESS. ntfy's topics are open: who
knows a topic's name can read it. So a person's topic is
``dvara-<id>-<16 hex>``, the hex an HMAC of their id under a key kept in
``<state>/ntfy.key`` (the owner's alone). Their page shows it to them
(``GET /web/push``) and nobody else; a new key moves every topic.

ON FOR EVERYONE, HEARD BY WHOEVER SUBSCRIBED. With ``--ntfy`` every
person's notices are posted to their topic, as the web channel's lines
are kept for everyone: nothing in the actors file to add, and nothing
reaches a phone that did not subscribe. Only notices go -- a schedule's
answer, a refused sign-in, what a look back noticed. The answer to
something they just wrote on the page is on the page.

A SERVER DOWN IS NOT A CRASH. A post that fails is recorded as failed
for that notice (notices.py), and the other channels still get it.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import secrets
import urllib.request
from pathlib import Path

#: The channel's kind, in notices.
KIND = "ntfy"
KEY_FILE = "ntfy.key"
#: How long one post may take.
WITHIN = 10.0


def _key(state: Path) -> bytes:
    path = state / KEY_FILE
    try:
        return bytes.fromhex(path.read_text().strip())
    except (OSError, ValueError):
        key = secrets.token_bytes(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(key.hex())
        return key


def topic(state: Path, actor: str) -> str:
    """This person's topic: their id (as ntfy allows) and 16 hex of an
    HMAC of it, so it can be read on a phone and never guessed."""
    mark = hmac.new(_key(state), actor.encode(), hashlib.sha256).hexdigest()[:16]
    shown = re.sub(r"[^A-Za-z0-9_-]", "-", actor)[:24]
    return f"dvara-{shown}-{mark}"


class Pusher:
    """Posts a notice's words to the person's topic on ``url``."""

    def __init__(self, url: str, state: Path, *, click: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.state = state
        #: Where a tap on the notice opens (the home page), when known.
        self.click = click

    def topic(self, actor: str) -> str:
        return topic(self.state, actor)

    async def notice(self, address: str, text: str, file: Path | None = None) -> None:
        words = text if file is None else f"{text}\n(a file came with it: {file.name})"
        await asyncio.to_thread(self._post, address, words)

    def _post(self, topic_name: str, text: str) -> None:
        headers = {"Title": "Your agents", "Tags": "speech_balloon"}
        if self.click:
            headers["Click"] = self.click
        request = urllib.request.Request(f"{self.url}/{topic_name}",
                                         data=text.encode()[:4000], method="POST",
                                         headers=headers)
        with urllib.request.urlopen(request, timeout=WITHIN) as answer:
            answer.read()

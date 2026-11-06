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
notice would pass through somebody else's computer. An iPhone is the one
exception, and it is the server's setting, not Dvara's: iOS wakes an app
only through Apple, so the house's ntfy may tell ntfy.sh that a message
came (its id and a hash of the topic, never the words), and the iPhone
fetches the words from the house (Sarathi's ``[dvara] ntfy_upstream``).

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

KEEP AND NOT NOW ON THE PHONE, WITH NO KEY IN THEM. A skill offered
comes with two buttons (ntfy's http actions), pressed from the
notification itself. The ntfy app sends the request from the phone, so
whatever it carries is in the notification for anyone who reads the
topic. It carries no token: only a mark, an HMAC under ``ntfy.key`` of
this person, this agent, this offer and this word, which Dvara checks
(``POST /push/answer``, through the home page's ``/api/push/answer``).
Copied, it can keep or drop that one offer and nothing else, which is
what the person reading the notification could do anyway. What a look
back noticed comes the same way, ONE NOTIFICATION PER FACT: ntfy draws
three buttons at most, so each fact's has Keep and No for it and, when
there are several, Keep all. Only the first makes a sound; the rest
arrive at low priority, so several facts are still one buzz. Each
button carries the facts' short marks in the offer's place
(remembering.py), and the answer comes back as a notice of its own. The buttons
go where the tap already opens (``--ntfy-click``, the home page's
address on the house network); without one, the words still say what
to type.

A SERVER DOWN IS NOT A CRASH. A post that fails is recorded as failed
for that notice (notices.py), and the other channels still get it.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

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


#: The words a button may send, and what each is called on the phone.
WORDS = {"keep": "Keep", "drop": "Not now"}
#: A look back's facts on a button: this, then their marks joined by dots,
#: in the ``offer`` place, so the mark covers exactly those facts.
REMEMBER = "remember:"
REMEMBER_ONE = {"keep": "Keep", "drop": "No"}
#: The third button on each fact's notification, when there are several.
REMEMBER_ALL = "Keep all"
#: ntfy's "low" priority: shown, with no sound and no buzz.
QUIET = 2
#: Where on the home page a button's press goes.
ANSWER_PATH = "/api/push/answer"


def mark(state: Path, actor: str, agent: str, offer: str, word: str) -> str:
    """The mark for one button: good for this person, agent, offer and
    word only."""
    said = "\n".join((actor, agent, offer, word)).encode()
    return hmac.new(_key(state), b"answer\n" + said, hashlib.sha256).hexdigest()[:32]


def marked(state: Path, actor: str, agent: str, offer: str, word: str, given: str) -> bool:
    return word in WORDS and hmac.compare_digest(mark(state, actor, agent, offer, word),
                                                 str(given))


class Pusher:
    """Posts a notice's words to the person's topic on ``url``."""

    def __init__(self, url: str, state: Path, *, click: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.state = state
        #: Where a tap on the notice opens (the home page), when known.
        self.click = click
        #: Whose each topic is, as named here: a notice is handed only its
        #: topic, and a button's mark needs the person.
        self._whose: dict[str, str] = {}

    def topic(self, actor: str) -> str:
        name = topic(self.state, actor)
        self._whose[name] = actor
        return name

    async def notice(self, address: str, text: str, file: Path | None = None,
                     extra: dict | None = None) -> None:
        words = text if file is None else f"{text}\n(a file came with it: {file.name})"
        actor = self._whose.get(address)
        extra = extra or {}
        posts = self.remember_posts(actor, extra.get("remember")) \
            if actor and file is None and not extra.get("offer") else []
        if posts:
            for n, (said, buttons) in enumerate(posts):
                # one sound for the lot: the rest arrive quietly
                await asyncio.to_thread(self._post, address, said, buttons, quiet=n > 0)
            return
        actions = self.actions(actor, extra.get("offer")) if actor else []
        await asyncio.to_thread(self._post, address, words, actions)

    def actions(self, actor: str, offer: dict | None) -> list[dict]:
        """Keep and Not now for a skill offered, when a phone can reach the
        home page; none otherwise."""
        if not offer or not offer.get("id") or not offer.get("agent"):
            return []
        return self._buttons(actor, str(offer["agent"]), str(offer["id"]), WORDS)

    def remember_posts(self, actor: str, noticed: dict | None) -> list[tuple[str, list[dict]]]:
        """What a look back noticed, as the phone gets it: one notification
        for EACH fact, so each can be kept or turned down on its own.

        ntfy draws three buttons a notification, so a single notification
        for several facts could only offer all or none of them. Each
        fact's has Keep and No for that fact, and Keep all (with several)
        for every fact the look back listed. The buttons carry the facts'
        marks (remembering.fact_mark), found again at the press among what
        still waits: a fact answered from another notification, the page
        or Telegram is "already answered", never another one. None without
        a home page to press to (``--ntfy-click``): the words are then
        posted whole, as any notice."""
        from dvara.remembering import fact_mark
        noticed = noticed or {}
        facts = [f for f in noticed.get("waiting") or noticed.get("items") or []
                 if isinstance(f, str)]
        agent = str(noticed.get("agent") or "")
        if not facts or not agent or not self.click:
            return []
        every = REMEMBER + ".".join(fact_mark(f) for f in facts)
        posts = []
        for n, fact in enumerate(facts, 1):
            one = REMEMBER + fact_mark(fact)
            buttons = self._buttons(actor, agent, one, REMEMBER_ONE)
            if len(facts) > 1:
                buttons += self._buttons(actor, agent, every, {"keep": REMEMBER_ALL})
                head = f"{agent} noticed this about you ({n} of {len(facts)}):"
            else:
                head = f"{agent} noticed this about you:"
            posts.append((f"{head}\n{fact}", buttons))
        return posts

    def _buttons(self, actor: str, agent: str, offer: str,
                 labels: dict[str, str]) -> list[dict]:
        if not self.click:
            return []
        place = urlsplit(self.click)
        url = f"{place.scheme}://{place.netloc}{ANSWER_PATH}"
        return [{"action": "http", "label": label, "url": url, "method": "POST",
                 "headers": {"Content-Type": "application/json"}, "clear": True,
                 "body": json.dumps({"actor": actor, "agent": agent, "offer": offer,
                                     "word": word,
                                     "mark": mark(self.state, actor, agent, offer, word)})}
                for word, label in labels.items()]

    def _post(self, topic_name: str, text: str, actions: list[dict] | None = None, *,
              quiet: bool = False) -> None:
        if actions:
            # buttons need ntfy's JSON form: the header form can't carry a body
            body = {"topic": topic_name, "message": text[:4000], "title": "Your agents",
                    "tags": ["speech_balloon"], "actions": actions}
            if quiet:
                body["priority"] = QUIET
            if self.click:
                body["click"] = self.click
            request = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                             method="POST",
                                             headers={"Content-Type": "application/json"})
        else:
            headers = {"Title": "Your agents", "Tags": "speech_balloon"}
            if self.click:
                headers["Click"] = self.click
            request = urllib.request.Request(f"{self.url}/{topic_name}",
                                             data=text.encode()[:4000], method="POST",
                                             headers=headers)
        with urllib.request.urlopen(request, timeout=WITHIN) as answer:
            answer.read()

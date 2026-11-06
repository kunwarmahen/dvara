"""The words an agent answers, as one list every road draws from.

A person finds ``/remember`` by typing ``/``. On Telegram that menu was
built here, agent by agent, from what the package can do; the home page
kept a short list of its own, written once by hand, and every word added
since -- ``/remember``, ``/household``, ``/voice``, ``/accounts`` --
reached Telegram and never the page. The page then looked like it could
not do what it could: the words always worked there when typed, because
the page's chat is the same turn Telegram's is.

ONE LIST, ASKED FOR. Telegram sets its bot's menu from ``words_for`` at
start; the web channel's look hands the same list to the page for each
agent the person may use (web.py). A page keeps its own extras -- boxes
it opens, like Teach -- but no longer its own copy of what Dvara answers,
so the two can't drift apart again.

ONLY WHAT THIS AGENT ANSWERS. ``/files`` for one that writes them, the
account words for one whose package asks for accounts, ``/memory`` and
``/remember`` for one that remembers people, ``/phone`` for one whose
package lets the phone in on a service that has one. A word offered that
answers "I can't do that here" is worse than one not offered.

Each entry is (word without its slash, what it does): Telegram's form,
which wants the bare command and a description of at most 256 characters.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any


def menu(spec: Any, *, schedules: bool = False, watches: bool = False,
         phone: bool = False) -> list[tuple[str, str]]:
    """``/`` menu entries for this agent, in the order a person needs them."""
    words = [("new", "Start our conversation over"),
             ("carry", "Carry on a job a restart stopped"),
             ("steps", "What my last answer did, step by step"),
             ("chats", "Our conversations: find, open, delete"),
             ("tests", "Answers kept as tests, and how each did"),
             ("doctor", "What's wrong with yours; /doctor every morning")]
    if writes_files(spec):
        words += [("files", "What I keep for you"),
                  ("file", "Send one of them: /file NAME")]
    if remembers(spec):
        words += [("memory", "What I remember about you"),
                  ("remember", "Keep what I noticed: /remember 1 2; /remember declined")]
    if spec.connections:
        words += [("accounts", "Your connected accounts"),
                  ("connect", "Connect one: /connect NAME"),
                  ("disconnect", "Remove one: /disconnect NAME"),
                  ("lock", "Lock your accounts with a passphrase"),
                  ("unlock", "Unlock them for a while")]
    if getattr(spec, "skills", None):
        words += [("skills", "Skills I've learned, and ones to keep"),
                  ("learn", "Keep what I just did as a skill; /learn start to teach me")]
    # every agent is told what everyone in the house knows (household.py)
    words += [("household", "What everyone's agents know; /remember for everyone …"),
              ("tools", "What I can use for you"),
              ("voice", "Answers read aloud: when, and in whose voice")]
    if phone:
        words += [("phone", "Your phone's screen and its last steps; /phone NAME for another")]
    if schedules:
        words += [("schedules", "Your schedules")]
    if watches:
        words += [("watches", "What I watch for you; /watches every N 6h, pause N, resume N")]
    return words


def words_for(service: Any, spec: Any) -> list[tuple[str, str]]:
    """``menu`` for this agent on this service: the siblings it was
    started with decide schedules, watches and the phone."""
    from dvara.service import works_phone

    return menu(spec, schedules=service.samay is not None,
                watches=service.prahari is not None,
                phone=service.sparsh is not None and works_phone(spec))


def remembers(spec: Any) -> bool:
    """Whether this agent's package keeps memories about people at all."""
    return getattr(spec, "memory", None) not in (None, "off")


def writes_files(spec: Any) -> bool:
    """Whether this agent can leave a file in the person's folder -- the
    only kind worth telling them ``/files`` exists."""
    allowed = spec.tool_allow is None or any(fnmatch("write_file", p)
                                             for p in spec.tool_allow)
    return allowed and not any(fnmatch("write_file", p) for p in spec.tool_deny)

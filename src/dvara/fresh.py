"""Starting over: one word that is the person's to type.

A chat with an agent is one conversation for as long as the chat lasts.
Every message and every tool result goes back to the model on the next
turn, and when that grows too long Yantra summarizes the oldest part --
it does not drop it. That is what makes "and the one before?" work, and
it is also how a habit sets in: a model that fetched a page one way five
times will fetch it that way a sixth time, even after its package gave
it a better tool. Nothing the person could say from the chat cleared
that. Telegram's own "Clear history" only clears their phone; the bot
is never told.

    /new        start this conversation over

THE PERSON'S WORD, NOT THE MODEL'S. Like ``/files`` and ``/accounts``
it is answered here, never a turn: no model reads it, nothing is spent,
and it works the same whatever model is behind the door.

THE CONVERSATION GOES, NOTHING ELSE DOES. Only the saved conversation
(sessions.sqlite3) is let go, through Yantra's ``forget``. The ledger
keeps every run's message and reply, so ``dvara runs`` and the day's
spending are unchanged; the person's folder with this agent keeps its
files; their schedules and their accounts are not conversations at all.
A question the conversation was still holding for them goes with it --
a new message would have set it aside anyway.

NEVER UNDER A RUNNING TURN. A turn that is still working on this
conversation would save it again the moment it finished, so ``/new``
then says to send it once the answer is in, and changes nothing.
"""

from __future__ import annotations

WORDS = ("/new",)

STARTED_OVER = ("Starting fresh: I won't remember what we said before. "
                "Your files, schedules and accounts are all still here.")
NOTHING_YET = "Starting fresh. (There was nothing to forget yet.)"
STILL_ANSWERING = ("I'm still working on your last message. Send /new "
                   "again once I've answered it.")


def is_new_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in WORDS

# 45 — Going back

*`/new` let a conversation go for good ([note 28](28-starting-over.md)).
That was right for what it was for -- a small model's habit, carried
from one turn to the next -- and wrong for everything else: "what did we
work out about the trip?" had nowhere to go but the person's memory.
Yantra's own page saves sessions and loads them again; nothing here
did.*

## Kept, not forgotten

```
/new          start over; this conversation is kept
/chats        the ones kept, newest first
/chats 2      go back into one; the one you're in is kept in its place
```

`/new` now hands the conversation it ends to `past.py`'s book before
letting it go: its saved form exactly as Yantra wrote it (one
checkpoint payload), a title (the person's first words in it), where it
was (Telegram, the page) and when it ended. The newest thirty per person
per agent are kept. A conversation in which the person said nothing is
not kept: there is nothing to go back to.

The answer to `/new` says so now: *"Starting fresh. What we said before
is kept: /chats lists it, if you want to go back."*

## Going back swaps

`/chats N` takes that conversation out of the book and makes it the one
here, through Yantra's `SessionStore.save_payload` (a payload carried to
another id, appended like any checkpoint). The one you were in goes into
the book first, so going back never loses anything. The answer says
where you are: its title and, in a line, where it was left.

ONE CONVERSATION PER CHANNEL STILL HOLDS: what you open becomes this
channel's conversation. The list is per person per agent across
channels, so a conversation begun on Telegram can be carried on on the
page -- by the person's word, never by default.

Like `/new`, it is THE PERSON'S WORD, never a turn: no model, nothing
spent, and never under a turn still working on the conversation. One
person's list is never another's.

## Receipt

A scratch Dvara on the web channel, `qwen3.8:latest`:

```
you    My daughter's school trip is on Friday 24 October to the science
       museum; she needs a packed lunch.
mailer Got it — I'll note that: packed lunch needed by Friday, 24 October …
you    /new
mailer Starting fresh. What we said before is kept: /chats lists it, if you
       want to go back. …
you    What's 17 times 3?
mailer 17 × 3 = **51**
you    /chats
mailer Your earlier conversations with mailer, newest first:
       1. My daughter's school trip is on Friday 24 October to the sc… —
          Sat 17 Oct 00:09, on the page, 1 message
you    /chats 1
mailer Back in: My daughter's school trip is on Friday 24 October to the sc…
       Where we left it: Got it — I'll note that: …
you    Remind me, what does she need to bring, and where is the trip?
mailer The trip is to the science museum on Friday 24 October, and she
       needs to bring a packed lunch. …
```

## What the tests hold

`tests/test_past.py`: `/new` keeps what it ends and `/chats` lists it;
going back shows the model that conversation and keeps the one it
replaced; a number that isn't there is said; one person's conversations
are never another's; nothing said is nothing kept; the book keeps only
the newest. Yantra's `tests/test_session.py`: a payload saved under
another id loads as it was and carries on from there.

## What is not here yet

* **The page's lines for an old conversation.** Going back on the page
  restores what the model sees; the page's own lines (what you scroll)
  stay as they were, and the answer says where it was left.
* **Naming or deleting a kept conversation** from the chat. The oldest
  go by themselves after thirty.

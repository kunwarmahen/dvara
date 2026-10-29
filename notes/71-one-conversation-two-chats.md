# 71 — One conversation, two chats

You ask about the boiler on Telegram in the kitchen, then sit down at
the computer and want to carry on there. `/chats 1` on the page used to
answer *"That conversation is still going on Telegram. Carry it on
there, or send /new there first."* Two chats writing one row would each
overwrite the other, so a conversation was open in one place at a time
([note 50](50-every-conversation-kept.md)).

That was the safe answer and the wrong one. A person doesn't think of
Telegram and the page as two conversations; they think of one, picked up
wherever they are.

## Shared, not moved

**OPENING ONE JOINS IT.** `/chats 1` on the page now opens it there and
leaves it open on Telegram too, and says so: *"It's open on Telegram
too: what's said in either carries it on."* Whatever is said on the page
is in front of the model the next time Telegram speaks, and the other
way round. `/new` leaves only the chat it was sent on.

The difficulty was never the row. Each chat keeps its own copy of where
the conversation is (Yantra's sessions, one per chat), and a turn starts
from that copy. Two chats on one conversation means two copies, and
the one that spoke second would start from a conversation missing the
first one's turn.

**THE LOG SAYS WHO IS UP TO DATE.** One more small table beside the one
that says which conversation each chat is in: `latest`, which chat's
copy matches the row as the log has it. Each write to the log marks the
chat that wrote it. Before a turn, a chat that is not the latest takes
the row again, and is the latest from then on. A chat that is the
latest (the usual case: one chat, one conversation) does nothing new.

**ONE AT A TIME.** A turn holds the conversation as well as its chat,
so two chats never write it at once. A message on the page while
Telegram's turn is still working waits for it, as a second message on
one chat already did.

**A WAITING QUESTION IS SET ASIDE.** If Telegram was waiting on a yes
(*"may I send this email?"*) and you say something new on the page, the
question is set aside, the rule a new message already follows on one
chat. Its buttons answer that it's gone. The alternative, a yes on
Telegram carrying on from a conversation that has since moved on, would
write over what the page said.

## Every road it went on

The list used to say where a conversation was going on now. Now it says
every road it went on: *"— Thu 29 Oct 16:09, on Telegram and the page,
3 messages"*. A puck's conversation is named by its puck (*the kitchen
puck*), not by the program behind it. One kept before that says only
*vaani*, and nothing recorded which puck, so it's listed as *a puck*.

## Named and pinned

A conversation can have a title of the person's own, shown in the list
and found by search instead of its first words, and can be pinned above
the newest. Both live in the person's own file (Yantra's
`ConversationLog.rename` and `pin`), so they leave with it. A pinned one
says so in `/chats`: *"1. when is the trip? (pinned) — …"*. A page sets
them over the web channel:

```
POST /web/chats/ID/rename   {"actor": A, "title": "Holiday"}   empty title: first words again
POST /web/chats/ID/pin      {"actor": A, "pinned": true}
```

Each row of `GET /web/chats` carries `roads` and `pinned` too, and
`here`: whether the page's own chat is in it, so a page can show the
conversation it is in even when its window has no lines of it left.
Someone else's conversation, or one that's gone, is a 404.

## What was sent, by itself

A page that lists conversations at the side wants what was sent to the
person unasked (a schedule's answer, a watch, a sign-in that stopped) in
a place of its own, not between their words. Those are already lines on
the web channel, marked `notice`; but a page opened afresh shows only
the lines since the last `/new`, so a notice from before it was gone
from the page. `GET /web/notices?actor=A` gives the person's notices,
newest first, whatever `/new` cleared, from the same kept lines (they
age out with the rest). Sarathi's bell counts and lists them.

## Live receipt

A scratch Dvara from `examples/`, `qwen3.8:latest`, the `greeter` agent,
`dvara say` on two threads standing in for Telegram and the page:

```
> [telegram:1] In one sentence: what pressure should a home boiler show when cold?
A home boiler should read roughly 1 to 1.5 bar on its cold gauge, generally within the green marker zone.

> [web:chat] /chats 1
Back in: In one sentence: what pressure should a home boiler show when cold?

Where we left it:
You: In one sentence: what pressure should a home boiler show when cold?
greeter: A home boiler should read roughly 1 to 1.5 bar on its cold gauge, generally within the green marker zone.

It's open on Telegram too: what's said in either carries it on.

> [web:chat] And if it shows 0.5 bar? One sentence.
That's low, so you'd need to repressurize it via the filling loop until it reads in the green band, or call a heating engineer if it keeps dropping.

> [telegram:1] What did I just ask on the page? One sentence.
You asked what to do if the boiler pressure reads 0.5 bar.
```

Telegram's turn knew what was asked on the page: it took the row again
before it ran. `/chats` then listed one conversation of three messages.

## Tests

`tests/test_past.py`: two chats each see what the other said, in one
row of three turns on both roads; a chat that is not behind keeps its
own copy; `/new` on one chat leaves the other in it; another chat
speaking sets a waiting question aside; a puck's road is named by its
puck; the page renames and pins only the person's own. Yantra's
`tests/test_history.py`: a name shows and is searched, survives the next
turn, and an empty one gives the first words back; a pin stays above
newer rows; an older file gains the columns.

## What is not here yet

* **The same answer on both screens at once.** The page's chat lines and
  Telegram's messages are each their own. What the page said shows on
  Telegram as the model's knowledge of it, not as messages in the
  Telegram chat.

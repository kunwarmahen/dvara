# 50 — Every conversation kept, found by its words

*Last week someone asked their agent on Telegram what pressure the
boiler should show. Today they want the answer again. `/chats` showed
what `/new` had ended, the newest thirty. They had never sent `/new` in
that chat, so it wasn't there.*

## Kept as it goes

[Note 45](45-going-back.md) kept a conversation when `/new` ended it.
Now every turn writes its conversation down, and `/new` only starts the
next one. The record is Yantra's own conversation log (Yantra's
notes/130): the same file format, the same full-text search, the same
delete. The terminal, Yantra's page, Telegram and Sarathi's home page
all keep conversations the same way.

```
/chats                  every conversation with this agent, newest first
/chats boiler           only the ones that say "boiler", the word marked
/chats 2                go back into that one
/chats open 2           the same, as Yantra's terminal says it
/chats delete 2         asks: "Delete … for good? Send /chats delete 2 sure"
/chats delete 2 sure    deleted for good
/chats export 2         that one as a Markdown file, sent with the answer
```

ONE FILE PER PERSON. `state/past/<person>.sqlite` holds one person's
conversations with every agent; each row's folder is the agent's name.
One person's list never reaches another's, because nothing else is in
their file. A person who leaves is removed with the file
(`PastBook.forget_all`).

WHICH CONVERSATION A CHAT IS IN is one small table
(`state/past/current.sqlite3`): each chat (person, agent, thread) maps
to the id its turns write to. `/new` drops the mapping, `/chats N` points
it at the old one, and that conversation's next turn grows its own row.
The list holds one line per conversation, never a copy per reopening.

~~NOT OPENED TWICE.~~ A conversation still going on Telegram now opens on
the page as well, and both carry it on: each chat takes the row again
before a turn when the other wrote it since ([note 71](71-one-conversation-two-chats.md)).

A NUMBER MEANS WHAT WAS ON SCREEN. `/chats boiler` shows each match with
its number in the whole list, so the `/chats 2` sent next opens the row
that said 2.

ASKED ONCE, IN WORDS. A chat has no dialog box, so `/chats delete 2`
names the conversation and says what to send, and only `/chats delete 2
sure` deletes it. Not the one open in this chat: its next turn would
write it again, so it says to send `/new` first.

A SCHEDULE'S RUN IS NOT A CONVERSATION. An unattended turn isn't kept
here. Samay's logbook and the run ledger have it.

THE OLD BOOK COMES OVER ONCE. What `/new` kept in `past.sqlite3` is moved
into each person's log on the first start, with when each one ended. The
old file then goes.

## The page's history

Three routes on the web channel, for a page that wants a list rather than
a chat word:

```
GET    /web/chats?actor=A&q=WORDS     every agent's, newest first; q searches
GET    /web/chats/ID?actor=A          one, to read: entries (tools too) + transcript
GET    /web/chats/ID/export?actor=A   one as a Markdown file, to share
DELETE /web/chats/ID?actor=A          gone for good; 409 if open in a chat now
POST   /web/chats/ID/rename           {actor, title}: the person's own title
POST   /web/chats/ID/pin              {actor, pinned}: kept above the newest
```

The last two, and each row's `roads` and `pinned`, are
[note 71](71-one-conversation-two-chats.md)'s.

A page carries one on by saying `/chats open ID` as a message, so the
answer is a line like any other, with its transcript drawn in place.
Sarathi's home page used all of this behind a **History** button; it
is now the list of conversations beside its chat (Sarathi's notes/33).

## Live receipt

A scratch Dvara on `qwen3.8:latest`, the `greeter` agent, the web
channel:

```
> In one sentence: what pressure should a home boiler show when cold?
A home boiler should read around 1 to 1.5 bar when cold, with 1.25 bar being the most common target.
> /new
Starting fresh. What we said before is kept: /chats lists it, ...
> In one short sentence: a good month to visit Lisbon?
May or early June is lovely—warm but not yet the peak-summer crush, ...
> /chats
Your conversations with greeter, newest first:
1. In one short sentence: a good month to visit Lisbon? (this one) — Sun 18 Oct 16:25, on the page, 1 message
2. In one sentence: what pressure should a home boiler show when cold? — Sun 18 Oct 16:25, on the page, 1 message
> /chats boiler
Your conversations with greeter that say “boiler”, newest first:
2. In one sentence: what pressure should a home boiler show when cold? — ...
    …what pressure should a home *boiler* show when cold? A home *boiler*…
> /chats delete 2
Delete “In one sentence: what pressure should a home boiler show when cold?” for good? ...
```

Then Sarathi's home page in front of it, in a browser at 1280 px and at
390 px. **History** listed both, with the Lisbon one marked *open in a
chat* and its Delete greyed out. Typing *boiler* narrowed it to one,
with the word marked. Opening it showed the question and answer with
*boiler* marked. **Carry on in the chat** sent `/chats open
ea51cd053863`, and the chat answered *"Back in: In one sentence: what
pressure…"* with the conversation unfolded under it. **Delete** on the
Lisbon one, now no longer open, removed it. `grep -c Lisbon` on
`state/past/owner.sqlite` then counted 0. The other person's
`/web/chats` was empty.

## Sharing one

`/chats export 2` writes that conversation as a Markdown file with
Yantra's `export_markdown`. The file holds your words, the agent's
answers under the agent's name, and the names of the tools it used,
never what a tool returned. It goes into the person's folder with that
agent, under `shared/` (so `/files` lists it), and goes out with the
answer: a document on Telegram, a file line on the page.
`GET /web/chats/ID/export` gives the same file to a page without a chat
line. Sarathi's History uses it for **Download** and **Send…**, and its
**Save as PDF** prints the same conversation through the browser.

Live, on the scratch Dvara above with `qwen3.8:latest`, `/chats export 1`
answered *"Here is “In one sentence: what pressure should a home boiler
show when cold?”, to share: your words, my answers and the names of the
tools I used (never what they returned). It's kept in your files too, as
shared/2026-10-18-in-one-sentence-what-pressure-should-a-home-boil.md."*,
and the line carried that file. Sarathi's page downloaded the same file
and printed the conversation to a one-page A4 PDF at desktop and at
phone width.

## What is not here yet

* **The other places a chat's words are, left by choice.** Delete
  clears the person's history. The page's chat scroll (`web.sqlite3`,
  each person's newest lines) and the run ledger (`runs.sqlite3`: each
  turn's message and answer, the owner's record of spending behind
  `dvara runs`) keep the words until their lines age out; neither says
  which conversation a line belonged to. Blanking them on delete, cost
  figures kept, was weighed and turned down: the owner's record of each
  run stays whole. Telegram keeps its own copy on the phone.
* ~~**A conversation as a test.**~~ Built: `/keep test` and `/chats
  test N` ([note 57](57-a-test-of-your-own.md)).
* ~~**A PDF where there is no print window.**~~ `/chats export N pdf`,
  printed by the machine's own Chrome ([note 69](69-a-picture-and-a-pdf.md)).
* ~~**Naming a conversation.**~~ Rename and pin, kept in the person's own file ([note 71](71-one-conversation-two-chats.md)).

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

NOT OPENED TWICE. A conversation still going on Telegram isn't opened on
the page as well: two chats writing one row would each overwrite the
other. The answer says where it's open (*"That conversation is still
going on Telegram. Carry it on there, or send /new there first."*).

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
DELETE /web/chats/ID?actor=A          gone for good; 409 if open in a chat now
```

A page carries one on by saying `/chats open ID` as a message, so the
answer is a line like any other, with its transcript drawn in place.
Sarathi's home page has a **History** button that uses all of this.

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

## What is not here yet

* **The other places a chat's words are.** Delete clears the person's
  history. The page's chat scroll (`web.sqlite3`, each person's newest
  lines) and the run ledger (`runs.sqlite3`: each turn's message and
  answer, the owner's record of spending behind `dvara runs`) still
  hold the words until their lines age out. Neither says which
  conversation a line belonged to. Telegram keeps its own copy on the
  phone.
* **Naming a conversation.** Its title is its first words.

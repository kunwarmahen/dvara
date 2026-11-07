# 78 — Carried on where it was written

## The problem, as you would meet it

The owner asked something on Sarathi's home page, pressed **New chat**,
and asked a second question. While the second was still being answered,
they picked the first conversation from the list, which said *"Write
below to carry this conversation on here"*, and asked a follow-up about
it. The follow-up was answered in the second conversation.

The page's lines showed why:

```
you    hey can you tell me hows my calendar looks like tomorrow? ...
you    /chats open b4779213f56a
agent  I'm still working on your last message. Send /chats 2 again once I've answered it.
you    how as my day today
```

The page carried one on in two messages: `/chats open ID`, then the
words. Each message on the page is its own turn, and `/chats N` turned
away a chat that was still answering. So the first message was refused,
the page never read the refusal, and the second went into the
conversation the chat was still in, under a window drawn with the old
one. The refusal even told them to type a number they had never seen.

## The words carry their conversation

**THE WORDS SAY WHICH CONVERSATION THEY ARE FOR, AND THE MOVE AND THE
ANSWER ARE ONE THING.** A message can carry a `conversation`: the id of
the one it was written under (`POST /web/message {..., conversation}`,
`Service.deliver(conversation=...)`). Before anything else the chat
moves into it, and then the words are answered there. The page now
sends one request where it used to send two, so there is nothing in
between for a refusal to fall into.

**A CHAT STILL ANSWERING IS WAITED OUT, NEVER REFUSED.** Moving takes
the chat's own lock, the same one a second message waits on. The answer
that was running finishes in its own conversation, and only then does
the chat move and answer the new words. `/chats N`, typed on Telegram
or anywhere else, waits the same way now. The tradeoff: a chat in the
middle of a long job keeps the next words waiting until it ends, just as
a second message would. Answering two conversations side by side on one
page needs each conversation to be its own chat, which this does not do.

**A CONVERSATION THAT IS GONE IS SAID, AND THE WORDS ARE ANSWERED
NOWHERE.** If the id is deleted, or belongs to someone else or another
agent (it is looked up in that person's own list with that agent), the
reply says so and no turn runs. Answering the words in whatever
conversation the chat happened to be in is the exact mistake this
replaces.

## Telegram: a reply goes back

Telegram has one window per bot, and conversations follow each other
down it. **SO EACH MESSAGE REMEMBERS ITS CONVERSATION.** Every answer the
bot sends, and the message it answered, is kept with the conversation it
was in (`past.sent`, the newest 5000 per chat). A reply to one of them,
whether a swipe or a long-press and *Reply*, hands that conversation to
the turn as its `conversation`. If that moved the chat, the answer
starts with *"Back in: …"*, the conversation's name. A reply to a
message in the conversation you're already in just carries on, with
nothing said about moving.

**`/chats` HAS A BUTTON FOR EACH.** The list arrives with up to eight
buttons, one per conversation, labelled with its number and name. A
press sends `/chats N`, as if you had typed it. The one you're in has no
button, because there is nowhere to go.

Not built: Telegram's topics in a bot's private chat, which would give
each conversation its own thread like a sidebar. A reply is something
every Telegram app already does, and it needs no setting from
BotFather.

## Live receipt

A scratch Dvara on port 8798, `greeter` on `qwen3.8:latest` through
Ollama, driven over `/web/message` as the page would: a question, `/new`,
a second question, and then, **while the second was still running**
(`busy: ['greeter']`), a follow-up sent with the first conversation's id:

```
busy while carrying on: ['greeter']
 11 you    Explain in about 200 words why the sky looks blue, step by step.
 12 you    And which day of the week is best to arrive there? One line.
 13 agent  I'm just a doorkeeper's greeter and can only give you one short sentence, ...
 14 agent  A Tuesday or Wednesday arrival keeps crowds thinner before the weekend rush.

d975db1232c8 Name one city in Portugal for a weekend trip. One line. turns: 3
6a175f2d976f Explain in about 200 words why the sky looks blue, step by s turns: 1
```

The first conversation, read back:

```
you   | Name one city in Portugal for a weekend trip. One line.
agent | Porto is a lovely pick for a weekend in Portugal.
you   | What should I pack for it? One line.
agent | Comfortable walking shoes, a light jacket for cool coastal evenings, ...
you   | And which day of the week is best to arrive there? One line.
agent | A Tuesday or Wednesday arrival keeps crowds thinner before the weekend rush.
```

The answer about the sky finished in its own conversation, and the
follow-up waited for it and then went into the Porto one. The Telegram
half was not run against a real bot; the tests below drive it through a
fake Bot API.

## What the tests hold

`tests/test_carried_on.py`: words sent with a conversation are answered
in it, with *"Back in: …"* and the conversation on the reply; the
conversation the chat is already in is no move; a chat still answering
is waited out, not refused (the case above), and so is `/chats N`; a
conversation that is gone is said, with no turn; one person's id is
gone to another; `/new` leaves no conversation on its reply; `/chats`
offers a button for each but the one open, and a long name is cut on
its button; a message id finds its conversation in its own chat only,
and the oldest are let go; the page carries one on in one request; on
Telegram, a reply to an old answer carries that conversation on, a reply
in the one open says nothing about moving, and `/chats`'s button goes
back. Sarathi's `tests/test_home.py`: the words under an old
conversation reach Dvara with its id, and only an id is passed on.

## What is not here yet

* ~~**Two conversations answering at once.**~~ On the page, each
  conversation is its own chat, and the list marks the ones working
  ([note 79](79-each-conversation-its-own-chat.md)). Telegram's one
  window still takes them one at a time.
* **Telegram topics.** One thread per conversation in the bot's private
  chat, if the Bot API in use supports it there.
* ~~**The page's own refusal.**~~ The answer to words written under a
  conversation that is gone carries `gone` on its line (`Reply.gone`).
  The page then takes the old conversation's words out of the window,
  leaving your words and Dvara's sentence, and the window is a new chat
  again. Telegram needs nothing: its old messages are its own history.

Continues [note 71](71-one-conversation-two-chats.md) (one conversation,
two chats) and [note 45](45-going-back.md) (going back).

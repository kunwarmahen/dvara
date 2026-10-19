# 51 — Starting over at once

*Someone finishes asking about flights and sends `/new` to start on
something else. Nothing comes back for forty seconds. Then "Starting
fresh", with two things the agent noticed about them underneath.
Forty seconds is long enough to think the bot is broken.*

## The look back was in the way

A package that remembers looks back over a conversation when `/new`
ends it ([note 38](38-what-they-said-in-passing.md)). That look is one
call to the agent's own model. It used to run *before* the answer to
`/new`, because the list went underneath that answer. On a local
model, one call can take as long as the turn did: 42 seconds in the
receipt below, between `/new` and *"Starting fresh"*.

Now `/new` answers at once. Dvara copies the conversation it's about to
let go, forgets it, says *"Starting fresh"*, and only then starts the
look back over the copy. What the look notices comes as a message of
its own a little later, numbered for `/remember`, the same way the look
after a quiet half hour sends its list
([note 39](39-while-nobody-is-writing.md)):

```
greeter: Looking back over the conversation we just ended, I noticed this about you:
1. Lives near RDU (Raleigh-Durham International Airport).
2. Prefers concise, one-line responses.
Send /remember with the numbers to keep them (/remember 1 2), or /remember all. …
```

**ONLY NEWS IS A MESSAGE.** A look back that noticed nothing sends
nothing. The person didn't ask for it, and *"I looked and found
nothing"* on their phone is noise.

**THE COPY, NOT THE CONVERSATION.** The look reads the conversation as
it stood when `/new` arrived, handed to it directly. It doesn't read it
back from the session store, which `/new` has already cleared, and
which the next conversation on the same chat may be writing to by the
time the look gets there.

**THE SAME RECORD.** It is still one call, on the person's allowance,
recorded as a `looked_back` run. A look that fails is still a line for
the owner and nothing for the person.

## It takes its turn

Yantra's terminal and page stop a look running behind the prompt when
the person sends something, because one person shares the model with
nobody and their message should go first (Yantra's notes/131). Dvara
doesn't stop it. It serves several people from one model, so queueing
at the model is how it always works here. One person's next message
has no better claim than someone else's turn. On a local model, the
next message after `/new` may wait for the look to finish at the model.
On a cloud model they run side by side.

## In the terminal

`dvara say ... "/new"` is a single command that ends when it's done.
It prints *"Starting fresh"*, waits for the look, and prints the list
under it. The list isn't sent to the person's Telegram, because the
person is the one at the keyboard:

```
$ dvara say --actor owner --agent greeter "/new"
Starting fresh. What we said before is kept: /chats lists it, if you want to go back. …
[new]

greeter: Looking back over the conversation we just ended, I noticed this about you:
1. Lives near Raleigh-Durham International Airport (RDU).
2. Prefers one-line responses.
Send /remember with the numbers to keep them (/remember 1 2), or /remember all. …
```

## Receipt

`gemma4:12b` through Ollama, after one turn: *"Flying out of RDU to
Denver in March. One line: what do I pack?"*. In process, timing the
service itself: `/new` answered in 0.02s, and the notice above
arrived 42.0s later. Through `dvara say`, the whole command, look
included, took 40.6s, with *"Starting fresh"* printed first.

`tests/test_remembering.py` checks that `/new` comes back while its look
is still pending and has asked no model yet, that the list arrives
after, that nothing is kept until `/remember`, and that a look that
fails still lets the conversation go.

## What is not here yet

* **Saying a look is coming.** *"Starting fresh"* doesn't promise a
  list, because most looks find nothing, and a promise of news that
  doesn't come is worse than none.
* **Waiting for it when the service stops.** A look still running when
  Dvara is stopped is dropped. The conversation itself is already kept
  ([note 50](50-every-conversation-kept.md)), so nothing said is lost,
  only that one look.

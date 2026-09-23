# 12 — taken down everywhere it went

*A question goes to every place a person can be reached. Until this
note, it only came down from the place they answered it. Everywhere
else, it stayed up — with two live buttons on it, for a decision that
had already been made.*

## The problem, as you would meet it

Your agent runs behind `dvara serve --telegram scribe`, and it asks to
write a file. The question arrives on your phone with two buttons on it.
It is also listed at `GET /asks`, where whatever you use on your laptop
can see it — [note 05](05-one-person-two-channels.md)'s whole point: a
question is put to a *person*, and any door they have can answer it.

You answer from the laptop (`POST /asks/{id}`). The file is written. And
your phone still says *"scribe wants to run write_file"*, with
**approve** and **refuse** under it, looking exactly as urgent as it did
a minute ago.

Press one and you are told the question is no longer waiting. That is
true, and it comes too late: you already believed the question, and for
a moment you wondered whether something else was asking. The same
happened when a question timed out while your phone was in your pocket,
and when the turn that asked was cancelled. In each case the
message stays up, and it says something that is no longer true.

## Why the desk could not fix it alone

The desk (`asks.py`) holds every question in flight. When one ends, it
already tidied up after itself in one way: any delivery still *running*
was cancelled. That is what stops a terminal prompt from sitting there
waiting for a line nobody will type
([note 09](09-a-process-you-walk-away-from.md) made that read
cancellable).

But the Telegram delivery is not running. It finished the moment the
message was sent. What it left behind is a message *id* — Telegram's
number for that message, in Telegram's terms — and only the Telegram
code knows what to do with it. The desk has no business holding chat
ids and message ids for every kind of channel, and a desk that did would
need to learn a new kind of id for every new channel.

Note 05 saw this coming and wrote down what the fix would take: *"a
per-delivery handle the notifier hands back, and every adapter then has
to implement editing."* That is what was built, nearly word for word.

## The design

**A NOTIFIER MAY HAND BACK ITS OWN UNDO.** A notifier is the function
the desk calls to put a question in front of someone. It used to return
nothing. Now it may return a function, and the desk calls that function
exactly once, when the question is over, with how it ended:

* the **answer** — approved or refused, and where (`via`) it was decided;
* a **timeout** — nobody answered, so it was refused;
* or **nothing at all** (`None`), when the turn that asked went away
  before anybody decided. That is deliberately not an answer: a channel
  that wrote "refused" under it would be recording a decision nobody
  made.

The Telegram bot's undo keeps the message id in a closure and edits the
message: it removes the buttons and adds one line saying how the
question ended. The desk never sees the id. A notifier that returns
nothing — the terminal's, for one — works exactly as it always did.

**WHERE IT WAS DECIDED IS SAID ONLY WHEN IT WAS NOT HERE.** The message
you pressed gets `— approved`. A copy you did not press gets `— approved
over HTTP`, or `at the terminal`, or `on` whatever channel took the
answer. Without that, a phone that shows "approved" for something you
approved on your laptop looks like somebody else answered.

**ONE WRITER.** The bot used to edit the message itself when you pressed
it. It no longer does; the desk takes the question down on every channel
it went to, the one that was pressed included. So a press on the phone
and an answer from anywhere else go through the same code, and there is
no second edit racing the first.

**TAKING IT DOWN NEVER HOLDS UP THE TURN.** The edit is a network call,
and a network call can take forty seconds to fail. The model has been
waiting for this answer long enough, so the undo runs beside the turn
rather than in front of it. If it fails — Telegram refuses the edit, the
network is down — nothing else notices. The worst case is the old
behaviour: a question left showing, and a press that says it is no
longer waiting.

## A bug worth writing down

The first version of `AskDesk.withdrawn()` — the call that waits for the
take-downs in flight, used by tests and by anything about to close the
connection — hung forever. It waited on the set of tasks until the set
was empty. But a finished task is removed from that set by a callback
that runs on the *next* tick of the event loop, and waiting on tasks
that have already finished returns without giving the loop that tick.
So the loop never came round, the callback never ran, and the set never
emptied. It now waits only on tasks that have not finished.

## Receipt

A real turn with `qwen3.8:latest` on Ollama, using the `scribe` package
(it asks before writing a file). The question went to the real bot code,
which talked to a stand-in Telegram server on this machine — no bot
token was involved. The answer landed on the desk exactly the way
`POST /asks/{id}` lands one:

```
phone  ← 'scribe wants to run write_file:\n\nNEW FILE hello.txt (1 lines)'  [approve] [refuse]
laptop → POST /asks/cg-Kij… {"approve": true}
phone  ✎ 'scribe wants to run write_file:\n\nNEW FILE hello.txt (1 lines)\n\n— approved over HTTP'  (buttons: False)
reply: Done — hello.txt contains "hello".
```

The phone's copy of the question lost its buttons and says where it was
answered.

To see it on a real phone, put your Telegram id in `examples/actors.toml`
and run the bot and the HTTP surface in one process (one dvara per state
directory — [note 09](09-a-process-you-walk-away-from.md) — so this is
the way to have two doors open at once):

```
DVARA_TOKEN=secret TELEGRAM_TOKEN=... dvara --root examples/agents \
      --actors examples/actors.toml --ask --provider ollama \
      --model qwen3.8:latest serve --telegram scribe
```

Message the bot *"write hello to hello.txt"*. When the question arrives
on the phone, do not press it; answer from the laptop instead:

```
curl -s -H "Authorization: Bearer secret" "localhost:8765/asks?actor=owner"
curl -s -X POST -H "Authorization: Bearer secret" \
     -H "content-type: application/json" \
     -d '{"actor": "owner", "approve": true}' localhost:8765/asks/ID
```

The phone's copy loses its buttons and reads `— approved over HTTP`.
Leave one unanswered instead and it reads `— nobody answered in time,
so it was refused` once `--ask-timeout` passes.

## Deliberately not built

* **Taking a question down on shutdown.** When the process stops, its
  undo tasks are cancelled with everything else, and a question can be
  left showing. After a restart, pressing it says it is no longer
  waiting — the old behaviour, and an honest one. Doing better needs the
  message ids written to disk, and a question left showing is a small
  thing next to a reply never sent, which is what
  [note 13](13-a-reply-that-is-owed.md) writes down instead.
* **An undo for the terminal.** A question typed at a terminal has
  scrolled away by the time it matters, and the prompt waiting for a
  line was already cancelled.

## What is not here yet

* ~~**A crash loses the message that was in flight**~~ — shipped in
  [note 13](13-a-reply-that-is-owed.md).

Continues [note 05](05-one-person-two-channels.md), which predicted the
design, and [note 07](07-four-thousand-and-ninety-six.md), which gave it
its first real instance.

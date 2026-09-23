# 13 — a reply that is owed

*Note 07 decided what a crash does to a message the bot is in the middle
of answering, and decided right: the message is lost, and the turn is
never run twice. What it left was the person on the other end with no
way to know. This note does not change the decision. It writes down that
somebody is owed an answer, so a restart can tell them.*

## The problem, as you would meet it

You message the bot *"what changed in the repo today?"*. It shows
"typing…". Then the machine it runs on reboots for an update, or the
process runs out of memory, or somebody presses Ctrl-C.

The bot comes back a minute later. Your message is not answered. It
never will be — and nothing tells you that. From your side, a lost
message looks exactly like a slow one. The only way to find out is to
wait, and after a while to guess.

## Why the obvious fix is the wrong one

"Save the message, and run it again after a restart" sounds like the
fix. [Note 07](07-four-thousand-and-ninety-six.md) argued against it,
and the argument still holds: **an agent turn is not safe to repeat.**
The turn that was cut off may have already run a tool — written a file,
sent an email, called an API — and running it again does that twice. It
certainly spent some of your daily allowance, and running it again
spends that twice too. And an answer to *"what changed today?"* that
arrives nine hours late is a wrong answer delivered with confidence.

The one person who can safely decide to run it again is you. So the job
here is not to repeat the turn. It is to **tell you it did not finish**.

## The design

When the bot takes a message and is about to start a turn, it writes a
row into a small table, `outbox.sqlite3`, in the state directory. The
row says: this agent owes a reply in this chat, to this person, for the
message that began *"what changed in the repo…"*.

**A TURN IS NEVER RUN AGAIN. TEXT MAY BE SENT AGAIN.** The row goes
through two stages, and a restart treats them differently:

1. **Taken, no reply yet.** The turn never finished. On the next start,
   the bot sends one plain message: *I restarted before I could answer
   your message from 23 Sep 17:52 UTC: "…". It will not be run again on
   its own. Send it again if you still want an answer.*
2. **Replied, not fully sent.** The turn finished and its reply was
   split into parts (a long answer can be several messages — note 07),
   but the process died partway through sending them. The reply was
   written to the row before the first part went out, so on the next
   start the parts that had not gone out are sent, after one line saying
   why.

When the last part is sent, the row is deleted. A bot that never
crashes never has anything in this table for longer than a turn.

**AT-LEAST-ONCE FOR TEXT, AND IT IS SAID OUT LOUD.** Each part is marked
sent *after* Telegram accepts it. If the process dies between those two
moments, that one part is sent twice after the restart. The other order
would lose it instead — a missing paragraph in the middle of an answer,
which is exactly the truncation note 07 split replies to avoid. A
duplicated paragraph is visible and harmless. A missing one is neither.

**THE ROSTER IS ASKED AGAIN.** If the person was taken off the actors
file while the bot was down, they are a stranger now, and strangers get
silence. The row is dropped, and the owner gets a line on stderr.

**A NETWORK THAT IS DOWN KEEPS THE ROW; A CHAT THAT REFUSES DROPS IT.**
If Telegram cannot be reached at startup, the row stays for the next
start — the person is still owed their sentence. If Telegram answers
with a refusal (they blocked the bot, the chat is gone), retrying will
never help, and a row retried at every start forever would be a startup
line nobody could make go away. That row is dropped.

## What is kept, and where

The row keeps the chat id, the sender's id, the time, and **the first 60
characters** of the message — enough for the person to recognise which
message it was, not a second copy of the conversation. The run history
(`runs.sqlite3`) already keeps the full message and reply, so this adds
nothing new about anybody.

The table belongs to the Telegram bot, not to the service. A turn that
arrives over HTTP has a caller holding the connection, and that caller
sees it drop — so the gap this closes is a chat app's. It is keyed by
agent, so two bots (each serving one agent) never pay each other's
debts.

## Receipt

A real crash. The first process took a message and started a real turn
against `qwen3.8:latest` on Ollama, and was killed with `kill -9` while
the model was thinking. The second process started on the same state
directory. The Telegram side was a stand-in server on this machine; the
bot code, the service and the model were real:

```
== first boot (killed with -9 mid-turn)
dvara · telegram · @testbot → greeter
turn started -- the model is thinking
== second boot, same state directory
dvara · telegram · @testbot → greeter
telegram: 1 reply owed from before the last stop
phone  ← 'I restarted before I could answer your message from 23 Sep 17:52 UTC:\n\n“write me a haiku about lighthouses”\n\nIt will not be run again on its own. Send it again if you still want an answer.'
```

The model was asked once, on the first boot, and never again. The
person was told, in their own words, which message went unanswered.

## Deliberately not built

* **Replaying the turn.** See above. It is the one fix that turns a lost
  message into a tool that ran twice.
* **An apology at graceful shutdown.** Ctrl-C cancels the turns in
  flight and leaves their rows, which are paid on the next start like a
  crash's. Telling people at shutdown would mean sending messages while
  the process is being asked to stop, and a restart usually comes a
  minute later anyway.
* **A time limit on what is owed.** A bot that was down for a week
  still says it did not answer. Late, but true — and the message it
  sends says when the question was asked.

## What is not here yet

* **A question left showing across a restart**, from
  [note 12](12-taken-down-everywhere-it-went.md): its message id was in
  memory, so the buttons stay until pressed.

Continues [note 07](07-four-thousand-and-ninety-six.md), which made the
decision this note keeps, and closes the bullet it left.

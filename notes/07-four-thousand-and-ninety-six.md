# 07 — four thousand and ninety-six

*Six notes were spent making this one small. The roster decides who a
chat id is ([note 05](05-one-person-two-channels.md)), the desk decides
where a question goes ([note 02](02-a-question-that-can-wait.md)), the
actors file decides what goes under the answer
([note 06](06-a-number-you-can-act-on.md)), and every one of those was
argued without a bot existing to argue about. What was left is the
medium itself: a long poll, a rate limit, and a message with a hard
bottom at 4096 characters.*

## The problem, as you hit it

A chat app looks like the easiest front end anybody ever wrote. A loop
that reads messages, a call to `deliver`, a call to `sendMessage`. Forty
lines.

Then the first long answer disappears. Not truncated — *gone*, the whole
reply, with a 400 in a log nobody was reading, because Telegram caps one
message at 4096 characters and refuses the entire thing rather than
sending what fits. Then the first escalated tool call waits out its
deadline while the person it was put to sits there pressing a button that
does nothing. Then the process is restarted during an answer and the same
message runs again, charging the same allowance twice.

None of those three announces itself. **Every failure in a channel
adapter is silent**, because the only observer is somebody looking at a
bot that has not replied, and a bot that has not replied looks the same
whatever went wrong.

## A reply has a bottom, and it is measured in UTF-16

The cap is 4096. The trap is the unit.

Telegram counts a message in **UTF-16 code units**. Python counts a
string in **code points**. For ASCII they agree, which is why this
survives every test anybody writes by hand and fails the first time an
answer has an emoji in it — or a CJK character outside the basic plane,
or one of the mathematical letters a model reaches for in a formula.
Each of those is one Python character and two of Telegram's units.

```python
def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
```

A 3000-character answer can be 4200 units and be rejected whole. So
`utf16_len` is the only measure anything here uses, and `len()` appears
nowhere near a limit.

**SPLIT, NEVER TRUNCATE.** This is the decision under the decision. A
brief cut off at the cap still reads like a finished answer — it has an
opening, it has paragraphs, it simply stops — and the citations that
would have told you it was not finished are at the bottom, which is
exactly the part a truncation removes. Whoever asked gets all of it or
can see that they did not.

The cut walks outward from the hard limit looking for a blank line, then
a newline, then a space, and **takes one only if it does not waste half a
message**. Without that floor, one space near the front of a 4000
character run of prose produces a three-word message followed by the same
problem — a splitter that makes no progress. And every cut lands on a
Python character boundary, so the arithmetic that counts surrogate pairs
can never split one in half.

The receipt rides on the **last** part. On the first of three it is a
footer in the middle of an answer; in a message of its own it is a second
notification buzz and another second of rate limiting for one short line.

## Plain text, because a parse mode makes punctuation a syntax error

Nothing here sets `parse_mode`, and that is a refusal rather than an
omission.

Markdown and HTML modes make the **model's own punctuation** into
syntax. One unmatched asterisk, one stray `_` in a filename, and Telegram
returns a 400 — the person gets nothing at all, because of a character
the model happened to type. Formatting also does not survive splitting: a
cut through a code fence renders the second half as prose.

[Note 06](06-a-number-you-can-act-on.md) guessed the other way, in
passing, when it argued that a separator was not the service's to pick:

> **And a separator is not this service's to choose.** Telegram wants
> italics on a new line; a terminal wants a plain line.

It does not. The argument — that the channel decides — was right; the
guess about what this channel would decide was wrong, and it was wrong
because the answer being formatted is written by a model rather than by
the adapter. The receipt goes out as a plain line under a blank one.

## The poll loop never awaits a turn

This one is a deadlock, and it only appears on the path nobody tries by
hand.

A turn that wants to run a tool suspends until a person approves it. The
approval is a button press. Button presses arrive through `getUpdates`.
So if the loop *awaits* the turn, the answer can only come down the pipe
the turn is holding shut — every escalated call waits out its deadline
and is refused for a silence that had somebody sitting there, pressing.

```python
for update in updates:
    offset = update["update_id"] + 1
    self._spawn(self._handle(update))     # never awaited
```

Letting go of them is safe because something else is already holding the
line: `Service` takes **one lock per session key**, so two messages in
one chat still serialize into one history. The adapter does not need to
serialize anything, and the one place it tried to would have been the
place it broke.

There is one more line than the paragraph above suggests — `await
asyncio.sleep(0)` at the top of each round. A long poll normally suspends
on the socket for twenty-five seconds and every task in the process gets
its turn for free; an endpoint that answers *instantly* (a proxy, an
error returning as fast as it can be asked for, `--poll-seconds 0`) turns
the loop into a tight run of awaits that never actually suspend, and the
answer somebody is waiting for never advances a step. One yield, against
a failure that looks like a bot gone quiet at full CPU.

## An offset is an acknowledgement, and it is spent when the message is taken

Telegram redelivers an update until you ask for one past it. Where the
offset moves is therefore a choice about what a crash does, and it is the
only durability decision in the whole adapter.

Move it *after* the turn and you get at-least-once: the process dies
mid-answer, the same message arrives again on the next boot, and it is
run a second time — spending an allowance twice and possibly running a
tool twice. **AN AGENT TURN IS NOT IDEMPOTENT**, so this takes the other
one. The offset moves when the update is taken, a crash loses the
message, and the person who watched their message go unanswered is the
one participant in this whole system who can simply send it again.

The same argument decides the backlog. A bot that was down for a day
comes up holding a day of messages; answering "what changed today?" nine
hours late is a wrong answer delivered confidently, and a queue of ten
spends ten turns of somebody's allowance in one breath. So the default is
to take the offset past everything held and say so:

```
telegram: skipping the messages that arrived while this was down
(--catch-up answers them instead)
```

`--catch-up` is there for the owner who knows their backlog is worth
running. The line is there because **a message that silently evaporates
is indistinguishable from a bot that is broken** — and the owner is the
only person who can tell the difference.

## An approval is a button, because it cannot be a message

[Note 01](01-the-door.md) built the lock, and [note
02](02-a-question-that-can-wait.md) named the consequence: a turn holds
its conversation's lock while it waits for a person, so typing "yes" into
the thread queues that message *behind the very turn it was meant to
release*, where it sits until the deadline passes.

A chat app has exactly one other affordance, and it is the right one. The
question goes out with two inline buttons; the press arrives as a
`callback_query`, which is not a message, does not touch the session
lock, and lands on `AskDesk.answer` down a path the turn is not holding.

Four details, each of which is a way to get this wrong:

* **Who pressed decides who answered**, resolved through the roster like
  any other inbound identity — not whose chat it is sitting in. The desk
  already insists on both the id and the actor, so a question forwarded
  to somebody else is a press that resolves nothing.
* **The question goes to the person, not to the thread.** `ask.to` is
  their own chat with the bot, put there by note 05 so this module needs
  no table of its own. A turn running in a group still asks them
  privately.
* **The buttons are replaced once it is decided.** A pair that stays
  pressable invites a second press that can do nothing, and the chat is
  the only place this decision is written down where the person who made
  it will look again.
* **A question is elided, never split.** The reply is prose and survives
  being cut; a decision does not. An oversized summary keeps both ends —
  the verb at the front and the target at the end are the two parts
  somebody is actually deciding about.

## Rate limits, and the wait that is really a failure

Telegram publishes one message per second per chat and enforces it with a
429 carrying `retry_after`. Both halves are handled and they are
different problems.

A **minimum gap between two sends into one chat**, with one lock per
chat, so that a split reply does not become four hundred milliseconds of
flooding — and so two tasks cannot interleave their chunks and deliver
one person two half-answers shuffled together. A turn-shaped bot sends
one message per turn and never notices this; the split reply is precisely
the case that does.

And `retry_after` obeyed **as an instruction, up to a ceiling**. A flood
wait of five minutes is longer than the deadline on the question it was
going to deliver, so sitting through it produces a delivery that arrives
after the thing it was delivering has already been refused. **A WAIT
LONGER THAN THE DEADLINE IS NOT A WAIT, IT IS A FAILURE** — and reporting
it is better, because note 02 already knows what to do with a delivery
that failed:

> **A DELIVERY THAT FAILS IS A DENIAL, IMMEDIATELY.** If the notifier
> raises [...] there is nobody waiting at the other end and the deadline
> would just be two silent minutes.

The one refusal that is *not* retried at all is the 409. Two pollers on
one token do not collide, they **split**: half of somebody's messages
answered by a process nobody remembers starting. That is fatal at
startup, with a sentence saying so.

## One bot is one agent, and a stranger gets silence

Two decisions about what a bot is allowed to decide, which is almost
nothing.

**A token is an identity.** It has a name, a picture, an @handle somebody
types. Hanging the whole roster off one of them means a person prefixing
every message forever, and it means dvara owning a command dialect. A
second agent is a second token from BotFather and a second process.
`/start` is handled here — it is the literal text of the button a person
presses to open a chat, and forwarding it to a model produces an answer
to a question nobody asked — and it is the only command there is.

**An unknown identity gets silence.** The roster's refusal is polite and
says nothing about who else exists, but saying it to every stranger who
finds the bot makes a service out of the refusal. The line goes to the
owner's own terminal instead, because the owner is the only person who
can act on it, and it says exactly what to paste:

```
telegram: 5551212 messaged and is not in the actors file
(add [[actor.NAME.channel]] kind="telegram" id=5551212)
```

## What it looks like

Against `qwen3.8-64k:latest` on Ollama, reached through the
OpenAI-compatible endpoint so that a price exists to be charged (the rate
is a stand-in; the tokens, the turns and the splitting are real). The
`[...]` frames are what the chat received.

One person on the list, one person not:

```
$ TELEGRAM_TOKEN=... dvara --root ./agents --actors ./actors.toml \
      --provider openai --model qwen3.8-64k:latest \
      telegram --agent greeter
dvara · telegram · @yantra_demo_bot → greeter
telegram: 5551212 messaged and is not in the actors file
(add [[actor.NAME.channel]] kind="telegram" id=5551212)

  ┌─ message to chat 8675309 (73 chars, 73 UTF-16 units)
  │ I'm the doorkeeper's greeter, here to meet you at the threshold.
  │
  │ $0.0000
  └─
```

One message out, and the stranger got nothing. The receipt is note 06's,
on its own line under a blank one, because this channel turned out not to
want italics after all.

A 10,224-character answer, from a package whose prompt asks for one:

```
  ┌─ message to chat 8675309 (3229 chars, 3229 UTF-16 units)
  │ The solar system contains eight planets, all orbiting the Sun in a…
  │
  │ Mercury is the smallest planet and the closest to the Sun, sweepin…
  │
  │ Venus is often called Earth's sister planet because the two are si…
  └─

  ┌─ message to chat 8675309 (3245 chars, 3245 UTF-16 units)
  │ Earth is the only planet known to harbor life, a distinction enabl…
  │
  │ Mars, the fourth planet, is a small, cold, rust-colored world whos…
  │
  │ Jupiter, the fifth planet, dwarfs everything else in the system: i…
  └─

  ┌─ message to chat 8675309 (3750 chars, 3750 UTF-16 units)
  │ Saturn, the sixth planet, is famous above all for its spectacular …
  │
  │ Uranus, the seventh planet, was the first planet discovered with a…
  │
  │ Neptune, the eighth and farthest known planet, was discovered in 1…
  │
  │ Pluto, long considered the ninth planet, was reclassified in 2006 …
  │
  │ $0.0019
  └─
```

Three messages, each one cut at a paragraph break rather than at
character 4096, and the receipt on the last of them. Nobody had to know
the answer was going to be long.

And the loop that was the reason for all of it — `--ask`, the `scribe`
package, and a question that a person presses:

```
  ┌─ message to chat 8675309 (61 chars, 61 UTF-16 units)
  │ scribe wants to run write_file:
  │
  │ NEW FILE haiku.txt (2 lines)
  │ [approve] [refuse]
  └─
  ← pressed: y:Rbo_PR_OLYsQsVEMGMm86A
  ← toast: approved
  ← the question now reads: ...— approved

  ┌─ message to chat 8675309 (180 chars, 180 UTF-16 units)
  │ scribe wants to run write_file:
  │
  │ --- a/haiku.txt
  │ +++ b/haiku.txt
  │ @@ -1,2 +1,2 @@
  │  Door cracked on the hinge,
  │ -and moonlight steps through slow
  │ +and moonlight steps through so slow
  │ [approve] [refuse]
  └─
  ← pressed: y:mKQQ2a3jXsdJu1Zv32Pb1g
  ← toast: approved
  ← the question now reads: ...— approved

  ┌─ message to chat 8675309 (99 chars, 99 UTF-16 units)
  │ Wrote it to haiku.txt:
  │
  │ > Door cracked on the hinge,
  │ > and moonlight steps through so slow
  │
  │ $0.0011
  └─
```

The summary is Yantra's, not this adapter's — `NEW FILE haiku.txt (2
lines)` the first time and a diff the second, so what the person approves
is what runs. The turn suspended twice, in a process that went on polling
throughout, and the presses came back down the pipe it never stopped
reading.

## What is deliberately not here

* **No streaming, and no message that edits itself.** Unchanged from
  [note 01](01-the-door.md), and the typing indicator is what replaces
  it: renewed every four seconds for as long as the turn runs, which
  costs one API call and says the one thing a person needs to know.
* **No `parse_mode`.** Argued above. The cost is that code in an answer
  arrives as plain text, and the alternative cost is the answer arriving
  as nothing.
* **No answering by message.** "yes" typed into the chat is a message,
  and a message queues behind the turn it was meant to release. The
  buttons are not a nicety.
* **No commands but `/start`.** No `/new` to start a fresh thread, no
  `/agent` to switch packages. Both are real things to want and both are
  a command dialect, which is a thing to design rather than to accrete.
* **No groups, deliberately untested.** A chat id is a thread and a user
  id is a person, so a group technically works; whether a bot that
  answers everyone in a room is a thing anybody wants is a question this
  note does not have an answer to.
* **No webhook.** A long poll needs no public address, no TLS and no
  reverse proxy, which is the difference between running this on a
  laptop and not running it at all.

## What is not here yet

* **A question answered on one channel still sits on the others.** The
  button press edits the message it arrived on; the same question
  delivered to a second channel is untouched, which is [note
  05](05-one-person-two-channels.md)'s "withdrawing a delivered question"
  exactly as it was left. It now has one real instance rather than a
  hypothetical one.
* **A crash loses the message that was in flight.** Argued for above, and
  still a loss. A person who gets no reply has no way to tell it from a
  slow turn except by waiting.
* ~~**Nothing records which channel a question went out on**~~ -- a
  `Run` answers "where were you when you approved this?" as of
  [note 08](08-what-the-turn-actually-did.md), and a press on one of
  these buttons writes `telegram` into it.
* ~~**`dvara serve` and `dvara telegram` are two processes over one state
  directory.**~~ Settled in
  [note 09](09-a-process-you-walk-away-from.md), and not the way this
  bullet assumed: the SQLite contention was the symptom, and the disease
  was a split ask desk and a split set of conversation locks. Two
  processes are refused; `dvara serve --telegram AGENT` runs both jobs in
  one.
* ~~**A channel identity still cannot be added without a restart**~~ --
  shipped in [note 09](09-a-process-you-walk-away-from.md), which this
  note is the reason for.
* **Locks are still never evicted**, unchanged from notes 01–06.

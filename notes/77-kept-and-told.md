# 77 — Kept, and told

## The problem, as you would meet it

The owner, on Sarathi's home page, told the agent their drive to the
airport takes 12 minutes, and then their home address. Both were kept.
Neither was ever mentioned again, and the owner was sure nothing had
been remembered. On Telegram they were used to seeing *"I noticed this
about you … /remember 1 2"*, and this time that never came.

Dvara's run log told the story. The owner runs on `yolo`, so the
model's `remember` ran without asking (Yantra's notes/100: it asks
first, unless the person's mode says not to ask). The address went in
by a third road: the memory server's own `store_memory` tool, which the
model could still see (Yantra's notes/102 now hides it). Thirty quiet
minutes later the look back ran, found both facts already kept, and
said nothing, because a look back that finds nothing new sends nothing
(note 39). Three ways to write a memory, and none of them showed the
person what was written.

## The rule: follow the permission mode, always say it

Whether `remember` asks first is the person's permission mode, as for
every other tool. On `ask` it asks. On `yolo` it doesn't. **Whether
they hear about it is not up to the mode.** A write that went through
unasked is never a silent one. Two places say it.

**Under the answer.** Yantra's `remember` tool records what it kept
(`memory.kept`). Dvara takes that list after every turn and adds one
line under the answer, with the way to take it back:

```
(Kept about you: Lives about a 12-minute drive from RDU airport (Raleigh–Durham), a proximity that shapes airport pickup/timing. -- /memory forget 1 to undo.)
```

The line goes everywhere the answer goes: Telegram, Sarathi's page,
and the puck through Vaani. The run records it too (`Run.kept`, a new
column in `runs.sqlite3`).

**At the look back.** The quiet look back (note 39) and the one at
`/new` (note 38) used to fall silent when they found nothing new. Now,
when the model kept something during the conversation, the look back
names those things instead:

```
greeter: Looked back over our conversation: nothing new to offer. Already kept while we talked:
- Lives about a 12-minute drive from RDU airport (Raleigh–Durham), a proximity that shapes airport pickup/timing.
(/memory lists them with their numbers.)
```

* **ONCE.** It names only what was kept since the conversation's last
  look back (`RunStore.kept_since_look_back`). The look back is a run
  of its own, so the next quiet spell starts after it.
* **STILL ONLY NEWS.** A look back that found nothing new, in a
  conversation where nothing was kept, still sends nothing.

## Not offered what was just kept

In a turn where the model keeps a fact, Yantra may also notice the same
fact on the side (`memory.pending`, note 38), worded differently. The
first live run showed both lines under one answer: *Kept about you:
Lives near RDU …* and *I noticed a thing about you … /remember*, for
one fact. A candidate is dropped when it is about the same as something
the turn kept (`remembering.about_the_same`). That is looser than
`same`: "Lives near RDU, a 12-minute drive" and "Lives approximately 12
minutes' drive from RDU" have different heads, but share most of their
words. Dropping one by mistake costs little: the look back reads the
whole conversation and can offer it again.

## Receipt

A scratch Dvara with its own state folder, the `greeter` package with
`[memory] via = "local"`, the owner on `yolo`, against `qwen3.8:latest`
on Ollama. One message, then the quiet look back run as if 31 minutes
had passed:

```
ANSWER:
Noted — I'll keep the 12-minute RDU drive in mind when it comes to pickups.

(Kept about you: Lives about a 12-minute drive from RDU airport (Raleigh–Durham), a proximity that shapes airport pickup/timing. -- /memory forget 1 to undo.)

LOOKED BACK OVER 1; TOLD:
greeter: Looked back over our conversation: nothing new to offer. Already kept while we talked:
- Lives about a 12-minute drive from RDU airport (Raleigh–Durham), a proximity that shapes airport pickup/timing.
(/memory lists them with their numbers.)
```

The run before the `about_the_same` filter had an extra
*(I noticed a thing about you worth remembering …)* line under that
answer, for the same fact.

## What the tests hold

* A turn on `yolo` that calls `remember` gets the *Kept about you*
  line, and no *I noticed* line.
* The quiet look back after it names the kept fact once, and the next
  one doesn't name it again.
* A look back with nothing new and nothing kept still sends nothing.
* A noticed candidate worded differently from a kept fact is dropped;
  one about something else is still offered.

## What is not here yet

* **The page drawing the line as its own row.** Sarathi's chat shows
  it as part of the answer text. A chip beside the tools would be
  tidier, with **Undo** as a button.
* **Vaani reading it more briefly.** The puck speaks the whole line,
  memory number included.

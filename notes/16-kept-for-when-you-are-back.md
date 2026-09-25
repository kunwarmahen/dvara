# 16 — kept for when you are back

*[Note 02](02-a-question-that-can-wait.md) let the service ask a person
before a tool call, and decided that silence refuses. Yantra's note 88
then built a turn that can stop without an answer and carry on with one.
It said the queue on top belonged to a service. This is that queue.*

## The problem, as you would meet it

You let `scribe` ask before it writes, with a two-minute deadline. You
ask it to write two files, then get pulled into a meeting. The question
reaches your phone and nobody answers it. Two minutes later the call is
refused, and the model says so sensibly:

> Nobody answered in time, so neither file was written. Let me know when
> you're back and I'll try again.

An hour later you are back, and you have to ask again. The model plans
again, reads again, and asks for the same two writes a second time. The
refusal was correct. It just threw away a turn that was one "yes" from
finished.

## Silence may now wait

```bash
dvara --ask --ask-timeout 120 --on-timeout hold ... say --actor owner --agent scribe "..."
```

`--on-timeout` is what an unanswered question comes to. `deny`, the
default, is note 02 unchanged. `hold` stops the turn where it is:

* calls already approved in the same batch have run;
* calls refused in the same batch got their refusals;
* the unanswered ones are **held**. Nothing past them runs, the model is
  told nothing, and the reply says what is waiting:

```
Nobody answered in time, so this is waiting for your approval and nothing past it has run:
  write_file: NEW FILE a.txt (1 lines)
  write_file: NEW FILE b.txt (1 lines)
Answer it when you are back and the turn carries on from here.
```

**SILENCE STILL NEVER APPROVES.** `--on-timeout allow` is refused, for
note 02's reason: a deadline that approved would make an absent owner the
most permissive setting in the system.

**ONE DEADLINE PER TURN, NOT ONE PER CALL.** A batch is asked one call at
a time. Once one question in a turn has gone unanswered, the person is
evidently away, so the rest of the batch is held without being asked.
Otherwise two writes would wait out two deadlines before the turn could
stop.

**A SPENT DAY HOLDS TOO.** A person whose day of waiting is used up
([note 14](14-a-days-worth-of-being-asked.md)) is not asked either way.
Under `deny` the call is refused; under `hold` it is kept for when they
are back.

## A queue that survives a restart

Note 02 kept questions in memory on purpose:

> A persisted question would outlive the only thing that could act on it,
> which is not durability. It is a lie with a timestamp on it.

That is still true of a question. A question is a turn standing there
waiting, and no turn survives a restart. A **held** turn is the opposite
case. Nothing is standing there any more: the turn has *ended*, and what
can act on it is the conversation's saved checkpoint, which Yantra writes
with the hold inside it. So held turns go in a table (`holds.sqlite3`),
and a restart is a non-event. The receipt below stops the service between
the hold and the answer.

**THE CHECKPOINT IS THE TRUTH; THE TABLE IS ITS INDEX.** What is waiting,
and what already ran beside it, lives in the checkpoint. A row in the
table says only who may answer, what to show them, and where the turn is
filed. When the two disagree (a newer message set the hold aside, say)
the checkpoint wins, and the row is dropped the moment anyone tries to
use it.

**ONE HELD TURN PER CONVERSATION.** A conversation has one history, so it
can only be stopped in one place.

## Answering it

Three doors, one method underneath (`Service.resume`):

```bash
dvara held                                   # what is waiting, and how old
dvara resume ID --actor owner --approve      # or --refuse [REASON]
dvara resume ID --actor owner --call CALL=yes --call "CALL=leave b.txt alone"
```

```
GET  /holds?actor=owner
POST /holds/ID   {"actor": "owner", "answers": {"call_a": true, "call_b": "leave b.txt alone"}}
```

In Telegram, the reply that says the turn is waiting carries two buttons,
**approve all** and **refuse all**. A press carries the turn on, and the
rest of the answer arrives in the conversation's own chat: the group, if
that is where the turn started.

An answer is one entry per waiting call. `true` runs it. `false` refuses
it. A string refuses it in the person's own words, which the model reads
([Yantra's note 56](https://github.com/kunwarmahen/yantra/blob/main/notes/56-not-like-that-like-this.md)).
Over HTTP only a JSON `true` approves, for the reason `POST /asks/{id}`
insists on a boolean: the string `"yes"` is a refusal whose reason is
"yes", never a yes.

**ONLY THE PERSON IT RAN AS.** A hold id is unguessable, and answering
still requires naming the actor, the same two checks as a question. A
held turn lasts a day instead of two minutes, which is more time for an
id to be forwarded, not less.

**A WRONG ANSWER COSTS NOTHING.** An answer missing a call, naming a call
that is not waiting, or trying to edit a call's arguments is refused
before anything happens, and the hold is still there to answer properly.
So is an answer from somebody whose money for today is spent: a resume is
a new turn, it is checked against today's allowance like any other, and
the hold waits for tomorrow.

**THE ROW GOES BEFORE ANYTHING RUNS.** Resuming deletes the row and then
runs the approved calls. A crash in between loses the hold (you are told
nothing ran and ask again), where the other order could run a shell
command twice. [Note 13](13-a-reply-that-is-owed.md) made the same
choice for the same reason: an agent turn is not idempotent. Two answers
racing for one hold are settled under the conversation's lock. One
carries it on, and the other is told it was answered a moment ago.

**A RESUME IS ITS OWN RUN.** It has its own budget and its own row, with
`resumes` naming the held run. `dvara runs` shows both:

```
owner/scribe  end_turn   $0.0000  "Write 'one' to a.txt and 'two' to b.txt. …"
              resumes efa292db101a
              write_file[asked:terminal] -> write_file(refused)[asked:terminal]
owner/scribe  held       $0.0000  "Write 'one' to a.txt and 'two' to b.txt. …"
              write_file(held) -> write_file(held)  [waited 8s]
```

A held call is not a refused one. `dvara case` does not suggest
forbidding it ([note 08](08-what-the-turn-actually-did.md)), because it
was not turned away; its answer is on the run that resumes it.

## Or not answering it

**A NEW MESSAGE MEANS "NEVER MIND".** Sending something else in the same
conversation instead of answering is allowed. Yantra answers the waiting
calls "set aside, never ran" as the new turn begins, and the queue drops
the row so nobody can approve into a conversation that has moved on. A
message in a *different* conversation leaves it alone.

**IT EXPIRES.** A `write_file` approved a week late writes over whatever
is at that path now, and nothing can check whether the world moved in
between. So `dvara held` and the resume both say how old the turn is:

```
held 30s ago. What you approve runs against things as they are now, not as they were then.
```

After a day (`--hold-for SECONDS` to change it) the hold can no longer
be answered. Expiry is lazy: a row is dropped when it is listed or used,
not by a timer, because nothing is waiting for it to go.

**A HOLD OUTLIVES THE FLAG.** The table is opened whether or not the
service holds. A turn held yesterday by a service started with
`--on-timeout hold` can be answered today by one started without it.
Whether silence holds is a policy for new questions; it is not a way to
strand old ones.

## Both roads

Holding happens in the gate and the loop, before any tool runs, and
works the same whichever model asked for the call. What depends on the
model is the answer after a resume: it reads results for calls it asked
for a while ago, one of them refused in a person's own words, and has to
make sense of them. `qwen3.8:latest` did, in the receipt below, without
being told anything more.

## What was deliberately not built

**Editing a call's arguments on resume.** Yantra's resume accepts edited
arguments, and its browser page offers them beside a diff. A chat button
or a one-line command is not a place to review an edited write, so the
service takes yes, no, or a reason, and refuses anything else.

**Per-call buttons in Telegram.** Answering three calls separately would
mean the bot collecting presses and holding state of its own until the
last one. "Approve all" and "refuse all" cover the common case; the
terminal and HTTP answer call by call.

**Taking stale buttons down.** A held turn answered from the terminal
leaves its buttons showing in the chat. Pressing one says it is no longer
waiting. Removing them would mean keeping Telegram's message ids across a
restart, which [note 12](12-taken-down-everywhere-it-went.md) chose not
to do for questions.

**Reminders.** A held turn does not nag. The reply already said it was
waiting, and a second message an hour later is a thing a person turns
off.

## What is not here yet

* **Being told about expiry.** A hold that expires disappears from the
  list without a word to the person. They find out only if they come
  back and press a button that no longer works.

## Receipt

A fresh state directory, the `scribe` example package, `qwen3.8:latest`,
an eight-second deadline, and nobody at the keyboard (`sleep` holds the
input open and types nothing). Every command below is its own process,
so the service stops between each of them.

```
$ sleep 40 | dvara --ask --ask-timeout 8 --on-timeout hold ... \
    say --actor owner --agent scribe \
    "Write 'one' to a.txt and 'two' to b.txt. Issue both write_file calls together in one go."

scribe wants to run write_file:
  NEW FILE a.txt (1 lines)
approve? [y/N]
  dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor owner --approve   (or --refuse, or --call ID=yes|no|REASON)
[held · $0.0000 · 587in/91out · run efa292db101a]
Nobody answered in time, so this is waiting for your approval and nothing past it has run:
  write_file: NEW FILE a.txt (1 lines)
  write_file: NEW FILE b.txt (1 lines)
Answer it when you are back and the turn carries on from here.
```

One question went up and was taken down after eight seconds. The second
write was never asked. Both are waiting, in a process that has exited:

```
$ dvara held
VamBTs5Z_X3GzDPNY6UYeQ  owner/scribe  thread cli  run efa292db101a
    call_fq5canuu  write_file: NEW FILE a.txt (1 lines)
    call_b6dmlw42  write_file: NEW FILE b.txt (1 lines)
    held 30s ago. What you approve runs against things as they are now, not as they were then.
```

Somebody else, then half an answer. Both are refused and neither uses
the hold up:

```
$ dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor guest --approve
error: held turn VamBTs5Z_X3GzDPNY6UYeQ is not yours to answer

$ dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor owner --call call_fq5canuu=yes
error: resume() takes one answer per held call; unanswered: call_b6dmlw42
```

Then both, one approved and one refused with a reason:

```
$ dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor owner \
    --call call_fq5canuu=yes --call "call_b6dmlw42=leave b.txt alone, a.txt is enough"
held 39s ago. What you approve runs against things as they are now, not as they were then.
[end_turn · $0.0000 · run 2d1bb9f71e8c]
a.txt written with 'one'. b.txt was explicitly refused — a person said to leave it alone, so I won't retry.

$ dvara held
nothing is waiting for an answer

$ dvara runs
2026-09-25 03:16  owner/scribe  end_turn         $0.0000  "Write 'one' to a.txt and 'two' to b.txt. Issue b"
                  resumes efa292db101a
                  write_file[asked:terminal] -> write_file(refused)[asked:terminal]  [answered from terminal]
2026-09-25 03:15  owner/scribe  held             $0.0000  "Write 'one' to a.txt and 'two' to b.txt. Issue b"
                  write_file(held) -> write_file(held)  [waited 8s]
```

Only `a.txt` exists in the conversation's workspace.

`533 passed` (was 494).

# 14 — a day's worth of being asked

*[Note 06](06-a-number-you-can-act-on.md) gave each person a daily
allowance of money. This note gives them the other allowance a service
owes somebody it puts questions to: how long it may keep them waiting on
those questions in one day. Yantra left that open on purpose, in its
note 51, because it needs a store and an identity. This service has
both.*

## The problem, as you would meet it

A guest can reach your `scribe` agent, and you have let the service ask
them before it writes a file. They send a message, then go to dinner.

The agent tries to write. The question goes to their phone and waits
thirty seconds for an answer that does not come. The agent tries again,
and that waits another thirty. Their next message, sent hours later from
the train, starts another turn, and it asks again. Nothing ever says
"this person is not answering today; stop asking".

Each question has a deadline ([note 02](02-a-question-that-can-wait.md)).
Yantra added a deadline for a whole turn (its note 51,
`with_wait_budget`). Nothing puts a limit on a person's *day*.

## The design

```toml
[actor.guest]
permissions      = "ask"
max_wait_per_day = 300      # seconds this person may be kept waiting, a day
```

Every turn now records how long it spent waiting on answers
(`waited_seconds` on the run). Before each turn the service adds up
today's waiting for that person, midnight UTC to midnight UTC, and
subtracts it from their limit. That is exactly how the money allowance
is read ([note 06](06-a-number-you-can-act-on.md)), from the same table
and in the same place.

**TIME WAITED, NOT QUESTIONS ASKED.** A question answered in two seconds
cost the person two seconds. A question they never saw cost the full
deadline, and that is the case this exists for. Counting questions would
treat the quick yes and the unanswered ping as the same thing. Counting
time means someone who has gone to bed stops being asked once their
silence has used the day up.

**WHAT IS LEFT BECOMES THE QUESTION'S DEADLINE.** With 5 seconds left
today and a 15-second ask timeout, the question waits 5. When it runs
out, the model is told the day ran out, not that the person was silent
for 15 seconds:

```
write_file was denied: nobody answered in the 5 second(s) left of today's allowance for waiting on this person, which comes back at 00:00 UTC. This is silence, not a refusal.
```

It can only shorten a question's deadline, never lengthen it. The ask
timeout is the owner's word on how long any one question may wait.

**ONCE IT IS SPENT, NOBODY IS ASKED.** The question is not put at all,
so no notification goes out that nobody will wait for:

```
write_file was denied: nobody was asked. The person this conversation would ask has been kept waiting on questions for as long as this service allows in one day; that comes back at 00:00 UTC. ...
```

## The one decision that mattered: where to check it

Yantra already had `with_wait_budget`, a wrapper that spends down a
turn's allowance. The obvious build was to hand it what is left of the
day, the same trick the money allowance plays with Yantra's `Budget`.

It would have been wrong. **Once its allowance is gone, that wrapper
refuses every call, without asking the gate inside it**, including calls
nobody was ever going to ask about: a `read_file`, or a write a standing
rule ([note 03](03-standing-answers.md)) allows. For one turn that is a
small price. For a day it means an agent cannot even read a file until
midnight because its person was slow to answer this morning. That would
punish the person, not limit the waiting.

**SO IT IS CHECKED IN THE ONE PLACE A QUESTION IS PUT** (`gate.put`).
By the time a call reaches it, the rung and the rules have already
decided that a person is needed. Read-only calls, calls a rule allows,
and everything under `yolo` never get there, so the limit cannot touch
them. The receipt below shows it: on the second turn, `read_file` ran
and only `write_file` was refused.

## Not a refusal of the turn

A spent money allowance refuses the whole turn before it starts, because
nothing can run without spending. A spent waiting allowance does not:
the turn runs, and everything that needs nobody still works. Only the
questions stop.

## Both roads

Nothing here depends on the model. The receipt is a local run on
`qwen3.8:latest`, where money is free and only this allowance could ever
bite.

## What was deliberately not built

**No reservation across concurrent turns.** Two turns for one person
running at once both start from the same figure, and together they can
overspend it. The money allowance has the same gap
([note 06](06-a-number-you-can-act-on.md)). Closing it needs a
reservation this service does not keep.

**No limit counted in questions.** See above: the unanswered ping is the
case that matters, and a count cannot tell it from a quick yes.

**No change to Yantra's wrapper.** For a single turn, refusing
everything once the allowance is gone is a defensible rule, and its note
51 argues for it. A day is a different unit.

## What is not here yet

* ~~**The waiting is not in the receipt line.**~~ Shipped in [note 15](15-where-the-waiting-shows.md):
  under a turn that waited. Was: `receipt = "remaining"` showed money
  left only.
* ~~**`dvara runs` does not print `waited_seconds`.**~~ Shipped in
  [note 15](15-where-the-waiting-shows.md): `[waited 10s]` on the turn's line.

## Receipt

A scratch actors file, `scribe` from `examples/agents`, `qwen3.8:latest`,
a 15-second ask timeout, and a day of 20 seconds. Standard input is a
pipe that stays open and never sends anything: a person who is not
there.

```toml
[actor.owner]
permissions      = "ask"
max_wait_per_day = 20
```

```
$ sleep 120 | dvara --ask --ask-timeout 15 ... say --actor owner --agent scribe "Write the word hello into a file called hello.txt"

scribe wants to run write_file:
  NEW FILE hello.txt (1 lines)
approve? [y/N]
scribe wants to run write_file:
  NEW FILE hello.txt (1 lines)
approve? [y/N] [end_turn · $0.0000 · 2006in/597out · run 5a45ae450daf]
I couldn't write the file, because both attempts were denied only by silence — nobody answered within the wait allowance, and that allowance runs out for the rest of the day (it resets at 00:00 UTC) — so it's not that you said no, just that nobody was there to say yes. ...
```

The first question waited its 15 seconds. The second got the 5 left of
the day. Then a second turn, which asked nothing: no prompt was printed.

```
$ sleep 120 | dvara --ask --ask-timeout 15 ... say --actor owner --agent scribe "Read hello.txt if it exists, otherwise write hello into it"
[end_turn · $0.0000 · 3500in/357out · run b131279d6263]
The file doesn't exist yet, and I tried to write it, but the write was blocked again by timeout — nobody was available to approve it, and the daily wait window is exhausted until 00:00 UTC. ...

$ dvara ... runs
2026-09-24 15:10  owner/scribe  end_turn         $0.0000  'Read hello.txt if it exists, otherwise write hel'
                  read_file -> write_file(refused)
2026-09-24 15:07  owner/scribe  end_turn         $0.0000  'Write the word hello into a file called hello.tx'
                  write_file(refused)[asked] -> write_file(refused)[asked]
```

And the ledger:

```
5a45ae450daf  waited_seconds 20.005  write_file timeout (asked), write_file timeout (asked)
b131279d6263  waited_seconds 0.0     read_file ran, write_file out_of_time
```

The second turn's `read_file` ran; only the question was refused. The
model paraphrased that refusal as "blocked again by timeout", which is
not what its sentence said (it said nobody was asked). The code is
right in the ledger. The model's summary blurred the two, which is a
reason the code, not the sentence, is what gets counted.

`489 passed` (was 475).

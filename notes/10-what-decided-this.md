# 10 — what decided this

*Three questions an owner asks months later, when the thing that could
have answered them has gone: which rule stopped that, where were you when
you approved this, and which version of the agent was that? All three
were the last entries on the "not here yet" list, and all three turned
out to be one seam and one column.*

## The question you were never asked

[Note 03](03-standing-answers.md) ended with a gap it named precisely:

> **Nothing counts what the rules are doing.** An owner who wants to know
> which standing yes actually saved them a question, or which deny has
> never fired since the day it was written, has no way to find out.

The asymmetry is the whole problem. **A deny announces itself** — the
model is told, the turn changes shape, the answer is different. **An
allow is invisible by construction**: the call simply runs, exactly as it
would have if you had been woken up and said yes. That is the rule doing
its job perfectly and leaving no trace of having done it.

So a policy file fills up. Some of its rules are saving you a question a
day; some have never matched anything since the afternoon you wrote them,
and there is no way to tell which is which by looking. A rule that has
never fired is not neutral — it is a line you will read every time you
edit the file, and reason about, and be reluctant to delete.

```
$ dvara rules
policy.toml  ·  3 rule(s)  ·  calls settled over the last 30 days
      2  allow  write_file path=haiku.txt
      1  deny   write_file path=*.env|*/.ssh/*
      ·  allow  bash command=git status|git diff

  ·  = never matched a call in this window.
```

**Counted over calls, not turns.** A rule that saved one question in a
turn and one that saved nine did not do the same amount of work, and
"which standing yes is earning its place" is the question this exists to
answer.

### A rule is named by what it says

To count a rule you have to be able to name one, and the obvious name is
wrong. An index into the file is what the error messages use, and it is
exactly wrong here: insert a rule at the top and every count below it
silently moves to a different line.

So a rule's id is a hash of what it **says** — tool, verdict, argument
patterns:

```python
canonical = json.dumps([self.tool, self.verdict, sorted(...)])
return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
```

**A RULE YOU EDIT BECOMES A DIFFERENT RULE WITH A COUNT OF ZERO**, and
that is correct rather than a limitation. You changed the standing
answer; the old one's history belongs to what it used to say. `reason` is
deliberately outside the hash — rewording the sentence a model reads does
not make it a different standing answer.

The report says this out loud, because a zero beside a rule you have had
for a year is otherwise alarming rather than informative.

## Where were you when you approved this

[Note 08](08-what-the-turn-actually-did.md) recorded the doors a *turn's*
answers came through and could not go finer. Its stated reason was that
two escalations in one batch are gated concurrently — **and that was
wrong**, in a way worth correcting rather than quietly fixing.

Yantra gates a batch **sequentially**, on purpose:

> The gates are awaited one at a time ON PURPOSE. A gate that reaches a
> person can take minutes, and three questions arriving at once in a chat
> window is not a permission prompt, it is a pile.

Execution is concurrent; *gating* is not. So the Nth decision does belong
to the Nth call, and a host could simply count.

Which makes the real argument better than the one I had. **NOT BECAUSE
ORDER WOULD NOT WORK — BECAUSE IT WOULD.** Counting rests on three
properties of somebody else's loop: gates sequential, one gate per call,
results in submission order. None of them was ever promised to a caller.
A drift in any of them does not raise — it files one person's approval
against a different call, which is the worst shape a permission record
can take, because it is wrong and confident and silent.

So the framework grew the seam instead, argued on its own terms:

```python
#: The id of the ``ToolCall`` being decided, so a gate's answer can be
#: matched to the ``ToolExecuted`` it produces.
call_id: str = ""
```

Defaulted, not required: a request built by a test or by a host driving a
gate directly is still a valid request, and `""` reads as what it is.

Now the two halves of a turn meet in the middle. The loop knows *what
happened* — it emits a `ToolExecuted` per call. The gate knows *why* —
it wrote a rule id or a channel against the call's id. Neither knows
both, and the join is a string neither of them had to agree about.

```
write_file[rule:c0a621fc] -> write_file[rule:c0a621fc] -> read_file
write_file(refused)[rule:eabd9e26]
```

**ONLY THE INTERESTING ONES.** A call the rung simply allowed — a
read-only tool, or anything at all under `--yolo` — records nothing.
That is the ordinary case and most of them, and a field saying "nothing
in particular decided this" nine times in ten is a field nobody reads.
Absent means the rung, and the ledger above shows it: `read_file` has no
bracket after it.

`Run.answered_from` survives as the per-turn summary it always was, but
it is now **derived** from the per-call record rather than collected
beside it. One source of truth, read two ways, so the two cannot come to
disagree.

## Which version of the agent was that

§11.2 was the last of the design doc's five open questions:

> **A package edited on disk changes a live thread's next turn**, since
> agents are built per turn. Desirable (fix a prompt, the fix applies) or
> alarming (a conversation changes personality mid-sentence)? Pinning a
> package version per thread is the alternative, and it is a store column
> plus a lot of explaining.

Both readings are true, which is why it sat open for ten notes. It is
settled here, and not by choosing between them.

**THE EDIT APPLIES. THE ALARMING PART WAS NEVER THE CHANGE — IT WAS THAT
NOTHING SAID IT HAPPENED.** A conversation that changes personality
mid-sentence is frightening because the person watching has no way to
connect it to the thing you did on Tuesday. Given a line in the ledger it
stops being a mystery and becomes a fact:

```
$ dvara runs
2026-09-18 03:18  owner/scribe  end_turn   $0.0006  'read haiku.txt back to me'
                  read_file
2026-09-18 03:18  owner/scribe  end_turn   $0.0007  'write API_KEY=hunter2 into…'
                  scribe changed after this turn: 0.1.0 -> 0.2.0
                  write_file(refused)[rule:eabd9e26]
```

One column, `agent_version`, and a line printed only when it differs from
the next turn **in the same conversation**. Per conversation and not per
agent: two threads sitting at different versions is ordinary — one of
them simply has not had a turn since the edit — and flagging that would
be noise on every listing forever.

Pinning is still refused, and now for a reason rather than for want of a
decision. A pinned thread is a conversation that does not get the prompt
fix you made *because of it*, and a store column that has to be
explained, migrated and eventually overridden. The alternative cost — the
change is visible — is one line in a ledger nobody reads until they need
it.

The generated case carries it too, since a case outlives everything
around it:

```
Recorded from a real turn against scribe 0.2.0 on 2026-09-18 (run
63504faf8402, model qwen3.8-64k:latest).
```

A package with no `version` key writes nothing rather than "unrecorded" —
it has not lost anything, it simply never said.

## What it looks like

Against `qwen3.8-64k:latest` on Ollama, with `--ask` and **stdin closed**
throughout — so any question that was actually put to a person would have
been refused for silence. What runs, runs because a standing rule said so.

The standing yes:

```
$ dvara --ask --policy policy.toml say --actor owner --agent scribe \
        "write a two-line haiku about a door into haiku.txt" < /dev/null
Done — wrote this to haiku.txt:

    the door stands on old hinges
    a moonlit path spilling onto the floor

[end_turn · $0.0016 · 2868in/1753out · run 038a02927658]
```

No question, no prompt, nothing on screen to say a rule was involved at
all — which is the invisibility the whole feature is about. And the
standing no, on the same run of the same agent:

```
$ dvara --ask --policy policy.toml say --actor owner --agent scribe \
        "write API_KEY=hunter2 into secrets.env" < /dev/null
That write was refused by a standing rule of the service — secrets files
aren't edited by an agent, and retrying won't change that. To put it
another way: the call was declined by a human-set rule, not timed out or
unattended.
```

The model reading its refusal correctly and saying which of the three it
was is [note 02](02-a-question-that-can-wait.md)'s three sentences still
doing their job, eight notes later.

Then the ledger, and the report:

```
$ dvara runs
2026-09-18 03:18  owner/scribe  end_turn  $0.0007  'write API_KEY=hunter2 into…'
                  write_file(refused)[rule:eabd9e26]
2026-09-18 03:16  owner/scribe  end_turn  $0.0016  'write a two-line haiku abo…'
                  write_file[rule:c0a621fc] -> write_file[rule:c0a621fc] -> read_file

$ dvara rules
policy.toml  ·  3 rule(s)  ·  calls settled over the last 30 days
      2  allow  write_file path=haiku.txt
      1  deny   write_file path=*.env|*/.ssh/*
      ·  allow  bash command=git status|git diff
```

Two calls settled by the standing yes in one turn, which is the count a
per-turn number would have got wrong. And the `bash` rule, written in
good faith, that has never matched anything.

## What is deliberately not here

* **A rule id in the report.** `dvara rules` prints what the rule SAYS,
  because that is what the owner recognises. The hash is machinery and
  lives in the ledger, where a line has to be short.
* **Counting in SQL.** The trajectory is JSON in a TEXT column, so there
  is no index to use and a `LIKE` would match a rule id inside any other
  field. It is a scan in Python, and an owner with a year of runs and a
  slow answer wants a real schema — at which point the column is the
  thing to change, not the query.
* **A decision for calls the rung allowed.** Most of them. "Nothing in
  particular" is not a fact worth a field.
* **Pinning a package version per thread.** Argued above: the change is
  made visible instead.
* **A rules report per actor or per agent.** A rule is the owner's, one
  file, service-wide. Slicing it by person is a question about people,
  and the ledger already answers that one.

## What is not here yet

* **A rule that fires is not told apart from a rule that merely matched.**
  Strictest-match-wins means two rules can both match one call and only
  one decides it; only the decider is recorded. The other is indisputably
  doing nothing, and reports a dot, which is either exactly right or
  slightly unfair depending on how you look at it.
* **Nothing counts the questions that WERE asked.** "How often am I woken
  up, and for what" is the same rows and a different `GROUP BY`, and
  nobody has wanted it yet.
* **A version is the package's own word.** Nothing checks that an edited
  package bumped it, so two different prompts can both call themselves
  `0.1.0` and the ledger will say nothing changed. A content hash would
  be honest and would also flag a reformatted comment as a change.
* **Locks are still never evicted**, unchanged from notes 01–09.

---

That is the list. Every bullet the design doc opened with, and every one
the notes added, is either shipped or refused on the record.

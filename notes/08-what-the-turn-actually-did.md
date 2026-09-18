# 08 — what the turn actually did

*[Note 04](04-the-failure-loop.md) built the failure loop: a bad turn in
production becomes a case in the package that produced it, and the
package's own gate stops it coming back. It ended with an admission —
the case it generated could assert that a turn **completes** and nothing
else, which is the weakest assertion the format has. This is the row
that makes a stronger one possible, and the one field it still refuses
to fill.*

## The problem, as you hit it

You use `dvara case` for the first time on a real failure, paste the
block into the package, run the gate, and it goes green.

Nothing was fixed. The case says: send this message, and do not crash.
An agent that answers "I can't help with that" passes it. An agent that
has had the tool it needed taken away passes it. The only failure a
generated case could detect was a turn that fell over, and a turn that
falls over is the *easy* failure — the one you already knew about,
because somebody told you.

What the case was missing is the shape of the turn. Not what the agent
said, which no assertion can grade, but **what it did**: which tools it
called, in what order, and which of them the gate turned away.

The `Run` row never held it. It knew a turn happened, what it cost and
how it ended, and everything in between was gone by the time anybody
looked.

## Names, not arguments

The first decision is where the line goes, and it decides three things at
once.

A tool **name** is a fact about the shape of a turn. A tool's
**arguments** are the turn's content: a path, a command, the text being
written, which is to say whatever the model happened to be holding.

```
write_file → recorded
write_file(path="secrets.txt", content="hunter2") → not
```

Three reasons, and the first is the one that settles it. **The case
assertions take names.** `required_tools` and `forbidden_tools` are lists
of tool names; there is no assertion in the format that an argument could
serve. Recording them would buy the feature that motivated this work
exactly nothing.

**A row that grows with an argument is a row that can hold a file.** The
other columns here are bounded by what a person typed; this one would be
bounded by whatever a model decided to pass, which is a file's contents
as often as it is a path.

**And `dvara case` prints a Run into a file an owner commits.** Note 04
already worried about that, carefully, about the *message*:

> **A CASE CARRIES THE RUN ID AND THE DATE, NEVER WHO SAID IT.** [...]
> That still leaves the owner committing somebody's words into a
> repository, which no code here can decide for them, so the command says
> so out loud before they do.

Arguments would put a second and much larger body of text in the same
place, and unlike the message, nobody typed it. Whoever wants arguments
wants a transcript, which is a different feature with a different
retention story and a different conversation about how long it is kept.

## A refused call is still a step

The second decision is that the interesting steps are the ones that did
not happen.

```
write_file -> write_file(refused)
```

Yantra already made this easy, and made it in the right place: a denial
reaches the loop as an ordinary `ToolExecuted` carrying a refusal code,
rather than as an exception.

> **A REFUSED CALL IS STILL ONE OF THESE.** The loop turns a denial into
> an error `ToolResult` rather than an exception [...] so a refusal
> reaches a consumer through the same event as a crash and a success.

So this service reads one event and gets both facts, and the whole
collection is one branch inside a loop that was already running. What it
stores is Yantra's own refusal **code** — `policy`, `user`, `timeout`,
`unattended` — and not the sentence beside it, because the sentence is
written for a model and will be reworded, and a column you have to grep
for English is a column nobody queries twice.

The refused rows are the ones an owner is actually looking for. They are
the moments the service did its job, and they are the only record of what
an agent has been *trying* to do.

## A trajectory is a description; a prohibition is a judgement

Two fields were now fillable and only one of them is this command's to
fill. This is the decision the note is named after.

**`required_tools` is filled**, from the calls that ran. That is the
fossil rule as Yantra states it — replay the failure, and the fix must
still do the work. A turn that read a file and wrote one, badly, is still
a turn that has to read a file and write one; an agent that "fixes" it by
doing neither has not fixed it, and the old case called that a pass.

**`forbidden_tools` is not filled**, including from the calls the gate
refused — which is where the temptation is, because a refused call looks
exactly like a thing you would want to assert never happens again.

It is not, and note 04 already said why in a different context:

> **THE SERVICE KNOWS A TURN STOPPED BADLY; ONLY A PERSON KNOWS A TURN
> ANSWERED BADLY.**

The same line divides these two fields. What a turn **did** is a
description, and the service watched it happen. What a turn **must never
do again** is a judgement, and a call the gate refused might have been
the bug — or might have been the agent correctly asking for something it
should have been given, in which case the fix is a rule in `policy.toml`
and not a prohibition in the package.

So the refused calls are *printed*, beside the block rather than in it:

```
# This turn also had write_file refused by the gate, which is NOT asserted
# above: whether the fixed agent should stop trying is your call, not the
# service's. Add forbidden_tools = ["write_file"] if it is.
```

On stderr, so the block stays pasteable — and it works at all only
because of note 04's first decision. The block is printed, not written.
An assertion a person disagrees with is a line they delete in a file they
were already going to read.

The receipt below makes the argument better than this paragraph does: in
a real turn, `write_file` came out **both required and refused**, and a
service that had filled both fields would have written a case that
contradicts itself.

## Where were you when you approved this?

The other half, carried since [note 05](05-one-person-two-channels.md)
and unanswerable until [note 07](07-four-thousand-and-ninety-six.md) gave
a person more than one door to answer at.

`AskDesk.answer` takes a `via` now, and it is the **answering** front
end's word rather than the delivering one's: a question that went out to
three channels was answered on exactly one, and only the thing that took
the press knows which. The terminal says `terminal`, the bot says
`telegram`, the HTTP surface says whichever channel the caller named or
`http` when it named an actor instead. It is optional everywhere, because
it is a record and never a check — a front end that does not say still
gets its answer landed.

**IT IS A PROPERTY OF THE TURN, NOT OF A CALL**, and that is a limit
rather than a preference. Two escalated calls in one iteration are gated
*concurrently* — Yantra fans them out with `gather` and reports the
results in submission order — so their answers may arrive in either
order, and pairing an approval with the call it approved would need an id
on `PermissionRequest` that does not exist. Recording the set of doors
this turn's answers came through is the fact that can be got exactly, and
"you approved this from Telegram" is the question an owner actually asks.

Recorded for a refusal too. "They said no, from their phone" is a fact
worth as much as the yes.

## Add, never rebuild

The unglamorous decision, and the one that would have broken a running
service.

`CREATE TABLE IF NOT EXISTS` does nothing to a table that already exists.
There is a `runs.sqlite3` in somebody's `~/dvara/state` right now, and a
column added today is missing from it — so the first `INSERT` after an
upgrade fails with *table runs has no column named tools*, on a live
service, with no obvious cause and no obvious fix.

```python
have = {row[1] for row in
        self._db.execute("PRAGMA table_info(runs)").fetchall()}
for column, kind in ADDED:
    if column not in have:
        self._db.execute(f"ALTER TABLE runs ADD COLUMN {column} {kind}")
```

**ADD, NEVER REBUILD.** The alternative — create the new shape, copy,
drop, rename — is how an audit trail is lost to a power cut halfway
through, and this table exists to be the thing that does not lose
anything. A column with no default costs nothing and leaves the old rows
saying exactly what is true of them: nothing was recorded, because
nothing was recording.

A row from before this and a turn that called no tools are both *empty*,
and they are deliberately not distinguishable. Inventing a third state
for "we were not recording yet" would put a fact about this software into
a row that is about an agent.

## What it looks like

Against `qwen3.8-64k:latest` on Ollama, reached through the
OpenAI-compatible endpoint so a price exists to be charged. One turn, two
questions at the keyboard — the first approved, the second refused:

```
$ dvara --ask say --actor owner --agent scribe \
        "write a two-line haiku about a door into haiku.txt"

scribe wants to run write_file:
  NEW FILE haiku.txt (3 lines)
approve? [y/N] y

scribe wants to run write_file:
  --- a/haiku.txt
  +++ b/haiku.txt
  @@ -1,3 +1,2 @@
  -a hand on the latch
  -the hinges turn, light spills out
  -two rooms share one wall
  +a hand on the latch — light spills
  +two rooms now share one night
approve? [y/N]

The first two-line write was refused by the owner, so haiku.txt currently
holds the three-line version. [...] I won't retry the call.
[end_turn · $0.0007 · 2056in/520out · run 4e1832870b2b]
```

The agent read its refusal correctly and did not retry, which is note
02's three sentences doing their job. And the row remembers all of it:

```
$ dvara runs
2026-09-18 01:19  owner/scribe  end_turn   $0.0007  'write a two-line haiku…'
                  write_file -> write_file(refused)  [answered from terminal]
```

That second line is the whole feature. `end_turn` was always there and
says the turn finished; the line under it says what it *did*, and that
somebody was at a keyboard when they decided.

Turned into a case — and note which tool appears in which place:

```
$ dvara case 4e1832 --because "it wrote three lines when I asked for two,
                               then tried to patch it instead of rewriting"
# This turn also had write_file refused by the gate, which is NOT asserted
# above: whether the fixed agent should stop trying is your call, not the
# service's. Add forbidden_tools = ["write_file"] if it is.
[[case]]
id = "trace-4e183287"
description = """
it wrote three lines when I asked for two, then tried to patch it instead
of rewriting
...
"""
user_message = "write a two-line haiku about a door into haiku.txt"
required_tools = ["write_file"]
max_tokens = 3864
```

`write_file` is **required** and the advisory offers to **forbid** it,
because in this turn it was both. A service that filled both fields would
have generated a case that can never pass. That is not a hypothetical
about why the judgement belongs to a person; it is the first real run.

And the assertion is not decoration. Written into the package and run
through its own gate, with the gate closed:

```
$ yantra --agent ./scribe --eval --case 'trace-4e183287'
gate: read-only tools only; writes and commands are refused (--yolo opens it)

  FAIL  trace-4e183287  24.8s · 2245 tok · 2 it · no tools
        required tool not used: write_file

SUBSET RED · 0/1 passed
```

**`required tool not used: write_file`** is a sentence this loop could
not produce yesterday. The same case before this note asserted only that
the turn completed — and this run completed, so it would have been green.

Run again with `--yolo`, so the tool is available:

```
  FAIL  trace-4e183287  39.4s · 7218 tok · 6 it · write_file, write_file,
                                      write_file, write_file, read_file
        over token budget: 7218 > 3864
```

Still red, and honestly so: this is a regression case for a failure
nobody has fixed yet, and the model flailed — four writes where the
original turn made two. But the *trajectory* assertion is satisfied and
the failure has moved to a different one, which is what proves it
discriminates rather than simply always firing.

## What is deliberately not here

* **Tool arguments.** Argued above. The assertions take names, the row
  would become unbounded, and `dvara case` prints into a file somebody
  commits.
* **`forbidden_tools`, generated.** A judgement, not a description. The
  refused calls are printed where the owner can act on them.
* **A result, or a duration, per step.** "It called `bash` and it failed"
  is the beginning of a transcript, and a transcript is a feature with a
  retention story this one does not have.
* **Sub-agent calls as their own steps.** A child's tools run through the
  parent's registry, which Yantra already documents as a deliberate
  conflation: delegation is the parent's doing. Splitting them here would
  invent a distinction the layer underneath does not make.
* **A `max_iterations` on the generated case**, unchanged from note 04:
  the package's cap is part of what is under test.

## What is not here yet

* **An approval cannot be pinned to the call it approved.** Concurrent
  gating plus no id on `PermissionRequest` means the doors are recorded
  per turn. The shape of the fix is a call id on the request — a Yantra
  seam, argued on Yantra's terms, for a host that wants to correlate a
  gate decision with the event it produced.
* **Nothing counts what the rules are doing**, unchanged from
  [note 03](03-standing-answers.md): which standing yes saved a question,
  which deny has never fired since it was written. The rows to answer it
  from now exist.
* **A trajectory is recorded and never queried.** `dvara runs` prints it;
  nothing asks "which agent has had the most calls refused this week",
  which is now one `SELECT` away and not written.
* **`dvara serve` and `dvara telegram` are still two processes over one
  state directory**, unchanged from [note 07](07-four-thousand-and-ninety-six.md).
* **Locks are still never evicted**, unchanged from notes 01–07.

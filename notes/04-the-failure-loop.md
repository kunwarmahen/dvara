# 04 — the failure loop: the gate had no supply of cases

*Yantra's authoring arc ends with a package that carries its own
acceptance gate — `evals/cases.toml`, run with `yantra --eval`, exit
non-zero when a promise has stopped being true. What it never had was
anywhere for cases to come from. An author writes the failures they can
imagine; the ones that matter are the ones nobody imagined, and they
arrive later, in production, in front of a person. This service has been
writing them all down since its first commit.*

## The problem, as you hit it

Your agent does something stupid on a Tuesday. You fix the prompt. Three
weeks later it does it again, because nothing anywhere remembers that it
happened the first time.

The gate is right there. It just contains the four cases you thought of
in an afternoon, none of which is the one that bit you.

Meanwhile the `Run` table has held everything needed since note 01: the
message that provoked the failure, what it cost, how it ended, and the
detail if it crashed. The loop is not a new capability. It is a join
between two things this repo already had, and almost all of the work is
deciding what *not* to do with it.

## The service proposes; a person commits

The obvious version writes the case itself. A turn fails, the service
appends a `[[case]]` block to the package, and the gate is stronger
tomorrow than it was today with nobody lifting a finger. It is a good
demo and it is wrong, for a reason note 01 already settled about
something else:

> An agent that runs in production must not write into the folder you
> review and commit. `cwd` is a per-session workspace under the service's
> state directory; the package root is read-only input.

A failure loop is exactly where that rule quietly lapses. It is a
*different* process doing the writing, for a good reason, at the owner's
own request — and the result is the same: a package whose contents nobody
read, and a gate that grew overnight. A gate you did not write is a gate
you do not trust, and a gate you do not trust is one you will eventually
run with `--no-verify`.

So the command prints:

```
$ dvara case 265903 --because "It was asked to write a file and gave up
                               without saying what it would have written."
[[case]]
id = "trace-265903fc"
description = """
It was asked to write a file and gave up without saying what it would
have written.

Recorded from a real turn against scribe on 2026-09-17 (run 265903fc95ae,
model qwen3.8:latest). The ceiling below is what that turn spent, with
half again for headroom -- a fix that costs more than the failure did is
not a fix."""
user_message = "Write a file called secrets.env containing API_KEY=abc123, then read it back."
max_tokens = 2266
```

…to stdout, with the warning on stderr so the block stays pasteable:

```
# from run 265903fc95ae against scribe. Read it before you commit it:
# the message is somebody's own words.
```

`--write` exists, and it is a flag somebody types. That is the whole
difference, and it is the same difference as `--yolo`: not *can this
happen* but *did a person decide it should*.

## Which runs are cases, and which are not

Three rules, and the middle one is the interesting one.

**A refused run is never a case.** When the service turned the turn away
— not on the roster, no access to that agent, daily allowance spent, a
cost ceiling this machine has no price for — no agent ran at all. That
row describes *this service and this machine*, and a package is a thing
that travels to other machines. Pinning it would produce a case that
passes, or fails, for reasons that have nothing to do with the agent's
behaviour. Here is a real one — a ceiling of $0.05 against a model
nothing can price:

```
$ dvara say --actor owner --agent scribe --model claude-imaginary-9 "..."
[refused · run 98784b2a39d2]
that agent cannot run right now: budget: no list price is known for
'claude-imaginary-9', so a $0.05 ceiling could never stop anything.

$ dvara case 98784b2a
error: run 98784b2a39d2 was refused before any agent ran -- roster
access, an allowance already spent, or a package this machine could not
build. That is a fact about this service and this machine rather than
about the agent's behaviour, and it would mean nothing in somebody
else's copy of the package.
```

**The service knows a turn stopped badly; only a person knows a turn
answered badly.** This is the rule I did not expect to need and would
now put first.

`error`, `max_iterations` and `over_budget` carry their own verdict — the
turn fell over, and the stop reason plus the detail is a serviceable
description with nobody typing anything. But the commonest real failure
is not any of those. It is a turn that ended `end_turn`, with a fluent,
confident, wrong answer. From out here that looks *identical* to a turn
that went well. The service has no opinion about it and should not
pretend to one:

```
$ dvara case 265903
error: run 265903fc95ae ended 'end_turn', so nothing here knows what was
wrong with it. A turn that answered badly looks exactly like one that
answered well from the outside -- say what to pin with --because, and
that sentence becomes the case's description.
```

`--because` is not a formality. Six months later, `trace-265903fc` with
an empty description is a row in a gate that nobody dares delete and
nobody can explain, which is worse than no case at all — it is a case
that will eventually be deleted by somebody guessing.

The same rule catches `cancelled`. The caller hung up; whether that was
because the turn was going wrong is not something this service saw.

**A case carries the run id and the date, never who said it.** The
message has to travel — it *is* the case — but the actor does not. A
package is a thing you hand to somebody, and the people your service
serves are not part of it. That still leaves an owner about to commit
somebody's words into a repository, which no code here can decide for
them, so the command says so every time.

## What the case asserts, and what it deliberately does not

It asserts that the turn **completes**, within a ceiling of what the
failure spent times 1.5 — Yantra's own `case_from_trace` heuristic,
unchanged, and the sentence that justifies it is worth keeping: *a fix
that costs more than the bug did is not a fix.* A run that never reached
a model spent nothing and gets no ceiling, leaving the package's own in
force.

Two things it could have asserted and does not.

**Not `required_tools`.** A `Run` does not record which tools ran — and
even if it did, the tools a *failing* turn reached for are evidence about
the failure, not a specification of the fix. A case that demanded the
same tool calls would be pinning the shape of the bug.

**Not `max_iterations`,** even for a turn that died on one. The package's
cap is part of what is under test. A case that raised it to make room
would be grading a different agent than the one that failed.

Both of those make the generated case *weaker* than one an author would
write by hand, and that is the right trade. A weak case in the gate is
the floor; the author sharpens it when they look at it, which they have
to do anyway, because they are the one committing it.

## The writer lives in the framework

This repo has one standing rule about formats:

> **dvara never parses `agent.toml`.** It calls Yantra's `load_package`.
> One parser, in the framework, with the tests.

Writing `cases.toml` is the same rule pointing the other way, and it took
one attempt at doing it here to see it. Rendering a `[[case]]` block
means knowing when a TOML string needs escaping, when a multi-line
literal is right, and what happens to a description that ends in a quote.
Every one of those is a fact about a format whose *reader* is a hundred
lines further up somebody else's file.

So Yantra grew `render_case`, beside `load_cases`, with a test suite that
does nothing but round trips: render it, load it back with the parser
that will grade it, compare. Not string comparisons — a block that looks
right and does not parse is the only failure that would actually reach a
package.

It also refuses to render a case carrying Python. `check = "graders:fn"`
resolves to a *callable* at load time, and a callable cannot be turned
back into the reference it came from, so rendering one would silently
drop an assertion. That raises instead. The failure this repo is most
consistently built against is a gate that checks less than its author
believes.

## The receipt: all the way round

A turn that crashed in dvara, against a model that does not exist:

```
$ dvara say --actor owner --agent scribe "Summarise what you can do."
  ProviderError: 404: not_found_error: model 'no-such-model:latest' not found
[error · run 9dcfabec7f14]
```

Written down — no `--because`, because the turn said what was wrong with
it:

```
$ dvara case 9dcfabec --write
SCRATCH/agents/scribe/evals/cases.toml: added trace-9dcfabec
  run it with: yantra --agent SCRATCH/agents/scribe --eval --case 'trace-9dcfabec'
```

And then the other repo's gate, running the case this one wrote:

```
$ yantra --agent SCRATCH/agents/scribe --eval --provider ollama
eval scribe 0.1.0 · 1 case(s) · ollama · qwen3.8:latest
budget: $0.05 per turn -- inert here, a local model bills nothing

  PASS  trace-9dcfabec  5.5s · 997 tok · 1 it · no tools

SUITE GREEN · 1/1 passed · 997 tokens
```

The package had no `evals/` directory before this; it has a gate now, and
the first case in it came from a real failure rather than from somebody's
imagination.

That receipt also shows the honest limit of it, which is the next
section.

## What is not here yet

* **A crash the SERVICE caused looks like a crash the PACKAGE caused.**
  The receipt above is the example: that turn failed because the model
  name was wrong, not because the package was, and the case it produced
  passes trivially the moment the model exists. It is a weak case rather
  than a wrong one — the claim "this message should complete" is still
  true — but nothing here can tell the two apart, and `--because` is the
  only instrument for saying so.
* ~~**No trajectory, so no assertion about HOW.**~~ Shipped in
  [note 08](08-what-the-turn-actually-did.md). A `Run` records the tool
  calls now, and `required_tools` is filled from the ones that RAN. The
  privacy question this bullet anticipated was answered by refusing it:
  NAMES, NOT ARGUMENTS, because the assertions take names and a row that
  grows with an argument is a row that can hold a file. `forbidden_tools`
  is still not generated, and that turned out to be a decision worth its
  own section rather than an omission.
* **Nothing notices a run that keeps happening.** The same failure three
  times in a week is a much stronger signal than the same failure once,
  and there is no query for it — `dvara runs` prints a list and a person
  does the noticing.
* **The generated case is never re-run to confirm it fails.** A
  regression case that passes the first time you run it is a case that
  is not testing what you think, and the loop would be tighter if
  `--write` offered to run the gate immediately. It would also need a
  provider and a key at the moment somebody is doing bookkeeping. (Less
  likely to pass trivially since note 08 — a case that asserts a
  trajectory has something to fail on — but still nothing checks.)
* ~~**Locks are still never evicted**~~ — shipped in [note 11](11-only-while-somebody-is-waiting.md); unchanged from notes 01–03.
* ~~**One actor per channel**~~ -- settled in
  [note 05](05-one-person-two-channels.md), which was the last thing
  standing between escalation and somewhere real to escalate to.

---

The channel came next, in [note 07](07-four-thousand-and-ninety-six.md),
and the loop this note opened was finished in
[note 08](08-what-the-turn-actually-did.md) — where a generated case
stopped asserting only that a turn completes.

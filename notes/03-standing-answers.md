# 03 — standing answers: a rung is per turn, a rule is per call

*[Note 02](02-a-question-that-can-wait.md) built a route, so "ask" stopped
meaning "refuse" and started meaning ask. What it left is one decision
covering a whole conversation: three rungs, chosen once, applied to every
tool call an agent will ever make. This note is the owner writing
individual answers down in advance — and most of it is about the one way
that goes badly wrong.*

## The problem, as you hit it

You run the service with `--ask`, because you would rather be asked than
refused. By Wednesday you have approved `git status` eleven times.

So you reach for `--yolo`, and now nobody asks you anything — including
before `rm -rf`, including when a package you have not read decides to
write to `~/.ssh/config`. The dial has two settings and you want
different answers for different calls, which is not a setting at all. It
is a file.

```toml
[[rule]]
tool    = "bash"
args    = { command = "git status" }
verdict = "allow"

[[rule]]
tool    = "write_file"
args    = { path = ["*.env", "*/.ssh/*"] }
verdict = "deny"
reason  = "secrets are not edited by an agent -- tell me what needs
           changing and I will do it myself."
```

`--policy examples/policy.toml`, or `~/dvara/policy.toml` if it happens
to exist. **No file means no rules, and no rules means the gate note 02
built, unchanged** — not "an empty rule book that permits everything", but
the same three functions, chosen by the same branch. That is a property of
the code rather than a promise: the rule path is not entered at all.

## The rung says whether there is a question; a rule says what the answer is

Everything about how these two layers compose is in that sentence, and it
is worth being slow about, because the obvious alternative is a security
hole.

A rule could have been a fourth input to the ladder — another mode to take
the minimum of. It cannot be, because `allow` is not a rung. The ladder's
whole property is *tighten, never loosen*: a package that ships
`mode = "yolo"` does not get yolo, an actor marked `read_only` cannot be
talked upward by anybody. A per-call `allow` that granted permission would
be a hole straight through that, written by the owner, for the best of
reasons, and available to every actor the file did not think about.

So an `allow` rule is **a standing yes to a question that was going to be
asked**, and nothing else. Concretely:

| rung | what a rule can do |
|---|---|
| `yolo` | `deny` and `ask` bite. `allow` is redundant. |
| `ask` + a desk | all three: `allow` skips the question, `deny` refuses it, `ask` is the default. |
| `ask`, no desk | `deny` bites. `allow` grants nothing — there is no route, so there was never a question. |
| `read_only` | `deny` bites. `allow` grants nothing, and `ask` wakes nobody. |

Two predicates in the code, and they are the whole of it: `rung_allows`
(would this call have run with no rules?) and `can_escalate` (may a
person be put on the spot for this actor?).

The consequence worth seeing is in the last row. **The same policy file
reads differently for the owner and for a guest**, and that is the
feature rather than a wrinkle. Here is the same rule, the same tool, the
same path, twice — against a local model, nothing mocked:

```
$ dvara say --actor owner --agent scribe --ask --policy examples/policy.toml \
      "Write a file called notes.txt containing the single line: rules land today."
[end_turn · 2049in/218out · run 89d1f67a5f4d]
Done — notes.txt contains the single line "rules land today" (17 bytes).
```

No question was printed, because the owner had already answered it. Now
`guest`, who is `permissions = "read_only"` in `actors.toml`:

```
$ dvara say --actor guest --agent scribe --ask --policy examples/policy.toml \
      "Write a file called notes.txt containing the single line: guest was here."
[end_turn · 2131in/396out · run a7147b336bc1]
To sum up what happened: the write_file call that would have created
notes.txt with the single line "guest was here." was refused (not a
timed-out question, nor mere absence) because this sandbox is running
with read-only tools and nobody is available to approve an exception.
```

One file. The owner's standing yes; the guest's flat no. Nothing in
`policy.toml` mentions either of them.

## The strictest matching rule wins, not the first

Firewalls and ACLs almost always evaluate top to bottom and stop at the
first match, and there is a good reason for it: it lets you write "deny
this whole directory except for that one file". Expressive, and familiar.

This file does the other thing. Verdicts rank `deny < ask < allow`, every
matching rule is collected, and the answer is their **minimum** — the same
arithmetic the rungs already use. The exception pattern is gone; you
cannot carve a hole in a denial.

What it buys is that order does not matter. Nothing appended to the bottom
of the file can quietly undo something at the top, so a diff of a rule file
means what it looks like it means, and a rule that got moved during an
edit did not change anybody's permissions. For a file one person edits
occasionally, at odd hours, with no review, that is worth more than the
exception pattern is.

It also makes the failure mode of a careless rule *refusal*, which is the
direction you want a careless rule to fail in.

## Patterns widen a refusal, never a permission

This is the part I would most want somebody copying this design to take
with them, because the bug it prevents is completely invisible.

Write this, and read it back:

```toml
args    = { command = "git status*" }
verdict = "allow"
```

It looks careful. It looks *narrower* than allowing `git`. What it
actually means is that `git status; rm -rf ~` is approved without anybody
being asked, because `*` in a glob matches semicolons, and newlines, and
everything else.

The same trap wears a second costume:

```toml
args    = { path = "~/notes/*" }
verdict = "allow"
```

`*` matches `/`, and `..` is an ordinary directory name, so that rule
approves `~/notes/../../.ssh/id_rsa`.

A glob describes a shape. The shape of a dangerous argument is not
knowable in advance — that is the entire reason a permission gate exists,
and a pattern in an `allow` rule is an attempt to describe it anyway.

**So wildcards are refused in an `allow`, at load time.** `deny` and `ask`
take patterns, because a pattern that is too wide costs you a question;
`allow` takes exact strings, as many as you like in a list, because a
pattern that is too wide runs a command nobody saw. The asymmetry is
entirely about what a mistake costs.

```
$ dvara --policy bad-policy.toml agents
error: bad-policy.toml: [[rule]] entry 0 (tool = "bash") args.command =
'git status*' is an allow rule with a wildcard in it. A pattern describes
a shape, and the shape of a dangerous argument is not knowable in advance
-- "git status*" matches "git status; rm -rf ~", and "~/notes/*" matches
"~/notes/../../.ssh/id_rsa". Patterns widen a refusal and never a
permission: write the exact strings, as a list if there are several.
Anything that does not match is still ASKED, not refused.
```

Long, for an error message. It is long because the mistake is invisible,
the person reading it wrote something that looks careful, and the last
sentence is the one that makes the refusal acceptable: **a near miss is
not a denial.** `git status --short` does not match the allow rule, so it
falls through to being asked — which is exactly where it was before
anybody wrote a policy file. Narrow allow rules cost you a question, never
an outage.

There is a smaller cousin of the same rule inside the matcher:
`fnmatchcase`, never `fnmatch`. The second consults the platform's
case rules, and a policy file whose meaning depends on which machine the
service booted on is not a policy file.

## What the model is told, and why it is not "denied"

A refusal from a standing rule is a *different fact* from the three note
02 already distinguished, and it produces a different next move.

A timeout says wait and try later. A person saying no says propose
something else. But a rule is not about this conversation at all — nobody
was asked, nobody will be, and no amount of patience changes it. So the
sentence says so:

> `write_file` was denied: a standing rule of this service refuses it.
> Nobody was asked, and nobody will be — this is not about the present
> conversation, so waiting and retrying will not change it.

And then the owner's own `reason`, when they wrote one, which is usually
the part that tells the model what to do instead. Here is a local model
receiving exactly that, unedited:

```
$ dvara say --actor owner --agent scribe --ask --policy examples/policy.toml \
      "Write a file called secrets.env containing API_KEY=abc123."
[end_turn · 2108in/665out · run 53362e09f2d9]
That's neither a question nobody answered in time nor a person refusing —
I need to say that plainly. The write_file call was refused, and the
refusal came from a standing, automated rule of this service — one that
specifically bars the agent from writing files for secrets or keys — with
nobody present to ask, so I shouldn't retry it.

As a workaround that rule itself offers, I'll tell you what to change and
you can do it yourself: [...]

And one thing worth flagging while we're at it: an API key you type into
a chat message may already be compromised; consider rotating it rather
than reusing that value in the env file.
```

Nothing was asked and no keyboard was touched. The model correctly
separated the three denials, did not retry, and passed the owner's
suggested route back to the person — and threw in security advice nobody
prompted it for, which is a local model having a good day rather than
anything this note built.

Beside the sentence there is now a **code**, which is Yantra's note 39
machinery finally being used here: `policy`, `user`, `timeout`,
`unattended`. The sentence is written for the model and will be reworded;
the code is for whoever wired the gates up and wants to count timeouts
separately from refusals without matching on English.

## A papercut note 02 left, now closed

Note 02 recorded this and called it a note rather than a fix:

> A tightened ACTOR borrows the framework's "nobody is available to ask"
> sentence, when the truth is that somebody was available, just not for
> this person.

Inside the rule path both facts are in hand — whether there is a desk, and
what rung this actor is on — so both get said. A guest now reads that this
conversation *is not permitted to put questions to anyone*, rather than
that the house is empty. The model's next move is the same either way,
which is why it was never urgent; the sentence a person reads in a log
should still be true.

It is closed for a service that has rules and open for one that does not:
with no policy file the gate is Yantra's own `allow_read_only`, wearing
Yantra's own sentence, and reaching in to change that would cost the
property this note opened with.

## What is deliberately not here

* **Per-actor rules.** One file, the owner's, for everybody. The ladder
  already expresses "this person gets less" and it does it in the file
  that is *about* people; a second per-person dimension inside the rule
  file would mean two places to look when somebody asks why they were
  refused. Revisit when somebody wants a rule for one guest and not
  another.
* **Regular expressions.** Globs are what `tools.allow`, `has_tools` and
  `$YANTRA_DISABLED_TOOLS` already use, and a policy file is not the
  place to introduce a second matching language — particularly not one
  where a misplaced `.*` is the same catastrophe this note spends a
  section on.
* **Rules about anything but tool name and arguments.** Not the time of
  day, not how much has been spent, not how many calls this turn has
  made. Each is defensible and each needs its own argument; a rule that
  matched on the clock would also need a story about what a *pending*
  question does when the hour changes.
* **A way to see which rule fired.** The model is told a rule refused it;
  the owner reading `dvara runs` is not told which one. That belongs with
  the trajectory work below rather than as a column here.

## What is not here yet

* **Nothing counts what the rules are doing.** An owner who wants to know
  which standing yes actually saved them a question, or which deny has
  never fired since the day it was written, has no way to find out. The
  `Run` record is the obvious home and this note deliberately did not add
  a column to it. ([Note 08](08-what-the-turn-actually-did.md) added the
  rows — every refused call, with the code that refused it — so this is
  now a query nobody has written rather than a fact nobody has.)
* **A deny cannot constrain a list-valued argument.** Patterns match
  strings, and a non-string argument never matches — so a tool that takes
  a *list* of paths cannot be constrained here at all. Safe in the
  direction that matters (a rule that does not match falls through to
  being asked) and a real gap.
* **An allow rule is exact, and an argument is text.** `write_file` with
  `path = "notes.txt"` and `path = "./notes.txt"` are the same file and
  two different strings. Nothing here normalises anything, deliberately —
  a matcher that resolved paths would be resolving them against a
  workspace that only exists once the turn has started — but it means an
  allow rule is matching the model's spelling rather than the file.
* **Locks are still never evicted**, unchanged from notes 01 and 02.
* ~~**One actor per channel**~~ -- settled in
  [note 05](05-one-person-two-channels.md), and it was indeed more
  expensive than it looked: two actor ids is also two daily allowances.

---

Next: [note 04](04-the-failure-loop.md) — the failure loop. A bad `Run`
becomes a case in the package that produced it, and the package's own
gate stops it coming back.

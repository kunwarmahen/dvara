# 02 — escalation: a question that can wait, and a deadline that denies

*Note 01 ended on a sentence that decided everything about it: **"ask"
with nobody present is not a question, it is a hang.** So the service
refused anything that could change something, and said so. This note is
what changes when somebody is present — and it turns out that "somebody
is present" is not a fact about the world, it is a route: somewhere a
question can go, and somewhere an answer can come back from. Build the
route and the hang becomes a question. Leave it out and nothing waits.*

## The problem, as you hit it

Your agent can read. It cannot write, run a command, or touch anything
outside its own workspace, because a service with nobody watching refuses
every tool that could change something. That is the right default at
three in the morning and it is infuriating at three in the afternoon,
when you are holding your phone and would happily have said yes.

The obvious fix is obviously wrong. A gate that blocks until you answer
does not block *you* — it blocks the event loop, and with it every other
conversation in the process. One person's unanswered question becomes an
outage for everybody else. That is why note 01 refused to be clever about
this with a thread and a queue, and why the fix had to start one layer
down.

## What the framework had to grow first

`PermissionFn` used to be `Callable[[PermissionRequest], bool]`, and
`AsyncAgent` called it inline inside the running coroutine. Yantra now
allows the answer to be *awaitable*, and awaits it. That single change is
what makes a question that waits possible: the gate suspends, the loop
goes and serves everybody else, and the answer arrives whenever it
arrives.

What the framework deliberately did *not* grow is the deadline. A
timeout that denies is policy, and policy belongs to whoever owns the
conversation — a library that picked two minutes for everybody would be
picking for hosts it has never met. So the clock lives here.

That division is the shape of the whole relationship. dvara asks Yantra
for a seam; Yantra provides the mechanism and refuses the policy; the
policy is written where somebody actually knows the answer.

## A route, not a presence

The switch that turns "ask" from a refusal into a question is not a
setting. It is an **ask desk**: somewhere a question can be put, and
somewhere an answer can land.

```python
service = Service(roster=..., actors=..., state=...,
                  asks=AskDesk(timeout=120, notify=send_to_telegram))
```

With a desk, `mode = "ask"` means ask. With no desk it means exactly what
note 01 said it meant — read-only tools only — because a question with
nowhere to go is not a question. **The absence of a route is not a hang
and not an approval.** It is a denial that says nobody could be asked,
which is a fact the model can act on.

That fallback is also what keeps the default safe. A service built the
way note 01 built one has no desk and behaves precisely as it did before
any of this existed. Nothing starts waiting on somebody who was never
wired up.

## Three rungs, and the minimum wins

Note 01 had two modes because Yantra has two: `ask` and `yolo`. Once
"ask" can actually reach a person, two is not enough — an owner needs to
say *do not wake me up for this one* about a guest without saying it
about themselves. So the ladder grows a rung at the bottom:

    read_only  <  ask  <  yolo

and three different parties each name one:

| who | where | what it means |
|---|---|---|
| the package | `[permissions] mode` in `agent.toml` | what the author thinks this agent needs |
| the owner | `Policy(mode=...)`, or `--yolo` | what this machine allows at all |
| the actor | `permissions` in `actors.toml` | what this person may be asked to approve |

The composition is a minimum, not a paragraph of if-statements:

```python
mode = stricter(package, owner, actor)
```

which is what makes *tighten, never loosen* a property of the arithmetic
rather than a promise in a comment. Write `permissions = "yolo"` beside a
guest's name and it grants them nothing at all; the minimum simply
ignores it.

An unrecognised mode ranks below every real rung, so a typo and a mode
from a future version of the format both fail closed.

### Two kinds of silence

This is the part that took a rewrite to get right, because "absent" turns
out to mean two different things depending on who is silent.

**An actor who names no mode has no opinion**, and drops out of the
comparison entirely. That is how `permissions` composes exactly like
`max_usd_per_turn` in the same file: an absent key is not a ceiling. The
alternative — absent means the tightest rung — would have quietly broken
`--yolo` for every actor who had not been edited, and made a new key
mandatory in practice.

**A package that names no mode is treated as naming the tightest.** This
is the one silence read as a decision, and it is deliberate: an author
who ships code and leaves the `[permissions]` table out has not asked to
be escalated for, and a service that escalated on their behalf would be
putting a stranger's tool call in front of a person on no authority at
all.

## Three denials, three sentences

A refused call comes back to the model as text. Note 01 already made the
case that the text matters — a model that believes a person refused it
will argue with the person — and escalation triples the point, because
there are now three quite different ways to be told no:

* **They said no.** Somebody was asked and answered. Do not re-run this
  call; a different approach may be worth proposing.
* **Nobody answered.** The deadline passed. This is silence, not a
  refusal — the person may simply be away, and asking again later is
  reasonable.
* **Nobody could be reached.** The notifier raised: the bot is down, the
  token expired. Asking again will not help.

Three facts, three next moves. Collapsing them into "denied" would throw
away the only information the model could have used to choose.

The third one is also why **a delivery that fails is a denial
immediately**, rather than after the deadline. If the question never left
the building, the two minutes that follow are two minutes of nothing, and
the model gets told the wrong thing at the end of them.

## The deadline covers the question, not just the waiting

The first version of the desk awaited delivery and *then* started the
clock. That is fine for a bot adapter, which posts a message and returns
— and it is silently wrong for the front end that needs the deadline
most.

The terminal prompt does both jobs at once: it asks and it collects, and
it does not return until somebody types. With delivery awaited first, the
clock would not have started until the answer had already arrived. A
deadline that only applies to the front ends that do not need it is not a
deadline.

So delivery runs as a task alongside the wait. Found by trying to write a
receipt for the timeout and discovering there wasn't one.

## Only the person it was put to

A question id is unguessable, and answering it still requires naming the
actor it was put to. Either check on its own is weaker than it looks:
ids travel out through a channel and can be forwarded to anybody, and an
actor id by itself is a name off a roster that anyone can type. Together
they mean a leaked question is useless to whoever it leaked to.

A wrong answer resolves nothing — the question stays standing, for the
person it was actually put to, until they answer it or the clock runs
out.

## The answer does not arrive as a message

A turn holds its conversation's lock while it waits. That is not
incidental, it is note 01's serialization invariant doing its job: two
messages in one thread must not interleave.

The consequence is worth meeting here rather than in production. **Typing
"yes" into the chat does not approve anything.** That message queues up
behind the very turn it was meant to release, and sits there until the
deadline passes — at which point the turn is refused for silence, and
*then* your "yes" is delivered to a model that has no idea what it refers
to.

So answers arrive on their own path: `AskDesk.answer`, or
`POST /asks/{id}` over HTTP. An approval is not a sentence for the model
to read; it is a decision about a call that is already in flight, and the
two are different kinds of thing.

## Questions live in memory and die with the process

Not a table. A pending question is a promise that a turn is still
standing there waiting for the answer — and no turn survives a restart,
because agents are built per turn and the coroutine that asked is gone.
A persisted question would outlive the only thing that could act on it,
which is not durability. It is a lie with a timestamp on it.

The same reasoning covers a caller who hangs up. Cancellation takes the
question with it, and it does **not** become a denial: a dropped
connection is not a person saying no, and history must not record one.

## An answer may come from another thread

A channel adapter is under no obligation to be asyncio. A long-polling
bot in a worker thread is an ordinary way to write one, and this is the
failure it would have hit: resolving a future from the wrong thread does
not raise. It simply never wakes the loop. The turn waits out its
deadline and is refused for silence — which is the worst possible
symptom, an *approval that reads as absence*.

Found by writing the HTTP test the realistic way, with the turn on one
loop and the answer arriving from somewhere else. The desk remembers
which loop each question is waiting on, so an answer from anywhere lands.

## The terminal is a channel

There is no bot yet. There does not need to be one: a front end supplies
a way to put the question and a way to take the answer, and a terminal
has both.

```bash
dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8-64k:latest \
      --ask say --actor owner --agent scribe \
      "write a two-line haiku about doors into haiku.txt"
```

Live, against a local `qwen3.8-64k:latest` on Ollama. The answers below
were piped into stdin rather than typed, which is why no keystroke is
echoed after the prompt — everything else is verbatim. Approved:

```
scribe wants to run write_file:
  NEW FILE haiku.txt (1 lines)
approve? [y/N] [end_turn · $0.0000 · 2065in/961out · run 1bf114e57ff4]
Done — here's the two-line haiku in `haiku.txt`:

> The wooden door stands (5)
> and whispers of rooms gone by (7)
```

```
$ cat state/work/owner/scribe/h/haiku.txt
The wooden door stands
and whispers of rooms gone by
```

The same question, refused:

```
scribe wants to run write_file:
  NEW FILE hello.txt (1 lines)
approve? [y/N] [end_turn · $0.0000 · 1229in/192out · run c5f9066eadcd]
That write was refused because you (the owner) were asked and said no —
so I've left `hello.txt` unwritten and won't retry that call. If you'd
like it done a different way (different filename, different content, or
somewhere else), just let me know and I'm happy to propose that instead.
```

Two things in that reply were the point of the sentence the gate wrote.
The model named *who* refused, and it did not retry — it offered a
different approach instead, which is what a model does when it knows a
reachable person said no rather than that it is shouting into an empty
room.

Note also what the question shows: `NEW FILE hello.txt (1 lines)` is the
tool's own preview, built by Yantra — for an edit it is a real unified
diff. What you approve is what runs.

With nobody at the keyboard and an eight-second deadline:

```
scribe wants to run write_file:
  NEW FILE hello.txt (1 lines)
approve? [y/N]
The write attempt timed out — nobody confirmed it, so hello.txt doesn't
exist yet. Just let me know when you're back and I'll write it.
[end_turn · $0.0000 · 2019in/306out · run b4076c19b6c3]
```

Silence denied it, the file was not written, and the model can tell that
apart from having been refused.

And a guest the owner does not want to be woken up for — `permissions =
"read_only"` beside their name — never generates a question at all. No
prompt was printed, because nobody was asked:

```
[end_turn · $0.0000 · 1222in/174out · run 294526d82117]
Your call was refused — not by a person who said no, but because this
unattended session only auto-approves read-only tools and nobody is
available to ask, so writing "hello" into hello.txt didn't happen and I
won't retry it.
```

## Over HTTP, where a bot will plug in

A served process supplies neither half: there is nobody at its keyboard,
and the answer is going to arrive from an adapter talking to somebody
elsewhere. So questions wait to be collected.

```
GET  /asks?actor=mahen     -> {asks: [{id, actor, agent, thread, tool, summary, asked_at}]}
POST /asks/{id}            {actor, approve}   -> {answered, approved}
```

`approve` must be a JSON boolean. Anything truthy would make the string
`"no"` an approval, which is the exact shape of the bug that ends with a
command nobody agreed to: an adapter forwarding a person's literal words
into a field that was expecting a decision.

A question put to somebody else is a `403`, and one that has been
answered or has expired is a `404`.

## What is deliberately not here

* **No approve-with-edits.** Yantra's gate allows a request's arguments
  to be rewritten before approval, and the CLI uses it. Over a channel it
  would mean editing a shell command in a chat message, and the
  round-trip is long enough that the edit and the thing being edited
  drift apart in a person's head. Approve or refuse.
* **No per-tool policy.** Tool + argument globs → allow / deny / ask is a
  real thing to want and it is the next note, not this one. Inventing the
  dialect twice is how two incompatible dialects are born.
* **No record of which turns asked.** A Run row says what a turn cost and
  how it stopped, not that it stood waiting for ninety seconds first.
  Worth having, and it is a column in a table note 01 created — a
  migration, for a question nobody has asked yet.
* **No queue, no reminders, no retry.** One question, one deadline, one
  answer.

## What is not here yet

* ~~**A tightened actor borrows the wrong sentence.**~~ Half closed in
  [note 03](03-standing-answers.md): a service that has standing rules
  decides inside its own gate, where both facts are in hand, and a
  tightened actor is now told that this conversation may not put
  questions to anyone rather than that nobody is there. A service with no
  policy file still uses Yantra's own `allow_read_only` and its sentence,
  which is the price of that gate being the framework's function rather
  than a copy of it.
* ~~**A blocked keyboard survives its own deadline.**~~ Fixed in
  [note 09](09-a-process-you-walk-away-from.md), and with the cancellable
  read this bullet asked for rather than a bigger hammer on the thread:
  the descriptor goes to the event loop, so giving up on the question
  leaves nothing behind at all.
* **Locks are still never evicted**, unchanged from note 01, and now
  holding for longer at a time.
* ~~**One actor per channel.**~~ Closed by
  [note 05](05-one-person-two-channels.md). The two queues are one
  queue: a question is put to a PERSON, delivered to every channel they
  hold, and answerable from any of them.

---

Next: [note 03](03-standing-answers.md) — standing answers, so the same
question stops being asked every morning. The channel itself arrived in
[note 07](07-four-thousand-and-ninety-six.md), as a *client* of all this
rather than a special case inside it: it supplies a notifier and calls
`answer`, exactly as the terminal does.

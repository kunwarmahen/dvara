# dvara — the tutorial

> Written for someone who wants to put agents behind a door: what dvara
> does, in what order the pieces make sense, and what to type to see each
> one working. Every step names the note that argues the design.
>
> dvara is built on [Yantra](https://github.com/kunwarmahen/yantra). An
> agent here is a Yantra package — a directory with an `agent.toml` — and
> everything about the agent itself (tools, skills, permission modes,
> packages, evals) is in [Yantra's tutorial](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md). This one starts where
> that one ends.

Yantra ends at a keyboard. You run `yantra --agent ./researcher`, you talk
to it, you close the laptop and it is gone — and the whole framework
quietly assumes exactly that: one person, present and trusted, one
conversation, one process that dies when they walk away.

dvara is what happens when you take those assumptions away one at a time.

```
                 ┌──────────────┐
  Telegram ──┐   │              │   ┌─ greeter/      (agent.toml)
  HTTP ──────┼──▶│    dvara     │──▶├─ researcher/   (agent.toml)
  your CLI ──┘   │              │   └─ ops/          (agent.toml)
                 └──────┬───────┘
                        │  actors.toml · sessions · runs · workspaces
```

## 0 · Ten minutes, before you read anything

```bash
uv sync
dvara --root examples/agents --actors examples/actors.toml agents

dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8 \
      say --actor guest --agent greeter --thread demo "who are you, in one sentence?"

dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8 \
      say --actor guest --agent greeter --thread demo "what did I just ask you?"
```

Two separate invocations, no process shared between them, and the second
one remembers. Then try three things that should fail, and read the
sentence each one gives you:

```bash
# ... --actor stranger ...            not on the list
# ... --actor guest --agent scribe "write hello into hello.txt"
#                                     refused: nobody available to ask
# ... --ask --actor owner --agent scribe "write hello into hello.txt"
#                                     a question, at your keyboard
dvara --root examples/agents --actors examples/actors.toml runs
```

## 1 · Setup and a first turn

```bash
cd ../dvara
uv sync                          # dvara + Yantra from the checkout next door
cp .env.example .env
```

Add `--extra browse` to `uv sync` if an agent will read Amazon or X
through a browser (section 16).

An owner needs two things: a directory of agent packages, and a file of
people.

```bash
# what this service can offer
dvara --root examples/agents --actors examples/actors.toml agents

# one turn, in process -- no HTTP, no bot token
dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8-64k:latest \
      say --actor guest --agent greeter "who are you, in one sentence?"

# what it has been doing
dvara --root examples/agents --actors examples/actors.toml runs
```

`--root`, `--actors` and `--state` also read `$DVARA_ROOT`,
`$DVARA_ACTORS` and `$DVARA_STATE`, so the rest of this act drops them.

`dvara say` exists for a reason worth stating: it drives the service
**directly, in process**, with no HTTP and no channel. It is how you
rehearse a package against a local model before any bot token exists, and
it is how every receipt in the dvara notes was produced.

## 2 · The three nouns

A terminal never had to answer these. A service answers all three before
a single token is spent.

**Actor** — who is talking. **Agent** — which package. **Thread** — which
conversation.

```
session key = (actor, agent, thread)      →      mahen/greeter/chat-42
```

Not `(actor, thread)`. If two people use the same chat id with two
different agents, `(actor, thread)` gives them one shared history and the
agents start reading each other's mail. Fixing that later is a migration;
getting it right on day one is a tuple.

Each part is percent-escaped before it is joined, and that is not
decoration: join them raw and an actor named `a/b` in thread `c` produces
the same key as actor `a` in thread `b/c` — one person's conversation
opening inside another's because of how they happened to be named. It
stays readable rather than hashed on purpose, so
`select distinct session_id from checkpoints` answers your question
without a decoder ring. The same escaping names the folder an agent works in,
one per person per agent, and the dot segments (`..`) are neutralised
explicitly, because `quote()` leaves a dot alone and a folder that becomes
its own parent is a bad afternoon.

## 3 · An actor is assigned, never asserted

This is the sentence the whole security posture hangs on. Nothing arriving
from outside gets to say who it is. The owner writes a file — and it holds
no secrets, so it is a thing you commit:

```toml
[actor.owner]
# no keys at all: every agent in the roster, no ceilings, and this is
# somebody the service may wake up to approve a tool call

[actor.guest]
agents           = ["greeter"]     # a COMPLETE whitelist; omit for all
max_usd_per_turn = 0.02
max_usd_per_day  = 0.10
permissions      = "read_only"     # served, but never asked to approve
```

An identity with no name here is not served, and learns nothing about who
else exists:

```
$ dvara say --actor stranger --agent greeter "hello"
you are not on this service's list of people
[refused]
```

`agents` follows the convention `tools.allow` already set in Yantra:
absent means everything, a list is a complete whitelist, and an empty list
is an error rather than a silent "this person may reach nothing" — an
empty allowlist is far likelier to be a typo than a decision. Unknown keys
are errors too:

```
error: ~/dvara/actors.toml: [actor.guest] has unknown key(s) max_usd_per_dayz;
known: agents, channel, max_usd_per_day, max_usd_per_turn, permissions,
receipt
```

A misspelled ceiling that quietly means "no ceiling" is exactly the
failure a ceiling exists to prevent.

### An actor is a person, not a seat

The same file says where a person can be *reached*, which is the half
that lets a bot be a client of this rather than a second roster:

```toml
[[actor.owner.channel]]
kind = "telegram"
id   = 8675309       # a number is fine; stored and compared as text
```

A channel adapter does not carry its own `{chat_id: actor}` table — it
hands over the identity it has, and this file says whose it is. That is
the same sentence as the section title, extended one step: half an
assignment living in a bot's environment is half an assignment nobody
diffs.

The argument for one actor instead of two is not the tidiness. Write the
same person down twice — `mahen` and `mahen_tg` — and their
`max_usd_per_day = 2.00` is now **$4.00**, because the allowance is a sum
over runs keyed by actor id. A ceiling that doubles when you install a
bot is not a ceiling. The pending-questions queue and the agent whitelist
split the same way, and neither is as bad as that.

So: one person, one allowance, one queue, several doors — and a question
raised anywhere is delivered to every channel they hold, answerable from
any of them. dvara checks that a `(kind, id)` pair belongs to at most one
actor, and otherwise never branches on which channel `kind` names.

```bash
dvara say --as telegram:8675309 --agent greeter "who are you?"
```

One thing joining the actor *creates*, rather than fixes: two channels
whose thread ids collide would now share a conversation, where before it
was the differing actor ids keeping them apart — by accident. A turn that
arrives through a channel is keyed under `kind:thread`, so they stay two
conversations, and keys made by naming an actor directly are untouched.

### What follows the answer

```toml
receipt = "cost"        # $0.0013 under each answer
receipt = "remaining"   # $0.0489 left today
```

Absent — the default — is silence. Two words rather than one boolean,
because **two readers want two different numbers.** An owner is watching
a bill accumulate and wants what the turn cost. A guest has no bill, only
an allowance, and the one figure they can act on is what is *left* of it:
told `$0.0013`, they would have to know their ceiling and their spend and
subtract. That is [Yantra's note 43](https://github.com/kunwarmahen/yantra/blob/main/notes/43-a-bar-and-a-deadline.md)'s "what is
left, not what is spent", arriving one layer up.

Two rules fall out. Under a provider that bills nothing, both render
nothing — half this book's readers run Ollama, where a receipt is a meter
that cannot move. And a hosted model with no list price renders
`unpriced` rather than `$0.00`, because an owner who asked for a receipt
asked to watch a bill, and a zero there is a guess wearing a number's
clothes.

The line is a separate field, never appended to the reply text: `run.reply`
is the archive of what the agent *said*, and a channel gets to pick how a
footer looks in its own medium.

## 4 · Agents are named, never pathed

[Yantra's Act III](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md) said it in passing and this is where it is load-bearing: **loading
a package runs its Python.** That is fine for a package you chose. It stops
being fine the instant a package path could come from a message.

So dvara resolves agents by NAME, from one directory the owner controls,
and a name has to survive three checks: it matches a conservative pattern
(rejecting `..`, `/etc/passwd`, `~`, hidden directories, anything with a
newline in it), it joins to the root, and — after `resolve()` — it is
still inside that root. The third check is the one a pattern cannot make:
a symlink is a path that lies about where it goes.

The property that makes a roster safe to *list* at all belongs to Yantra:
`load_package` imports nothing. Code runs later, in `spec.build_async()`,
at the moment a request actually reached an agent. There is a test with a
package whose `tools/boom.py` raises on import; listing the roster and
reading its manifest both leave it sleeping.

Two more rules from the same family:

* **dvara never parses `agent.toml`.** It calls Yantra's `load_package`.
  One parser, in the framework, with the tests.
* **Nothing here is sandboxed by pretending.** Yantra's sandbox confines
  an agent's tool *calls*; it has nothing to say about a package's
  import-time side effects, and this service does not imply otherwise.

## 5 · Two ceilings, and a refusal to build a second meter

Yantra meters one turn. A service has to answer a different question: what
may *this person* spend, today, across every turn they have had?

| | |
|---|---|
| package | `max_usd_per_turn` — what the author thinks a task costs |
| actor | `max_usd_per_turn` — what the owner lets this person spend |
| today | `max_usd_per_day` minus what they have already spent |

The design decision is a refusal. **dvara does not build a second meter.**
It takes the minimum of whichever are set, hands that one number to
Yantra's existing `Budget`, and inherits the whole apparatus — the mid-turn
stop, the warning, and the shared meter that stops a sub-agent from
clearing its parent's spend. A daily allowance is therefore enforced by a
per-turn ceiling that shrinks as the day is spent. That is a strange
sentence and a correct design: every extra meter is another place the
arithmetic can disagree with itself, and the first place it would disagree
is sub-agents.

Live, against a local `qwen3.8-64k:latest` on Ollama, priced against
itself through `$YANTRA_PRICES` so a ceiling could be rehearsed without an
account with a card behind it:

```
$ dvara say --actor guest --agent greeter --thread money "hello"
Hello, come on in.
[end_turn · $0.0468 · 76in/41out · run c4a882d657b6]

$ dvara say --actor guest --agent greeter --thread money "and again?"
Well, hello again, friend.
[end_turn · $0.0584 · 99in/47out · run fe4843a1a381]

$ dvara say --actor guest --agent greeter --thread money "one more?"
your daily allowance is spent; it comes back at 00:00 UTC on 16 Sep
[refused · run 28bfabe88231]

$ dvara say --actor owner --agent greeter --thread money "still open?"
Yes, I'm still here—what can I help you with?
[end_turn · $0.0660 · 78in/87out · run 46add8708249]
```

Two turns came to $0.1052 against a $0.10 allowance; the third never
reached the model, and the owner — who has no allowance — was unaffected.
The day boundary is the UTC calendar day rather than a rolling 24 hours,
because the person you have just cut off needs a time they can plan
around.

**The tradeoff, named.** Look again at that first turn: $0.0468 against
the guest's $0.02 per-turn ceiling. It ran anyway. A per-turn meter can
only bite *between* model calls — there is nothing to weigh before the
first one — so a single expensive call always gets through. The daily
allowance is what makes that bounded rather than infinite, and it is the
honest reason a service needs both numbers.

## 6 · Three rungs, and the tightest wins

Yantra has two permission modes. Once "ask" can actually reach a person,
two is not enough — an owner needs to say *do not wake me up for this one*
about a guest without saying it about themselves. So the ladder grows a
rung at the bottom:

```
read_only  <  ask  <  yolo
```

and three parties each name one:

| who | where | what it means |
|---|---|---|
| the package | `[permissions] mode` in `agent.toml` | what the author thinks this agent needs |
| the owner | `Policy(mode=...)`, or `--yolo` | what this machine allows at all |
| the actor | `permissions` in `actors.toml` | what this person may be asked to approve |

The composition is a minimum, not a paragraph of if-statements:

```python
mode = stricter(package, owner, actor)
```

which makes *tighten, never loosen* a property of the arithmetic rather
than a promise in a comment. Write `permissions = "yolo"` beside a guest's
name and it grants them nothing at all. An unrecognised mode ranks below
every real rung, so a typo and a mode from a future version of the format
both fail closed.

**Two kinds of silence**, and this is the part that took a rewrite:

* **An actor who names no mode has no opinion** and drops out of the
  comparison entirely — exactly how `max_usd_per_turn` composes in the
  same file. The alternative would have quietly broken `--yolo` for every
  actor nobody had edited.
* **A package that names no mode is treated as naming the tightest.** An
  author who ships code and leaves `[permissions]` out has not asked to be
  escalated for, and a service escalating on their behalf would be putting
  a stranger's tool call in front of a person on no authority at all.

## 7 · Escalation — a route, not a setting

With nobody attached, a service refuses anything that could change
something and tells the model why. That is the right default at three in
the morning and infuriating at three in the afternoon, when you are
holding your phone and would happily have said yes.

The obvious fix is obviously wrong. A gate that blocks until you answer
does not block *you* — it blocks the event loop, and one person's
unanswered question becomes an outage for everybody else. That is the seam
Yantra had to grow first ([Yantra's tutorial, §16](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md)), and this is what is built on it.

The switch is not a setting. It is an **ask desk**: somewhere a question
can be put, and somewhere an answer can land.

```python
from dvara import AskDesk, Service

service = Service(roster=..., actors=..., state=...,
                  asks=AskDesk(timeout=120, notify=send_it_to_them))
```

With a desk, `mode = "ask"` means ask: the turn suspends — it does not
block, so every other conversation keeps running — until a person answers
or the deadline passes. With no desk it means read-only tools only, which
is exactly how the service behaved before any of this existed. **The
absence of a route is not a hang and not an approval.** It is a denial
that says nobody could be asked, which is a fact the model can act on.

**Three refusals, three sentences**, because they call for three different
next moves:

* **They said no.** Somebody was asked and answered. Do not re-run this
  call; a different approach may be worth proposing.
* **Nobody answered.** The deadline passed. This is silence, not a
  refusal — try again later.
* **Nobody could be reached.** The notifier raised: the bot is down, the
  token expired. Asking again will not help. (And a delivery that fails is
  a denial *immediately*, not after the deadline — if the question never
  left the building, the two minutes that follow are two minutes of
  nothing.)

### The terminal is a channel

There is no bot yet, and there does not need to be one. A front end
supplies a way to put the question and a way to take the answer; a
terminal has both.

```bash
dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8-64k:latest \
      --ask say --actor owner --agent scribe \
      "write a two-line haiku about doors into haiku.txt"
```

Live, against a local `qwen3.8-64k:latest`. Approved:

```
scribe wants to run write_file:
  NEW FILE haiku.txt (1 lines)
approve? [y/N] [end_turn · $0.0000 · 2065in/961out · run 1bf114e57ff4]
Done — here's the two-line haiku in `haiku.txt`:

> The wooden door stands (5)
> and whispers of rooms gone by (7)
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

Two things there were the point of the sentence the gate wrote: the model
named *who* refused, and it did not retry — it offered a different
approach, which is what a model does when it knows a reachable person said
no rather than that it is shouting into an empty room.

With nobody at the keyboard and an eight-second deadline, the model can
tell silence apart from refusal:

```
The write attempt timed out — nobody confirmed it, so hello.txt doesn't
exist yet. Just let me know when you're back and I'll write it.
```

And a guest with `permissions = "read_only"` beside their name never
generates a question at all. No prompt is printed, because nobody was
asked.

### Two rules about answers

**Only the person it was put to.** A question id is unguessable, and
answering it still requires naming the actor it was put to. Either check
alone is weaker than it looks — ids travel out through a channel and can
be forwarded; an actor id is a name off a roster anyone can type. Together,
a leaked question is useless to whoever it leaked to. A wrong answer
resolves nothing; the question stays standing.

**Answers do not arrive as messages.** A turn holds its conversation's
lock while it waits, so typing "yes" into the chat queues up *behind the
very turn it was meant to release* — and sits there until the deadline
passes, at which point the turn is refused for silence and *then* your
"yes" is delivered to a model with no idea what it refers to. Answers come
through the desk, or through `POST /asks/{id}`. An approval is a decision
about a call already in flight, not a sentence for the model to read.

Questions live in memory and die with the process, on purpose: a pending
question is a promise that a turn is still standing there waiting, and no
turn survives a restart. A persisted question would outlive the only thing
that could act on it.

**Unless you tell silence to wait.** Start the service with
`--ask --on-timeout hold` and an unanswered question stops the turn
instead of refusing the call. Nothing after it runs, and the turn waits,
for up to a day, for you to come back. This is the same hold the browser
has above, and it *can* survive a restart, because Yantra saves it
inside the conversation. A service keeps a list of them:

```
$ dvara held
VamBTs5Z_X3GzDPNY6UYeQ  owner/scribe  thread cli  run efa292db101a
    call_fq5canuu  write_file: NEW FILE a.txt (1 lines)
    call_b6dmlw42  write_file: NEW FILE b.txt (1 lines)
    held 30s ago. What you approve runs against things as they are now, not as they were then.

$ dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor owner \
      --call call_fq5canuu=yes --call "call_b6dmlw42=leave b.txt alone"
```

In a chat, the reply that says the turn is waiting has two buttons under
it, **approve all** and **refuse all**, and pressing one carries the turn
on. Only the person the turn ran as can answer it. Sending a new message
instead means "never mind", and the waiting calls are set aside.

## 8 · What a service does that a session never had to

* **A fresh agent per turn**, not a pool of warm ones. Warm agents buy
  latency and cost three things: memory that grows with every actor who
  ever said hello, a spec that goes stale the moment you edit a package,
  and a crash that loses history nobody wrote down. Rebuilding is also the
  only version where a restart is a non-event.
* **One provider, held.** The opposite decision for the opposite reason:
  constructing a provider opens two httpx connection pools, so resolving
  one per turn would leak pools for as long as the process lived.
* **History is restored; identity is rebuilt.** This is `history_only=True`
  from [Yantra's §19](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md) doing its job. What comes out of the store is the conversation.
  Everything else comes out of the package — so a prompt you fixed this
  morning takes effect this afternoon.
* **One lock per conversation.** Two messages in one thread serialize.
  Interleaving them would put two user messages into one history with a
  single assistant reply between them.
* **An agent writes in a workspace, not in its package.** The package
  directory is read-only input; each person gets a folder per agent under
  the service's state, shared by all their conversations with it, so a
  file a schedule wrote is one their chat can read
  ([note 25](notes/25-the-persons-folder.md)). They can have a file
  from it sent to them: `/files` lists it, `/file NAME` sends one, on
  Telegram as a document, and no agent is involved. An agent that lists
  `send_file` can send one too, asked like any write
  ([note 26](notes/26-the-file-itself.md)). An agent that edits the folder you
  review and commit is an agent whose package has stopped being
  reviewable — and being reviewable is the one property the whole format
  exists to have.

## 9 · Every turn leaves a row

Including the ones that failed. A script forgets; a service that forgets
cannot answer the owner's first question.

```
$ dvara runs
2026-09-15 17:46  guest/greeter  end_turn          $0.0584  'and again?'
2026-09-15 17:46  guest/greeter  end_turn          $0.0468  'hello'
2026-09-18 01:19  owner/scribe   end_turn          $0.0007  'write a haiku…'
                  write_file -> write_file(refused)  [answered from terminal]
```

That second line is what the turn **did**, and it is a different fact
from how the turn ended. `end_turn` says it finished; the line under it
says it wrote a file, tried to write it again, and was told no by
somebody standing at a keyboard.

**A turn that crashes still pays for what it spent.** Three model calls
and then a 500 is still three model calls, and the accounting happens in
the same `finally` that saves the session. Leave it out and a crash erases
its own cost, so the daily allowance never sees it and somebody with a $2
day can spend the afternoon in failing turns. The other direction matters
too: a turn that never reached a model costs `$0.0000`, not "unpriced" —
"unpriced" is the store admitting a doubt, and about a turn that never
happened there is no doubt to admit.

Three later features are queries over this one table, which is why it
exists in the first slice rather than the fourth. Money over time is a
`SUM`. An audit is a `SELECT`. And a failed run is a *trace* — which is
the shape Yantra's eval machinery turns into a case in the package that
produced it. That is the loop the whole arc was built to close: the agent
fails in production, the failure becomes a case, the package's own gate
stops it coming back.

**And the case can assert how the turn went**, because the row remembers.
`required_tools` is filled from the calls that actually ran, which is
`case_from_trace`'s own parameter finally having a source — so an agent
that "fixes" a bad turn by doing nothing at all no longer passes:

```
  FAIL  trace-4e183287  24.8s · 2245 tok · 2 it · no tools
        required tool not used: write_file
```

Two lines are drawn here and both are worth carrying away. **Names, never
arguments**: `write_file` is recorded and the path it was given is not,
because the assertions take names, a row that grows with an argument is a
row that can hold a file, and `dvara case` prints into a file somebody
commits. And **a trajectory is a description; a prohibition is a
judgement** — the service watched the turn happen, so it will say what
was called, but whether the fixed agent should stop *trying* something
the gate refused is a line the owner writes. The refused calls are
printed beside the block so they know what to write.

## 10 · The door itself

```
POST /message      {actor, agent, thread, text}  -> {text, ok, run_id, receipt, ...}
GET  /agents                                     -> {agents: [...]}
GET  /health
GET  /asks?actor=                                -> {asks: [{id, tool, summary, ...}]}
POST /asks/{id}    {actor, approve}              -> {answered, approved}
POST /notify       {actor, text}                 -> {sent, kept, nowhere}
```

```bash
DVARA_TOKEN=$(openssl rand -hex 24) dvara serve --port 8765
```

Two of these exist for a program that acts for people who are not
there — a scheduler. `/message` with `"unattended": true` runs a turn
nobody typed, with `"allow_tools"` standing in for the questions the
person answered ahead of time (they grant only what a question could
have), and `/notify` sends a person a finding they did not ask for, on
their own channels ([notes/17](notes/17-nobody-wrote-first.md)).

Every request carries `Authorization: Bearer $DVARA_TOKEN`. **The token
authenticates the caller, not the person.** A caller is a channel adapter
running inside the owner's trust boundary. The `actor` field in the body
is an assertion *by a trusted caller* — which is precisely why the token
is mandatory rather than optional. A service with no token refuses to
start, binds to localhost unless told otherwise, and compares the token
in constant time.

An adapter may instead send the identity it actually has, and let the
roster map it — the form it cannot get wrong:

```
POST /message   {"channel": {"kind": "telegram", "id": 8675309}, ...}
             -> {..., "actor": "owner"}
```

Exactly one of `actor` or `channel` per request, on all three endpoints
that name a person. Both is a `400`: honouring it would mean picking a
winner, and then a bridge with a stale hard-coded actor id either quietly
overrules the roster or quietly does not.

A refusal comes back as a `200` with a reason, not a `500`. A channel
adapter has to be able to deliver "you are not on this list" as a message;
an exception is a reply that silently never arrives. On the asks
endpoints, `approve` must be a JSON boolean — anything truthy would make
the string `"no"` an approval, which is the exact shape of the bug that
ends with a command nobody agreed to. A question put to somebody else is a
`403`; one already answered or expired is a `404`.

## 11 · A bot at the door

Everything up to here was built so that this part could be small. The
roster already says who a chat id is; the desk already knows where a
question goes; the actors file already decides what goes under an answer.
What a chat app adds is the medium, and the medium has three opinions.

```bash
export TELEGRAM_TOKEN=...          # BotFather gives you one per bot
dvara --ask telegram --agent researcher
```

There is no `--token` flag: a credential on a command line is in your
shell history and readable in every `ps` on the box. And **one bot is one
agent** — a token is an identity with a name, a picture and an @handle, so
a second agent is a second token and a second process rather than a prefix
on every message you type.

**A reply has a bottom at 4096, and it is measured in UTF-16.** Telegram
counts a message in UTF-16 code units; Python counts a string in code
points. They agree for ASCII, which is why this bug survives every test
written by hand and appears the first time an answer has an emoji in it —
one Python character, two of Telegram's units, and a 3000-character reply
that is 4200 units and is rejected *whole*. So a long reply is **split,
never truncated**: a brief cut off at the cap still reads like a finished
answer, and the citations that would tell you otherwise are at the bottom.
Cuts land on a blank line, then a newline, then a space.

**The poll loop never awaits a turn.** A turn waiting for approval is
released by a button press, and button presses arrive through the same
long poll. Await the turn in the loop and the answer can only come down
the pipe the turn is holding shut — every escalated call waits out its
deadline and is refused for a silence that had somebody pressing the
button. Updates become tasks; the service's per-conversation lock is
already holding the line that matters.

**An approval is a button.** §7's rule — answers do not arrive as
messages — is not a limitation of the terminal, it is a property of the
lock, and a chat app has exactly one other affordance:

```
  ┌─ message to chat 8675309
  │ scribe wants to run write_file:
  │
  │ NEW FILE haiku.txt (2 lines)
  │ [approve] [refuse]
  └─
  ← pressed: y:Rbo_PR_OLYsQsVEMGMm86A
  ← the question now reads: ...— approved
```

The summary is Yantra's, built so that what the person approves is what
runs. The press arrives as a `callback_query`, which does not touch the
session lock, and the message is edited afterwards so it cannot be pressed
twice.

Two more decisions worth knowing before you point one at a real chat.
Nothing is sent with a `parse_mode`, because Markdown mode makes the
*model's own punctuation* a syntax error — one unmatched `*` and the whole
answer comes back as a 400. And somebody who is not in `actors.toml` gets
**silence**, while you get the line that says how to add them.

## 12 · Leaving it running

The difference between a service and a program you run is what happens
when nobody is watching the terminal. Three things.

**One dvara per state directory**, and a second one is refused. The
visible symptom of running two is SQLite contention — `database is
locked` — and fixing *that* is three lines and the worst available
outcome, because it silences the only signal while leaving the real
problem alone. **A SERVICE IS A PROCESS.** The lock that serializes two
messages in one conversation (§8) and the queue of questions waiting for
a person (§7) both live in memory, so two processes would both rehydrate
one checkpoint, both save, and lose a turn without anything raising at
all.

```
$ dvara --state ~/dvara/state say --actor owner --agent greeter "hello"
error: another dvara is already using ~/dvara/state (pid 3641987 running
dvara serve). A service is a PROCESS, not a directory: …
```

It is an `flock`, not a pid file, because **the kernel releases it** — a
service killed with `SIGKILL` leaves no stale lock and no "is 4032 still
the same process?" heuristic to get wrong. A refusal needs a way out, so
a bot *and* an HTTP surface is one process:

```bash
dvara serve --telegram researcher
```

And a command that only *reads* — `runs`, `case`, `agents`, `status` —
claims nothing, because looking at your own ledger while the bot answers
somebody is the most ordinary thing an owner does.

**Is it serving?** The same lock answers that. `dvara status` tries it
without taking it: if it's held, something is running, and the file
under it says what and where. A file left behind by a crash says
nothing, because the lock went with the process:

```
$ dvara status
dvara 0.1.0 · state /home/you/dvara/state
serving at http://127.0.0.1:8765 (dvara serve, since 2026-10-06T02:56:39+00:00)
agents: greeter, minder, scribe  ·  people: 2
```

`dvara status --json` is the same for a program, such as Sarathi, that
started dvara for you ([note 23](notes/23-is-the-door-open.md)).

**Edit the actors file while it runs.** It is reread when it changes, so
adding the guest standing in front of you holding your bot's @handle is
one edit and no restart. What decides the feature is the failure case:
**A BAD FILE KEEPS THE LAST GOOD ONE.** An owner adding somebody at
midnight who leaves a bracket off is one typo away from a service that
refuses everybody — including themselves, including the person who would
fix it — so a file that has stopped parsing is a complaint on their
terminal and nothing more:

```
~/dvara/actors.toml: Expected ']' at the end of a table declaration
  -- keeping the roster already loaded; nothing changed for anybody
     talking right now
```

At *startup* the opposite is right, and that is what happens there: a
broken file is exit 2 and nothing serves. The difference between the two
answers is whether there is already something to lose. The parsers decide
none of it — they parse, and the host decides — which is the same
division as the ask deadline in §7.

**And a question you can walk away from.** A terminal question that times
out used to leave a thread parked in `input()`, and the interpreter joins
those at exit, so the process sat there wanting a keypress nobody had a
reason to give. The fix is not a bigger hammer on the thread; it is
`loop.add_reader`, and not using one.

## 13 · What decided this

Three questions an owner asks months later, when the thing that could
have answered them has gone.

**Which rule stopped that — and which one has never done anything?** The
asymmetry is the problem: a deny announces itself, because the model is
told and the turn changes shape. An allow is invisible *by construction*
— the call simply runs, exactly as it would have if you had been woken up
and said yes. So a policy file fills with lines you cannot tell apart by
looking:

```
$ dvara rules
policy.toml  ·  3 rule(s)  ·  calls settled over the last 30 days
      2  allow  write_file path=haiku.txt
      1  deny   write_file path=*.env|*/.ssh/*
      ·  allow  bash command=git status|git diff
```

A rule is named by what it **says** — a hash of tool, verdict and
patterns — not by where it sits, so inserting a line at the top does not
shuffle the counts. Edit a rule and it starts at zero, which is right:
you changed the standing answer.

**Where were you when you approved this?** This is the one that sent a
feature back into the framework. A gate's answer and the `ToolExecuted`
it produces had nothing joining them, so a host could only pair them by
counting — which *works*, because gates run once per call in submission
order. That is three properties of the loop that no caller was ever
promised, and a drift in any of them files one person's approval against
a different call: wrong, confident, and silent. So `PermissionRequest`
carries the `call_id` it is deciding ([Yantra's §16](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md)), and the two halves of a turn
meet on a string neither had to agree about:

```
write_file[rule:c0a621fc] -> write_file[rule:c0a621fc] -> read_file
```

Only the interesting ones are recorded. A call the rung simply allowed —
`read_file` above — says nothing, because "nothing in particular decided
this" nine times in ten is a field nobody reads.

**And which version of the agent was that?** Agents are rebuilt per turn
(§8), so a package edited on disk takes effect on a live conversation's
next turn. Desirable when you are fixing a prompt; alarming when a
conversation changes personality mid-sentence. The resolution is not to
choose: **the alarming part was never the change, it was that nothing
said it happened.**

```
2026-09-18 03:18  owner/scribe  end_turn  $0.0007  'write API_KEY=hunter2 into…'
                  scribe changed after this turn: 0.1.0 -> 0.2.0
```

Pinning a version per thread is the alternative, and it is refused for a
reason rather than for want of a decision: a pinned thread is a
conversation that does not get the prompt fix you made *because of it*.

## 14 · Embedding it

```python
from pathlib import Path
from dvara import ActorBook, Roster, Service

service = Service(
    roster=Roster(Path("~/agents")),            # owner-controlled, always
    actors=ActorBook.from_toml(Path("~/actors.toml")),
    state=Path("~/dvara/state"),
)
reply = await service.deliver(actor="mahen", agent="researcher",
                              thread="cli", text="what changed today?")
print(reply.text, reply.cost_usd)
```

The full map, one line per module with the note behind it, is the
README's [source tree](README.md#the-source-tree).

## 15 · A schedule asked for in the chat

With [Samay](https://github.com/kunwarmahen/samay) installed, `--samay` lets each person's agent offer
to do something later or on a repeat: *"check example.com every hour and
tell me if it's down"*. The agent previews it and reads the sentence
back; on a yes, the question arrives in the person's chat as a card in
words — when, who hears, what may run unasked — with two buttons on it.
Approved, the schedule is theirs: it runs this agent, as them, through
this door, on their allowance.

```bash
export SAMAY_DVARA_URL=http://127.0.0.1:8765 SAMAY_DVARA_TOKEN=$DVARA_TOKEN
dvara --ask --samay /path/to/samay serve --port 8765 --telegram helper
#   dvara: schedules through samay 0.1.0 (/path/to/samay); its clock is running
```

`examples/agents/minder` is a package built for this: it checks a web
page now, and offers to check it later or on a repeat. Ask it *"check
whether example.com is up once an hour and only tell me if it's down"*.
It previews the schedule, reads it back, and waits for your yes before
the card comes.

It's off unless the owner turns it on, because it lets everyone the bot
serves put work on a timer the owner pays for. The package has to ask
(`[permissions] mode = "ask"`), and Samay needs `SAMAY_DVARA_URL` and
`SAMAY_DVARA_TOKEN` set here too, to check each schedule against this
service ([notes/18](notes/18-a-schedule-asked-for-in-the-chat.md)). How
Samay itself is set up — its clock, its page, keeping it running — is in
[Samay's README](https://github.com/kunwarmahen/samay).

Every run starts a fresh conversation, so the hundredth run doesn't
drag the last ninety-nine answers into its prompt. Nothing continues
those conversations, so a week after one ends, its history is let go
(`--keep-unattended DAYS` changes the week). The runs stay in `dvara
runs`, and anything a run wrote stays in your folder with that agent,
where you can ask about it from the chat
([note 25](notes/25-the-persons-folder.md)). Only a conversation a program started is
ever let go: yours, and one with a question still waiting for you, are
not ([note 24](notes/24-a-conversation-nobody-will-continue.md)).

## 16 · Their own accounts

At a keyboard, Setu's accounts are whoever is typing. Behind a door there
are several people, so each one gets a Setu folder of their own, named in
the actors file:

```toml
[actor.raj]
setu = true                          # a folder of his own, under the state directory

[actor.priya]
setu = "~/.local/state/setu"         # an existing folder -- yours
setu_accounts = ["gmail:personal"]   # ...narrowed to one account
```

raj signs in from the chat. He sends `/connect gmail`, gets Google's
link, signs in on his phone, and sends back the address of the page that
then fails to load (it starts `http://127.0.0.1`). dvara hands that to
the waiting sign-in, never to an agent, and answers *"Connected
gmail:personal (raj@example.com) at Read only"*. `/accounts` lists what
he has; `/disconnect gmail:personal` removes one. `/lock` seals his
folder with a passphrase only he knows, and `/unlock` opens it for a
week at a time, so his schedules keep running
([notes/21](notes/21-a-passphrase-only-they-know.md)). priya's folder is
yours, so hers are connected at the machine (`SETU_HOME=<that folder>
setu connect gmail`). A site signed in to through a browser window,
like Amazon, is streamed to raj's phone if you give the service a window
address (`SETU_WINDOW_HOST`; see
[notes/22](notes/22-a-window-sent-to-their-phone.md) for which address
is safe for what). raj's fresh folder borrows your Google client file;
while your Google app is in Testing mode, add his address as a test
user ([notes/20](notes/20-signing-in-from-the-chat.md)).

**Your own phone, your own folder.** If you are an actor too, pointed at
the folder your desktop uses so the page and the chat share one set of
sign-ins, you are a guest there by default: `/connect` says the owner
looks after it. That owner is you, so say so:

```toml
[actor.owner]
setu = "~/.local/state/setu"
setu_manage = true
```

Now `/connect amazon`, `/disconnect amazon:personal` and `/accounts` work
from your phone on that folder. `/lock` still doesn't: locking it from a
chat would lock your desktop and page out of every account, so a shared
folder's passphrase is set at the computer
([notes/27](notes/27-your-folder-from-your-phone.md)).

**Their own page.** raj can also see his accounts in a browser. Start
Setu's page so it knows where people's folders are, on an address his
phone reaches (here a Tailscale one):

```bash
setu serve --host 100.64.0.7 --people ~/dvara/state/setu
```

and start the door with `SETU_PAGE_URL=http://100.64.0.7:8775/` (or the
window's `SETU_WINDOW_HOST`, which gives the same address). raj sends
`/accounts page` and gets a link that opens once, on the first device,
within ten minutes. It shows his connections and what each one did, with
Connect, Change level and Disconnect, and none of your settings. To turn
people's pages off: `setu config people-page off`
([notes/31](notes/31-their-own-page.md)).

From then on, each of their turns reads Setu in *their* folder
and starts their connections there, so their agent can open only their
accounts, and only what the package asks for in `[connections] needs`,
at the package's level. Scheduled runs get the same. An account the
package needs that they haven't connected is named to the agent with the
truth: they send `/connect` for it (or, for priya, the owner connects it).

Live, with two people asking *"how many unread emails do I have?"*: priya
got her count from `gmail-personal` alone, with the owner's other account
never started; raj got *"the Gmail account isn't connected … it would
need to be connected by the owner of this service"*. A person's tokens
sit on the owner's disk, and the owner could read them. Say so to anyone
you give a folder ([notes/19](notes/19-their-own-accounts.md)).

## 17 · The owner's page

Everything `dvara runs` and `dvara status` say, in a browser:

```
$ dvara page --as owner
dvara's page for owner:
  http://127.0.0.1:8785/#token=…
```

Open the address. You'll see a card for each person with today's spend
against their allowance, the agents and who may use them, and every turn,
newest first, with its tools. A refused call is red. Pick a person or an
agent to narrow the list.

At the top, **Waiting for you** shows what your agents are asking you
right now, with **Allow** and **Refuse**. Pressing one is the same as
pressing the button in your chat. Start the page with the door's token
(`DVARA_TOKEN=... dvara page --as owner`) so it can pass your answer to
the running door. Only your own questions are shown.

Two lines are drawn, and both are about other people. **Their words stay
theirs**: your own turns show what you said and what the agent answered,
and everyone else's show only the agent, the cost and the tools. **How to
reach them stays theirs too**: the card says `reached on telegram`, not
their id. And the page changes nothing: to change who's served, edit the
actors file, which the door re-reads on its own
([notes/29](notes/29-the-owners-page.md)).

Further down are **Schedules** and **Files**. Schedules are each person's,
in Samay's own words, with when each one runs next. Start the page with
`dvara --samay PATH page` if `samay` isn't on PATH. Files are each
person's folder with each agent: names, sizes and dates. Click one of
your own to read it there. Everyone else's are names only, and so are
the words of their schedules.

## 18 · Your phone, from the chat

With [Sparsh](https://github.com/kunwarmahen/sparsh) installed and your
Android phone plugged into the computer running the door (or the
emulator running there), you can ask from Telegram for something done
on the phone: *"turn on Do Not Disturb"*, *"what's the code in my newest
text?"*, *"text Sam I'm running late"*.

Mark yourself as the phone's person in the actors file:

```toml
[actor.owner]
phone = true
```

and start the door with `--sparsh` and the `phone` agent:

```bash
dvara --ask --root examples/agents --sparsh /path/to/sparsh telegram --agent phone
#   dvara: the phone through sparsh 0.1.0 (/path/to/sparsh); phone: emulator-5554
```

The agent reads the phone's screen as a numbered list and taps by
number. Most steps happen without a question. A step that can't be
taken back — Send, Pay, Delete, typing a password — stops, and the
question comes to your chat with **Yes** and **No** under it, saying
exactly what will happen:

```
Do this on the phone?
On the phone emulator-5554: tap button "Send SMS" in com.google.android.apps.messaging
…
4 field "running late"
```

Press **No** and nothing is sent; the agent tells you so.

**The button is the question.** A held step lives only while that turn
runs. If the agent asks *"shall I send it?"* in words and you answer
*"yes"*, the step it held is gone by then, so the door doesn't show you
a card for it at all. The agent is told to do the step again and ask
with the button. The `phone` example's prompt says so; give your own
agent the same sentence.

**The screen stays on while it works.** A local model can think for
longer than your phone's screen timeout between steps, and a dark screen
locks. So Sparsh keeps the screen on while the agent works and puts your
own timeout back two minutes after its last step (`SPARSH_AWAKE`, in
Sparsh's README: `working`, `always` for a phone set aside for the
agent, or `off`). If you pick the phone up mid-task, Sparsh notices the
screen changed and does nothing; the agent looks again.

**Try it without Telegram first.** `dvara say` runs one turn in the
terminal, and its questions come to the terminal too:

```bash
printf '[actor.owner]\nphone = true\n' > /tmp/phone-actors.toml
dvara --root examples/agents --actors /tmp/phone-actors.toml --state /tmp/phone-state \
  --provider ollama --model gemma4:26b --ask --sparsh /path/to/sparsh \
  say --actor owner --agent phone "Text 555-0123 from my phone: hello"
```

It stops at `Do this on the phone? … "Send SMS"`; type `n` and nothing
is sent. Sparsh's SETUP.md, Part T, checks the phone itself first.

**A tap you answer by looking.** On a screen the phone can't describe
as a list (Settings' About page), the agent taps a spot on a screenshot,
and every such tap asks. The question comes with the picture, the spot
ringed in red: in Telegram as a photo just above the buttons, on your
page above the words, and at the terminal as a file whose path is
printed. Say yes only if the ring is on what you asked for
([notes/32](notes/32-the-ring-in-the-chat.md)).

**Your own agent package.** The `phone` example lets the phone in. An
agent of your own (Sarathi's `minder`, say) must too: if its `[tools]
allow` lists tools, add `"mcp__sparsh__*"` to it. Without it that agent
gets no phone at all, and a schedule on it is refused with that line,
before you're asked to unlock anything. Then add the phone to its
`prompt.md`, especially if that prompt tells it to wait for a yes in the
person's own words (Sarathi's `minder` does, for schedules):

```
If they ask for something done on their phone, use the phone tools. A
step that comes back held (sending, paying, deleting) is asked with a
button, not in words: say in one sentence what it will do, then call
confirm in that same answer. The yes in their own words above is for
schedules only; a phone's held step is gone by the time they reply.
```

Only one person can be the phone's: the phone is somebody's, with their
messages on it, so two people marked `phone = true` is an error. And
it's off unless you start the door with `--sparsh`
([notes/30](notes/30-do-this-on-my-phone.md)).

**On a schedule.** A scheduled run gets the phone only when its schedule
says so: one your agent made in a chat that had the phone, or `samay add
--phone`. Before it starts, the door looks at the phone. In your hand: it
waits up to ten minutes, then skips. Locked with a PIN: it asks you in
your chat to unlock it, and waits the schedule's wait. Asleep, or behind
a swipe lock with no PIN: it wakes it and goes, without asking. A Send the
schedule names when you accept it (*"send in Messages when the screen
shows 555-0123"*) goes through by itself; anything else held is asked in
your chat, and lapses if you don't answer in time
([notes/33](notes/33-the-phone-on-a-schedule.md)). Setting up the phone
itself is in Sparsh's SETUP.md.

**Test the locked-phone question by hand.** Make a schedule that works
the phone, lock the phone, and run the schedule now:

```bash
samay add "On my phone, open Settings and tell me what the Battery row says." \
  --when "at 08:00" --runner dvara --as owner --agent phone --phone --wait 5
adb shell input keyevent KEYCODE_SLEEP         # lock it (a PIN must be set to be asked)
samay run-now <the id samay printed>
```

Your chat gets *"Your phone is locked, and a schedule wants it now: …
Unlock it and it will start; it waits 5 minutes."* Unlock it, and the
run answers, on a real Nexus 6P:

```
ok   Your phone's Settings show the Battery row as: Battery — 99% · charging.
```

Leave it locked and after five minutes `samay runs` says `skipped: the
phone stayed locked for 5 minutes after you were asked to unlock it`.
With no PIN, nothing is asked and the run just goes. `samay rm <id>`
when you're done, or it runs every morning.

---

# Where to read next

Each topic, and the note that argues it:

| | |
|---|---|
| `notes/01-the-door.md` | the three nouns, the security rules, and why a daily allowance is enforced by a per-turn ceiling that shrinks |
| `notes/02-a-question-that-can-wait.md` | escalation, and why a deadline that denies belongs in the service rather than in the framework |
| `notes/03-standing-answers.md` | a rung is per turn, a rule is per call, and why patterns may widen a refusal but never a permission |
| `notes/04-the-failure-loop.md` | a bad turn becomes a case in the package that produced it — and why only a person can say a turn *answered* badly |
| `notes/05-one-person-two-channels.md` | an actor is a person, not a seat; and the allowance that silently doubled when it was not |
| `notes/06-a-number-you-can-act-on.md` | what follows an answer — and why an owner and a guest want two different numbers |
| `notes/07-four-thousand-and-ninety-six.md` | the Telegram bot: a cap measured in units nobody counts by hand, a poll loop that must not wait, and an approval that has to be a button |
| `notes/08-what-the-turn-actually-did.md` | the trajectory on a run — names and not arguments, and why the service describes a turn but will not judge one |
| `notes/09-a-process-you-walk-away-from.md` | one dvara per state directory, a roster you can edit while it runs, and the fix that would have hidden the bug |
| `notes/10-what-decided-this.md` | counting the standing answer that leaves no trace by working, and why counting by ORDER is the wrong thing to depend on |
| `notes/11-only-while-somebody-is-waiting.md` | a conversation's lock let go once nobody needs it, and not a moment before |
| `notes/12-taken-down-everywhere-it-went.md` | a question cleared off every channel it went to, once it is over |
| `notes/13-a-reply-that-is-owed.md` | after a crash, a person is told their message was not answered and will not be run again |
| `notes/14-a-days-worth-of-being-asked.md` `notes/15-where-the-waiting-shows.md` | how long a person may be kept waiting on questions in a day, and where that shows |
| `notes/16-kept-for-when-you-are-back.md` | a question nobody answered waits for the person instead of being refused |
| `notes/17-nobody-wrote-first.md` | a turn nobody typed (a schedule's), the answers given ahead of time, and a message nobody asked for |
| `notes/18-a-schedule-asked-for-in-the-chat.md` | a person's agent offering a schedule in the chat, made only with their yes on their own channel |
| `notes/19-their-own-accounts.md` | each person's own Setu sign-ins, and an agent that reaches only those, as far as its package asks |
| `notes/20-signing-in-from-the-chat.md` | `/connect`, `/accounts`, `/disconnect`: a person's own sign-in from their phone, the address pasted back to the sign-in and never to an agent |
| `notes/22-a-window-sent-to-their-phone.md` | `/connect amazon`: a browser-window sign-in streamed to the person's phone, at an address the owner chooses |
| `notes/26-the-file-itself.md` | `/files`, `/file NAME`: a person's own file from their folder, sent as itself rather than retold by the agent |
| `notes/27-your-folder-from-your-phone.md` | `setu_manage`: the owner's phone changes the owner's own folder from the chat; `/lock` stays at the computer |
| `notes/29-the-owners-page.md` | `dvara page`: the door in a browser for the owner, and why other people's words stay off it; files and schedules |
| `notes/30-do-this-on-my-phone.md` | `--sparsh` and `phone = true`: one person's phone worked from their chat, Send held for their button |
| `notes/31-their-own-page.md` | `/accounts page`: a one-time link to a person's own Setu page, and the owner's one switch |
| `notes/21-a-passphrase-only-they-know.md` | `/lock`, `/unlock`: a person's folder sealed with their passphrase, opened for the days they choose |

---

# What is deliberately not here

A feature list that only says what exists is half a map. These are
refusals and gaps, and each one is argued in the note that owns it.

* **No Slack app, and no webhook.** The Telegram bot long-polls, which
  needs no public address, no TLS and no reverse proxy. A second channel
  is an adapter and three lines of TOML, because nothing in the service
  branches on which channel a person is reachable on.
* **No per-tool policy ladder.** Tool and argument globs → allow / deny /
  ask is a real thing to want, and inventing that dialect twice is how two
  incompatible dialects are born.
* **No approve-with-edits over a channel.** The round trip is long enough
  that the edit and the thing being edited drift apart in a person's head.
  Two buttons: approve or refuse.
* **No streaming, no web UI, no registry, no scheduling.** Channels are
  turn-shaped, and each of the others is a service of its own wearing this
  one's clothes. Scheduling became exactly that: [Samay](https://github.com/kunwarmahen/samay), a program of its
  own. So did the owner's page (§17): `dvara page`, its own process, which
  only reads.
* **Locks are never evicted** — one `asyncio.Lock` per session key the
  process has ever served. A few hundred bytes against a correctness
  property, and the reason two dvaras may not share a state directory:
  that lock is in memory, so a second process does not see it.
* **No preferred channel, and no taking a question back.** A person
  reachable three ways gets the question three times, in no order, and
  answering on one leaves the other two sitting there — the bot edits the
  copy that was pressed, and only that one. Ranking channels
  means a second deadline inside the first; retracting means every
  adapter implements editing.
* **Two dvaras may not share a state directory.** A service is a process:
  the lock serializing one conversation and the queue of pending
  questions are in memory, so a second one is refused rather than made to
  work. `serve --telegram` is how one process does both jobs.
* **A package edited on disk changes a live conversation's next turn** —
  desirable when you are fixing a prompt, alarming when a conversation
  changes personality mid-sentence. Settled as a decision rather than left
  as a consequence: the edit applies, and the version is recorded on every
  Run, so the change appears in the ledger instead of being guessed at.
  Pinning a version per thread stays refused, because a pinned thread is
  one that does not get the prompt fix you made *because of it*.
* **Browser-window sites need a window address.** Amazon and X are
  streamed to the person's phone only when the owner says where that
  page listens; it's served from the owner's computer, which sees what
  they type ([notes/22](notes/22-a-window-sent-to-their-phone.md)).
* **A person's tokens are readable by the owner** unless they lock them.
  With `/lock` they're sealed with the person's passphrase while not in
  use; while unlocked, the key is in the service's memory, which the
  machine's owner could still reach
  ([notes/21](notes/21-a-passphrase-only-they-know.md)).

---

# The shape of it, in one page

1. **An actor is assigned, never asserted. An agent is named, never
   pathed.** Both are the same rule: nothing arriving from outside gets to
   choose what code runs or who it runs as.
2. **Permission composes as a minimum** across the package, the owner and
   the actor, so nothing anybody writes can loosen what somebody else
   allowed.
3. **"Ask" with nobody present is not a question, it is a hang** — so
   presence is modelled as a *route* rather than a setting, and with no
   route the answer is a denial that says so.
4. **A fresh agent per turn.** History is restored; identity is rebuilt
   from the package, so a fix made this morning applies this afternoon.

---

*dvara: 635 offline tests passing. Copyright 2026 Mahen Singh, Apache
License 2.0.*

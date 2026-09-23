# dvara — the door your agents live behind

[Yantra](https://github.com/kunwarmahen/yantra) makes an agent you can
name, hand to someone, meter and gate: a directory with an `agent.toml`
in it. **dvara is where those directories live once you stop watching
them** — one process, many people, many agents, many conversations, with
the owner's money and permissions around all of it.

*dvāra* (द्वार) is Sanskrit for a door or gateway. That is the whole job:
a door you decide who may knock on.

```
                 ┌──────────────┐
  Telegram ──┐   │              │   ┌─ greeter/      (agent.toml)
  HTTP ──────┼──▶│    dvara     │──▶├─ researcher/   (agent.toml)
  your CLI ──┘   │              │   └─ ops/          (agent.toml)
                 └──────┬───────┘
                        │  actors.toml · sessions · runs · workspaces
```

What it knows how to do is in the notes:
[01 — the door](notes/01-the-door.md) has the three nouns, the security
rules, and why a daily allowance is enforced by a per-turn ceiling that
shrinks; [02 — a question that can wait](notes/02-a-question-that-can-wait.md)
has escalation, and why a deadline that denies belongs here rather than
in the framework; [03 — standing answers](notes/03-standing-answers.md)
has the rule file, and the one mistake in it that is invisible in a diff;
[04 — the failure loop](notes/04-the-failure-loop.md) turns a bad turn
into a case in the package that produced it.
[05 — one person, two channels](notes/05-one-person-two-channels.md) makes
an actor a person rather than a seat.
[06 — a number you can act on](notes/06-a-number-you-can-act-on.md) decides
what follows an answer, and for whom;
[07 — four thousand and ninety-six](notes/07-four-thousand-and-ninety-six.md)
is the Telegram bot, and the three things a chat app decides for you;
[08 — what the turn actually did](notes/08-what-the-turn-actually-did.md)
puts the trajectory on a run, so a generated case can assert more than
"it finished";
[09 — a process you walk away from](notes/09-a-process-you-walk-away-from.md)
is the difference between a service and a program you run;
[10 — what decided this](notes/10-what-decided-this.md) counts the
standing answers, pins an approval to the call it released, and settles
what an edited package does to a live conversation;
[11 — only while somebody is waiting](notes/11-only-while-somebody-is-waiting.md)
lets a conversation's lock go when nobody needs it any more, and not a
moment before.

## Status

Roster, actors, sessions, budgets, run history, an HTTP surface and
escalation to a person, standing allow/deny/ask rules, a failure loop
that turns a bad turn into an eval case, one actor reachable on several
channels, a line under the answer for the people who asked for one, and a
Telegram bot that answers messages and puts a tool call in front of you
with two buttons on it, a run record that remembers which tools a turn
called and what decided each one, and a roster you can edit without
restarting anything. A process left running for months holds a lock only
for each conversation in flight, not for every one it has ever served —
covered by 452 tests. The API is not stable.

## The shape of it

Three nouns, one key. **Who** is talking (an actor), **which** agent they
are talking to, and **which conversation** this is (a thread). Every
session, every ceiling and every recorded run is keyed by that triple.
An actor is a **person**, not a seat: one actor may be reachable on
several channels, and the allowance, the whitelist and the queue of
pending questions are the person's.

Two rules run through every module, and both are enforced where they are
stated rather than promised:

* **dvara never parses `agent.toml`.** It calls Yantra's `load_package`.
  One parser, in the framework, with the tests.
* **The dependency edge runs one way.** dvara imports Yantra; Yantra
  never learns dvara exists.

## Setup

```bash
uv sync                          # dvara + Yantra from the checkout next door
cp .env.example .env             # then fill in a key, or point at Ollama
```

Cloud models and local ones are both first-class, and the service decides
which — not the package. A package authored against a frontier cloud
model runs on your own Ollama box with `--provider ollama`, with no edit
to somebody else's files.

## Running it

An owner needs two things: a directory of agent packages, and a file of
people.

```bash
# what this service can offer
dvara --root examples/agents --actors examples/actors.toml agents

# one turn, in process -- no HTTP, no bot token
dvara --root examples/agents --actors examples/actors.toml \
      --provider ollama --model qwen3.8-64k:latest \
      say --actor guest --agent greeter "who are you, in one sentence?"

# ask me before anything that could change something -- the question is
# printed here and the answer is a keystroke
dvara --root examples/agents --actors examples/actors.toml --ask \
      --provider ollama --model qwen3.8-64k:latest \
      say --actor owner --agent scribe "write a haiku into haiku.txt"

# ...and stop asking me the ones I have already answered
dvara --root examples/agents --actors examples/actors.toml --ask \
      --policy examples/policy.toml \
      --provider ollama --model qwen3.8-64k:latest \
      say --actor owner --agent scribe "write a haiku into notes.txt"

# what it has been doing -- what each turn did, and what decided it
dvara --root examples/agents --actors examples/actors.toml runs
#   2026-09-18 03:18  owner/scribe  end_turn   $0.0007  'write API_KEY=…'
#                     scribe changed after this turn: 0.1.0 -> 0.2.0
#                     write_file(refused)[rule:eabd9e26]

# and which of your standing answers are earning their place
dvara --root examples/agents --actors examples/actors.toml \
      --policy examples/policy.toml rules

# and when one of those turns was bad, write it into the package's gate
dvara --root examples/agents --actors examples/actors.toml \
      case 9dcfabec --because "it invented a filename I never gave it"

# answer messages as a Telegram bot, asking you before anything that
# could change something -- the question arrives with two buttons on it
TELEGRAM_TOKEN=... dvara --root examples/agents --actors examples/actors.toml \
      --ask --provider ollama --model qwen3.8-64k:latest \
      telegram --agent scribe

# listen for channel adapters that are somewhere else -- optionally with
# a bot in the same process, which is the only way to have both
DVARA_TOKEN=$(openssl rand -hex 24) dvara serve --port 8765
DVARA_TOKEN=... TELEGRAM_TOKEN=... dvara serve --telegram researcher
```

`--root`, `--actors`, `--policy` and `--state` also read `$DVARA_ROOT`,
`$DVARA_ACTORS`, `$DVARA_POLICY` and `$DVARA_STATE`.

### The actors file

Who this service serves. It holds no secrets — it is a thing you commit.

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

`permissions` can only ever tighten. The mode a turn runs under is the
minimum of the package's, the owner's and this one, so `"yolo"` beside a
guest's name grants them exactly nothing.

An unknown key is an error, not a shrug:

```
error: ~/dvara/actors.toml: [actor.guest] has unknown key(s) max_usd_per_dayz;
known: agents, channel, max_usd_per_day, max_usd_per_turn, permissions,
receipt
```

**What follows their answers.** `receipt = "cost"` puts what the turn cost
under it; `receipt = "remaining"` puts what is left of their allowance.
Absent — the default — puts nothing.

Two keys rather than one boolean because two readers want two different
numbers: an owner is watching a bill, and a person on an allowance is
deciding whether to ask the follow-up. `"remaining"` without a
`max_usd_per_day` is refused at load. Under a provider that bills nothing
both render nothing, because a meter that cannot move is noise.

**Where a person can be reached.** A channel adapter does not carry its
own table of who is who; it hands over the identity it has and the
roster maps it.

```toml
[[actor.owner.channel]]
kind = "telegram"
id   = 8675309       # numbers are fine; stored and compared as text
```

One person, one allowance, one queue of questions, several doors — and a
question raised anywhere is delivered to every channel that person holds.
`kind` is any lower-case token; dvara never branches on which channel it
names. A `(kind, id)` pair belongs to at most one actor, checked across
the whole file at load:

```
error: ~/dvara/actors.toml: telegram id '8675309' is claimed by both
[actor.owner] and [actor.guest]; one channel identity is one person, and
there is no right way to guess which
```

Check a mapping without standing up a bot:

```bash
dvara say --as telegram:8675309 --agent greeter "who are you?"
```

A turn that arrives through a channel is keyed under `kind:thread`, so
two channels whose thread ids collide stay two conversations. Naming an
actor directly keys exactly as it always did.

### The policy file

Optional, and with none the service behaves exactly as it did before
rules existed. A rung is chosen once per turn; a rule is matched per
*call*, so the same question stops being asked every morning
([notes/03](notes/03-standing-answers.md)):

```toml
[[rule]]
tool    = "bash"
args    = { command = ["git status", "git diff"] }
verdict = "allow"

[[rule]]
tool    = "write_file"
args    = { path = ["*.env", "*/.ssh/*"] }
verdict = "deny"
reason  = "secrets are not edited by an agent -- tell me and I will do it"
```

Three rules hold it up, and the third is the one worth carrying away:

* **The rung says whether there is a question; a rule says what the
  answer is.** A `deny` bites at every rung including `--yolo`; an
  `allow` grants nothing the ladder would not have been willing to *ask*
  about, so the same file is a standing yes for the owner and nothing at
  all for a `read_only` guest.
* **The strictest matching rule wins, not the first.** Order does not
  matter, so a rule appended at the bottom cannot quietly undo one at the
  top.
* **Patterns widen a refusal, never a permission.** `deny` and `ask` take
  globs; wildcards in an `allow` are refused at load time, because
  `"git status*"` matches `git status; rm -rf ~` and `"~/notes/*"`
  matches `~/notes/../../.ssh/id_rsa`. Write the exact strings — a near
  miss is still *asked*, not refused.

`--policy` is required if you name it and optional at
`~/dvara/policy.toml`, so a typo in the path is an error rather than a
file that silently does nothing.

**What each rule has actually done.** A deny announces itself; an allow
is invisible by construction, because the call just runs. So a policy
file fills up with lines you cannot tell apart by looking
([notes/10](notes/10-what-decided-this.md)):

```
$ dvara rules
policy.toml  ·  3 rule(s)  ·  calls settled over the last 30 days
      2  allow  write_file path=haiku.txt
      1  deny   write_file path=*.env|*/.ssh/*
      ·  allow  bash command=git status|git diff

  ·  = never matched a call in this window.
```

Counted over *calls*, not turns. A rule is identified by what it **says**,
not where it sits — so inserting a line at the top does not shuffle the
counts, and editing a rule starts its count over, because you changed the
standing answer.

### The failure loop

An author writes the failures they can imagine. The ones that matter
arrive later, in production, and this service records every one of them
as a `Run`. `dvara case RUN_ID` turns one into a `[[case]]` block for
that package's own acceptance gate
([notes/04](notes/04-the-failure-loop.md)):

```
$ dvara case 9dcfabec
[[case]]
id = "trace-9dcfabec"
description = """
This turn crashed in production: ProviderError: 404: not_found_error:
model 'no-such-model:latest' not found
...
```

It **prints**, and `--write` is a flag somebody types. A service that
appended to the package it runs would be editing the folder its owner
reviews and commits, which is the thing note 01 refused to let a running
agent do — and a gate that grew overnight is not a gate anybody trusts.

Two rules worth knowing before you reach for it:

* **A refused run is never a case.** No agent ran, so the row is about
  this machine rather than about the package.
* **A turn that ended normally needs `--because`.** The service can see
  that a turn *stopped* badly; only a person can see that one *answered*
  badly, and that is the commoner failure. The sentence you type becomes
  the case's description, which is all anybody has six months later.

**The case asserts how the turn went, not just that it finished.** A
`Run` records every tool call and which of them the gate refused
([notes/08](notes/08-what-the-turn-actually-did.md)), so `required_tools`
is filled from the calls that actually ran — an agent that "fixes" a bad
turn by doing nothing no longer passes:

```
  FAIL  trace-4e183287  24.8s · 2245 tok · 2 it · no tools
        required tool not used: write_file
```

`forbidden_tools` is **not** generated, and the refused calls are printed
beside the block instead:

```
# This turn also had write_file refused by the gate, which is NOT asserted
# above: whether the fixed agent should stop trying is your call, not the
# service's. Add forbidden_tools = ["write_file"] if it is.
```

A trajectory is a description and the service watched it happen; a
prohibition is a judgement, and a call the gate refused might have been
the bug or might have been the agent correctly asking for something it
should have been given.

**Names, never arguments.** `write_file` is recorded; the path it was
given is not. The assertions take names, a row that grows with an
argument is a row that can hold a file, and this command prints into a
file you commit.

### The Telegram bot

One bot, one agent, however many people the roster allows
([notes/07](notes/07-four-thousand-and-ninety-six.md)):

```bash
export TELEGRAM_TOKEN=...          # BotFather gives you one per bot
dvara telegram --agent researcher
```

There is no `--token`, on purpose: a credential on a command line is in
your shell history and readable in every `ps` on the box. **A bot token
is an identity** — a name, a picture, an @handle somebody types — so a
second agent is a second token and a second process rather than a prefix
on every message. `/start` is answered here, from what the package says
about itself, and it is the only command there is.

The bot runs the service **in its own process** and reaches the ask desk
directly, which is why a question can be pushed the moment it is raised.
`dvara serve` is the other thing entirely: the way in for an adapter that
is somewhere else.

Three things the medium decides for you:

* **A reply is split at 4096, never truncated**, and the cap is counted
  in UTF-16 code units rather than characters — so a 3000-character
  answer with emoji in it is 4200 units and would otherwise be rejected
  whole. Cuts land on a blank line, then a newline, then a space.
* **Nothing is sent with a `parse_mode`.** Markdown mode makes the
  model's own punctuation a syntax error: one unmatched `*` and the whole
  answer comes back as a 400.
* **An approval is a button, not a message.** A turn holds its
  conversation's lock while it waits, so "yes" typed into the chat queues
  behind the very turn it was meant to release.

A backlog is passed over at startup — a day-old "what changed today?"
answered now is a wrong answer, and ten held messages spend ten turns of
somebody's allowance at once. `--catch-up` answers them instead.

Somebody who is not in `actors.toml` gets **silence**, and you get the
line that says how to add them:

```
telegram: 5551212 messaged and is not in the actors file
(add [[actor.NAME.channel]] kind="telegram" id=5551212)
```

### Leaving it running

**One dvara per state directory.** A second one is refused, and says who
is already in there ([notes/09](notes/09-a-process-you-walk-away-from.md)):

```
error: another dvara is already using ~/dvara/state (pid 3641987 running
dvara serve). A service is a PROCESS, not a directory: the lock that
serializes two messages in one conversation, and the questions waiting
for you to answer them, both live in memory and cannot be shared. Stop
that one, give this one its own --state, or run both jobs in one process
(dvara serve --telegram AGENT).
```

The SQLite contention two processes cause is only the symptom. The
disease is that the lock serializing two messages in one conversation,
and the queue of questions waiting for a person, are in memory — so two
processes would both rehydrate one checkpoint, both save, and lose a turn
without anything raising.

So a bot *and* an HTTP surface means one process:

```bash
DVARA_TOKEN=… TELEGRAM_TOKEN=… dvara serve --telegram researcher
```

Commands that run a turn (`say`, `serve`, `telegram`) take the claim.
Commands that only read (`runs`, `case`, `agents`) do not — looking at
your ledger while the bot answers somebody is ordinary. And `Service`
itself claims nothing, so embedding it in your own process is unaffected.

**Edit the actors and policy files while it runs.** Both are reread when
they change, so adding a guest is one edit and no restart:

```toml
[actor.guest]
agents          = ["greeter"]
max_usd_per_day = 0.05
```

**A bad file keeps the last good one.** A typo at midnight must not
refuse everybody — including the person who would fix it — so a file that
has stopped parsing is a complaint on the owner's terminal and nothing
else:

```
~/dvara/actors.toml: Expected ']' at the end of a table declaration (at
line 3, column 13)
  -- keeping the roster already loaded; nothing changed for anybody
     talking right now
```

At *startup* the opposite holds and a broken file is exit 2: nothing is
serving yet, so there is nothing to lose.

### The HTTP surface

```
POST /message      {actor, agent, thread, text}  -> {text, ok, run_id, actor, receipt, ...}
GET  /agents                                     -> {agents: [...]}
GET  /health
GET  /asks?actor=                                -> {asks: [{id, tool, summary, ...}]}
POST /asks/{id}    {actor, approve}              -> {answered, approved}
```

Every request carries `Authorization: Bearer $DVARA_TOKEN`. **The token
authenticates the caller, not the person**: a caller is a channel adapter
inside your trust boundary. A service with no token refuses to start, and
binds to localhost unless told otherwise.

**Two ways to say who, and an adapter should prefer the second.** `actor`
is an assertion by a trusted caller. `channel` hands over the identity
the adapter actually has and lets the roster map it — a bridge that
carries no table of its own cannot carry a stale one. Exactly one form
per request; both is a 400.

```
POST /message      {"channel": {"kind": "telegram", "id": 8675309}, ...}
GET  /asks?channel=telegram&channel_id=8675309
POST /asks/{id}    {"channel": {...}, "approve": true}
```

`/message` answers with the `actor` it ran as, which is what a bridge
needs to answer a question that turn raised.

## Asking a person

With nobody attached, a service refuses anything that could change
something and tells the model why — which is the right default at three
in the morning and infuriating at three in the afternoon. Escalation is
what you add when somebody is around, and it is **a route, not a
setting**: somewhere a question can go, and somewhere an answer can come
back from.

```python
from dvara import AskDesk, Service

service = Service(roster=..., actors=..., state=...,
                  asks=AskDesk(timeout=120, notify=send_it_to_them))
```

A desk may instead route by channel, and then a question put to a person
goes to every channel they are listed on — answer it from any of them,
or over HTTP:

```python
desk = AskDesk(timeout=120)
desk.route("telegram", send_to_telegram)   # ask.to is their address
```

With a desk, `mode = "ask"` means ask: the turn suspends — it does not
block, so every other conversation keeps running — until a person answers
or the deadline passes. With no desk it means read-only tools only, which
is exactly how a service behaved before any of this existed.

Three refusals, three different sentences to the model, because they call
for three different next moves: **they said no** (do not re-run it),
**nobody answered** (silence, not a refusal — try again later), and
**nobody could be reached** (asking again will not help).

**Answers do not arrive as messages.** A turn holds its conversation's
lock while it waits, so typing "yes" into the chat queues up behind the
very turn it was meant to release. Answers come through the desk, or
through `POST /asks/{id}` — or, in a chat, as a button press, which is a
`callback_query` and not a message.

`dvara telegram --ask` is the whole of this wired up: the question is
delivered to the person's own chat with two buttons on it, the press
lands on `AskDesk.answer`, and the message is edited to say what was
decided so it cannot be pressed twice.

## Embedding it

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

## The source tree

| module | what it holds |
|---|---|
| `service.py` | `Service.deliver` — one message in, one reply out ([notes/01](notes/01-the-door.md)) |
| `roster.py` | agents resolved by NAME from one owner-controlled root |
| `actors.py` | who is served, what they may reach, what they may spend, and where they can be reached ([notes/05](notes/05-one-person-two-channels.md)); reread when the file changes ([notes/09](notes/09-a-process-you-walk-away-from.md)) |
| `keys.py` | the `(actor, agent, thread)` session key and its escaping |
| `locks.py` | one lock per conversation or chat, dropped once nobody holds or waits on it ([notes/11](notes/11-only-while-somebody-is-waiting.md)) |
| `money.py` | package ∧ actor ∧ what is left of today, and the line under the answer ([notes/06](notes/06-a-number-you-can-act-on.md)) |
| `gate.py` | three rungs, and the tightest wins ([notes/02](notes/02-a-question-that-can-wait.md)); how a rung and a rule compose ([notes/03](notes/03-standing-answers.md)) |
| `rules.py` | standing allow/deny/ask answers, matched per call ([notes/03](notes/03-standing-answers.md)), and counted ([notes/10](notes/10-what-decided-this.md)) |
| `asks.py` | questions waiting for a person, the deadline on them ([notes/02](notes/02-a-question-that-can-wait.md)), and which channels they go out on ([notes/05](notes/05-one-person-two-channels.md)) |
| `runs.py` | every turn that happened, what it cost, which tools it called and what decided each one ([notes/08](notes/08-what-the-turn-actually-did.md), [notes/10](notes/10-what-decided-this.md)) |
| `cases.py` | a bad turn -> a `[[case]]` in that package's gate ([notes/04](notes/04-the-failure-loop.md)), asserting the trajectory it took ([notes/08](notes/08-what-the-turn-actually-did.md)) |
| `http.py` | five endpoints and a bearer token (`[http]` extra) |
| `telegram.py` | the long poll, the 4096-character cap and the button ([notes/07](notes/07-four-thousand-and-ninety-six.md)) |
| `claim.py` | one dvara per state directory, and why ([notes/09](notes/09-a-process-you-walk-away-from.md)) |
| `cli.py` | `agents`, `say`, `runs`, `rules`, `case`, `telegram`, `serve` |
| `errors.py` | `Refused` (answer the person) vs `ConfigProblem` (tell the owner) |

## Security, in four sentences

1. **Agents are named, never pathed.** Loading a package runs its Python;
   a package path that can come from a message is remote code execution.
   Names resolve inside one owner-controlled root, symlinks included.
2. **Actors are assigned, never asserted.** An identity that is not in
   the owner's file is not served — including a channel's own identity,
   which the roster maps rather than the adapter, so the file the owner
   reviews is the whole answer to who is served.
3. **A package's permission mode is a floor the service may tighten and
   never loosen.** Three parties name a rung — the package, the owner and
   the actor — and the tightest wins, so nothing anybody writes can
   loosen what somebody else allowed. With no route to a person, that
   means read-only tools only. A standing rule may tighten that further
   at any rung, and may only pre-answer a call the ladder would have been
   willing to put to a person.
4. **Nothing here is sandboxed by pretending.** Yantra's sandbox confines
   an agent's tool calls; it has nothing to say about a package's
   import-time side effects, and this service does not imply otherwise.

## Provenance and license

dvara is built on [Yantra](https://github.com/kunwarmahen/yantra), a
framework for building agents written from scratch — no SDKs, no
pydantic, no heavyweight frameworks. The receipts in `notes/` were
produced against a local `qwen3.8-64k:latest` on Ollama, on hardware I
own.

Copyright 2026 Mahen Singh. Licensed under the Apache License, Version
2.0 — see [LICENSE](LICENSE).

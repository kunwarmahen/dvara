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

## Status

Roster, actors, sessions, budgets, run history, an HTTP surface and
escalation to a person, standing allow/deny/ask rules, a failure loop
that turns a bad turn into an eval case, and one actor reachable on
several channels — covered by 298 tests. No channel adapter ships yet:
the terminal is still the only thing that asks you anything, but a bot
is now a client of what exists rather than a thing to be designed
around. The API is not stable.

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

# what it has been doing
dvara --root examples/agents --actors examples/actors.toml runs

# and when one of those turns was bad, write it into the package's gate
dvara --root examples/agents --actors examples/actors.toml \
      case 9dcfabec --because "it invented a filename I never gave it"

# listen for channel adapters
DVARA_TOKEN=$(openssl rand -hex 24) dvara serve --port 8765
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
known: agents, channel, max_usd_per_day, max_usd_per_turn, permissions
```

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

### The HTTP surface

```
POST /message      {actor, agent, thread, text}  -> {text, ok, run_id, actor, ...}
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
through `POST /asks/{id}`.

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
| `actors.py` | who is served, what they may reach, what they may spend, and where they can be reached ([notes/05](notes/05-one-person-two-channels.md)) |
| `keys.py` | the `(actor, agent, thread)` session key and its escaping |
| `money.py` | package ∧ actor ∧ what is left of today |
| `gate.py` | three rungs, and the tightest wins ([notes/02](notes/02-a-question-that-can-wait.md)); how a rung and a rule compose ([notes/03](notes/03-standing-answers.md)) |
| `rules.py` | standing allow/deny/ask answers, matched per call ([notes/03](notes/03-standing-answers.md)) |
| `asks.py` | questions waiting for a person, the deadline on them ([notes/02](notes/02-a-question-that-can-wait.md)), and which channels they go out on ([notes/05](notes/05-one-person-two-channels.md)) |
| `runs.py` | every turn that happened, including the ones that failed |
| `cases.py` | a bad turn -> a `[[case]]` in that package's gate ([notes/04](notes/04-the-failure-loop.md)) |
| `http.py` | five endpoints and a bearer token (`[http]` extra) |
| `cli.py` | `agents`, `say`, `runs`, `case`, `serve` |
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

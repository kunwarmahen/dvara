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
in the framework.

## Status

Roster, actors, sessions, budgets, run history, an HTTP surface and
escalation to a person — covered by 161 tests. Channels do not exist yet:
the terminal is the only thing that asks you anything. The API is not
stable.

## The shape of it

Three nouns, one key. **Who** is talking (an actor), **which** agent they
are talking to, and **which conversation** this is (a thread). Every
session, every ceiling and every recorded run is keyed by that triple.

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

# what it has been doing
dvara --root examples/agents --actors examples/actors.toml runs

# listen for channel adapters
DVARA_TOKEN=$(openssl rand -hex 24) dvara serve --port 8765
```

`--root`, `--actors` and `--state` also read `$DVARA_ROOT`,
`$DVARA_ACTORS` and `$DVARA_STATE`.

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
known: agents, max_usd_per_day, max_usd_per_turn, permissions
```

### The HTTP surface

```
POST /message      {actor, agent, thread, text}  -> {text, ok, run_id, cost_usd, ...}
GET  /agents                                     -> {agents: [...]}
GET  /health
GET  /asks?actor=                                -> {asks: [{id, tool, summary, ...}]}
POST /asks/{id}    {actor, approve}              -> {answered, approved}
```

Every request carries `Authorization: Bearer $DVARA_TOKEN`. **The token
authenticates the caller, not the person**: a caller is a channel adapter
inside your trust boundary, and it is the adapter's job to map its
channel's identity onto an actor. A service with no token refuses to
start, and binds to localhost unless told otherwise.

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
| `actors.py` | who is served, what they may reach, what they may spend |
| `keys.py` | the `(actor, agent, thread)` session key and its escaping |
| `money.py` | package ∧ actor ∧ what is left of today |
| `gate.py` | three rungs, and the tightest wins ([notes/02](notes/02-a-question-that-can-wait.md)) |
| `asks.py` | questions waiting for a person, and the deadline on them ([notes/02](notes/02-a-question-that-can-wait.md)) |
| `runs.py` | every turn that happened, including the ones that failed |
| `http.py` | three endpoints and a bearer token (`[http]` extra) |
| `cli.py` | `agents`, `say`, `runs`, `serve` |
| `errors.py` | `Refused` (answer the person) vs `ConfigProblem` (tell the owner) |

## Security, in four sentences

1. **Agents are named, never pathed.** Loading a package runs its Python;
   a package path that can come from a message is remote code execution.
   Names resolve inside one owner-controlled root, symlinks included.
2. **Actors are assigned, never asserted.** An identity that is not in
   the owner's file is not served.
3. **A package's permission mode is a floor the service may tighten and
   never loosen.** Three parties name a rung — the package, the owner and
   the actor — and the tightest wins, so nothing anybody writes can
   loosen what somebody else allowed. With no route to a person, that
   means read-only tools only.
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

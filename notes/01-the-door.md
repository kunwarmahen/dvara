# 01 — the door: one process, many people, many conversations

*Yantra ends at a keyboard. You run `yantra --agent ./researcher`, you
talk to it, you close the laptop and it is gone — and everything in the
framework quietly assumes that: one person, present and trusted, one
conversation, one process that dies when they walk away. dvara is what
happens when you take those assumptions away one at a time. This note is
the first slice: a service that holds agents, a door people knock on, and
the three nouns that make "who is talking?" a question with an answer.*

## The problem, as you hit it

You have built an agent. It is a folder — `agent.toml`, a `prompt.md`,
maybe a `tools/` directory — and it works. Now you want two things that
sound small and are not:

1. It should still be there tomorrow, without a terminal open.
2. A friend should be able to ask it something.

The moment you try, three questions appear that a terminal never had to
answer. Who is this? Which agent are they asking for? And which of their
conversations is this — because your friend will have several, and so
will you, and mixing them up means one person reading another's history.

Everything below follows from those three questions having to be answered
before a single token is spent.

## The three nouns

**Actor** — who is talking. **Agent** — which package. **Thread** — which
conversation. Together they are the key to a session:

    session key = (actor, agent, thread)

Not `(actor, thread)`. If you and I both use the same chat with two
different agents, `(actor, thread)` gives us one shared history and the
agents start reading each other's mail. Fixing that later is a migration;
getting it right on day one is a tuple.

Yantra's `SessionStore` takes one string, so the three become one:

    mahen/greeter/chat-42

Each part is percent-escaped before it is joined, and that is not
decoration. Join them raw and an actor named `a/b` in thread `c` produces
the same key as actor `a` in thread `b/c` — one person's conversation
opening inside another's because of how they happened to be named. Escape
the separator and the mapping is one-to-one. It stays readable on purpose
rather than being hashed: `select distinct session_id from checkpoints`
should answer your question without a decoder ring.

The same escaping gives each conversation a scratch directory —
`state/work/mahen/greeter/chat-42` — and there is one hole escaping does
not close. `quote()` leaves `.` alone, because a dot is perfectly legal
in a URL path. So a thread named `..` survives escaping intact, and a
scratch directory becomes its own parent. The dot segments are
neutralised explicitly. A test names each of them.

## An actor is assigned, never asserted

This is the sentence the whole security posture hangs on.

Nothing arriving from outside gets to say who it is. The owner writes a
file:

```toml
[actor.owner]
# no keys at all: every agent, no ceilings

[actor.guest]
agents           = ["greeter"]   # a complete whitelist
max_usd_per_turn = 0.02
max_usd_per_day  = 0.10
```

A channel adapter — the thing that will one day bridge Telegram — maps
its own native identity onto one of these names. An identity with no name
here is not served, and learns nothing about who else exists:

```
$ dvara say --actor stranger --agent greeter "hello"
you are not on this service's list of people
[refused]
```

`agents` follows a convention Yantra already set for `tools.allow`:
absent means everything, a list is a complete whitelist, and an empty
list is an error rather than a silent "this person may reach nothing" —
because an empty allowlist is far likelier to be a typo than a decision.
Unknown keys are errors too. A misspelled `max_usd_per_dayz` that quietly
means "no ceiling" is exactly the failure a ceiling exists to prevent.

## Agents are named, never pathed

Yantra's note 32 has a paragraph this note exists to enforce: **loading a
package runs its Python.** `tools/*.py` is imported as you, at import
time, before any permission gate exists. That is fine for a package you
chose. It stops being fine the instant a package path can come from a
message.

So dvara resolves agents by NAME, from one directory the owner controls,
and the name has to survive three checks: it matches a conservative
pattern (rejecting `..`, `/etc/passwd`, `~`, hidden directories and
anything with a newline in it), it joins to the root, and — after
`resolve()` — it is still inside that root. The third check is the one a
pattern cannot make: a symlink is a path that lies about where it goes.

The property that makes a roster safe to list at all is Yantra's, not
ours: `load_package` imports nothing. It parses TOML and *names*
directories. Code runs later, in `spec.build_async()`, at the moment a
request actually reached an agent. There is a test with a package whose
`tools/boom.py` raises on import; listing the roster and reading its
manifest both leave it sleeping.

## Two ceilings, and a refusal to build a second meter

Yantra meters one turn. A service has to answer a different question:
what may *this person* spend, today, across every turn they have had?

There are three numbers, and one of them is not a ceiling at all:

| | |
|---|---|
| package | `max_usd_per_turn` — what the author thinks a task costs |
| actor | `max_usd_per_turn` — what the owner lets this person spend |
| today | `max_usd_per_day` minus what they have already spent |

The design decision here is a refusal: **dvara does not build a second
meter.** It takes the minimum of whichever are set, hands that one number
to Yantra's existing `Budget`, and inherits the entire apparatus that
already exists — the mid-turn stop, the warning at 80%, and the shared
meter that stops a sub-agent from clearing its parent's spend. A daily
allowance is therefore enforced by a per-turn ceiling that shrinks as the
day is spent. That is a strange sentence and a correct design: every
extra meter is another place the arithmetic can disagree with itself, and
the first place it would disagree is sub-agents.

The other half of the job is remembering *whose* number won. "Over
budget" is a log line, not an answer. This is a real session, and the
model is a local one — `qwen3.8-64k:latest` on Ollama, priced against
itself through `$YANTRA_PRICES` so a ceiling could be rehearsed without
an account with a card behind it:

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

For a local model the whole path stays visible and stays quiet: with no
price override, that same turn records `$0.0000`, not "unknown". A
missing list price means two opposite things — on your own Ollama box
there is nothing to pay, on a hosted model nobody knows — and writing a
zero into a row you will later sum is how a bill becomes a surprise.

## Permission, with nobody in the room

A package declares a permission mode. dvara treats it as **a floor it may
tighten and never loosen**: a package that ships `mode = "yolo"` does not
get yolo because it asked. It gets yolo only if the owner of the machine
said so too.

And then the sentence that decides what this slice is: **"ask" with
nobody present is not a question, it is a hang.** There is no human
attached to a service at three in the morning. So the gate decides by
policy alone — tools that declared `read_only` are approved, everything
else is denied — and the denial arrives as *data*, which is what Yantra's
gate already does: a refused call becomes an error result the model can
read and work around, never an exception that kills the turn.

Escalating properly — asking you, in the chat you are already in, whether
this `bash` may run — is the next note, and it needs something Yantra
does not have yet. `PermissionFn` is synchronous, and `AsyncAgent` calls
it inline inside the running coroutine. A gate that waited for a human
would block the event loop and every other conversation on the service
with it. That is a missing seam in the framework, not a puzzle to be
clever about here with a thread and a queue.

## What a service does that a session never had to

**A fresh agent per turn.** Not a pool of warm ones. Warm agents buy
latency and cost three things: memory that grows with every actor who
ever said hello, a spec that goes stale the moment you edit a package,
and a crash that loses history nobody wrote down. Rebuilding is also the
only version of this where a restart is a non-event, which is the whole
point of an always-on thing.

**One provider, held.** The opposite decision, for the opposite reason.
Constructing a provider opens an httpx connection pool — two, in fact,
one sync and one async — so resolving one per turn would leak pools for
as long as the process lived. Providers are cached by name for the life
of the service and passed in through `build_async(provider=...)`.

**History is restored; identity is rebuilt.** Yantra's `apply_payload`
restores the system prompt, the model and `max_iterations` along with the
messages. That is exactly right for `/load` at a keyboard and exactly
wrong here: a prompt you fixed this morning must take effect this
afternoon, and a model you chose must not be silently replaced by
whatever answered last week. So those three fields are captured from the
freshly built agent and put back after rehydration. What comes out of the
store is the conversation. Everything else comes out of the package.

Here is the whole of it working — two separate invocations of the
command, one after the other, no process shared between them:

```
$ dvara say --actor guest --agent greeter --thread demo "who are you, in one sentence?"
I'm the doorkeeper's greeter — I let you in and point you the right way,
and that's about all I do.
[end_turn · 83in/61out · run d00e7bb697d5]

$ dvara say --actor guest --agent greeter --thread demo "what did I just ask you?"
You asked who I am, in one sentence.
[end_turn · $0.0000 · 132in/36out · run 8ab69c279abe]
```

**One lock per conversation.** Two messages in one thread serialize.
Interleaving them would put two user messages into one history with a
single assistant reply between them, and Yantra's resumability invariant
holds at prompt boundaries for a reason.

**An agent writes in a workspace, not in its package.** The package
directory is read-only input; each conversation gets its own scratch
directory under the service's state. An agent that edits the folder you
review and commit is an agent whose package has stopped being
reviewable — and being reviewable is the one property the whole format
exists to have.

## Every turn leaves a row

Including the ones that failed. A script forgets; a service that forgets
cannot answer the owner's first question.

```
$ dvara runs
2026-09-15 17:46  guest/greeter  end_turn          $0.0584  'and again?'
2026-09-15 17:46  guest/greeter  end_turn          $0.0468  'hello'
```

**A turn that crashes still pays for what it spent.** Three model calls
and then a 500 is still three model calls, and the accounting has to
happen in the same `finally` that saves the session — the handler that
catches the exception has a run record and no agent left to ask. Leave it
out and a crash erases its own cost, so the daily allowance never sees
it, and somebody with a $2 day can spend the afternoon in failing turns.
The other direction matters too: a turn that never reached a model costs
`$0.0000`, not "unpriced". "Unpriced" is the store admitting a doubt, and
about a turn that never happened there is no doubt to admit.

Three later features are all queries over this one table, which is why it
exists in the first slice rather than the fourth. Money over time is a
`SUM` over it. An audit is a `SELECT`. And a failed run is a *trace* —
which is the shape Yantra's `case_from_trace` turns into an eval case in
the package that produced it. The loop the authoring arc was built to
close runs through this table: the agent fails in production, the failure
becomes a case, the package's own gate stops it coming back.

## The door itself

Three endpoints, and the module is honest about being only a transport:

    POST /message   {actor, agent, thread, text}
    GET  /agents
    GET  /health

**The token authenticates the caller, not the person.** That distinction
is the whole posture of this layer. A caller is a channel adapter running
inside the owner's trust boundary, and it is the adapter's job to map its
channel's identity onto an actor. The `actor` field in the body is an
assertion *by a trusted caller* — which is precisely why the bearer token
is mandatory rather than optional. Without it, anyone who reaches the
port can claim to be anyone in the file. A service with no token refuses
to start, the default bind is localhost, and the comparison is
constant-time.

A refusal comes back as a `200` with a reason, not a `500`. A channel
adapter has to be able to deliver "you are not on this list" as a
message; an exception is a reply that silently never arrives.

## What is deliberately not here

* **No channel.** Telegram is note 02, and the core it plugs into had to
  exist first. `dvara say` drives the service in-process, with no HTTP
  and no bot token, which is how every receipt above was produced.
* **No escalation.** See the permission section: it needs an awaitable
  gate in Yantra, which is Yantra's feature to argue.
* **No policy ladder.** Tool + argument globs → allow / deny / ask is
  note 04, and it only means anything once there is a human to escalate
  to. Inventing the dialect twice is how two incompatible dialects are
  born.
* **No streaming.** One message in, one reply out. Channels are
  turn-shaped, and a bot that streams is a bot that edits the same
  message forty times and gets rate-limited for it.
* **No web UI, no registry, no scheduling, no second process.** Each of
  those is a service of its own wearing this one's clothes.

## What is not here yet

* **Locks are never evicted.** One `asyncio.Lock` per session key the
  process has ever served — a few hundred bytes against a correctness
  property, and evicting them safely needs a refcount nobody has asked
  for yet.
* **A denied tool call still says "Permission denied by user."** There
  was no user. The string is Yantra's, and the model is being told
  something untrue about why it was refused.
* **No `Provider.close()`.** Shutdown reaches into `.client` and
  `.aclient` directly, which works and is not a seam anybody promised.
* **A package edited on disk changes a live conversation's next turn.**
  Desirable when you are fixing a prompt, alarming when a conversation
  changes personality mid-sentence. Pinning a package version per thread
  is the alternative, and it is a column plus a great deal of explaining.
* **One actor per channel.** The same person on Telegram and over HTTP is
  two actor ids today. One actor with several channel identities is
  right, and is a table.

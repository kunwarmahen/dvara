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
moment before;
[12 — taken down everywhere it went](notes/12-taken-down-everywhere-it-went.md)
clears a question off every channel it was sent to, once it is answered,
refused, timed out or no longer needed;
[13 — a reply that is owed](notes/13-a-reply-that-is-owed.md) tells a
person, after a crash, that their message was not answered and will not
be run again;
[14 — a day's worth of being asked](notes/14-a-days-worth-of-being-asked.md)
limits how long a person may be kept waiting on questions in a day,
without stopping anything that needed nobody;
[15 — where the waiting shows](notes/15-where-the-waiting-shows.md)
puts that allowance under the answer and in `dvara runs`;
[16 — kept for when you are back](notes/16-kept-for-when-you-are-back.md)
lets a question nobody answered wait for the person instead of being
refused, across a restart, and carries the turn on when they answer.
[17 — nobody wrote first](notes/17-nobody-wrote-first.md) runs a turn
nobody typed (a schedule's, from Samay) with the answers the person gave
ahead of time, and tells a person something they did not ask about.
[18 — a schedule asked for in the chat](notes/18-a-schedule-asked-for-in-the-chat.md)
lets a person's agent offer one, made only with their yes on their own
channel. [19 — their own accounts](notes/19-their-own-accounts.md) gives
each person their own Setu sign-ins, and
[20 — signing in from the chat](notes/20-signing-in-from-the-chat.md)
lets them connect one from their phone;
[21 — a passphrase only they know](notes/21-a-passphrase-only-they-know.md)
lets them lock it; and
[22 — a window sent to their phone](notes/22-a-window-sent-to-their-phone.md)
lets them sign in to Amazon or X from wherever they are.

New here? [TUTORIAL.md](TUTORIAL.md) walks through it in order, from a
first turn to a bot that asks you before anything changes.

## Works with

* **[Yantra](https://github.com/kunwarmahen/yantra)** — every agent here is a Yantra package, built fresh
  for each turn. Tools, skills, permission modes and evals are Yantra's,
  and [its tutorial](https://github.com/kunwarmahen/yantra/blob/main/TUTORIAL.md) is where they are explained.
* **[Samay](https://github.com/kunwarmahen/samay)** — runs a person's schedules through this door, as
  them ([notes/17](notes/17-nobody-wrote-first.md)), and with `--samay`
  lets their agent offer one in the chat
  ([notes/18](notes/18-a-schedule-asked-for-in-the-chat.md)). Samay's
  own setup is in its README.
* **[Setu](https://github.com/kunwarmahen/setu)** — each person can have
  a folder of sign-ins of their own (`setu` in the actors file); their
  agent reaches only those accounts, as far as the package asks
  ([notes/19](notes/19-their-own-accounts.md)), and they connect them
  from the chat with `/connect gmail`
  ([notes/20](notes/20-signing-in-from-the-chat.md)).
* **[Sparsh](https://github.com/kunwarmahen/sparsh)** — with `--sparsh`,
  the agents of the one person marked `phone = true` work the phone
  plugged into this machine, and a step that can't be taken back (Send,
  Pay, Delete) comes to their chat as Yes and No buttons
  ([notes/30](notes/30-do-this-on-my-phone.md)).
* **[Sarathi](https://github.com/kunwarmahen/sarathi)** — starts this
  door beside Yantra's page and Samay's clock, wired to the clock, with
  a Telegram bot: `sarathi dvara`, then `sarathi up` (its note 04).

## Status

Roster, actors, sessions, budgets, run history, an HTTP surface and
escalation to a person, standing allow/deny/ask rules, a failure loop
that turns a bad turn into an eval case, one actor reachable on several
channels, a line under the answer for the people who asked for one, and a
Telegram bot that answers messages and puts a tool call in front of you
with two buttons on it, a run record that remembers which tools a turn
called and what decided each one, and a roster you can edit without
restarting anything. A process left running for months holds a lock only
for each conversation in flight, not for every one it has ever served, and
a question answered in one place stops asking in all the others. A crash
mid-answer is owned up to on the next start rather than left as silence,
a person who stops answering stops being asked for the day, and a
question they never saw can wait for them to come back instead of being
refused. A turn nobody typed runs with the yes the person gave ahead of
time and nothing more, and a finding nobody asked for reaches them on
their own channels; with `--samay`, a person can ask for a schedule in
the chat and say yes to it there; and each person's agent reaches that
person's own accounts through Setu, never anybody else's; and a program
that started it can ask whether it is serving, and a scheduled run's
conversation is let go a week after it ends while what it wrote stays
where the person's chat can read it, and sent to them as a file when
they ask; and with `--sparsh`, the phone on this machine works for its
one person from their chat, with Send held for their button — covered
by 728 tests. The API is not stable.

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

Two extras, when you want them: `--extra http` for `dvara serve`'s HTTP
side, and `--extra browse` for a package that reads a site through a
browser (Setu's Amazon or X) -- without it those tools are offered and
fail for want of Playwright.

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

# ...and if I do not answer in time, keep it for me rather than refusing
dvara --root examples/agents --actors examples/actors.toml --ask \
      --ask-timeout 60 --on-timeout hold \
      --provider ollama --model qwen3.8-64k:latest \
      say --actor owner --agent scribe "write a haiku into haiku.txt"
dvara --root examples/agents --actors examples/actors.toml held
dvara --root examples/agents --actors examples/actors.toml \
      resume HOLD_ID --actor owner --approve

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

# ...or all of it in a browser: people, today's spend, agents, every turn
dvara --root examples/agents --actors examples/actors.toml page --as owner

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

[actor.friend]
permissions      = "ask"           # may be asked to approve a write...
max_wait_per_day = 300             # ...for up to five minutes of waiting a day
```

`permissions` can only ever tighten. The mode a turn runs under is the
minimum of the package's, the owner's and this one, so `"yolo"` beside a
guest's name grants them exactly nothing.

An unknown key is an error, not a shrug:

```
error: ~/dvara/actors.toml: [actor.guest] has unknown key(s) max_usd_per_dayz;
known: agents, channel, max_usd_per_day, max_usd_per_turn,
max_wait_per_day, permissions, phone, receipt, setu, setu_accounts,
setu_manage
```

**How long they may be kept waiting.** `max_wait_per_day` is seconds a
day the service may spend waiting on this person's answers. What is
left shortens each question's deadline; once it is spent, calls that
would have been asked are refused without asking, while reads and
anything a standing rule allows still run. Time, not questions, because
an unanswered ping is the case that matters
([notes/14](notes/14-a-days-worth-of-being-asked.md)).

**What follows their answers.** `receipt = "cost"` puts what the turn cost
under it; `receipt = "remaining"` puts what is left of their allowance,
and, under a turn that kept them waiting, how much waiting is left today
([notes/15](notes/15-where-the-waiting-shows.md)). Absent — the default —
puts nothing.

Two keys rather than one boolean because two readers want two different
numbers: an owner is watching a bill, and a person on an allowance is
deciding whether to ask the follow-up. `"remaining"` without a
`max_usd_per_day` or `max_wait_per_day` is refused at load. Under a
provider that bills nothing the money renders nothing, because a meter
that cannot move is noise; the waiting still shows, because a person's
time costs the same on every road.

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

**Their own accounts.** `setu = true` gives a person a
[Setu](https://github.com/kunwarmahen/setu) folder of their own
(`<state>/setu/<name>`, readable by the service alone); a path points at
an existing one, such as yours. `setu_accounts` narrows a folder to the
accounts meant. Absent means none. `setu_manage = true` lets a person
change a folder they were pointed at from the chat -- meant for you, on
your own folder, from your phone ([notes/27](notes/27-your-folder-from-your-phone.md)).

```toml
[actor.raj]
setu = true

[actor.priya]
setu = "~/.local/state/setu"         # your own folder...
setu_accounts = ["gmail:personal"]   # ...but only this account of it

[actor.owner]
setu = "~/.local/state/setu"         # the folder your desktop and page use
setu_manage = true                   # ...and /connect, /disconnect reach it
```

**Their phone.** `phone = true` says the phone plugged into this machine
is theirs: with `--sparsh`, their agents can work it (*Your phone, from
the chat*, below). One person at most: two marked is an error naming
both.

Each turn reads Setu in that person's folder and starts their
connections there, so their agent can only open their accounts, and only
those the package asks for in `[connections] needs`, at the package's
level.

A person with a folder of their own -- or one the owner let them manage
-- signs in from the chat:

```
/connect gmail                 they get Google's link, sign in on their phone, and
                               send back the address of the page that won't load
/accounts                      what's connected for them
/accounts page                 a link to their own folder's page in Setu: once, on the
                               first device, for ten minutes (notes/31)
/disconnect gmail:personal     revoke and forget
/lock, /unlock [days]          a passphrase only they know (notes/21); a folder of
                               their own only -- a shared one is locked at the computer
```

Anyone can ask for the files their agent keeps for them (a log a
schedule writes, a report), whether or not they have accounts:

```
/files                         what's in their folder with this agent
/file uptime-log.txt           that file, sent as a Telegram document
```

These are answered by dvara too, from that person's folder and nowhere
else. An agent whose package lists `send_file` can send one itself
("send me the log", or a schedule's weekly report). It's a write, so it
asks in a chat, and in a schedule it runs only if the card allowed it
([notes/26](notes/26-the-file-itself.md)).

And anyone can start their conversation with an agent over:

```
/new                           forget this conversation; files, schedules,
                               accounts and the ledger all stay
```

A chat is one conversation for as long as it lasts, and a long one can
teach a small model a habit (an old way of reading a site, kept after a
better tool arrived). Telegram's own "Clear history" never reaches the
bot; `/new` does ([notes/28](notes/28-starting-over.md)).

These go to dvara, never to an agent, and the pasted address goes only to
the waiting sign-in ([notes/20](notes/20-signing-in-from-the-chat.md)).
Their folder borrows your Google client file; while your Google app is in
Testing mode, add each person's address as a test user. A folder you
pointed them at (priya's, above) stays yours to change, at the machine:
`SETU_HOME=<folder> setu connect gmail`. Sites signed in to through a
browser window (Amazon, X) are streamed to their phone when you give
the service a window address (`SETU_WINDOW_HOST`, and `SETU_WINDOW_URL`
behind a tunnel); without one they're connected at the machine
([notes/22](notes/22-a-window-sent-to-their-phone.md)). A
person's tokens sit on your disk, where you could read them; say so to
anyone you give a folder ([notes/19](notes/19-their-own-accounts.md)).

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
about itself, and it is the only command there is. A bot running in
this process is also where `POST /notify` sends a person something they
did not ask about — a schedule's finding — straight to their chat
([notes/17](notes/17-nobody-wrote-first.md)).

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

Under `--on-timeout hold`, a question nobody answered stops the turn
rather than refusing the call, and the reply that says so ends with
**approve all** and **refuse all**. A press carries the turn on, and the
rest of the answer arrives in the conversation's own chat — the group,
if that is where it started. One answer for the whole batch; answering
call by call is `dvara resume` or `POST /holds/{id}`
([notes/16](notes/16-kept-for-when-you-are-back.md)).

A backlog is passed over at startup — a day-old "what changed today?"
answered now is a wrong answer, and ten held messages spend ten turns of
somebody's allowance at once. `--catch-up` answers them instead.

A message the bot was in the middle of answering when it stopped is
**never run again** — the turn may already have run a tool — but it is
not forgotten either. On the next start, that person is told their
message was not answered and can be sent again; an answer that was
finished but only partly sent has its remaining parts sent
([notes/13](notes/13-a-reply-that-is-owed.md)):

```
telegram: 1 reply owed from before the last stop
```

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

Commands that run a turn (`say`, `serve`, `telegram`, `resume`) take the claim.
Commands that only read (`runs`, `held`, `case`, `agents`, `status`) do not — looking at
your ledger while the bot answers somebody is ordinary.

**Is it serving?** `dvara status` asks the same lock, so the answer is right
after a `kill -9` and from another container
([notes/23](notes/23-is-the-door-open.md)):

```
$ dvara status
dvara 0.1.0 · state /home/you/dvara/state
serving at http://127.0.0.1:8765 (dvara serve, since 2026-10-06T02:56:39+00:00)
agents: greeter, minder, scribe  ·  people: 2
```

`--json` prints the same as `dvara.status.v1`, for a program that started
this one. And `Service`
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

### The owner's page

`dvara page` shows your door in a browser. It's a separate process that
only reads, so it runs whether or not `dvara serve` does:

```
$ DVARA_TOKEN=... dvara page --as owner
dvara's page for owner:
  http://127.0.0.1:8785/#token=…
```

The page has a card for each person in the actors file (today's spend
against their daily allowance, the past seven days, their agents, how
they're reached), the agents and who may use each, and every turn newest
first, filtered by person or agent, with the tools it called and the
refused ones in red.

* **What was said is shown only for your own turns** (`--as`, default
  `owner`). Everyone else's turns show their shape (agent, cost, tools,
  outcome) but not their words. Channels show by kind (`telegram`), never
  by id.
* **Your own questions, answered.** **Waiting for you** at the top shows
  what your agents are asking you now, and turns held for you, with
  Allow and Refuse. Answers go to the running door as you, the same as
  the button in your chat. Start the page with `DVARA_TOKEN` set (the
  door's token, kept server-side) and, if the door isn't where `dvara
  status` says, `DVARA_URL`. Nobody else's questions appear.
* **Each person's files**, folder by folder with each agent: names, sizes
  and dates. Only your own open on the page, as text, inside the same
  walls as `/file` in the chat.
* **Each person's schedules**, in Samay's own words: the sentence, when it
  runs next, and how the last run ended. What a schedule asks for is
  shown only for yours. The page reads them with `samay list --json`
  (`dvara --samay PATH page`, `$DVARA_SAMAY`, or `samay` on PATH), and links
  to Samay's page for changes.
* **Nothing else changes from it.** To change who is served or what
  they may spend, edit the actors file as before.
* **Its own token.** Every `/api` call needs `$DVARA_PAGE_TOKEN`, or the one
  the page makes once in the state folder (`page.token`, 0600). It isn't
  `DVARA_TOKEN`, which can speak as anyone and never goes to a browser.
  The page listens on 127.0.0.1 only unless you pass `--host`, and no
  other site can frame it.

The reasoning is in [notes/29](notes/29-the-owners-page.md).

### The HTTP surface

```
POST /message      {actor, agent, thread, text}  -> {text, ok, run_id, actor, receipt, files, ...}
GET  /agents                                     -> {agents: [...]}
GET  /health
GET  /asks?actor=                                -> {asks: [{id, tool, summary, ...}]}
POST /asks/{id}    {actor, approve}              -> {answered, approved}
GET  /holds?actor=                               -> {holds: [{id, calls, age, ...}]}
POST /holds/{id}   {actor, answers: {call: true|false|"reason"}}  -> like /message
POST /notify       {actor, text}                 -> {sent, kept, failed, nowhere}
GET  /notices?channel=                           -> {notices: [{id, to, text, file, ...}]}
```

A program that runs turns for people who are not there — a scheduler —
adds `"unattended": true` to `/message`, and may add `"allow_tools":
[globs]`: the questions the person answered ahead of time. They grant
only what the person could have been asked about (a deny rule still
refuses), the call is recorded as `[ahead]` in `dvara runs`, and the
reply carries `needs_person`, `busy` and `refused`. `/notify` sends a
text to a person's channels from the actors file; a channel with no
adapter in this process collects from `/notices`, each one once, kept
in memory ([notes/17](notes/17-nobody-wrote-first.md)).

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
needs to answer a question that turn raised — and, for a turn that
stopped to wait, with `held`: the id `POST /holds/{id}` answers, and the
calls to show. Only a JSON `true` approves; the string `"yes"` is a
refusal whose reason is "yes".

### Schedules, asked for in the chat

With [Samay](https://github.com/kunwarmahen/samay) installed, `--samay`
lets each person's agent offer to do something later or on a repeat:
*"check whether example.com is up every hour, and tell me if it's down"*.
The agent previews it and reads the sentence back; on a yes, the question
arrives on the person's channel as a card in words (when, who hears, what
may run unasked), and approved, the schedule is theirs, running this
agent as them through this service.

```bash
export SAMAY_DVARA_URL=http://127.0.0.1:8765 SAMAY_DVARA_TOKEN=$DVARA_TOKEN
dvara --ask --samay /path/to/samay serve --port 8765        # or DVARA_SAMAY=PATH
#   dvara: schedules through samay 0.1.0 (/path/to/samay); its clock is running
```

* Off unless asked for: it lets every person you serve put work on a
  timer that you pay for.
* `examples/agents/minder` is a package that can: it checks a page now,
  offers to on a schedule, and keeps a record in a file if asked. Try it with the owner's actor and
  `--root examples/agents`.
* Each turn starts `samay mcp --for <that person> --agent <this agent>
  --runner dvara` and stops it when the turn ends. A scheduled turn gets
  none of it.
* The package must say `[permissions] mode = "ask"` (a `read_only`
  package refuses without asking), and a package with `[tools] allow`
  must list `mcp__samay__*`.
* `SAMAY_DVARA_URL` and `SAMAY_DVARA_TOKEN` must be set here as well as
  for `samay serve`: Samay checks every schedule made here against this
  service. The start warns when they aren't.
* The person sees their schedules by asking; the owner sees all of them
  with `samay list`
  ([notes/18](notes/18-a-schedule-asked-for-in-the-chat.md)).
* Each run is a conversation of its own, and nothing continues it. A week
  after it ends (`--keep-unattended DAYS`), its history is let go; its
  runs stay in `dvara runs`, and its files stay in the person's folder
  with that agent, shared by all their conversations with it, so a log a
  schedule keeps is one they can ask about from the chat
  ([notes/25](notes/25-the-persons-folder.md)). Only a thread a
  program started goes, never one a person did, and never one with a
  question still waiting
  ([notes/24](notes/24-a-conversation-nobody-will-continue.md)).

### Your phone, from the chat

With [Sparsh](https://github.com/kunwarmahen/sparsh) installed and a
phone plugged into this machine (or the emulator running), `--sparsh`
lets you say *"turn on Do Not Disturb"*, *"what's the code in my newest
text?"* or *"text Sam I'm running late"* from Telegram, and have it done
on the phone.

```bash
dvara --ask --sparsh /path/to/sparsh telegram --agent phone        # or DVARA_SPARSH=PATH
#   dvara: the phone through sparsh 0.1.0 (/path/to/sparsh); phone: emulator-5554
```

```toml
[actor.owner]
phone = true            # the phone on this machine is yours
```

* **One person's phone.** Only the person marked `phone = true` gets the
  phone tools. Two marked is an error.
* **Their yes, as buttons.** Reading the screen and ordinary taps run
  without asking. Sparsh holds a tap on Send, Pay, Buy, Delete and the
  like, typing a password, and Enter beside a Send button. Its `confirm`
  always asks, so the question arrives in the chat as Sparsh's own
  account of the step (*"Do this on the phone? … tap button "Send SMS"
  … 1 field "running late""*), with **Yes** and **No** under it.
* **In a scheduled run only when its schedule says so** (made in a chat
  that had the phone, or `samay add --phone`). The phone is checked
  first: in your hand, it waits up to ten minutes, then skips; locked,
  it asks you to unlock it; asleep (or a lock with no PIN), it wakes it. Steps you granted with
  the schedule (*"send in Messages when the screen shows 555-0123"*) go
  through by themselves; anything else is asked in your chat and lapses
  after the schedule's wait ([notes/33](notes/33-the-phone-on-a-schedule.md)).
* **A tap by position** (a screen only a picture shows) is asked every
  time, and the question brings the picture with the spot ringed: a
  photo above the buttons in Telegram ([notes/32](notes/32-the-ring-in-the-chat.md)).
* `examples/agents/phone` is the package for it (`[tools] allow =
  ["mcp__sparsh__*"]`, `mode = "ask"`). Another package needs both. One
  whose allow list leaves the phone out gets no phone and no word of one,
  and a schedule run on it is refused before you're asked to unlock
  anything ([notes/33](notes/33-the-phone-on-a-schedule.md)).
* Each turn starts `sparsh mcp` and stops it when the turn ends. A
  screen the list can't read comes with a screenshot when the model is
  local and can see, never to a cloud model unless
  `YANTRA_PHONE_SHOTS=on`.
* Off unless asked for; asked for and not found stops the start. No
  phone attached yet is fine: plug one in and the next turn has it
  ([notes/30](notes/30-do-this-on-my-phone.md)).

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

A notifier that leaves something behind — a message with buttons on it —
may return how to take it down. The desk calls that once the question is
over, on every channel it went to, with the `Answer` it ended on (or
`None` if the turn that asked went away first):

```python
async def send_to_telegram(ask):
    sent = await post_question(ask.to, ask.summary)
    async def withdraw(answer):
        await edit_message(ask.to, sent.id, "done" if answer else "no longer needed")
    return withdraw
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

**When nobody answers.** By default, silence refuses the call, and the
model is told it was silence. `--on-timeout hold` (`AskDesk(...,
on_timeout="hold")`) keeps it instead: the turn **stops**, nothing past
the question runs, and it waits — for a day, or `--hold-for` seconds —
for the person to come back ([notes/16](notes/16-kept-for-when-you-are-back.md)).

```
$ dvara held
VamBTs5Z_X3GzDPNY6UYeQ  owner/scribe  thread cli  run efa292db101a
    call_fq5canuu  write_file: NEW FILE a.txt (1 lines)
    call_b6dmlw42  write_file: NEW FILE b.txt (1 lines)
    held 30s ago. What you approve runs against things as they are now, not as they were then.

$ dvara resume VamBTs5Z_X3GzDPNY6UYeQ --actor owner \
      --call call_fq5canuu=yes --call "call_b6dmlw42=leave b.txt alone"
```

A held turn is **on disk, not in memory** — Yantra saves it inside the
conversation's checkpoint — so it survives a restart, where a question
never could. An answer is a new turn with its own budget, recorded as its
own run with `resumes` pointing back. Sending a new message instead means
"never mind": the waiting calls are set aside. Silence still never
approves.

`dvara telegram --ask` is the whole of this wired up: the question is
delivered to the person's own chat with two buttons on it, the press
lands on `AskDesk.answer`, and the message is edited to say what was
decided so it cannot be pressed twice. That edit happens however the
question ended — pressed here, answered at the terminal or over HTTP,
timed out, or abandoned by a turn that went away — and says which
([notes/12](notes/12-taken-down-everywhere-it-went.md)).

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
| `service.py` | `Service.deliver` — one message in, one reply out ([notes/01](notes/01-the-door.md)); `Service.resume` — a held turn answered ([notes/16](notes/16-kept-for-when-you-are-back.md)); a turn's Samay tools, for its person ([notes/18](notes/18-a-schedule-asked-for-in-the-chat.md)), its person's own accounts ([notes/19](notes/19-their-own-accounts.md)), and the phone, for its one person ([notes/30](notes/30-do-this-on-my-phone.md)); `Service.tidy` — finished scheduled runs let go ([notes/24](notes/24-a-conversation-nobody-will-continue.md)); one folder per person per agent ([notes/25](notes/25-the-persons-folder.md)) |
| `accounts.py` | `/connect`, `/accounts`, `/disconnect` and the address pasted back, answered before any turn and never seen by an agent ([notes/20](notes/20-signing-in-from-the-chat.md)); a shared folder only with `setu_manage`, and never its `/lock` ([notes/27](notes/27-your-folder-from-your-phone.md)); `/accounts page`, a one-time link to their own folder's Setu page ([notes/31](notes/31-their-own-page.md)) |
| `accounts.py` (window) | `/connect amazon`: Setu's streamed window, its link sent to the person ([notes/22](notes/22-a-window-sent-to-their-phone.md)) |
| `files.py` | `/files`, `/file NAME`: the person's own files from their folder with this agent, sent by the channel (Telegram: a document), never a turn; `send_file`, the same for the agent, a write to the gate, sent with the answer or (in a schedule) as a notice ([notes/26](notes/26-the-file-itself.md)) |
| `fresh.py` | `/new`: the person's conversation with this agent forgotten, never a turn, never under a running one; the ledger and their folder stay ([notes/28](notes/28-starting-over.md)) |
| `unlocked.py` | `/lock`, `/unlock`: the passphrase to Setu only, the key held in memory for the days asked, sealed again when they are up ([notes/21](notes/21-a-passphrase-only-they-know.md)) |
| `roster.py` | agents resolved by NAME from one owner-controlled root |
| `actors.py` | who is served, what they may reach, what they may spend, and where they can be reached ([notes/05](notes/05-one-person-two-channels.md)); reread when the file changes ([notes/09](notes/09-a-process-you-walk-away-from.md)); whose Setu sign-ins ([notes/19](notes/19-their-own-accounts.md)); whose phone, one person at most ([notes/30](notes/30-do-this-on-my-phone.md)) |
| `keys.py` | the `(actor, agent, thread)` session key and its escaping |
| `locks.py` | one lock per conversation or chat, dropped once nobody holds or waits on it ([notes/11](notes/11-only-while-somebody-is-waiting.md)) |
| `money.py` | package ∧ actor ∧ what is left of today, and the line under the answer ([notes/06](notes/06-a-number-you-can-act-on.md)) |
| `patience.py` | how long a person may be kept waiting on questions in a day, spent only where a question is actually put ([notes/14](notes/14-a-days-worth-of-being-asked.md)), and shown under the answer ([notes/15](notes/15-where-the-waiting-shows.md)); a scheduled run's own wait, after which a question lapses ([notes/33](notes/33-the-phone-on-a-schedule.md)) |
| `ready.py` | before a scheduled run on the phone: in use (wait, then skip), locked (ask them to unlock it), asleep (wake it) ([notes/33](notes/33-the-phone-on-a-schedule.md)) |
| `gate.py` | three rungs, and the tightest wins ([notes/02](notes/02-a-question-that-can-wait.md)); how a rung and a rule compose ([notes/03](notes/03-standing-answers.md)); answers given ahead of time, where a question would be put ([notes/17](notes/17-nobody-wrote-first.md)) |
| `rules.py` | standing allow/deny/ask answers, matched per call ([notes/03](notes/03-standing-answers.md)), and counted ([notes/10](notes/10-what-decided-this.md)) |
| `asks.py` | questions waiting for a person, the deadline on them ([notes/02](notes/02-a-question-that-can-wait.md)), which channels they go out on ([notes/05](notes/05-one-person-two-channels.md)), taking them down from all of them once they are over ([notes/12](notes/12-taken-down-everywhere-it-went.md)), and whether silence refuses or holds ([notes/16](notes/16-kept-for-when-you-are-back.md)); a picture the question needs, such as the spot a phone tap lands ([notes/32](notes/32-the-ring-in-the-chat.md)) |
| `holds.py` | turns that stopped for an answer nobody gave, kept on disk until somebody does, and who may give it ([notes/16](notes/16-kept-for-when-you-are-back.md)) |
| `runs.py` | every turn that happened, what it cost, which tools it called and what decided each one ([notes/08](notes/08-what-the-turn-actually-did.md), [notes/10](notes/10-what-decided-this.md)), which held turn it carried on ([notes/16](notes/16-kept-for-when-you-are-back.md)), which conversations a program started ([notes/24](notes/24-a-conversation-nobody-will-continue.md)), and how many turns had no price ([notes/29](notes/29-the-owners-page.md)) |
| `cases.py` | a bad turn -> a `[[case]]` in that package's gate ([notes/04](notes/04-the-failure-loop.md)), asserting the trajectory it took ([notes/08](notes/08-what-the-turn-actually-did.md)) |
| `http.py` | nine endpoints and a bearer token (`[http]` extra) |
| `notices.py` | telling a person something nobody asked about: their channels, routed or kept for collection ([notes/17](notes/17-nobody-wrote-first.md)); one may carry a file, a scheduled run's `send_file` ([notes/26](notes/26-the-file-itself.md)) |
| `telegram.py` | the long poll, the 4096-character cap and the button ([notes/07](notes/07-four-thousand-and-ninety-six.md)), which loses its buttons however the question ended ([notes/12](notes/12-taken-down-everywhere-it-went.md)), and the two under a turn that stopped to wait ([notes/16](notes/16-kept-for-when-you-are-back.md)); a person's file sent as a document ([notes/26](notes/26-the-file-itself.md)); the `/` menu, only the words this agent answers ([notes/28](notes/28-starting-over.md)); a question's picture sent as a photo above its buttons ([notes/32](notes/32-the-ring-in-the-chat.md)) |
| `outbox.py` | replies the Telegram bot owes, written down so a restart can finish sending them or say they were never answered ([notes/13](notes/13-a-reply-that-is-owed.md)) |
| `claim.py` | one dvara per state directory, and why ([notes/09](notes/09-a-process-you-walk-away-from.md)); who holds it, read without taking it ([notes/23](notes/23-is-the-door-open.md)) |
| `page.py`, `static/` | `dvara page`: the owner's page. People, today's spend, agents and every turn, read from the actors file and the ledger; words only for the owner's own turns, channels by kind; the owner's own questions and held turns answered through the running door; each person's files by name (the owner's opened) and schedules in Samay's words; its own token ([notes/29](notes/29-the-owners-page.md)) |
| `status.py` | `dvara status --json`: is it serving, where, and what it would serve, asked of the lock ([notes/23](notes/23-is-the-door-open.md)) |
| `cli.py` | `agents`, `status`, `page`, `say`, `runs`, `held`, `resume`, `rules`, `case`, `telegram`, `serve`; `--samay` and `--sparsh` checked at the start |
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

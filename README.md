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
  for each turn. Tools, skills, permission modes, evals and the MCP
  servers a package declares (`[[mcp]]`, started for each turn, after the
  person's own and kept to the package's `[tools] allow`) are Yantra's,
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
  plugged into this machine (or, with several phones named, each
  person's agents their own `phones`), and a step that can't be taken back (Send,
  Pay, Delete) comes to their chat as Yes and No buttons
  ([notes/30](notes/30-do-this-on-my-phone.md)).
* **[Smritikosh](https://github.com/kunwarmahen/smritikosh)** — with
  `--memory`, a package that asks for memory keeps each person's in
  Smritikosh, which finds them by meaning, with that person's own key
  ([notes/37](notes/37-their-own-memories.md)).
* **[Vaani](https://github.com/kunwarmahen/vaani)** — a Home Assistant
  Voice puck answered by a person's agents: Vaani hears the question
  (Whisper on that computer), tells who asked it (a voice print, or the
  puck's own person when unsure), and calls `POST /message` as that
  person with `came_by: "vaani"` and a thread per puck (`vaani:<puck>`).
  Who may do what stays here. The agent's questions reach the puck too:
  Vaani reads `GET /asks` while a turn runs, puts each to the person out
  loud and answers `POST /asks/ID`; a question no standing yes covers
  says `"always_ask": true`, and Vaani asks for the person's spoken PIN.
  `/new` from the puck starts that conversation over. `$DVARA_WHISPER`
  is the same Whisper, for voice notes ([notes/47](notes/47-a-voice-note.md)).
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
one person from their chat, with Send held for their button; and with
`--web`, a page can be a chat too, where everything sent to a person
waits for them; and what an agent remembers about a person is filed
under that person, in Yantra's own file or, with `--memory`, behind a
key of their own; and while nobody is writing, a quiet conversation is
looked back over and every sign-in checked daily, with notices reaching
phones through the house's own ntfy; and the owner's files changed from
a page, each checked before it's written; and a turn watched while it
runs on every channel, a job of several steps offered back as a skill
the person keeps for themselves, and `/tools`, `/schedules` and
`/watches` answered from the record (`/watches every 2 6h` changes how
often one looks); and with `--prahari`, its owner's agent offers to tell
them when something happens; and limits for a child (hours, messages a
day, an approver), facts everyone in the house knows, and a ready-made
morning brief, and `dvara keeps` for a backup of the house; and answers
read aloud on this machine, after the words, for whoever wants to hear
them, in their own voice or one for the answer's language — covered by
1074 tests. The API is not stable.

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

# and a page's chat, where every notice waits for each person
DVARA_TOKEN=... dvara serve --port 8765 --web
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

[actor.kid]
permissions       = "ask"          # changes are questions...
approver          = "owner"        # ...put to the owner, not to them
hours             = "07:00-21:00"  # when their agents answer, schedules too
max_turns_per_day = 40             # messages a day that reach an agent
speak             = "always"       # every answer read aloud too (default: when they spoke)
voice             = "hi_IN-pratham-medium"   # their own voice (default: the house's)

[actor.raj]
zone              = "Europe/London" # their clock: the time told, schedules, hours
trusted           = ["samay"]       # their own schedules aren't outside text
```

`permissions` can only ever tighten. The mode a turn runs under is the
minimum of the package's, the owner's and this one, so `"yolo"` beside a
guest's name grants them exactly nothing. The owner's is `--yolo` on the
command line: started with `--ask` alone, every change is asked about,
whatever this file or a package says. Sarathi's `[dvara] yolo` adds it
([notes/72](notes/72-asked-less-not-never.md)).

`trusted` names servers whose answers are that person's own words, by
the server's name (`samay`) or one tool's full name; after reading one,
a change asks nothing new. No wildcards, and never the web
([notes/72](notes/72-asked-less-not-never.md)). The name must be the server's exact name, the part between `mcp__` and
the next `__` in its tools' names (`mcp__homeassistant-home__call_service`
is `homeassistant-home`); a near miss like `homeassistant` matches nothing
and isn't an error. Like the rest of this file it's reread before each
message, with no restart. `--yolo`, on the command line, needs one.

An unknown key is an error, not a shrug:

```
error: ~/dvara/actors.toml: [actor.guest] has unknown key(s) max_usd_per_dayz;
known: agents, approver, channel, hours, max_turns_per_day, max_usd_per_day,
max_usd_per_turn, max_wait_per_day, permissions, phone, phones, receipt, setu,
setu_accounts, setu_manage, speak, trusted, voice, zone
```

**Limits for a child.** `hours` is when their agents answer, on their
clock (`zone`, below; else this machine's); it may run past midnight (`"22:00-06:00"`), and it
bounds a schedule of theirs too, because a schedule is the easiest way
round a bedtime. `max_turns_per_day` counts what they sent that reached
an agent: not a refusal, not a schedule's run, not a chat word like
`/memory`. `approver` is who is asked when their agents want to change
something (a spend too): the question goes to that person's channels,
says `For kid: …`, can't be answered by the child, and is refused rather
than held if nobody answers. Their `permissions` still decides whether
there is a question at all, so pair it with `"ask"`
([notes/61](notes/61-limits-for-a-child.md)).

**Someone who isn't where this machine is.** `zone` is their own time
zone, by its IANA name (`Europe/London`, `Asia/Kolkata`). Their agent is
told the time on their clock with each message (when its package has
`[env] context`), their schedules are made on it (their Samay server
gets `SAMAY_TZ`, so "every day at 7" is their 7), and their `hours`
open and close on it. Change it and their schedules follow: the ones
in the zone they left move to the new one, and they're told which
([notes/74](notes/74-their-schedules-move-with-them.md)). A name that
isn't a zone (`IST`, `+05:30`, a typo) stops the file loading. The day
for money and messages stays UTC's ([notes/66](notes/66-their-own-clock.md)).

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
both. With several phones named in Sparsh (`SPARSH_PHONES`),
`phones = ["nexus"]` gives a person theirs: their agents reach those and
no others, and a phone under two people is an error naming both
([notes/54](notes/54-each-phone-ones.md)).

Each turn reads Setu in that person's folder and starts their
connections there, so their agent can only open their accounts, and only
those the package asks for in `[connections] needs`, at the package's
level. `"*:read"` there asks for every account the person has, at read.
That's for a household's own agent, and a named connector keeps its own
higher level beside it. An account the package didn't ask for is named
to the agent as not given, so it says so rather than reaching the
account some other way, such as the phone.

A person with a folder of their own -- or one the owner let them manage
-- signs in from the chat:

```
/connect gmail                 they sign in on their phone; with a window address
                               set, Google's page is streamed to them (notes/52),
                               else they send back the address of the page that
                               won't load
/accounts                      what's connected for them
/accounts page                 a link to their own folder's page in Setu: once, on the
                               first device, for ten minutes (notes/31)
/connect server https://x/mcp  an MCP server of their own that needs no token; one
                               that signs in on its own page sends its link (in the
                               streamed window when there is one, else the address
                               it ends on is pasted back), as Google's; one
                               that needs a token gets their page's link instead,
                               so no token is typed into a chat (notes/48)
/connect mail                  mail by IMAP takes an app password, never typed into a
                               chat: they're sent to /accounts page, whose Mail
                               (IMAP) card takes it straight to Setu
/disconnect gmail:personal     revoke and forget
/lock, /unlock [days]          a passphrase only they know (notes/21); a folder of
                               their own only -- a shared one is locked at the computer
```

When an agent's answer tells them to send `/connect gmail` (or
`/unlock`), the word comes as a button under it, on Telegram and on the
page; pressing it is the word typed, by them
([notes/20](notes/20-signing-in-from-the-chat.md)).

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
([notes/26](notes/26-the-file-itself.md)). A picture of a signed-in site
("send me a screenshot of my chart") is one such file: the site's
`screenshot` saves it under `screenshots/` in their folder, and
`send_file` sends it (Yantra's notes/137). On Telegram a picture an
agent or a notice sends arrives as a photo you see in the chat, not a
file to open; `/file NAME` still sends the original as a document, and a
picture Telegram won't take as a photo goes as a document too
([notes/69](notes/69-a-picture-and-a-pdf.md)).

And the other way: a photo or a file sent to the bot (or with the
paperclip on the page) is kept in their folder with that agent under
`from-you/`, and the agent is told it's there. A picture is shown to the
model when it can see one (a cloud model, or a local one Ollama lists
with "vision"); otherwise the agent says it can't look
([notes/44](notes/44-what-they-send.md)). A voice note is heard into
words first by a local model that can hear, and the answer starts with
*I heard: "…"* on Telegram, and on a page the words go on their own line as soon as they're heard ([notes/47](notes/47-a-voice-note.md)). And the answer
comes back spoken too: read aloud on this machine by Piper and sent as a
voice note after the words, when they spoke (the default), always, or
never, as each person chooses with `/voice`; the page has ▶ Listen on
every answer ([notes/64](notes/64-an-answer-read-aloud.md)). Each person
may have a voice of their own, an answer in Hindi (or any language with
a voice here) is read in a voice for it, Hindi typed in Latin letters
("kal kya hai") too, and under "always" a schedule's answer is read
aloud too ([notes/65](notes/65-whose-voice-and-which-language.md),
[notes/73](notes/73-hindi-in-latin-letters.md)).

And anyone can start their conversation with an agent over:

```
/new                           start over; files, schedules, accounts and
                               the ledger all stay, and this conversation is kept
/chats                         every conversation, pinned ones first, then newest
                               (a question is there from the moment it's asked,
                               not when answered; each says every road it went on)
/chats boiler                  only the ones that say "boiler"
/chats 2                       go back into one (the one you're in is kept); one
                               open on Telegram stays open there too
/chats export 2                that one as a file to share (words, answers,
                               tool names -- never what a tool returned)
/chats export 2 pdf            the same as a PDF, made here (opens on any phone)
/chats delete 2                delete one for good (asks you to add "sure")
/chats test 2 May 20, refund   keep one as a test: replayed with the tools
                               answering from what they said then (nothing
                               real runs); the words are what the answer
                               must say
/keep test May 20, refund      the same, for the conversation you're in
/chats test 2 turn 1           an earlier answer in that conversation
/tests                         your kept tests, and how each did last time
/tests delete 1                take one back (the conversation stays)
/carry                         carry on a job a restart stopped, from its last step
/steps                         what your last turn did, step by step (/steps 2: turn 2)
/doctor                        what's wrong with what's yours, and the fix
/doctor every morning          checked at 07:30 your time, told only what's new (off: stop)
```

A chat is one conversation for as long as it lasts, and a long one can
teach a small model a habit (an old way of reading a site, kept after a
better tool arrived). Telegram's own "Clear history" never reaches the
bot; `/new` does ([notes/28](notes/28-starting-over.md)). Every
conversation is kept as it goes, whether `/new` ends it or not, in each
person's own file. `/chats` finds one by its words and goes back into
it, on whichever channel you ask from
([notes/45](notes/45-going-back.md),
[notes/50](notes/50-every-conversation-kept.md)). One open on Telegram
stays open there when the page opens it: both carry it on, each taking
what the other said before its next turn
([notes/71](notes/71-one-conversation-two-chats.md)). A page gets the same
through `GET /web/chats`, `GET /web/chats/ID`, `GET
/web/chats/ID/export` (Markdown; `?as=pdf` for the PDF) and `DELETE /web/chats/ID`,
and names or pins one with `POST /web/chats/ID/rename` and `/pin`; Sarathi's home page uses them.
The PDF is printed by the browser already on this machine (headless
Chrome, the one the browser tools use), so Hindi and emoji come out
right with nothing new installed; with no browser you get the Markdown
file and a sentence saying why ([notes/69](notes/69-a-picture-and-a-pdf.md)).

With an agent that remembers people (below), anyone can see and choose
what it keeps about them:

```
/memory                        what is kept about them, each with an id
/memory forget 2               that one, gone
/remember                      what the agent noticed, numbered, not kept yet
/remember 1 3                  keep those (or /remember all)
/remember not 2                not that one, never offered again (or /remember none)
/remember declined             what you turned down, newest first
/remember undo 1               that one may be offered again (back on the list, not kept)
```

Anyone can also tell every agent in the house something, with any agent:

```
/remember for everyone the bins go out Tuesday night
/household                     what everyone's agents know (and, for you, what's offered)
/household yes 1               keep what someone offered   (the owner)
/household no 1                not that                    (the owner)
/household forget 2            that one, gone              (the owner)
```

And whether answers are read aloud to them, and in whose voice, their
own choice over the owner's `speak` and `voice`
([notes/64](notes/64-an-answer-read-aloud.md),
[notes/65](notes/65-whose-voice-and-which-language.md)):

```
/voice                         what holds, the voices here, and whether this machine can speak
/voice always                  every answer and every notice, as a voice note after the words
/voice when-spoken             only when they sent a voice note (the default)
/voice off                     never
/voice use 2                   that voice for them (or by name; /voice use default goes back)
```

The voices are every Piper voice found in `$PIPER_VOICES`,
`~/.local/share/piper/voices` and `/usr/share/piper/voices`.
`$DVARA_VOICE` names the house's own (else the first English one), or is
`off`. An answer in a language their voice doesn't speak is read in one
that does; with none here for it, it isn't read, and your log names the
voice to add.

**A job a restart stopped.** Every step of every turn is saved as it
happens. When Dvara comes back after `sarathi down && up` or a crash,
each person who had a job running is told what it was and how far it
got, once, and `/carry` carries it on from the last step: nothing done
is done again, and the agent looks at the screen again before it acts.
Anything else they send leaves it. A schedule's run is Samay's to carry
on (`carry_on` on `POST /message`)
([notes/59](notes/59-a-job-a-restart-stopped.md)).

```
I stopped part way through "return the blue kettle" (6 steps done:
phone_open_app, phone_tap) when I was restarted (minder). Send /carry to
carry on from there -- I'll look again before I do anything. Anything
else leaves it.
```

**What a turn did.** `/steps` answers with the last turn one step at a
time (the tool, what it was given, what came back, how long, who said
yes), and `/steps 2` with the second. The owner's page has **Steps** on
every run. The owner sees anybody else's run as its shape only, without
what the tools were given and read. On a page's chat (Sarathi's home
page), every answer has **Steps** folded under it: that person's own
run, whole, and its file for a bug report
([notes/60](notes/60-a-run-step-by-step.md)).

**What's wrong with mine.** `/doctor` answers in red, amber and green
about what is the person's own, each line from the program that knows:
their accounts (a sign-in the site ended, a Google one in its last
days, a locked folder), their schedules' runs of the last day, their
watches, their phones, and today's allowance, messages and hours. Each
red or amber line says the fix in words they can use (`/connect gmail
as personal`, or whom to ask). Nobody else's line is ever in it; the
owner's ends with where the whole house is, Settings → Check or
`sarathi doctor` ([notes/67](notes/67-a-check-of-your-own.md)).
`/doctor every morning` has Samay send `/doctor` as them at 07:30 on
their clock; that run says only the lines not said before, and nothing
at all when nothing is new ([notes/75](notes/75-a-check-every-morning.md)).

`/new` answers at once and looks back over the conversation behind the
answer: what it noticed comes as a message of its own, numbered, and
nothing comes if it noticed nothing
([notes/51](notes/51-starting-over-at-once.md)); a turn that noticed
something says so in one line.
Nothing is kept until the person sends `/remember`
([notes/38](notes/38-what-they-said-in-passing.md)). The agent's package
must say `[memory] via`; Telegram's menu shows the two words after the
bot restarts.

These go to dvara, never to an agent, and the pasted address goes only to
the waiting sign-in ([notes/20](notes/20-signing-in-from-the-chat.md)).
With a window address (below), Google's and Home Assistant's sign-in
pages are streamed to their phone too, so the page's return to
`127.0.0.1` lands on your computer and nothing is pasted. Telegram's own
browser hides the address a paste needs
([notes/52](notes/52-googles-page-in-the-window.md)).
Their folder borrows your Google client file; while your Google app is in
Testing mode, add each person's address as a test user (publishing the
app ends that, and the weekly sign-out too; Setu's README). A folder you
pointed them at (priya's, above) stays yours to change, at the machine:
`SETU_HOME=<folder> setu connect gmail`. Sites signed in to through a
browser window (Amazon, X) are streamed to their phone when you give
the service a window address (`SETU_WINDOW_HOST`, `SETU_WINDOW_NAME` for
the name in its link, and `SETU_WINDOW_URL` behind a tunnel); without one
they're connected at the machine
([notes/22](notes/22-a-window-sent-to-their-phone.md)). A
person's tokens sit on your disk, where you could read them; say so to
anyone you give a folder ([notes/19](notes/19-their-own-accounts.md)).

A sign-in the site refused later (Google expires a Testing app's after
seven days) is marked by Setu, and the person's agent stops offering that
account and tells them to sign in again: `/connect gmail` once more, or
the owner, for a folder the owner looks after. The next message has it
back; nothing is restarted (Yantra's notes/127).

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
* **No standing yes covers a call that asks every time.** A spend, or a
  change after the turn read an email, a page or a server's answer
  (Yantra's notes/142), is put to the person even under an `allow` rule
  or `--yolo`, with what was read on the card's first line; with nobody
  to ask it is refused, and the model is told why. `send_file` is not
  such a change: it goes only to the person asking
  ([notes/58](notes/58-outside-text-asks.md)). A change asked only
  because of a read can be answered **approve all for this task**: the
  rest of that turn's such questions then run, until it reads something
  new; a spend is never covered ([notes/72](notes/72-asked-less-not-never.md)).

`--policy` is required if you name it and optional as `policy.toml`
beside the actors file (`~/dvara/policy.toml` by default), so a typo in
the path is an error rather than a file that silently does nothing. One
written later, by hand or from Sarathi's home page, is picked up without
a restart.

**Changed from a page.** `dvara settings` shows and changes the actors
file, the rules and each agent for a page (Sarathi's home page uses it):
a person, all the rules, or an agent's tables and prompt as JSON on
stdin, or a whole file as text. Each change is parsed the way Dvara
parses it before it's written, the rest of the file (comments included)
is kept, and the file before stays as `.bak`
([notes/41](notes/41-the-owners-files-from-a-page.md)).
`show` also lists every tool an agent could be given, in plain words and
marked *asks you first* or *runs unasked*, with each agent's boxes ticked
from its allow list and anything no box stands for (`amazon_*`) kept
apart, so the page draws checkboxes instead of a text box
([notes/43](notes/43-a-box-for-each-tool.md)).

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
  answer comes back as a 400. The answer's `**bold**`, `*italic*`, code,
  links, headings and items are still shown, not printed: the marks are
  taken out here and sent beside the words as entities, which Telegram
  has nothing to parse in ([notes/70](notes/70-bold-not-asterisks.md)).
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
dvara 2026.10.25.1 · state /home/you/dvara/state
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

**While nobody is writing.** `serve` and `telegram` do two things on
their own ([notes/39](notes/39-while-nobody-is-writing.md)). A
conversation nobody has written in for 30 minutes is looked back over
once, for a package that remembers, and the person is sent what it
noticed for `/remember` (`--quiet-for MINUTES`, `0`: only at `/new`).
And once a day every Setu folder Dvara reads is checked with `setu
check`. A sign-in the site refused is told once to whoever can fix it,
with the words that do: `Send /connect gmail as work to sign in again`
(`--check-sign-ins HOURS`, `0`: never).

**Notices on a phone.** `--ntfy URL` posts every notice to each person's
own topic on an ntfy server in your house, for the ntfy app on their
phone. `--ntfy-click URL` is where tapping one opens. A topic is
`dvara-<id>-<16 hex>`, which nobody can guess, and `GET /web/push` gives
it to that person's page. A skill offered comes with **Keep** and **Not
now** on the notification, pressed on the phone: each button carries a
mark made for that one offer and word, never a token, and goes to the
home page at `--ntfy-click`'s address, which hands it to `POST
/push/answer`. Sarathi starts the server with `[dvara] ntfy = true`
([notes/40](notes/40-a-notice-on-their-phone.md)).

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
first, filtered by person, agent or the way it came in (Telegram, Web,
Samay, CLI), with the tools it called and the refused ones in red
([notes/36](notes/36-which-way-it-came-in.md)).

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
                   (+ "stream": true -> NDJSON: text, using, step lines, then {kind: reply, ...})
                   (+ "carry_on": true -> the turn a restart stopped in this thread, from
                    its last step; stop_reason "nothing" when there is none)
                   (+ "if_late": "send"|"keep" -> a caller that hung up before the
                    turn ended: its answer sent to the person, or only kept)
GET  /runs/{id}/steps                            -> yantra.steps.v1: that run, step by step
GET  /agents                                     -> {agents: [...]}
GET  /health
GET  /asks?actor=                                -> {asks: [{id, tool, summary, ...}]}
POST /asks/{id}    {actor, approve, for_turn?}   -> {answered, approved}
GET  /holds?actor=                               -> {holds: [{id, calls, age, ...}]}
POST /holds/{id}   {actor, answers: {call: true|false|"reason"}}  -> like /message
POST /ask          {actor, tool, summary, arguments, timeout}  -> {approved, reason, code, via}
POST /phone/ready  {actor, wait, about}           -> {go, said}
POST /notify       {actor, text}                 -> {sent, kept, failed, nowhere}
POST /call         {actor, agent, tool, args, allow_tools}  -> yantra.call.v1
POST /mail-login   {actor, ref}                  -> their mail login, from their Setu folder
GET  /notices?channel=                           -> {notices: [{id, to, text, file, ...}]}
GET  /web?actor=&after=N                         -> {lines, agents, busy, live, asks, holds}
POST /web/message  {actor, agent, text}          -> {line}
POST /web/asks/{id}  {actor, approve, for_turn?} -> {answered, approved}
POST /web/holds/{id} {actor, answers}            -> {started}
GET  /web/file?actor=&line=&n=                   -> a file a line carried
GET  /web/spoken?actor=&line=                    -> that answer read aloud (WAV), made once
GET  /web/steps?actor=&line=                     -> yantra.steps.v1 of that answer's own run, + said
GET  /web/steps/export?actor=&line=              -> the same, as a file for a bug report (Markdown)
GET  /web/push?actor=                            -> {topic}  (their ntfy topic, or null)
POST /push/answer {actor, agent, offer, word, mark} -> {said}  (Keep / Not now on a phone; 403 unless the mark is that offer's)
POST /web/accounts-page  {actor}                 -> {url, said}  (as /accounts page)
GET  /web/declined?actor=                        -> {declined: [newest first], waiting}
POST /web/declined {actor, undo: [fact, ...]}    -> {back, declined, waiting}  (not kept)
GET  /web/chats/ID/export?actor=&as=pdf          -> that conversation as a PDF (503: no browser)
POST /web/chats/ID/rename {actor, title}         -> {renamed}  (empty title: its first words)
POST /web/chats/ID/pin    {actor, pinned}        -> {pinned}
GET  /web/notices?actor=                         -> {notices: [newest first], read}  (what was sent unasked, kept whatever /new cleared; how far they've read)
POST /web/notices/read    {actor, upto}          -> {read}  (read up to that line on every page; never moves back)
```

A program that runs turns for people who are not there — a scheduler —
adds `"unattended": true` to `/message`, and may add `"allow_tools":
[grants]`: the questions the person answered ahead of time. A grant is
a tool name or glob, or one tool fixed to exact argument values —
`call_service(domain=switch, entity_id=switch.lights_2)` covers that
switch and not the front door — and one that doesn't read as a grant is
a 400. They grant only what the person could have been asked about (a
deny rule still refuses), the call is recorded as `[ahead]` in `dvara
runs`, and the reply carries `needs_person`, `busy` and `refused`.
A caller may name itself with `"came_by"`, one short lowercase word
(Samay sends `"samay"`); the page labels the turn with it, and a turn
that names nothing is `http` ([notes/36](notes/36-which-way-it-came-in.md)).
An unattended caller may also say `"if_late": "send"`: if it has hung up
by the time the turn ends (a schedule's time limit ran out), the answer
goes to the person's channels instead of nowhere; Samay sends it for
every schedule that tells its person anything
([notes/76](notes/76-an-answer-written-to-nobody.md)).
`/notify` sends a text to a person's channels from the actors file; a
channel with no adapter in this process collects from `/notices`, each
one once, kept in memory ([notes/17](notes/17-nobody-wrote-first.md)).

`/ask` is for a run that isn't Dvara's: Samay's direct road starts
Yantra with nobody at it, and when that run meets a write nobody
allowed, it puts the question here. It goes through the same gate a turn
here gets (the owner's rules, the person's rung, their channels) and the
reply is the answer after at most `timeout` seconds: approved, or a
refusal with its reason and code (`user`, `timeout`, `policy`,
`unattended`). Silence lapses; it is never held
([notes/35](notes/35-a-question-for-a-run-that-is-not-ours.md)).
`/phone/ready` is the check before such a run works the phone (a
schedule made on Yantra's page): the person's phone in use is waited on
up to ten minutes, locked asks them in their chat to unlock it for
`wait` seconds, asleep is woken; `{go: false, said}` is the skip, in
words. Only for someone marked `phone = true` or given `phones`; `phone`
in the body names which of theirs (`"nexus"`), needed when they have
several.

`/call` runs one tool once, as a person, with no model: a watch's look
(Prahari). Their agent is built with their own accounts, and the tool
runs by Yantra's rule, a tool that reads or the one call `allow_tools`
grants word for word; no run is written and no allowance spent. 404 for
a person watches are off for ([notes/56](notes/56-a-look-as-them.md)).
`/mail-login` is the mailbox Prahari keeps open for someone: it runs
`setu login mail:<account> --json` in their own Setu folder, with the
key they unlocked it with, and answers with what Setu handed (Setu's
refusal, such as a locked folder, as `{"error"}`). Only a `mail:`
account, only for a person whose watches are on, only with a folder of
their own.

**The web channel: a chat on a page.** `dvara serve --web` gives every
person a list of lines kept on disk: what they said on a page, what
their agent answered, and every notice sent to them. So a schedule's
answer waits there until they open the page, even for someone with no
Telegram (`nowhere` is never true with `--web` on). `POST /web/message`
writes the line and starts the turn behind the request; the answer is a
later line, so a page reloaded mid-turn loses nothing. The page's turns
run as their own conversation (`web:chat`): a chat on Telegram doesn't
continue there. Questions and held turns are listed in the same look
and answered with `/web/asks` and `/web/holds`. Sarathi's home page is
one such page ([notes/34](notes/34-a-chat-on-a-page.md)): the owner's,
and each person's in the house once they sign in there, as their id in
`actors.toml` (Sarathi's own sign-in; nothing here decides who).

**Seeing the work.** While a turn runs, `GET /web` carries it as `live`:
the answer so far, and each step as a line (the tool and its one-line
summary, never what it read). Telegram shows a *Working…* message with
the last steps instead, edited every few seconds and deleted when the
answer arrives. `"stream": true` on `/message` gives the same events as
NDJSON. For a package with skills, a job of four steps or more is looked
at after the answer and may come back as a skill to keep (`/skills keep
ID`, or the Keep button on Telegram and a page), saved in that person's
own folder only. `/learn` asks for one now, after any job, even a short
one; the offer follows the same way. A job walked through one step per
message is a lesson: `/learn start <what it's for>`, then each step,
then `/learn done` keeps the whole walk as one skill (`/learn watch` the
same with the person's own hand on the phone, `/learn stop` or `/learn
clear` drops it; [notes/49](notes/49-a-job-taught-step-by-step.md)). A
page's look lists each open lesson, so Sarathi's home chat shows it with
Done and Stop, and the skill a phone lesson leaves opens its app by name,
for either phone (Yantra's notes/133). An agent sees only its package's skills (its
`skills/` folder) and the person's own, never the ones in
`~/.yantra/skills` on this computer. `/tools`, `/schedules` and
`/watches` answer from the record, with no turn, and `/watches every N
6h` changes how often watch N looks
([notes/42](notes/42-seeing-the-work.md)).

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
#   dvara: schedules through samay 2026.10.23.8 (/path/to/samay); its clock is running
```

* Off unless asked for: it lets every person you serve put work on a
  timer that you pay for.
* `examples/agents/morning` is a morning brief: new mail worth reading,
  today's calendar, positions, to-dos, the phone's battery and missed
  calls, and last night's tests, read only (`[connections] needs =
  ["*:read"]`). Ask it "send me my morning brief on weekdays at 7:30" and
  it makes that schedule, on your yes. Best on `qwen3.8` or a cloud
  model; `gemma4:12b` invents tools for what isn't connected
  ([notes/63](notes/63-a-morning-brief.md)).
* `examples/agents/minder` is a package that can: it checks a page now,
  offers to on a schedule, and keeps a record in a file if asked. Try it with the owner's actor and
  `--root examples/agents`.
* Each turn starts `samay mcp --for <that person> --agent <this agent>
  --runner dvara` and stops it when the turn ends. A scheduled turn gets
  only its tools that read (`list_schedules`, `schedule_runs`), so a
  morning brief can say how last night's tests went; nothing with nobody
  watching makes, pauses or deletes a schedule ([notes/63](notes/63-a-morning-brief.md)).
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

### Watches, asked for in the chat

With [Prahari](https://github.com/kunwarmahen/prahari) installed,
`--prahari` lets each person's agent offer a watch: *"tell me when a mail
from the bank arrives"*, *"tell me when ALAB drops under $50"*. Prahari
looks with no model and wakes the agent only when the thing happens;
the person says yes on a card in their chat that names the exact call
it will run.

```bash
export PRAHARI_DVARA_URL=http://127.0.0.1:8765 PRAHARI_DVARA_TOKEN=$DVARA_TOKEN
dvara --ask --prahari /path/to/prahari serve --port 8765
#   dvara: watches through prahari 2026.10.23.1 (/path/to/prahari) for everyone; it is watching
```

* EACH PERSON'S OWN: a watch's look comes back here as its person
  (`POST /call`): their agent, their own Setu folder, one tool, no model.
  So a guest's watch reads the guest's mail, never the owner's
  ([notes/56](notes/56-a-look-as-them.md)). `--prahari-for asha,mahen`
  (or `DVARA_PRAHARI_FOR`) narrows the watches to the people named.
* Each of their turns starts `prahari mcp --for <them> --agent <this
  agent> --runner dvara` and stops it when the turn ends; a scheduled
  turn gets none.
* A package with `[tools] allow` must list `mcp__prahari__*` (*Watches
  (Prahari)* in the tool picker).
* A watch that fires with work to do runs here as the person
  (`came_by: prahari` on the page, `dvara runs --came-by prahari`), and
  what it sees reaches their channels through `/notify`
  ([notes/55](notes/55-a-watch-for-one-person.md)).
* Each person has their own key to Prahari's inlet, so their phone's
  knocks reach only their watches: their agent's `inlet_address` tool
  gives it to them.
* A mailbox Prahari keeps open for someone (mail the moment it lands)
  is a mail account in THEIR Setu folder (their `/accounts page` link,
  the Mail card); Prahari gets its login through `POST /mail-login`.
* `/watches` lists their own watches, numbered, with no turn;
  `/watches every 2 6h` changes how often the second one looks (and
  Prahari still refuses anything under 5 minutes)
  ([notes/42](notes/42-seeing-the-work.md)).

### Your phone, from the chat

With [Sparsh](https://github.com/kunwarmahen/sparsh) installed and a
phone plugged into this machine (or the emulator running), `--sparsh`
lets you say *"turn on Do Not Disturb"*, *"what's the code in my newest
text?"* or *"text Sam I'm running late"* from Telegram, and have it done
on the phone.

```bash
dvara --ask --sparsh /path/to/sparsh telegram --agent phone        # or DVARA_SPARSH=PATH
#   dvara: the phone through sparsh 2026.10.23.3 (/path/to/sparsh); phone: emulator-5554
```

```toml
[actor.owner]
phone = true            # the phone on this machine is yours
```

Several phones, each someone's (Sparsh's `SPARSH_PHONES` names them):

```toml
[actor.owner]
phones = ["nexus", "iphone"]

[actor.asha]
phones = ["asha-phone"]
```

* **One person's phone.** Only the person marked `phone = true` gets the
  phone tools. Two marked is an error. With `phones`, each person's
  turns start Sparsh with only theirs (`sparsh mcp --phone NAME`), a
  phone listed under two people is an error, and `phone = true` beside
  anyone's `phones` is one too: it means every phone. `/phone` shows
  their first phone and names the others; `/phone asha-phone` shows that
  one. A schedule works the phone it names, or their only one; for a
  person with several, one that names none is refused, not guessed
  ([notes/54](notes/54-each-phone-ones.md)).
* **Their yes, as buttons.** Reading the screen and ordinary taps run
  without asking. Sparsh holds a tap on Send, Pay, Buy, Delete and the
  like, typing a password, and Enter beside a Send button. Its `confirm`
  always asks, so the question arrives in the chat as a photo of the
  phone's screen with what it would tap ringed, then Sparsh's own
  sentence (*"Do this on the phone? … tap button "Send SMS" … On the
  screen: field "running late""*), with **approve** and **refuse** under
  it. Not the screen's numbered list: that's the model's (Sparsh's
  notes/10).
* **In a scheduled run only when its schedule says so** (made in a chat
  that had the phone, for a job that works it, or `samay add --phone`). The phone is checked
  first: in your hand, it waits up to ten minutes, then skips; locked,
  it asks you to unlock it; asleep (or a lock with no PIN), it wakes it. Steps you granted with
  the schedule (*"send in Messages when the screen shows 555-0123"*) go
  through by themselves; anything else is asked in your chat and lapses
  after the schedule's wait ([notes/33](notes/33-the-phone-on-a-schedule.md)).
  **The battery and missed calls need none of that.** A package whose
  only phone tool is `mcp__sparsh__phone_status` (no screen, no taps, the
  morning brief) gets the phone on every run, a schedule's too, with no
  wait and no unlock ([notes/63](notes/63-a-morning-brief.md)).
* **A tap by position** (a screen only a picture shows, or one the list
  reads only in part, like Google Maps' places) is asked every time,
  and the question brings the picture with the spot ringed: a photo
  above the buttons in Telegram ([notes/32](notes/32-the-ring-in-the-chat.md)).
* `examples/agents/phone` is the package for it (`[tools] allow =
  ["mcp__sparsh__*"]`, `mode = "ask"`). Another package needs both. One
  whose allow list leaves the phone out gets no phone and no word of one,
  and a schedule run on it is refused before you're asked to unlock
  anything ([notes/33](notes/33-the-phone-on-a-schedule.md)).
* Each turn starts `sparsh mcp` and stops it when the turn ends. A
  screen the list can't read, or reads only in part (Google Maps'
  places, a map's pins), comes with a screenshot when the model is
  local and can see, never to a cloud model unless
  `YANTRA_PHONE_SHOTS=on`.
* Off unless asked for; asked for and not found stops the start. No
  phone attached yet is fine: plug one in and the next turn has it
  ([notes/30](notes/30-do-this-on-my-phone.md)).
* `/phone`, from the phone's person: the screen now, as a picture and
  Sparsh's numbered list, and the last steps done on it (theirs and the
  agent's). A peek, so an agent at work keeps its numbers; never a turn.
  Anyone else gets one sentence and no screen.

### What an agent remembers about each person

A package that asks for memory (`[memory] via = "local"` in its
agent.toml) remembers the people it talks to. Each one's memories are
filed under their own name, their id in the actors file, never under the
login running Dvara. A package that doesn't ask gets no memory.

With [Smritikosh](https://github.com/kunwarmahen/smritikosh), which finds
a memory by meaning, the owner names it once:

```bash
dvara --ask --memory smritikosh-mcp.json serve --port 8765        # or DVARA_MEMORY=FILE
```

The file names one MCP server, in the format of Yantra's `--mcp-config`;
its settings may say `${DVARA_MEMORY_USER}` and `${DVARA_MEMORY_KEY}`.
Each turn starts it with that person's name and key from
`<state>/memory.json` (readable by you alone), and stops it when the turn
ends:

```json
{"people": {"owner": {"user": "asha", "key": "sk-smriti-..."},
            "priya": {"user": "dvara-priya", "key": "sk-smriti-..."}}}
```

A person with no key there gets no memory, never somebody else's, and you
are told once. `sarathi smritikosh` writes both files: an account and key
for each person in the actors file, and you as yourself
([notes/37](notes/37-their-own-memories.md)).

**What they said in passing.** Nobody says "remember I live in Pune";
they say it on the way to something else. When a person sends `/new`
(or nobody has written for 30 minutes, [notes/39](notes/39-while-nobody-is-writing.md)), a
package that remembers looks back over the conversation once (Yantra's
look back, on the agent's own model and their allowance, recorded as a
`looked_back` run) and sends what it noticed as a message. At `/new` that
look runs after "Starting fresh" has gone, so starting over is instant
([notes/51](notes/51-starting-over-at-once.md)). What
Yantra notices mid-turn waits on the same list, with a one-line hint.
Nothing is kept until they send `/remember 1 3` (or `all`); what they
turn down with `/remember not 2` (or `none`) is never offered again; and
`/memory` shows them what is kept, with `/memory forget ID` to take one
back. The list waits in `<state>/offered.json`, yours alone
([notes/38](notes/38-what-they-said-in-passing.md)). A "not" sent with
the wrong number can be taken back: `/remember declined` lists what they
turned down, newest first, and `/remember undo 1` puts it back on the
list, not kept, for `/remember N` to keep. Sarathi's home page has the
same list under **Turned down**, with an Undo beside each
([notes/68](notes/68-what-you-turned-down.md)). A memory an answer
drew on says when, `(used 2026-10-23)`, and stays among the newest: Yantra
tells the store at the end of each turn, so a fact someone relies on
doesn't age out of what their conversations start with (Yantra's note 143).

**What everyone in the house knows.** Facts that are true for everybody
(the wifi, bin day) are the owner's to keep: `/remember for everyone …`
from the owner keeps one, from anyone else offers it to the owner, who
gets it with its number and answers `/household yes N`. Every turn of
every agent is shown them whole, as Yantra's `household` prompt layer,
including agents that keep no memories, because these are the owner's
notes, not something a person said. They live in
`<state>/household.json` (yours alone), at most 40 of under 300
characters each, not in a memory store: a few facts everyone must see are
shown, not searched for. The owner is whoever `--owner` (or
`$DVARA_OWNER`) names; Sarathi passes it, and its Settings has a
**Household** tab. At this computer: `dvara household [list|add|forget|yes|no]`
([notes/62](notes/62-what-everyone-knows.md)).

**An account you made yourself.** To give someone a Smritikosh account
you made in its dashboard: sign in as them, make a key under **Settings →
API keys** (shown once), and add `"<their id>": {"user": "<the account's
name>", "key": "sk-smriti-…"}` to `memory.json`. It is read again on every
turn, so there's no restart. Always their own key, never an admin's: a
key opens only its own account's memories, and that is the wall between
two people.

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

A store for people's memories goes in as `memory=Store.load(path)`
(`from dvara.memory import Store`), the same as `--memory`; each turn
reads that person's key from `<state>/memory.json`
([notes/37](notes/37-their-own-memories.md)).

## The source tree

| module | what it holds |
|---|---|
| `service.py` | `Service.deliver` — one message in, one reply out ([notes/01](notes/01-the-door.md)); `Service.resume` — a held turn answered ([notes/16](notes/16-kept-for-when-you-are-back.md)); a turn's Samay tools, for its person ([notes/18](notes/18-a-schedule-asked-for-in-the-chat.md)), Prahari's, for its person ([notes/55](notes/55-a-watch-for-one-person.md)), and a watch's look made as them (`Service.call`, [notes/56](notes/56-a-look-as-them.md)), its person's own accounts ([notes/19](notes/19-their-own-accounts.md)), and the phone, for its one person ([notes/30](notes/30-do-this-on-my-phone.md)), and its memory, the person's own ([notes/37](notes/37-their-own-memories.md)), and the package's own `[[mcp]]` servers, last ([notes/48](notes/48-a-server-of-their-own.md)), then past twenty tools only those the turn's words point at ([notes/53](notes/53-the-tools-a-turn-is-sent.md)), looked back over at `/new` ([notes/38](notes/38-what-they-said-in-passing.md)), behind its answer ([notes/51](notes/51-starting-over-at-once.md)), or after 30 quiet minutes, and every Setu folder checked daily (`Service.chores`, [notes/39](notes/39-while-nobody-is-writing.md)); `Service.tidy` — finished scheduled runs let go ([notes/24](notes/24-a-conversation-nobody-will-continue.md)); one folder per person per agent ([notes/25](notes/25-the-persons-folder.md)) |
| `accounts.py` | `/connect`, `/accounts`, `/disconnect` and the address pasted back, answered before any turn and never seen by an agent ([notes/20](notes/20-signing-in-from-the-chat.md)); a shared folder only with `setu_manage`, and never its `/lock` ([notes/27](notes/27-your-folder-from-your-phone.md)); `/accounts page`, a one-time link to their own folder's Setu page ([notes/31](notes/31-their-own-page.md)); `/connect server`, an MCP server of their own, its token only on that page ([notes/48](notes/48-a-server-of-their-own.md)); Google's page in the streamed window when one is set ([notes/52](notes/52-googles-page-in-the-window.md)), and a server's own sign-in page too ([notes/48](notes/48-a-server-of-their-own.md)) |
| `accounts.py` (window) | `/connect amazon`: Setu's streamed window, its link sent to the person ([notes/22](notes/22-a-window-sent-to-their-phone.md)) |
| `heard.py` | a voice note (Telegram voice, the page's 🎤) heard into words before the turn by a Whisper server when `$DVARA_WHISPER` gives one (the OpenAI transcription road), else a local model listing "audio" (`$DVARA_HEARING`), ffmpeg to WAV; the agent told it was a voice note, the person shown what was heard; none said plainly ([notes/47](notes/47-a-voice-note.md)) |
| `spoken.py` | an answer read aloud by Piper on this machine, sent after the words: a Telegram voice note (OGG Opus by ffmpeg), the page's ▶ Listen (WAV, made once per voice); code, links and tables left out, long answers cut at a sentence; `speak` per person (off, when-spoken, always: notices too) and their own `/voice`; every voice here, each person's own (`voice =`, `/voice use`), the answer's language told by script or small words and read in a voice for it, never in one that can't ([notes/64](notes/64-an-answer-read-aloud.md), [notes/65](notes/65-whose-voice-and-which-language.md)) |
| `romanised.py` | Hindi typed in Latin letters ("kal kya hai") written in Devanagari for the Hindi voice: the commonest words from a list, the rest by rule ([notes/73](notes/73-hindi-in-latin-letters.md)) |
| `attached.py` | a picture or file sent with a message (Telegram photo/document, the page's paperclip): kept in the person's folder under `from-you/`, named in the message, a picture shown to a model that can see ([notes/44](notes/44-what-they-send.md)) |
| `files.py` | `/files`, `/file NAME`: the person's own files from their folder with this agent, sent by the channel (Telegram: a document, the original), never a turn; `send_file`, the same for the agent, a write to the gate, sent with the answer or (in a schedule) as a notice ([notes/26](notes/26-the-file-itself.md)) |
| `promoting.py` | a person's learned skill made a tool, the owner's from the settings page: `show` lists each agent's people's learned skills with how each did; `settings tool AGENT --person --skill` writes it, tests it once (the press is the yes), keeps it in their folder if it passed; `--remove` takes it back, the skill a recipe again ([notes/46](notes/46-a-tool-from-their-skill.md)) |
| `marked.py` | an answer's Markdown as Telegram entities: the plain words, and beside them which are bold, italic, code or a link, counted in UTF-16; a mark only where it opens and closes against a word, so `snake_case` and `rm *.log` stay as typed; refused, the words go as written ([notes/70](notes/70-bold-not-asterisks.md)) |
| `printed.py` | a conversation as a PDF for `/chats export N pdf` and `?as=pdf`: an escaped HTML page with nothing to fetch, printed by the machine's own headless Chrome so every script prints; no browser, the Markdown file and why ([notes/69](notes/69-a-picture-and-a-pdf.md)) |
| `phoneview.py` | `/phone`: the phone's screen (picture + Sparsh's list, a peek) and its last steps, for its one person, never a turn ([notes/30](notes/30-do-this-on-my-phone.md)); `/phone NAME`, one of theirs ([notes/54](notes/54-each-phone-ones.md)) |
| `past.py` | `/chats`: every conversation kept as it goes, one log per person (Yantra's `history.ConversationLog`); `/chats WORDS` finds, `/chats N` goes back in, `/chats delete N sure` deletes for good; the page's `/web/chats` routes ([notes/45](notes/45-going-back.md), [notes/50](notes/50-every-conversation-kept.md)); one conversation open on several chats, each taking the row again when another wrote it, the turn holding the conversation's lock, rename and pin, each row's `here` for the page's own chat ([notes/71](notes/71-one-conversation-two-chats.md)); `/keep test` and `/chats test N [turn K]` keep one as a test in the person's own suite, which Yantra's `--tests` runs with everyone's; `/tests` lists them with each one's last result, `/tests delete N` takes one back ([notes/57](notes/57-a-test-of-your-own.md)) |
| `runsteps.py` | a run, step by step: its own turn in its conversation (tagged with its run id), whole for the door and the owner's own runs, as shape only for anybody else's on the owner's page; `/steps` in the chat; an answer's own on a page's chat, by its line (`web.py`) ([notes/60](notes/60-a-run-step-by-step.md)) |
| `checkup.py` | `/doctor`: a person's own check in red, amber and green -- their accounts (`setu status` in their folder), schedules' runs of the last day, watches, phones, and today's limits -- each with a fix they can use; only what is filed under them (the owner: `local` too) ([notes/67](notes/67-a-check-of-your-own.md)); `/doctor every morning`, a Samay schedule whose run says only what's new ([notes/75](notes/75-a-check-every-morning.md)) |
| `carrying.py` | `/carry`: a job a restart stopped part way, told to its person once as the door starts (`carry-told.json`) and carried on from its last step; a schedule's or a watch's run left to Samay and Prahari ([notes/59](notes/59-a-job-a-restart-stopped.md)) |
| `fresh.py` | `/new`: the person's conversation with this agent forgotten, never a turn, never under a running one; the ledger and their folder stay ([notes/28](notes/28-starting-over.md)) |
| `remembering.py` | `/memory`, `/memory forget ID`, `/remember`: what is kept about a person, theirs to see and take back, or turn down for good; the look back at `/new` and what a turn noticed, listed and kept only on their word ([notes/38](notes/38-what-they-said-in-passing.md)); `/remember declined` and `/remember undo N`, and the page's `/web/declined`, to see and take back what they turned down ([notes/68](notes/68-what-you-turned-down.md)) |
| `signins.py` | a sign-in that ran out, found by `setu check` once a day and told once to whoever can fix it ([notes/39](notes/39-while-nobody-is-writing.md)) |
| `push.py` | ntfy on the house's own server: each person's unguessable topic, every notice posted to it; **Keep** / **Not now** on a skill offered, a mark per button in place of any key (`POST /push/answer`) ([notes/40](notes/40-a-notice-on-their-phone.md)) |
| `settings.py`, `tomledit.py` | `dvara settings`: people, rules and agents changed from a page, each checked by the code that reads it, the rest of the file kept byte for byte, the old one as `.bak` ([notes/41](notes/41-the-owners-files-from-a-page.md)) |
| `unlocked.py` | `/lock`, `/unlock`: the passphrase to Setu only, the key held in memory for the days asked, sealed again when they are up ([notes/21](notes/21-a-passphrase-only-they-know.md)) |
| `roster.py` | agents resolved by NAME from one owner-controlled root |
| `actors.py` | who is served, what they may reach, what they may spend, and where they can be reached ([notes/05](notes/05-one-person-two-channels.md)); reread when the file changes ([notes/09](notes/09-a-process-you-walk-away-from.md)); whose Setu sign-ins ([notes/19](notes/19-their-own-accounts.md)); whose phone, one person at most ([notes/30](notes/30-do-this-on-my-phone.md)); whose phones, one owner each ([notes/54](notes/54-each-phone-ones.md)); which servers' answers are their own words, `trusted` ([notes/72](notes/72-asked-less-not-never.md)) |
| `keys.py` | the `(actor, agent, thread)` session key and its escaping |
| `locks.py` | one lock per conversation or chat, dropped once nobody holds or waits on it ([notes/11](notes/11-only-while-somebody-is-waiting.md)) |
| `money.py` | package ∧ actor ∧ what is left of today, and the line under the answer ([notes/06](notes/06-a-number-you-can-act-on.md)) |
| `patience.py` | how long a person may be kept waiting on questions in a day, spent only where a question is actually put ([notes/14](notes/14-a-days-worth-of-being-asked.md)), and shown under the answer ([notes/15](notes/15-where-the-waiting-shows.md)); a scheduled run's own wait, after which a question lapses ([notes/33](notes/33-the-phone-on-a-schedule.md)) |
| `ready.py` | before a scheduled run on the phone: in use (wait, then skip), locked (ask them to unlock it), asleep (wake it) ([notes/33](notes/33-the-phone-on-a-schedule.md)); of several, the one the schedule names ([notes/54](notes/54-each-phone-ones.md)) |
| `gate.py` | nothing asked from behind a turn that is over (`NOBODY_ASKED`, [notes/42](notes/42-seeing-the-work.md)); one yes for the rest of a task, over a turn's after-reading questions only ([notes/72](notes/72-asked-less-not-never.md)); three rungs, and the tightest wins ([notes/02](notes/02-a-question-that-can-wait.md)); how a rung and a rule compose ([notes/03](notes/03-standing-answers.md)); answers given ahead of time, where a question would be put ([notes/17](notes/17-nobody-wrote-first.md)), each a grant that may be fixed to one thing ([notes/35](notes/35-a-question-for-a-run-that-is-not-ours.md)); no standing yes and no yolo rung covers an `always_ask` call (a spend, or a change after outside text), which is asked or refused in words ([notes/58](notes/58-outside-text-asks.md)) |
| `rules.py` | standing allow/deny/ask answers, matched per call ([notes/03](notes/03-standing-answers.md)), and counted ([notes/10](notes/10-what-decided-this.md)) |
| `asks.py` | questions waiting for a person, the deadline on them ([notes/02](notes/02-a-question-that-can-wait.md)), which channels they go out on ([notes/05](notes/05-one-person-two-channels.md)), taking them down from all of them once they are over ([notes/12](notes/12-taken-down-everywhere-it-went.md)), and whether silence refuses or holds ([notes/16](notes/16-kept-for-when-you-are-back.md)); a picture the question needs, such as the spot a phone tap lands ([notes/32](notes/32-the-ring-in-the-chat.md)); a yes for the rest of a turn, kept per turn in memory ([notes/72](notes/72-asked-less-not-never.md)) |
| `holds.py` | turns that stopped for an answer nobody gave, kept on disk until somebody does, and who may give it ([notes/16](notes/16-kept-for-when-you-are-back.md)) |
| `runs.py` | every turn that happened, what it cost, which tools it called and what decided each one ([notes/08](notes/08-what-the-turn-actually-did.md), [notes/10](notes/10-what-decided-this.md)), which held turn it carried on ([notes/16](notes/16-kept-for-when-you-are-back.md)), which conversations a program started ([notes/24](notes/24-a-conversation-nobody-will-continue.md)), how many turns had no price ([notes/29](notes/29-the-owners-page.md)), and which way each came in ([notes/36](notes/36-which-way-it-came-in.md)) |
| `cases.py` | a bad turn -> a `[[case]]` in that package's gate ([notes/04](notes/04-the-failure-loop.md)), asserting the trajectory it took ([notes/08](notes/08-what-the-turn-actually-did.md)) |
| `http.py` | seventeen endpoints and a bearer token (`[http]` extra); `/ask` for a run that isn't Dvara's ([notes/35](notes/35-a-question-for-a-run-that-is-not-ours.md)); `/message` streamed as NDJSON when asked ([notes/42](notes/42-seeing-the-work.md)); `if_late` sends a hung-up caller's answer to its person ([notes/76](notes/76-an-answer-written-to-nobody.md)) |
| `watch.py` | a turn watched while it runs: its words, each step as a line, never what a tool read; a watcher that breaks is dropped, never the turn ([notes/42](notes/42-seeing-the-work.md)) |
| `learning.py` | Yantra's learner behind the answer, asking nobody; offers kept per person per agent; `/learn` (a look asked for now); `/learn start|watch|done|stop|clear`, a lesson kept on disk per person per agent, no look halfway ([notes/49](notes/49-a-job-taught-step-by-step.md)); `/skills`, `/skills keep|drop|forget`, a kept skill in the keeper's own folder; an agent sees only its package's skills and its person's own, never the computer's ([notes/42](notes/42-seeing-the-work.md)) |
| `toolbox.py` | every tool an agent could be given, for the settings page's checkboxes: Yantra's built-ins, `send_file`, and Samay's, Prahari's and Sparsh's families filled in from what turns met ([notes/43](notes/43-a-box-for-each-tool.md)) |
| `seen.py` | `/tools`, what the last turn was given; `/schedules`, the person's own from Samay; `/watches`, theirs from Prahari, and `/watches every N 6h` ([notes/42](notes/42-seeing-the-work.md)) |
| `web.py` | the web channel: each person's lines on disk (what they said on a page, the answers, every notice, and the notices by themselves for a page's bell, with how far each person has read them, kept here so every page and address agrees, [notes/71](notes/71-one-conversation-two-chats.md)); a voice note's words on the person's own line ([notes/47](notes/47-a-voice-note.md)); an answer's steps from the kept conversation once the chat moved on, and each step's picture by line, step and number, only as an image ([notes/60](notes/60-a-run-step-by-step.md)); turns that run behind the request, the page's own conversation ([notes/34](notes/34-a-chat-on-a-page.md)); a running turn as `live`, and a skill offered on its notice ([notes/42](notes/42-seeing-the-work.md)); each open lesson as `lessons`, for a page's lesson bar ([notes/49](notes/49-a-job-taught-step-by-step.md)); `/new`'s answer marked `fresh`, and a page shown only from the newest one ([notes/34](notes/34-a-chat-on-a-page.md)) |
| `notices.py` | telling a person something nobody asked about: their channels, routed or kept for collection ([notes/17](notes/17-nobody-wrote-first.md)); one may carry a file, a scheduled run's `send_file` ([notes/26](notes/26-the-file-itself.md)); read aloud too for someone who chose "always", in their voice ([notes/65](notes/65-whose-voice-and-which-language.md)) |
| `telegram.py` | the long poll, the 4096-character cap and the button ([notes/07](notes/07-four-thousand-and-ninety-six.md)), which loses its buttons however the question ended ([notes/12](notes/12-taken-down-everywhere-it-went.md)), and the two under a turn that stopped to wait ([notes/16](notes/16-kept-for-when-you-are-back.md)); a person's file sent as a document ([notes/26](notes/26-the-file-itself.md)), a picture as a photo, falling back to a document ([notes/69](notes/69-a-picture-and-a-pdf.md)); an answer's Markdown as bold and italic, not asterisks ([notes/70](notes/70-bold-not-asterisks.md)); the `/` menu, only the words this agent answers ([notes/28](notes/28-starting-over.md)), `/memory` and `/remember` where its package remembers ([notes/38](notes/38-what-they-said-in-passing.md)); a question's picture sent as a photo above its buttons ([notes/32](notes/32-the-ring-in-the-chat.md)); **approve all for this task** under a question asked only because of a read ([notes/72](notes/72-asked-less-not-never.md)); a *Working…* message with a turn's last steps, and Keep / Not now under a skill offered ([notes/42](notes/42-seeing-the-work.md)) |
| `outbox.py` | replies the Telegram bot owes, written down so a restart can finish sending them or say they were never answered ([notes/13](notes/13-a-reply-that-is-owed.md)) |
| `claim.py` | one dvara per state directory, and why ([notes/09](notes/09-a-process-you-walk-away-from.md)); who holds it, read without taking it ([notes/23](notes/23-is-the-door-open.md)) |
| `page.py`, `static/` | `dvara page`: the owner's page. People, today's spend, agents and every turn, read from the actors file and the ledger; words only for the owner's own turns, channels by kind; each turn labelled and filtered by the way it came in ([notes/36](notes/36-which-way-it-came-in.md)); the owner's own questions and held turns answered through the running door; each person's files by name (the owner's opened) and schedules in Samay's words; its own token ([notes/29](notes/29-the-owners-page.md)) |
| `status.py` | `dvara status --json`: is it serving, where, and what it would serve, asked of the lock ([notes/23](notes/23-is-the-door-open.md)) |
| `version.py` | `dvara --version` and status's `"version"`: the day of the last commit and that day's count (2026.10.25.3), with the commit; from git, else the VERSION file `sarathi image` writes |
| `keeps.py` | `dvara keeps --json` (`dvara.keeps.v1`): where the agents, the actors file, the rules and the state are, asked with the same folders as `status`, for Sarathi's `sarathi backup`; people's browser caches, the folder's lock and the page's answers read aloud (`voice-cache`) left out, nothing opened |
| `household.py` | what everyone in the house may know: the owner's facts, shown whole in every agent's turn; `/remember for everyone` keeps (the owner) or offers (anyone else), `/household` lists and answers ([notes/62](notes/62-what-everyone-knows.md)) |
| `moved.py` | a person's `zone` changed: their schedules in the zone they left moved by Samay (`samay zone`), and they're told ([notes/74](notes/74-their-schedules-move-with-them.md)) |
| `limits.py` | a person's limits that aren't money: the hours their agents answer (on their own `zone`'s clock, `now_for`), a day's messages, and the approver their questions go to ([notes/61](notes/61-limits-for-a-child.md), [notes/66](notes/66-their-own-clock.md)) |
| `memory.py` | whose memories a turn reads, and where: each person under their own name, and with `--memory` the owner's store, started per turn with that person's own key from `memory.json` ([notes/37](notes/37-their-own-memories.md)) |
| `cli.py` | `agents`, `status`, `page`, `say`, `runs`, `held`, `resume`, `rules`, `case`, `telegram`, `serve`, `settings`; `--samay`, `--prahari` (`--prahari-for` narrows it), `--sparsh` and `--memory` checked at the start |
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

# 18 — a schedule asked for in the chat

*[Note 17](17-nobody-wrote-first.md) gave Samay what it needed from the
door: a turn nobody typed, and a message nobody asked for. A schedule
could then run through here as a person. But only the owner could make
one, at a terminal, with `samay add`. This note is about the person
making their own, from the chat they already talk in.*

## The problem, as you would meet it

At a keyboard, Yantra finds Samay by itself and the agent can offer:
*"shall I check that every two hours?"* (Yantra's note 115). In a
Telegram chat with an agent behind this service, the same sentence goes
nowhere. Agents here are built fresh for each turn and get no MCP
servers at all, so there's nothing to offer with. The person has to ask
the owner, and the owner has to type a `samay add` on their behalf.

Three things make it more than "start Samay's server":

* **Whose schedules.** One service serves many people. A server that
  knew everybody's schedules would put them one model mistake away
  from each other.
* **Who says yes.** Making a schedule spends money on a timer. The
  person whose allowance pays must say yes, on their own channel, to
  something they can read.
* **Whose money.** It's the owner's machine and, in the end, the
  owner's bill. Whether people may set up work that runs while nobody
  is talking is the owner's decision, not a default.

## One server per turn, for that person

`dvara --samay` (or `DVARA_SAMAY=PATH`) turns it on. Each turn for a
person then starts Samay's MCP server beside the agent:

```
samay --state … mcp --for priya --agent helper --runner dvara
```

* `--for` is the turn's actor. The model has no argument with which to
  name anybody else, and someone else's schedule is "no schedule" to
  every tool.
* `--agent` is the agent of this conversation, so a schedule made while
  talking to `helper` runs `helper`.
* `--runner dvara` puts every run back through this door, as that
  person: their allowance pays, the owner's rules apply, and anything
  not allowed ahead of time is refused or asked about.

**IT STOPS WHEN THE TURN DOES.** It's the same reason a fresh agent is
built per turn ([note 01](01-the-door.md)): nothing that lives between
turns can carry one person's state into another's. It costs two short
process starts per turn, `samay status --json` and the server, which is
small next to a model turn. The status is read fresh each turn so the
agent knows whether Samay's clock is running *now*.

**A SCHEDULED TURN GETS NONE.** A turn Samay started (`unattended`, note
17) has nobody to say yes. It gets no Samay tools and no prompt layer
telling it to offer.

**A SAMAY THAT WON'T START COSTS THE TOOLS, NOT THE TURN.** If the
server fails, the turn goes on without it, and the owner is told once
on stderr. The person still gets an answer.

## The yes is the card, on their channel

`create_schedule` is a write, so it goes through the gate like any
other. The question carries Yantra's card in words, not the call's
JSON. From a live run, over HTTP, as the person's channel would show
it:

```
Save a schedule. At each time this agent runs it with NOBODY watching.
  when:      every hour -- next: Mon 5 Oct 17:11, 18:11, 19:11 (America/New_York)
  tells you: only when there is something new
  without asking, it may also use:
    web_fetch
  Anything else that changes something is refused while nobody is there.
  does:      Check whether example.com is up. Use web_fetch on https://example.com …
```

Approved, the schedule is the person's. Samay lists it as `owner:
priya`, `runner: dvara`, `agent: helper`, `allow_tools: ["web_fetch"]`.
Run now, it came back through this door, and the ledger shows the whole
chain:

```
20:11  priya/helper  end_turn  '(A scheduled run -- every hour. Nobody is watchi'
                     web_fetch[ahead]
20:11  priya/helper  end_turn  'Yes, please set that up.'
                     mcp__samay__create_schedule[asked:http]  [answered from http]
20:10  priya/helper  end_turn  'Check whether example.com is up once an hour, an'
                     mcp__samay__preview_schedule
```

**THE PACKAGE MUST ASK.** A write becomes a question only under a
package whose `[permissions] mode` is `ask`. Under `read_only` it is
refused without asking anybody, which is the correct answer for a
package that never meant to change anything, schedules included. A
package with a `[tools] allow` list must also name `mcp__samay__*`, or
the tools are not its to use.

## What the person is told differs from the keyboard

Two lines of the prompt layer are written by the host, not by Yantra:

* **Where they see their schedules.** At a keyboard it's the web page's
  panel or `samay list`. In a chat it's *by asking*: the agent lists,
  pauses and deletes them with Samay's tools.
* **Who starts a stopped clock.** The first live run told priya *"it
  won't start running until you start `samay serve`"*. Priya is on
  Telegram and can start nothing. On this service the line says the
  schedule starts once the owner starts the clock, and not to ask the
  person to run anything. The owner hears it at startup:

  ```
  dvara: schedules through samay 0.1.0 (…/samay); its clock is NOT running (samay serve)
  ```

## Samay checks each schedule against this door

A Dvara-road schedule is checked when it is made: this service is
reachable, the agent is on its roster, the person is real. Samay does
that with `SAMAY_DVARA_URL` and `SAMAY_DVARA_TOKEN`. Set them in this
service's environment too, and the server it starts inherits them; this
service never needs to know its own address. Without them, every
schedule made here is refused, and the start says so.

## An example to try it with

`examples/agents/minder` is the smallest package that can make a
schedule here. It fetches a page now (`web_fetch`), and offers to do it
later. Its allowlist names `mcp__samay__*` and its mode is `ask`, the two
things above that a package must get right. Its prompt says to preview
first, read the sentence back, and wait for a yes in the person's own
words before calling `create_schedule`.

The whole chain, from the chat to a run, on `qwen3.8:latest` through
Ollama. The person (priya, allowed `minder` and nothing else) talks over
HTTP, and the card is what her channel shows:

```
priya: Can you check whether example.com is up once an hour, and only tell me if it's down?
minder: Here's what it would do: check example.com every hour (next runs around
        00:05, 01:05, 02:05 in your timezone), and only message you if the site is
        down or unreachable. Does that sound right? If you say yes, I'll create it.

priya: Yes, that's right, please set it up.

Save a schedule. At each time this agent runs it with NOBODY watching.
  when:      every hour -- next: Tue 6 Oct 00:05, 01:05, 02:05 (America/New_York)
  tells you: only when there is something new
  without asking, it may also use:
    web_fetch
  Anything else that changes something is refused while nobody is there.
  does:      Check whether example.com is up: fetch https://example.com with web_fetch. …

minder: Done — schedule `c9792d27` is set: example.com checked every hour, and
        you'll only hear from me if it's down.
```

Then `samay run-now c9792d27`, which went back through this door as
priya, with `web_fetch` already allowed:

```
Mon 5 Oct 23:05  quiet  I fetched https://example.com. The request succeeded …
NOTHING NEW

$ dvara runs
03:05  priya/minder  end_turn  '(A scheduled run -- every hour. Nobody is watchi'
                     web_fetch[ahead]
03:05  priya/minder  end_turn  "Yes, that's right, please set it up."
                     mcp__samay__create_schedule[asked:http]  [answered from http]
03:05  priya/minder  end_turn  'Can you check whether example.com is up once an '
                     mcp__samay__preview_schedule
```

`samay show` lists it as priya's: `runner: dvara`, `agent: minder`,
`allowed: web_fetch`. The run was quiet because the site was up, so
priya heard nothing, which is what she asked for.

## What was deliberately not built

* **On by default, the way Yantra is at a keyboard.** At a keyboard the
  person is the owner. Here they aren't, and a feature that lets every
  served person put work on a timer is one the owner should switch on
  knowingly.
* **A per-person switch.** Who may make schedules is already decided by
  what decides everything else here: the person's agents, their
  allowance, their permission level, and Samay's cap of twenty
  schedules per person. A `read_only` person can never approve one.
* **A warm server per person.** It would save two process starts a turn,
  at the price of state that outlives turns, which is the trade note 01
  turned down for agents.

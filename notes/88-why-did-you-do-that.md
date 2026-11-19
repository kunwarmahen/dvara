# 88 · "Why did you do that?"

The guest room's heat came on at 4:38 in the afternoon and nobody had
typed anything. The answer to "why?" was in four places, none of them
the chat: Prahari's page had the watch that started it, the grants page
counted what had been allowed, `/steps` showed what a turn did (but only
the chat's own turns, never a watch's or a schedule's), and what the
agent believed about the person wasn't kept anywhere at all.

```
/why       the last thing this agent did for you: typed, scheduled or watched
/why 2     the one before it (as far back as 20)
```

## What it says

From the house's real ledger (a copy; nothing written to the live one):

```
Why: "The outside temperature in Cary, NC has gone below 70°F. Set the guestroom thermostat to heat: call mcp__homeassistant-home__call_service with domain='climate'…" (Wed 11 Nov 16:38)
Your watch "Guestroom heat when below 70°F" (Prahari) saw what it was waiting for and started it.

What it did:
1. call_service (homeassistant-home): ran unasked: this agent may act without asking

It finished (qwen3.8-64k:latest).
```

```
Why: "Write my morning brief." (Wed 18 Nov 07:30)
Your schedule 713aefd8 (Samay) started it; nobody typed it.

What it did:
1. list_available_tools ×3: ran unasked: this agent may act without asking
2. get_accounts (robinhood-personal): ran unasked: this agent may act without asking
…
```

Three things, in order:

**Who or what started it.** The ledger already knew: each program names
the thread it starts (`samay-<schedule>-…`, `prahari-<watch>-…`,
`vidhi-<routine>-…`), the puck's is `vaani:<room>`, and a typed turn
keeps the channel it came by. A watch's name is in the words Prahari
starts the turn with, so it's said by name.

**What let each step happen.** Every call in the ledger keeps what
settled it (`decided_by`): the person's yes on a channel, a standing
rule by its name, a grant given ahead with a schedule, one yes for the
whole task. With none of those, the rung let it through. On the ask
rung, that means the call only looked; on yolo it ran unasked, and the
reply says so plainly. That's the honest answer for the heat: this
agent may act without asking, and that was the setting that turned it
on. A refused call says why in words (*nobody answered in time*, *you
said no*). The same call let through the same way, several in a row, is
one line with a count.

**What it went by about you.** New in the ledger: at each answer Yantra
notes which of the memories, facts and guesses it was shown the answer
drew on (`Memory.leaned`, from the same word test that keeps a memory in
use fresh), and Dvara keeps them with the run (`leaned_on`). It's a
judgement made from the words of the answer, not the model's own account
of its reasons, so the reply heads it *What it seems to have gone by
about you*. It's noted every turn, whether or not the memory store keeps
use. Before, only stores that did were told, once a day per memory.
Runs from before this have none.

## Theirs only

`/why` finds runs by the person and the agent they're talking to,
nothing else, so it can never show another person's. It is answered
here, never by a model, and costs nothing. The receipt above found two
faults before this was committed: a watch's framing has brackets inside
brackets (*(every hour)*), and cutting at the first closing one showed
half of the framing as the question; and a hedge (*it changes nothing,
or this agent changes things unasked*) where the plain answer was known.

## What was deliberately not built

* **The model's reasons in its own words.** Asked afterwards, a model
  makes up a plausible story. What's here is what happened, from the
  ledger.
* **A schedule's name.** The thread carries its id; Samay's own page
  and `/schedules` have the name. One more call per `/why` to fetch it
  waits until the id alone proves confusing.
* **Whether a call only reads, on yolo.** The ledger keeps the call's
  name and what settled it, not whether it could change anything.

## Tests

`tests/test_why.py`: a typed turn says its channel; a schedule, a watch
(by name), a routine (with dashes in its name) and the puck are named;
a framing with brackets inside is skipped whole; each kind of yes and
the rung are told apart, and a refusal says why; on yolo a change
nobody was asked about isn't called a look; the same step in a row is
one line; what it went by and kept are said as judgements, with the
cost; `/why` shows their own newest run and nobody else's, `/why 2` the
one before, and asks no model; a turn keeps what its answer leaned on.
Yantra's `tests/test_memory_in_use.py`: every turn notes what it leaned
on, even after it was reported; a turn that leaned on nothing clears the
last; a store without `used` still notes it.

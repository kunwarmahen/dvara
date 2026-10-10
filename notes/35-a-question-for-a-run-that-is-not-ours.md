# 35 — a question for a run that is not ours

*[Note 17](17-nobody-wrote-first.md) let a scheduler run a turn here
that nobody typed, with `allow_tools` standing in for the questions its
person answered ahead of time. That covers Samay's Dvara road. This
note covers the other road, and makes an answer given ahead of time as
narrow as the person meant it.*

## The problem, as you would meet it

You tell your agent at your computer: "turn off my stairs light in 5
minutes". It makes a schedule and you say yes. Five minutes later the
run reports that the switch was refused, *"Nobody is available to
ask"*, and the light stays on. You were looking at Telegram, where this
service has asked you a hundred questions before.

The schedule was made at the computer, so it ran on Samay's direct
road: Samay started Yantra as a program, with nobody at it and no way
to reach this service's desk. Every question this service knows how to
put went unasked, because the turn wasn't ours.

## `POST /ask`

One question, one answer:

```
POST /ask  {actor, tool, summary, arguments, timeout}
        -> {approved, reason, code, via}
```

The run that is not ours sends what it would have shown on a card: the
tool, its own summary of the call (`NEW FILE stairs.txt (1 lines)`), the
arguments, and how long it can wait. The question goes on the same desk
every other question here uses: Telegram's two buttons, the web
channel's card. The reply is the answer.

**THE SAME GATE A TURN HERE IS GIVEN.** `service.ask` builds the gate
exactly as for one of our own turns, as a package that asks, because
the run on the other end already decided this call is one it would ask
about. So the owner's deny rules refuse without anybody being asked, an
allow rule answers it, and a person on `read_only` is never put on the
spot. A question from outside never gets a looser gate than one from
inside.

**SILENCE LAPSES; IT IS NEVER HELD.** A turn here can be held for a
person who is away (note 16), because this service can resume it. A run
on the other end can't be resumed from here. So `timeout` is treated as
a scheduled run's own wait: a question still unanswered when it runs
out is a refusal, code `timeout`, in the words a scheduled turn's lapse
uses. A run that no longer needs the answer hangs up, and the question
is withdrawn from the channels like any other.

**200 EITHER WAY.** "They said no" and "nobody answered" are answers.
Only a malformed question (400) or somebody not on the roster (404) is
an error.

Yantra's side of this is `unattended.Reach` (Yantra's notes/126), and
Samay's direct road sets it up when the clock knows this service
(Samay's notes/07). In Sarathi it already does: `SAMAY_DVARA_URL` and
`SAMAY_DVARA_ACTOR` were there for sending answers.

## A yes fixed to one thing

The same story's other half: had the agent listed Home Assistant's
`call_service` ahead of time, that yes would have covered every device
the tool can reach, the front door's lock among them. A grant in
`allow_tools` may now fix arguments:

```
mcp__homeassistant-home__call_service(domain=switch, service=turn_off, entity_id=switch.lights_2)
```

`gate.put` matches with Yantra's own `Grant`, so a grant means the same
thing on both roads. A call with other values isn't covered. It goes on
to be asked, as if nothing had been granted. Values match exactly,
because note 03 already argued why a glob in an *allow* is a trap. And
`/message` refuses, with a 400, a grant that doesn't read as one: an
unclosed bracket must not be read as the whole tool.

## The receipt

A scratch Dvara on 8798 (owner only, no Telegram), a scratch Samay on
the direct road, `qwen3.8:latest`. A schedule with nothing allowed
whose job was to write `OFF` into `stairs.txt`:

```
GET /asks -> {"asks":[{"actor":"owner","agent":"samay","tool":"write_file",
              "summary":"NEW FILE stairs.txt (1 lines)", …}]}
POST /asks/{id} {"actor":"owner","approve":true,"via":"telegram"}
samay:  ok    The stairs light is off. (I wrote "OFF" into stairs.txt …)
```

Answered no, the same job came back `refused` in Samay, and its notice
arrived on the web channel ending *Not allowed without asking:
write_file*. With `write_file(path=stairs2.txt)` allowed ahead of time,
the next run wrote the file and `/asks` stayed empty.

## Not here yet

- **The ledger.** A question from `/ask` waits on the person's day of
  waiting (patience) but isn't written to a run, because the run isn't
  ours. `dvara runs` doesn't show it; Samay's record does.
- **`ask_user` from outside.** Only a yes or a no crosses. A run that
  wants a typed answer still ends its turn.

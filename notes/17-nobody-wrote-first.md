# 17 — nobody wrote first

*[Note 01](01-the-door.md) refused scheduling outright: "a service of its
own wearing this one's clothes". That service now exists. It's Samay, a
separate program that keeps a person's schedules and wakes up when one
is due. This note is about the two things it needed from the door, and
why they're general rather than Samay's.*

## The problem, as you would meet it

You ask for a check of your mail every two hours, with a message on
Telegram when something needs you. Two things this service has never
done are needed:

1. **A turn nobody typed.** At 08:00 a program asks for a turn on your
   behalf. You're asleep. Writing to a file may still be fine, because
   you said yes to that when you accepted the schedule. But a browser
   that hits a sign-in page must not open a window on a server nobody
   is looking at, and the program needs to learn what went wrong
   without reading prose.
2. **A message nobody asked for.** Every message this service has ever
   sent was an answer, going back to where a message came from. The
   08:00 finding has nowhere to go back to.

## A turn nobody typed: `unattended`

```
POST /message  {"actor": "mahen", "agent": "scribe", "thread": "samay-…",
                "text": "…", "unattended": true, "allow_tools": ["write_file"]}
```

`unattended: true` tells Yantra, for this one turn, that nobody is in
front of it. That's Yantra's note 114, used per turn: Yantra's
`unattended.scope()` gives the turn a record of its own, so two
scheduled turns running at once in this process never report each
other's sign-in walls. The reply carries the three lists Yantra keeps
for a turn like that:

* `needs_person`: something only the person can fix, like a sign-in;
* `busy`: something another process was using, like a browser profile;
* `refused`: tools that were refused. This list comes from the run's
  own steps, so it's there for every turn, unattended or not.

**A QUESTION THAT CAN REACH THEM STILL DOES.** Unattended doesn't mean
unaskable. That's the difference between this road and Yantra's direct
one, and the reason to have it. A tool nobody allowed is put to the
person on Telegram as usual. Under `--on-timeout hold`, an unanswered
question keeps the turn for when they're back (note 16).

## Answers given ahead of time: `allow_tools`

The person accepted "write a line to log.txt every six hours". That's a
yes to `write_file`, given before the call exists. The question was
where such a yes belongs, and the answer was already written down in
note 03: **`allow` grants nothing the rung would not have been willing
to ASK about.**

So `allow_tools` lives where a question is put: the start of `put`,
the one function every question goes through. A call reaches `put`
only if the person could have been asked about it. That settles every
case without a single new rule:

* a **deny** rule still refuses, because it's decided before any
  question;
* a **read-only** person is never answered for, because they're never
  asked;
* a service started **without `--ask`** grants nothing, because with no
  desk, nothing is askable;
* a tool marked **`always_ask`** still asks, because a yes given before
  the call existed is exactly what such a tool refuses to count.

`allow_tools` without `unattended` is a 400. A person who *is* there
answers the question when it comes.

**WRITTEN DOWN AS WHAT IT WAS.** A call released this way is recorded
as `ahead`, beside `rule:<id>` and `asked:<channel>` (note 10), so
`dvara runs` answers "why did this run without asking me?":

```
2026-10-05 01:17  owner/scribe  end_turn  $0.0000  '(A scheduled run -- every 6 hours. Nobody is wat'
                  read_file -> write_file[ahead]
```

## A message nobody asked for: `POST /notify`

```
POST /notify   {"actor": "mahen", "text": "2 new mails from the bank"}
            -> {"actor": "mahen", "sent": ["telegram"], "kept": [], "failed": {}, "nowhere": false}
GET  /notices?channel=signal
            -> {"notices": [{"id", "actor", "channel", "to", "text", "at"}]}
```

The notice goes to **the person's channels from the actors file**, at
the address listed there. That's the same place a question for them
goes (note 05). There's no thread to reply into, because nothing
started one.

* **Routed if it can be.** A Telegram bot running in this process
  registers a sender when it starts, the same way it does for
  questions. The notice goes out at once, split the way an answer is,
  with no parse mode (note 07).
* **Kept if it can't.** A channel with no sender here (an adapter in
  another process) collects from `GET /notices`, each notice handed
  over once. A send that fails is kept the same way rather than lost.
* **Nowhere is an answer, not an error.** A person with no channel
  gets `nowhere: true`. Somebody nobody knows gets a 404, as they do
  everywhere else.

**IT KNOWS NOTHING ABOUT SCHEDULES.** Whether something is worth
sending is decided by the program that calls it. This module only
sends, so anything else that needs to tell a person something can use
it unchanged.

**KEPT IN MEMORY, AND SAID SO.** The outbox (note 13) is durable
because it's owed to somebody who wrote. A notice is owed to nobody
yet. A restart drops what wasn't collected, and each channel keeps only
its newest hundred. A caller that has to know keeps its own record, and
Samay's run log is that record.

## Receipt

`dvara serve` on the example `scribe` agent, with `--ask --ask-timeout
20 --on-timeout hold` and `qwen3.8:latest` through Ollama. The person's
only channel was one this process doesn't serve, so notices waited to
be collected. Through Samay:

```
$ samay run-now 4dd8ac19          # write_file allowed ahead of time
Sun 4 Oct 21:17  ok            sent  I wrote 'checked' plus the current time (≈ 2026-10-05 01:17 UTC) into…
$ curl -H "Authorization: Bearer $DVARA_TOKEN" "localhost:8799/notices?channel=signal"
{"notices":[{"id":"aeab6950","actor":"owner","channel":"signal","to":"me","text":"I wrote 'checked' …"}]}

$ samay run-now 678740c0          # write_file NOT allowed; nobody answered
Sun 4 Oct 21:18  held          Nobody answered in time, so this is waiting for your approval and not…
$ dvara held
lVxSFx5_…  owner/scribe  thread samay-678740c0-1791163084  run 58b8c388a0a9
    call_dfah3uxz  write_file: NEW FILE log2.txt (1 lines)
```

## What was deliberately not built

* **Scheduling.** Note 01's refusal stands. The clock, the records,
  and deciding what's worth sending all live in Samay. This service
  gained two general verbs, not a timer.
* **Cancelling a turn from outside.** A caller that stops waiting
  (Samay's time limit) doesn't stop the turn here. A cancel endpoint
  would let one program stop another person's turn, and that needs
  its own argument.
* **Durable notices**, as above.

Each scheduled run's conversation is let go a while after it ends, and
its runs stay in the ledger: [note 24](24-a-conversation-nobody-will-continue.md).

# 76 — An answer written to nobody

## The problem, as you would meet it

A weekday morning brief, started by Samay at 07:30, came back
*too long* two mornings running. Dvara's run log said both turns
finished: one after twenty minutes, one after fifty. Samay had a
ten-minute limit, stopped listening, and recorded `timed_out`. When
the turn ended here, its answer went back down a connection nobody
held. The brief was written and nobody read it. (Samay's notes/13 has
the rest: why the turns ran long, and the limit.)

## Said ahead, done only if it happens

A caller on `POST /message` may say what a late answer is for:

```json
{"actor": "owner", "agent": "morning", "thread": "samay-713aefd8-…",
 "text": "Write my morning brief.", "unattended": true, "came_by": "samay",
 "if_late": "send"}
```

**ONLY A CALLER THAT REALLY HUNG UP CHANGES ANYTHING.** When the turn
ends, Dvara asks the connection whether the caller is still there. If
it is, the answer goes back as always and nobody is told twice. If it
isn't, and the caller said `send`, the answer goes to the person's
channels, the same way `/notify` sends:

```
Finished after Samay had stopped waiting (morning):

**Mail** — …
```

`keep` (or saying nothing) leaves it in the run's record and tells
nobody. Samay sends `keep` for a schedule set to tell nobody
(`--notify never`), and `send` for the rest. `if_late` goes with
`unattended: true`: a person who is there gets their answer the
ordinary way.

Checked against the real thing: uvicorn, with a client using Python's
`urllib` and a one-second timeout, as Samay does. The turn sees the
caller gone. With a client that waits, it doesn't.

## What was deliberately not built

* **Sending every late answer.** A caller that stopped listening on
  purpose (a page closed, a script killed) didn't ask for its answer
  on the person's phone. Only a caller that said `send` gets it.
* **Samay collecting it later.** Asking Dvara for the run by its
  thread after a timeout would put the answer in Samay's logbook too.
  It is a second call path and a second record of one run; the
  person having the answer was the part that mattered.
* **A streamed turn.** `stream: true` callers read the answer as it
  comes, and have their own way of knowing they left.

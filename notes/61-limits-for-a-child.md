# 61 — Limits for a child: hours, messages, and who says yes

A child in the house gets their own Telegram chat with the agents. Money
had a ceiling already (note 06), and so did being kept waiting (note 14).
None of the limits a parent actually reaches for was there, though:

* they could talk to the agents at 2 am;
* they could send four hundred messages a day on a local model, where
  the dollar allowance never moves;
* a question before a change (writing a file, a spend, a step after the
  turn read an email) went to **them**, so their yes was the only yes.

Three keys in the actors file, read by `limits.py`:

```toml
[actor.kid]
permissions       = "ask"           # changes are questions...
approver          = "owner"         # ...put to the owner, not to them
hours             = "07:00-21:00"   # when their agents answer
max_turns_per_day = 40              # messages a day, not dollars
```

## The hours bound every turn, a schedule's too

A schedule is the easiest way round a bedtime there is: "every night at
2" made at 8 pm. So `_turn` checks the hours at the start of every turn
that is theirs, typed or scheduled, on this machine's own clock (the
local time zone; Sarathi sets it for the containers). A window may run
past midnight (`"22:00-06:00"`). The answer outside it is a refusal,
recorded like any other, that says when to come back:

```
I'm not answering now -- your hours here are 07:00-21:00. Ask again after 07:00.
```

An answer to a question that was held (note 16) is not checked. A hold
made at 20:59 can still be answered at 21:05, because nothing new is
being asked for.

## The count is of what they sent

`RunStore.asked_since` counts the day's turns that reached an agent:
not a refusal, not a look back at `/new`, not a schedule's run. Each
exclusion prevents a different failure:

* **Refusals.** A child at the limit who tries again would otherwise
  push the count further past it and never get back under.
* **Look backs.** The person didn't send those.
* **Schedules.** A minder that checks a page every hour would use up the
  child's day by lunchtime and then refuse the child.

Chat words (`/memory`, `/household`, `/files`) are not turns and leave
no run, so they don't count either. The day is money's day (UTC), so
the two allowances reset together.

## The question goes to the approver

The rung (`permissions`) still decides whether a call becomes a question
at all. `approver` decides whom it is put to. `limits.ForApproval` is
the ask desk with three things changed: the question goes to the
approver, on the approver's channels, and its summary says whose agent
is asking (`For kid: NEW FILE homework.txt`). The child's own list of
questions is empty, and an answer from them is refused: *that question
was put to somebody else*.

**Silence refuses; it never holds.** A held turn can only be taken up by
the person it belongs to (note 16), and the person who could answer it
here is somebody else. So under an approver the desk's `on_timeout` is
always `deny`.

A spend, and a change after the turn read outside text, ask on every
call (Yantra's `always_ask`, note 58). So those always reach the
approver too, which is the point of naming one.

**An approver is somebody here.** A name that isn't in the actors file
is an error at load. Otherwise every question would have nobody to go
to, a refusal of every change dressed up as a setting. Naming the person
themselves is an error too: leave the key out and they're asked, as by
default.

## Which agents and sites

These were there already, and the Sarathi form now shows them beside
the new keys: `agents` is a complete list of what they may use, and
`setu_accounts` narrows a shared Setu folder to the accounts named
(`gmail:family`). Sites the browser may open are a package's own
(`[connections]`), so a child gets an agent made for them rather than a
per-person site list.

## Receipt

`gemma4:12b` on Ollama, a scratch Dvara on port 8798 (`--ask --owner
owner`), the example `greeter` and `scribe`, and three people: `owner`,
`kid` (`approver = "owner"`, `max_turns_per_day = 3`) and `night`
(`hours = "03:00-04:00"`, run at 16:34).

The kid asked scribe to write a file. The question went to the owner:

```
owner's asks: {"asks":[{"actor":"owner","agent":"scribe","thread":"k2",
  "tool":"write_file","summary":"For kid: NEW FILE homework.txt (1 lines)"}]}
kid's asks: {"asks":[]}
kid answers: {"detail":"that question was put to somebody else"}
owner answers: {"answered":true,"approved":true}
end_turn | I've created the file `homework.txt` with the content: "maths page 12".
```

The kid's fourth model turn of the day (three chat words in between
counted for nothing):

```
refused | That's all 3 messages for today. They come back at midnight UTC; ask
whoever looks after this for more if it can't wait.
```

And `night`, at the wrong hour:

```
refused | I'm not answering now -- your hours here are 03:00-04:00. Ask again after 03:00.
```

## What was deliberately not built

* **A per-person time zone.** One house, one clock: the machine's. A
  child abroad on holiday is a reason to change the hours, not to
  model the planet.
* **Per-person site lists.** A site's tools come from the package's
  `[connections]`. Narrowing those per person would mean two places
  deciding one thing, and the agent list already does the job.
* **More messages on the approver's yes.** "Ask whoever looks after this"
  is the sentence. A button that raised the day's limit from the chat
  would be a limit the child could talk their way past.

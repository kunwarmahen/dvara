# 90 · The same ask, again: offered as a schedule

People ask their agent the same thing at the same time of day, and type
it every time, because nothing noticed. A schedule could always have
done it (`/schedules`, or asking the agent to set one up), but only for
someone who thought of it.

The house's own history, read from a copy of the ledger: 451 runs, 269
of them typed and answered, and two habits in them:

```
minder | "What is the temperature outside" — asked on 6 days, around 18:45
minder | "any new mails in my yahoo account" — asked on 4 days, around 21:45 on weekdays
```

## What happens now

The third time an ask comes on a different day, one line goes under the
answer:

```
It's 41°F outside.

You've asked this on 3 days, around 18:45. /repeats yes 1 makes it a schedule;
/repeats no 1 and I won't offer it again.
```

```
/repeats             what I noticed you ask again and again
/repeats yes 1       a Samay schedule, at the time you usually ask, in your words
/repeats no 1        not that one, never offered again
```

**Three different days, not three times.** Asking twice in a minute is a
retry. A request counts when it was typed and answered, never a
schedule's or a watch's run, never a chat word like `/memory`, and the
habit is the same ask on three days within thirty, with the same agent.

**The same ask in other words.** *"what's the guest room temp"* and
*"Guest room temperature?"* are one ask. Small words are dropped, endings
trimmed, each word cut to its first four letters, and two asks match
when most of their words do. NO MODEL JUDGES IT: a model asked whether
two sentences mean the same says yes too easily, and the cost of a
missed habit is only an offer not made. A one- or two-word message
("thanks") is never a habit.

**At the time you ask.** The schedule's time is the middle of the first
ask on each day, rounded to five minutes, on your clock, so one late
night doesn't pull a morning habit to midnight. If every ask was on a
weekday, the schedule is weekdays only. The words are your latest. The
schedule is Samay's, sent to you through Dvara as you, with the same
agent, so its answer comes the way your typed one did, every time
(`notify = always`).

## An offer is a line, not a question

Nothing is held open for the answer: the offer waits in
`<state>/repeats.json`, theirs alone, until `/repeats yes` or `no`, the
house's rule for anything offered after a turn. It is offered once.
Turned down, the same ask (in any of its wordings) is never offered
again. If Samay can't make the schedule, the offer goes back on the
list, so a yes that didn't land isn't lost. With schedules switched off,
nothing is offered.

## Why a schedule and not a routine

The idea started as "a draft Vidhi routine". But an ask that comes back
at the same time is one prompt on a clock, which is exactly what a Samay
schedule is. A routine is for steps with choices between them, and
drawing one for a single question would be a picture of a schedule.

## What was deliberately not built

* **Habits across agents.** The same words to two agents may mean two
  things (the minder's "temperature" is the house's, another agent's
  might be the oven's).
* **Learning the weekdays exactly.** Weekdays or every day; a habit on
  Mondays and Thursdays is offered every day, and the person can change
  the schedule's words (`/schedules when 1 …`).
* **Offering at the computer.** Yantra's own terminal has its history;
  this lives where many people's turns already meet.

## Tests

`tests/test_repeats.py`: other words for the same ask match, different
asks don't; three days is a habit at the time they ask; three times in
one day is a retry; a schedule's run and a failed turn aren't asks;
older than thirty days or another agent's don't count; one late ask
doesn't drag the time; weekdays only becomes a weekday schedule; a word
or two is no habit; offered once and never after no, per person; the
third day gets one line under the answer and only once; without
schedules nothing is offered; yes makes a Samay schedule as them, at
their time, `notify = always`; no drops it and asks no model.

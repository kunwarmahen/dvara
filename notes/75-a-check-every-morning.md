# 75 — A check every morning

Continues [67](67-a-check-of-your-own.md), whose first "not here" this
is.

## The problem, as you would meet it

`/doctor` tells a person what's wrong with what's theirs, when they
think to ask. The owner's whole-house check runs every morning by
itself (Samay's doctor road). A person's couldn't: a schedule's run is
sent to their agent as a model's turn, wrapped in words for a model,
and `/doctor` isn't a turn. So the Gmail sign-in that ended on Tuesday
was found on Friday, when the morning brief didn't come and they asked
why.

## Made with a word, answered without a model

**`/doctor every morning`** makes the schedule: Samay, the Dvara road,
as them, with the agent they're talking to, at 07:30 on their own clock
(their `zone`), told only when new. `/doctor every morning off` removes
it, and saying it twice says *Already*. A plain `/doctor` ends by saying
the word exists, where schedules are on.

**A WORD IS SENT AS A WORD.** Samay frames a scheduled prompt for a
model (*"(A scheduled run -- every day at 07:30. Nobody is watching
…)"*). For a schedule whose prompt is a slash word it sends the word
alone, since Dvara answers those words itself, so the run is still no
model and no allowance.

**ONLY WHAT'S NEW, AND NOTHING NEW IS QUIET.** With nobody watching,
`/doctor` answers with just the red and amber lines it didn't say last
morning (`state/doctor-told.json`, per person), or `NOTHING NEW`, which
Samay keeps and doesn't send. A phone left unplugged all week is said
once. A line that goes away and comes back is news again.

**A WORD ANSWERED IS A RUN THAT WENT WELL.** Dvara's `ok` means a
model's turn ended, and a word is never that. The first live run was
marked *failed* by Samay for exactly this, and the next morning's check
dutifully reported *"/doctor" failed* about itself. Samay now counts a
word's run as done unless Dvara said `refused` or `error`.

## Receipt

A scratch Dvara on 8798 with the real Samay (a scratch state, its clock
deliberately not serving), `asha` with `zone = "Europe/London"`. The
word over Dvara's HTTP, then `samay run-now` as the clock would at
07:30, twice:

```
> /doctor every morning
Done: I'll check what's yours every day at 07:30 (Europe/London) and tell you only when something new is wrong. /doctor every morning off stops it.

$ samay list
704dcdd4  active  every day at 07:30 -- next: Sat 31 Oct 07:30, … (Europe/London)
          /doctor

--- first morning
Fri 30 Oct 11:51  ok            Your check: 1 red
🔴 Samay's clock isn't running, so none of your 1 schedule runs
   → tell the owner: it starts again with Sarathi
--- second morning
Fri 30 Oct 11:51  quiet         NOTHING NEW

> /doctor every morning off
Stopped: no more morning checks.
```

The red line is true: this scratch Samay wasn't serving.

## Tests

`tests/test_checkup.py`: a scheduled `/doctor` says its trouble once and
`NOTHING NEW` the next time, with no model either time; `/doctor every
morning` asks Samay for exactly the Dvara-road schedule, as them, on
their zone (`SAMAY_TZ`), says *Already* the second time, and `off`
removes it; with schedules off it says so and `/doctor` doesn't offer
it. Samay's `tests/test_dvara.py`: a slash word goes alone, and a word
answered is ok unless refused.

## What is not here yet

* **A time of their own.** 07:30 on their clock; another time is
  `/schedules` and asking the agent to change it.
* **What's still wrong, said again.** Only new lines come. A sign-in
  that stays ended is said the morning it ended, and `/doctor` shows it
  any time.

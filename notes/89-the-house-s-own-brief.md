# 89 · The house's own brief

A morning brief written by an agent says what the world did: the
calendar, the mail, the portfolio. It costs a model's time, and it
can't say what the house itself did, because the house isn't one of its
tools. Which watch fired at 3 am and what the agent did about it. Which
schedule ran and whether it ended waiting on a yes. What was kept about
you. What's still due today. Which watch has quietly stopped looking.
What yesterday cost.

All of that is already written down: Dvara's ledger has every run,
Samay every schedule and its next times, Prahari every watch and how
often it fired. So `/brief` reads it and asks no model:

```
/brief                       now
/brief every morning         sent every day at 07:30 your time
/brief every morning 6:45    moved (7am, 18:30 work too)
/brief every morning off     stopped
```

## What it says

The house's real records (a copy of the ledger; Samay's and Prahari's
listings read from their containers), late on a Wednesday:

```
Your house, the last 24 hours (Wed 18 Nov 23:43):

What ran that nobody typed:
- 07:30 Your schedule 713aefd8 (Samay): "Write my morning brief." — done (/why 6)

Due today:
- nothing more today

Watches: 6 looking
- paused: Cary temp below 60 (paused by you)

Model use: 6 turns, nothing billed.
```

**What nobody typed, first.** The runs listed are the unattended ones (a
schedule's, a watch's, a routine's), because those are what a person
didn't see happen. Each is one line: what started it, in `/why`'s words,
what it was asked, how it ended, and the `/why N` that explains it. The
day is the last 24 hours, not the calendar's, so a brief at 07:30 covers
the night.

**Due today** is what's still to come today on the person's own clock,
then any paused schedule with why. **Watches** says how many are
looking, which saw what they wait for and how often, and which are
paused and why. A camera that stopped sending pictures
([Prahari's notes/14](../../prahari/notes/14-a-picture-seen.md)) shows up
here the morning after. **Kept about you** lists what the agents kept.
**Model use** is the day's turns and dollars.

A program that couldn't be read is said in the brief (*Samay didn't
answer*), never left out, so a missing section doesn't read as an empty
one.

## Every morning means every morning

`/doctor every morning` is told only when something new is wrong. The
brief's schedule is sent every day (Samay's `notify = "always"`): a
quiet day that says so is the brief working, and a brief that didn't
come would look like the house being down. The schedule sends `/brief`
here as the person, unattended, and the brief is answered the same way
a typed one is.

## Only theirs

Runs by their name, schedules and watches they own. For the house's
owner that includes the ones made at the computer (filed as `local`).
`/why` was made to cover all of a person's runs, whichever agent did
them, so the `/why N` beside each line in the brief names the right
one.

## What was deliberately not built

* **The doctor's lines.** `/doctor every morning` already sends what's
  newly wrong; the same words twice a morning would teach a person to
  skip both.
* **A model's summary on top.** The point is that it costs nothing and
  can't be wrong about what happened.
* **Other people's days for the owner.** The grants page and Dvara's
  page show everyone's; a brief is one person's.

## Tests

`tests/test_brief.py`: a watch's and a schedule's runs are listed with
how they ended and their `/why N`; a typed turn and an older run are not
"unseen"; model use counts the day and says when nothing was billed;
only what's still due today in their zone is listed, and paused
schedules are named; a program that couldn't be read is said, not
skipped; watches say how many look, which fired and which stopped; the
morning words read a time, off and nonsense; `/brief` is theirs alone
and asks no model; a scheduled `/brief` is answered, not refused.

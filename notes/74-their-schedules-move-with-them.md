# 74 — Their schedules move with them

Continues [66](66-their-own-clock.md), whose first "not here" this is.

## The problem, as you would meet it

Asha is in New York for a term, so the owner set her `zone` to
`America/New_York`, and she asked her agent for the weather every day at
8. Samay kept that schedule in New York's zone, as it should: 8 on her
clock. Then she came home to London and the owner changed her zone. Her
agent now told her London's time, her hours opened on London's clock,
and the weather still came at 8 in New York: 1 pm in London. Nothing
said it would, and the only fix was to ask for each schedule again.

## Moved, and told

**NOTICED, NOT ASKED.** Dvara rereads the actors file while it runs, so
a chore that already runs every minute compares each person's zone with
the last one it saw (`state/zones.json`). When it changed, Dvara runs
`samay zone asha --from America/New_York --to Europe/London`, and Asha
is told on her channels:

```
Your time zone is now Europe/London, so your schedules moved with you:
• the weather: every day at 08:00 -- next: Sat 31 Oct 08:00, … (Europe/London)
Any schedule you set in another time zone on purpose stays where it is.
```

**NO YES, BECAUSE NOTHING SHE AGREED TO CHANGES.** [66](66-their-own-clock.md)
said changing a schedule's zone would mean making it again, a yes on a
card. But the card she said yes to read *"every day at 08:00"* on her
clock, and her clock is what moved. Keeping it in New York would be the
change: 8 becoming 1 pm. So it moves without a question, and she gets a
line saying so, because a move nobody mentions is still a surprise.

**ONLY WHAT WAS IN THE ZONE SHE LEFT.** A schedule she made *"at 9:30
Kolkata time"* is in Kolkata's zone on purpose and stays. Samay decides
this (its `move_zone`), from the zone each schedule is in; Dvara only
says who moved, from where and to where. A person with no `zone` is on
this machine's clock, and so were their schedules: `""` on either side
means that.

**THE FIRST LOOK ONLY WRITES DOWN.** A service starting for the first
time, or a person just added to the file, has no zone it saw before:
that's not a move, and nothing runs. A move that fails (Samay not
answering) isn't written down, so the next tick tries again, and the
owner sees a line saying why.

## Receipt

The real Samay, with a scratch state holding two of Asha's schedules
(the weather at 08:00 in New York, a market reminder at 09:30 in
Kolkata), and a real Dvara service on an actors file giving her New
York, changed to London between two ticks:

```
first tick: 0 {"asha": "America/New_York"}
after the move: 1
Your time zone is now Europe/London, so your schedules moved with you:
• the weather: every day at 08:00 -- next: Sat 31 Oct 08:00, Sun 1 Nov 08:00, Mon 2 Nov 08:00 (Europe/London)

$ samay list
a4ab40db  active  every day at 08:00 -- next: Sat 31 Oct 08:00, … (Europe/London)
          the weather
bdf7f085  active  at 09:30, Mon–Fri -- next: Mon 2 Nov 09:30, … (Asia/Kolkata)
          market open
```

## Tests

`tests/test_chores.py`, `TestMoving`: a first look writes the zone down
and asks Samay nothing; a move asks Samay once, tells the person once,
and not again on the next tick; no zone is passed as `""`; a move Samay
refused is a line for the owner and is tried again on the next tick;
with schedules off nothing is asked or written. Samay's own side is in
its `tests/test_cli.py`, `TestMovingZone`.

## What is not here yet

* **Watches.** Prahari's watches look *every 3 hours*, not at a time of
  day, so a move doesn't change them.
* **A zone the person sets from the chat**, as before
  ([66](66-their-own-clock.md)).

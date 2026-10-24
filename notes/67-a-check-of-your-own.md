# 67 — A check of your own

Sarathi's doctor answers the owner at the computer: is the image older
than the code, is a port closed, which sign-in is about to end, which
schedule failed this morning. A person in the house had none of that.
When their morning brief didn't come, or their agent said it couldn't
read their mail, the only way to find out why was to ask the owner, who
then ran `sarathi doctor` and read through everyone's lines to find
theirs.

## `/doctor`, in any chat

```
/doctor
Your check: 1 red · 2 amber
🔴 Prahari isn't running, so none of your 1 watch looks or hears
   → tell the owner: it starts again with Sarathi
🟠 "Rain in Pune": the check answered, but its pick found nothing in it (pick {"json": "current_condition[0].nope"}); the page or the tool's answer may have changed
   → ask me to look at it
🟠 your agents answer 07:00-22:00, and it's 04:01 for you: closed now
   → ask again in your hours
🟢 no accounts connected
🟢 $0.00 of your $0.50 today
```

Five parts, each from the program that knows (`checkup.py`), as the
house doctor's lines are:

| part | from | red | amber |
|---|---|---|---|
| accounts | `setu status --json` in their folder (narrowed to theirs) | a sign-in the site ended | a Google sign-in in its last 3 days; a locked folder |
| schedules | `samay list` + `samay runs` | Samay's clock stopped (they have schedules) | a run of the last day that failed, ran out of time, needed them or was refused; a schedule paused for a reason |
| watches | `prahari list` | Prahari stopped (they have watches) | a watch paused for a reason; a last look that failed, broke or hit a sign-in |
| phone | `sparsh status` (their phones only) | | a phone of theirs not connected |
| limits | this service's ledger | the day's allowance or messages spent | the allowance 80% spent; outside their hours now |

ONLY WHAT IS THEIRS. A schedule, a watch or an account is in their check
when it is filed under their name, and nobody else's ever is: a guest
doesn't hear that the owner's schedule failed. The owner's own things
made at the computer (Yantra's page) are filed as `local`, so the
owner's check counts those as theirs too.

THE FIX IS WORDS THEY CAN USE. A sign-in in a folder of their own:
`/connect gmail as personal`. In a folder the owner looks after: *ask
mahen to sign it in again*. The owner gets the computer's words (`setu
connect gmail --as personal at the computer, or Setu's page`), and a
stopped piece is *`sarathi up` at the computer* for them, *tell the
owner* for anyone else.

A STOPPED PIECE DOESN'T HIDE WHAT'S UNDER IT. Prahari not running is
red, and the watch whose pick broke is still said beneath it: when it
starts again, that one will still be broken.

THE HOUSE IS SAID TO BE ELSEWHERE. The owner's answer ends with where
the rest is: *Settings → Check on the home page, or `sarathi doctor`*.
Dvara can't see the image or the firewall from inside a container, and
doesn't pretend to. Times are on the person's clock (note 66).

It's a word, not a turn: no model is asked, nothing is recorded as a
run, and Telegram's `/` menu lists it as *What's wrong with what's
yours, and the fix*.

## Live receipt

A scratch Dvara with the real `samay` and `prahari` programs on scratch
states, `away` with `zone = "Asia/Kolkata"`, `setu = true`, an
allowance and hours, and a watch of theirs whose pick was wrong (looked
once, `broken`): the answer above. The owner's, with the same Prahari
stopped:

```
Your check: 1 red
🔴 Prahari isn't running, so none of your 2 watches looks or hears
   → `sarathi up` at the computer (or Apply on the home page)

The whole house (the image, the firewall, every piece): Settings → Check on the home page, or `sarathi doctor` at the computer.
```

And the owner pointed at this computer's real Setu folder (read only,
`setu status --json`):

```
Your check: 2 amber
🟠 gmail:mine: Google ends this sign-in Mon 20:48
   → sign in again before then: setu connect gmail --as mine at the computer, or Setu's page
🟠 gmail:personal: Google ends this sign-in Sun 22:44
```

## Not here

- **Every morning, unasked.** Samay's morning doctor runs the house's
  check for the owner. A person's own check on a schedule is a schedule
  they can make ("every morning at 8, run /doctor" isn't one: a chat word
  isn't a turn), so it waits for somebody to want it.
- **Fixing anything.** Each line says the fix; none is pressed for them.
  A sign-in needs the person; a start needs the computer.
- **The house's lines for a person.** The image, the firewall and the
  disk are the owner's to know.

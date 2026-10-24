# 66 — Their own clock

One computer serves a household, and a household isn't always in one
place. A son at university in London, a parent visiting family in Pune:
each still messages the same agents, on the same machine in North
Carolina. Everything that knew the time knew the machine's:

* their agent was told the machine's time with each message, so
  "remind me in an hour" was counted right but "what's today?" at 3 am in
  Pune came back as yesterday evening;
* their schedule "every day at 7" ran at 7 on the machine's clock, which
  was 4:30 pm for them;
* their hours (`hours = "07:00-21:00"`, note 61) opened and closed on the
  machine's clock, so a bedtime was hours out.

Note 61 turned this down on purpose ("one house, one clock"). The case
for it came from the people, not the planet: a household that has
somebody abroad for months doesn't change their hours by hand twice a
year, and their morning brief (note 63) shouldn't arrive after lunch.

## One key

```toml
[actor.raj]
zone = "Europe/London"
```

An IANA zone's name (`Asia/Kolkata`, `America/Los_Angeles`, `UTC`). Left
out, the person keeps the machine's clock, exactly as before. Three
things read it:

* **The time their agent is told.** An agent with `[env] context` set is
  told the time with every message (Yantra's notes/29). For this person
  it is their clock: Dvara calls Yantra's `EnvContext.set_zone` on each
  turn it builds. The start-of-session line reads in it too, and the
  location line (from the machine's public IP) says it is *this
  computer's location*, because it isn't theirs.
* **When their schedules run.** Samay gives every schedule its own zone
  and has always read a default from `$SAMAY_TZ`. Dvara starts that
  person's Samay server with `SAMAY_TZ` set to their zone, so "every day
  at 7" made in their chat is 7 on their clock, and the card says so:
  *next: Sun 25 Oct 07:00 … (Asia/Kolkata)*. A schedule made before the
  zone was set keeps the zone it was made with; Samay never moves one.
* **Their hours.** `limits.now_for(zone)` is now on their clock, so the
  hours check at the start of every turn of theirs, typed or scheduled,
  is too.

A ZONE THAT ISN'T ONE IS AN ERROR AT LOAD. `Europe/Londn`, `IST` (an
abbreviation that means three different places), `+05:30` (an offset
that is wrong half the year somewhere): each stops the file from loading
with `zone must be a time zone's name, like "Europe/London" …`, like
every other key in the file. A misspelling quietly read as the machine's
clock would be a bedtime hours out, the failure note 61's own rule about
unknown keys exists to prevent.

Sarathi's Settings → People has a **Their time zone** box, with every
zone the browser knows as suggestions.

## What still reads the machine's clock

* **The day for money and messages** is UTC (note 06's day), for
  everybody, so the two allowances reset together. Their "messages a
  day" comes back at midnight UTC, as the refusal says.
* **Times shown in lists** (`/chats`, the runs page) are the machine's.
  They are for the owner reading the house's record.
* **Watches** (Prahari) don't keep a clock beyond "how often".

## Live receipt

A scratch Dvara on `qwen3.8:latest` through Ollama, the `minder` example
(`[env] context = "local"`), `away` with `zone = "Asia/Kolkata"`, the
owner with none, and a scratch Samay. The machine's clock said Sat 18:22
EDT:

```
$ dvara … say --actor away --agent minder "What time is it for me right now? …"
Sunday, 3:52 AM
$ dvara … say --actor owner --agent minder "What time is it for me right now? …"
Saturday, 6:22 PM EDT
$ dvara … say --actor away --agent minder "Use preview_schedule … 'every day at 7am' …"
"every day at 07:00 -- next: Sun 25 Oct 07:00, Mon 26 Oct 07:00, Tue 27 Oct 07:00 (Asia/Kolkata)"
```

## Not here

- **Moving schedules when a zone changes.** A schedule keeps the zone it
  was made in; "every day at 7" made in London stays London's 7 after
  they fly home. Changing it means making it again, which is a yes on a
  card, and that is where a person sees the new time.
- **A zone the person sets from the chat.** The owner sets it, as every
  other key in the file: it moves a child's bedtime.
- **Guessing a zone** from a phone's language or a Telegram account. A
  wrong guess is worse than the machine's clock, which at least is
  somebody's.

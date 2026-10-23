# 63 — A morning brief, ready-made

Everything a morning brief needs was already here, each piece on its
own: the person's accounts through Setu (note 19), their schedules
through Samay (note 18), their phone through Sparsh (note 30), and
last night's kept tests as a Samay schedule (note 57). What was missing
was one agent that read them all for one message. One piece also
didn't fit: a schedule could have the phone only as a phone job, which
waits for the phone to be free and may ask for it to be unlocked.

`examples/agents/morning` is that agent. A person says "send me my
morning brief on weekdays at 7:30". It makes that one schedule, asking
first, and each weekday Samay starts it and Dvara sends what it wrote to
their chat. "Brief me now" writes one straight away.

## Read only, all the way down

```toml
[tools]
allow = ["mcp__samay__*", "mcp__sparsh__phone_status"]

[connections]
needs = ["*:read"]
```

`"*:read"` is every account the person connects, now and later, read
only: Gmail, Google Calendar, Robinhood, Notion, whichever they have. A
brief that could send a mail or place a trade is a brief that one bad
morning could do either. This one can't. Of Samay's tools, only making,
pausing and deleting a schedule change anything, and those ask.

## The phone, without a phone job

Sparsh has a new read-only tool, `phone_status`. It reads the battery
(percent, and whether it is charging) and the calls missed since they
were last looked at, without touching the screen. On Android it comes
from `dumpsys battery` and the call log. On an iPhone it is the battery
from WebDriverAgent; an iPhone lets nothing read its calls.

A phone job (note 33) waits for the phone to be free, wakes it, and asks
its person to unlock it. That is right for a schedule that taps, and
absurd for one that reads the battery. So Dvara's `reads_phone` asks
whether a package admits `phone_status`. One that admits it and none of
the screen's tools gets the phone on **every** run, a schedule's too,
with no phone job: nothing it can call needs the phone free or
unlocked. Yantra's phone layer tells such an agent only about
`phone_status`, not how to tap, so the prompt doesn't describe tools the
model can't call.

## Last night's tests, read from a schedule

The nightly replay of kept tests (note 57) is a Samay schedule of the
person's. The brief calls `list_schedules`, finds the one that runs
their kept tests, and says in one line how its last run went.

A scheduled turn used to get none of Samay's tools: nobody is there to
say yes to a new schedule (note 18). But **reading** a schedule needs no
yes, and the brief runs as a schedule. So a scheduled turn now gets
Samay's tools to read, `list_schedules` and `schedule_runs`. Every tool
that makes, pauses or deletes one is taken out of its registry, and its
`schedules` layer says so instead of explaining how to offer one. A
schedule that made schedules would still be one nobody approved.

## Receipt

A scratch Dvara on port 8798, `--sparsh` on the Android emulator
(`Medium_Phone_API_35`), with a missed call from 555-0100 placed and the
battery set to 23%, unplugged. There are no accounts, and Samay is off,
so the brief has the phone and nothing else. That is the hard case for
"leave out what you can't see". Each run was sent as a schedule sends
it, `unattended: true`.

`phone_status` alone, over Sparsh's MCP:

```
Battery: 23%, not charging.
Missed calls (1 new): 5550100.
```

Through Dvara on **`gemma4:12b`**, the first prompt listed the parts,
and the model called tools it had never been given:

```
mcp__mail_query -> mcp__calendar_query -> mcp__portfolio_summary -> ... -> mcp__sparsh__phone_status
end_turn | Mail: report missing due to tool error. ...  Phone: Battery 23%, missed call 5550100.
```

A sharper prompt (*use only the tools you were given, by their exact
names; a part none of them covers is left out without a word*) made 1
clean run out of 3. The other two still invented tools
(`mcp__google_mail__list_messages`, `get_mail_data`).

On **`qwen3.8-64k:latest`**, with the same prompt, 3 out of 3 were clean.
Each called `mcp__sparsh__phone_status` and nothing else:

```
**Phone**
- Battery at 23% and not charging overnight — plug it in.
- 1 missed call from 5550100.
```

So the brief is for a model that keeps to its tools: `qwen3.8` on
Ollama, or a frontier cloud model. On `gemma4:12b` it works once every
part is connected, and invents the parts that aren't.

Then with Samay on, a scratch Samay state holding one nightly
`--runner tests` schedule that hadn't run yet, and the brief sent as a
schedule on `qwen3.8-64k:latest`:

```
end_turn | **Last night's tests** — the 02:00 "Replay the kept tests" schedule
hasn't run yet, so there's no result to report.
                  mcp__samay__list_schedules -> mcp__samay__schedule_runs
```

Not run live here: the set-up conversation that makes the schedule
(Samay's `preview_schedule` and `create_schedule`, the same path as
minder's), and a brief over real Gmail, Calendar, Robinhood and Notion
sign-ins.

## What was deliberately not built

* **A brief written by Dvara rather than by an agent.** What is worth
  saying from forty unread mails is judgement, and judgement is the
  model's. Dvara stays plumbing.
* **Missed calls on an iPhone.** WebDriverAgent can't read the call log.
  Opening the Phone app's Recents and reading the screen would be a
  phone job, with the wait and the unlock that come with one. The brief
  says the battery and nothing about calls.
* **A fixed schedule shipped with the package.** When it runs is the
  person's to say, and the schedule is theirs, made with their yes.

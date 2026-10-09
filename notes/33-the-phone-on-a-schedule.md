# 33 — the phone on a schedule

*[Note 30](30-do-this-on-my-phone.md) gave the phone's person their
phone in a chat turn, and kept it from every scheduled run: nobody would
be there to press Yes at Send. This note lets a schedule have it, on
the owner's three answers: what it may do unasked, how long it waits for
a yes, and what happens when the phone isn't free.*

## The problem, as you would meet it

"Every morning at 8, text Sam I'm on my way." In a chat that's one Send
and one Yes. On a schedule, at 8, the phone may be in your hand, or
locked on the nightstand, and nobody is watching the chat to press Yes.
Refusing every scheduled phone run was safe and useless.

## Only when the schedule says so

**A RUN GETS THE PHONE WHEN ITS SCHEDULE WORKS IT.** Samay's schedule
says `phone` (Samay's note 06): one the agent made in a chat turn that
had the phone (this service starts the person's Samay tools with
`--phone`), or `samay add --phone`. `POST /message` then carries
`phone: true`. Without it a scheduled run gets no phone, as before. The
run's person must be the phone's (`phone = true`); anyone else is
refused before anything runs.

## Is the phone free? (ready.py)

Before the turn, the door asks Sparsh (`sparsh state`):

* **In use** (screen on, unlocked): someone has it in hand. Looked at
  each minute for up to ten, then the run is **skipped** and says so. A
  run that took a phone out of someone's hand would tap through
  whatever they were doing.
* **Locked**: an agent can't open it; it would need the PIN. **The
  person is asked**, in their own chat: *"Your phone is locked, and a
  schedule wants it now: … Unlock it and it will start; it waits N
  minutes."* Unlocked in time is a yes: the run goes, though the screen
  is on. Still locked at the end of the schedule's wait: skipped.
* **Asleep** (screen off, no lock): woken (`sparsh wake`), and the run
  goes.
* **Unknown** (an iPhone says only whether it's locked): goes.

A phone that can't be reached is a skip in Sparsh's words. A skip
starts no turn and spends nothing. Samay records it as `skipped`, which
doesn't count toward pausing the schedule.

## What it may do unasked, and how long a yes may take

**STEPS THE PERSON GRANTED.** `phone_steps` are sentences the person
accepted with the schedule (*"send in Messages when the screen shows
555-0123"*). They go to Sparsh as `SPARSH_GRANTS` when the turn starts
its tools, and Sparsh decides each held tap against them (its note 07).
The door doesn't interpret them: one place reads the form, and it's the
one that sees the screen.

**THE SCHEDULE'S OWN WAIT.** A scheduled run's questions wait, in all,
what its schedule says (`wait`, default 30 minutes), not the door's own
two minutes. The person accepted that wait with the schedule, so it may
be longer than the desk's deadline; it is still cut by their daily
allowance for waiting (note 14).

**A QUESTION THAT OUTWAITS IT LAPSES.** Refused, never held, even when
the owner runs the door with `--on-timeout hold`: a turn kept for later
has nobody coming back to it, and the next run is tomorrow's. Once the
wait is used up, later questions in the same run aren't put at all. The
reply's `refused` names each lapsed question in Sparsh's words, so
`samay runs` can show what was waiting for a yes.

## Live, on the emulator

The door on `qwen3.8:latest` (Ollama), the `phone` agent, its person
with no chat, Samay running the schedule now:

```
samay run-now 542c20c0      # "Text 555-0123 ...", step granted, wait 2
  ok        Done. The message "running late, home by 7" was sent to 555-0123
  (sparsh: tap "Send SMS — SMS" -> done (granted ahead: "send in Messages
   when the screen shows 555-0123"))
samay run-now 542c20c0      # with a PIN set, the screen off
  skipped   skipped: the phone stayed locked for 2 minutes after you were asked
samay run-now 542c20c0      # locked, unlocked 20 seconds after asking
  ok        Done. Today's message ... was sent
samay run-now 59e02c0b      # "Text 555-0199 ...", the same step
  ok        ... the send step is one that needs your explicit go-ahead ...
    asked, not answered: mcp__sparsh__confirm: On the phone emulator-5554:
    tap item "Send SMS — SMS" in com.google.android.apps.messaging -- held
    because it says "send".
```

The emulator's sent box held the two texts to 555-0123 and none to
555-0199. In that last run the question had nowhere to go, since the
scratch person had no chat, and was refused at once. With a chat, it
waits the schedule's wait first.

## Live, on a real phone

A Nexus 6P (Android 8.1) with a PIN, reached over Wi-Fi from Sarathi's
containers, the door on `qwen3.8-64k:latest`, the `minder` package, and
its person on Telegram. A schedule "On my phone, open Settings and tell
me what the Battery row says", wait 2 then 5 minutes:

```
samay run-now ...   # locked; the Wi-Fi link stale from the screen being off
  skipped   skipped: the phone couldn't be reached (adb said: error: closed)
samay run-now ...   # locked; asked on Telegram; away from the phone
  skipped   skipped: the phone stayed locked for 2 minutes after you were asked
samay run-now ...   # locked; asked; unlocked in time
  ok        I couldn't do that -- the phone tools (Sparsh) aren't connected
            in this scheduled session ...
samay run-now ...   # the same, after the fix below
  ok        Your phone's Settings show the Battery row as: Battery -- 99% ·
            charging.
```

The question reached the chat each time. The first skip was Sparsh's: a
Wi-Fi link that went stale while the screen was off, now reconnected
once (Sparsh's note 08).

**THE PACKAGE MUST LET THE PHONE IN, OR THE RUN NEVER STARTS.** The third
run is the one this note didn't foresee. `minder`'s `[tools] allow` named
its own tools and not `mcp__sparsh__*`, and an allow list is complete:
every phone tool was hidden. But the door still started Sparsh and wrote
the phone into the prompt, so the model called `open_app`, read "no such
tool", and told its person the phone wasn't connected, right after they
had unlocked it to let the run in. Now a package whose list leaves the
phone out gets neither the server nor the prompt, and a schedule that
works the phone on such a package is refused before the phone is
looked at:

```
minder can't work the phone: its package's [tools] allow leaves out
mcp__sparsh__* (add it, as examples/agents/phone does)
```

Nobody is asked to unlock a phone for a run that can't touch it.

## What the tests hold

`tests/test_phone.py`: a scheduled run whose schedule works the phone
gets it and its granted steps (asleep: woken first); without its
schedule saying so, none; someone who isn't the phone's person is
refused; a phone in use is left alone and the run skipped; a locked
phone asks its person once, then skips; `ready.py` alone, with a phone
made of answers and a clock (unlocked after asking goes; in use is
looked at each minute for ten; put down and locked then asks; an iPhone
goes; unreachable is a skip). `tests/test_gate.py`: a schedule's wait
may be longer than the desk's; a question that outwaits it lapses,
never held, and is named. `tests/test_http.py`: the new fields go with
`unattended: true`. 709 tests before, 726 after; 728 with a package that leaves the
phone out (refused before asking; no phone and no word of one).

## What is not here yet

* ~~**A real phone, with a real lock** and a real Telegram chat to ask
  in.~~ A Nexus 6P with a PIN, asked on Telegram: *Live, on a real
  phone*, above.
* **Asking the person in the run's own words for a lapsed step,
  afterwards** ("it's in the compose box: send it?"). The agent says so
  in its answer today; nothing turns that into a button.

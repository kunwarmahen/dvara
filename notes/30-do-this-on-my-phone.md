# 30 — do this on my phone

*[Note 18](18-a-schedule-asked-for-in-the-chat.md) gave a person's turn
Samay's tools, started for that person and stopped with the turn. This
note does the same for the phone plugged into the machine the door runs
on, through [Sparsh](https://github.com/kunwarmahen/sparsh).*

## The problem, as you would meet it

At a keyboard, Yantra finds Sparsh by itself and the agent can work the
phone: open an app, tap by number, type, and stop before Send for your
yes. From Telegram, the same request goes nowhere. Agents here are built
fresh for each turn and get no phone, and "text Sam I'm running late"
from your phone, while you're out, is the moment it would matter.

Two things make it more than "start Sparsh's server":

* **Whose phone.** A door serves several people, and the phone on the
  cable is one person's, with their messages on it. Another person's
  agent on it would read those messages and tap over each other.
* **Who says yes, and where.** A held step (Send, Pay, Delete) needs its
  person's yes. At a keyboard, that's a prompt. Here, it has to reach
  them in the chat they're writing from.

## One person's phone

`phone = true` in the actors file marks the person the phone belongs to.
**ONE PERSON, CHECKED AT LOAD.** Two people marked is a config error
naming both, the same rule as one channel identity belonging to one
person: there is no right way to guess which of them owns it.

`dvara --sparsh` (or `DVARA_SPARSH=PATH`) turns the phone on. Off unless
asked for, like Samay: a door doesn't switch on hands on someone's
phone because a program was found on `PATH`. Asked for and not found
stops the start, where the owner is looking. No phone attached yet is
said and not refused: plug one in, and the next turn asks Sparsh again.

```
dvara: the phone through sparsh 0.1.0 (/home/you/sparsh/.venv/bin/sparsh); phone: emulator-5554
```

Each turn of that person starts `sparsh mcp` beside the agent, through
Yantra's own `sparsh_link`, and stops it when the turn ends. Everyone
else's turns get nothing, and so does a **scheduled turn**: nobody would
be there to press Yes, and a held step could only be refused.

## The yes, as buttons

Nothing new was needed here, which is the point of having built it
twice already. Sparsh's `confirm` is the only way through a held step,
and Yantra marks it `always_ask`. The door's gate puts any such call to
the person on their channels (asks.py), and the Telegram adapter draws
every question with two buttons. What the question says is Yantra's
card for `confirm`: Sparsh's own account of the step and the screen it
was on. So the button sits under the message that will be sent, not a
hold id.

The package has to ask: `[permissions] mode = "ask"`, or `confirm` is
refused with nobody asked. And a package with `[tools] allow` must name
`mcp__sparsh__*`. `examples/agents/phone` is one that does both.

## Live receipt

The Android emulator, `gemma4:26b` on Ollama, `dvara say` with the
terminal standing in for the chat (the same desk, the same question):

```
$ dvara --root examples/agents --actors actors.toml --provider ollama \
    --model gemma4:26b --ask --sparsh ~/sparsh/.venv/bin/sparsh \
    say --actor owner --agent phone "Text 555-0123 from my phone: dvara phone test"
dvara: the phone through sparsh 0.1.0 (…/sparsh); phone: emulator-5554, emulator-5556

phone wants to run mcp__sparsh__confirm:
  Do this on the phone?
On the phone emulator-5554: tap item "Send SMS — SMS" in com.google.android.apps.messaging -- held because it says "send".
The screen when it was asked for:
App: com.google.android.apps.messaging
1 text "Texting with 555-0123 (SMS/MMS)"
…
3 field "dvara phone test" [tap, type, focused]
…
5 item "Send SMS — SMS" [tap]
approve? [y/N] n
The message wasn't sent because you declined the confirmation.
```

The phone's sent messages afterwards: none with that text.

An earlier try on the same model didn't get that far: Messages' "Start
chat" screen kept moving under it, and it gave up without a word about
why. Both emulators and the model were sharing one machine at the time.

## What the tests hold

`tests/test_phone.py`: the phone's person gets the tools and the prompt;
a held step reaches the desk in Sparsh's words, and a yes lets `confirm`
through; a no sends nothing; no server outlives its turn. Someone else,
a scheduled turn, and a door started without `--sparsh` get none. A
Sparsh that won't start costs the phone, never the turn. Two people
marked is an error; `phone` is true or false; asked for and missing
stops the start. 676 tests before, 689 after.

## What is not here yet

* ~~**A real phone over Telegram.**~~ Pressed from a real chat, to a
  Nexus 6P over Wi-Fi from Sarathi's containers: the Send card came with
  the message in its box and the yes went through (the phone had no SIM,
  so Messages said *"Network is not ready"* and the agent said so). It
  found two things. A model asked *"shall I send it?"* in words, so the
  hold was gone by the reply. That card is no longer shown, and
  the `phone` prompt says to confirm in the same answer (Yantra's note
  124). The second was a screen that went dark mid-task, now kept on
  while the agent works (Sparsh's note 09). The ring card, from a real
  chat, waits for a task that needs a tap by position.
* **More than one phone**, one per person. One cable, one person, for
  now.
* ~~**A phone in a scheduled run.**~~ When its schedule says so, after
  the phone is checked free, with the steps its person granted
  ([note 33](33-the-phone-on-a-schedule.md)).
* ~~**A question you answer by looking.**~~ A tap by position's question
  carries the screen with the spot ringed, to every channel
  ([note 32](32-the-ring-in-the-chat.md)), and so does every held step:
  the screen with what it would tap ringed and one line of what's
  filled in, where the card above had the whole numbered list (Sparsh's
  notes/10).
* **The door in containers.** Sarathi's containers can't reach a phone
  on a cable; that waits for pairing over Wi-Fi.

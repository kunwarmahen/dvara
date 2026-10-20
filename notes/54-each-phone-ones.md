# Each phone, one person's

`phone = true` said that the phone on this machine's cable was one
person's ([note 30](30-do-this-on-my-phone.md)). One phone, one person:
two people marked was an error naming both. Sparsh can now serve
several phones, each by a name
([its note 18](https://github.com/kunwarmahen/sparsh/blob/main/notes/18-several-phones.md)),
so a house can have an old Nexus kept for the agent, the owner's
iPhone, and a phone of Asha's. Each is still one person's, messages and
all. Here that means each phone has one owner, and no agent reaches a
phone that isn't its person's.

## Whose is which

```toml
[actor.owner]
phones = ["nexus", "iphone"]

[actor.asha]
phones = ["asha-phone"]
```

**A PHONE HAS ONE OWNER.** A name under two people is a config error
that names both, the same rule as two `phone = true`, and for the same
reason: two people's agents on one phone would read each other's
messages and tap over each other. `phone = true` keeps its meaning and
gains a sharper one. It is every phone here, so one person with it and
anyone else with `phones` is an error too, and so is one person with
both. The names are Sparsh's (lower case, digits, dashes). Who owns
which phone is said here and nowhere else. Sparsh knows what phones
exist; Dvara knows whose they are.

## Their phones and no others

**SPARSH IS STARTED WITH ONLY THEIRS.** Each turn already started its
own Sparsh server and stopped it when the turn ended. Now, for a
person with `phones`, that server is started with `--phone` for each of
their phones, and Sparsh serves nothing else. The `phone` prompt layer
is narrowed the same way, so the model is told about their phones only.
Another person's phone isn't hidden from the agent. As far as the agent
can tell, it doesn't exist: a `phone` argument naming it is refused by
Sparsh before adb is asked. If a person's phone isn't one Sparsh names
(a typo, or a phone taken out of the house's settings), the turn goes
on without the phone and the owner is told why, as with a Sparsh that
won't start.

`/phone` shows the person's first phone that answers and names the
others under it (*"Your other phones: /phone iphone"*). `/phone NAME`
shows that one. Someone else's phone by name gets one sentence and no
screen, and nothing is asked of Sparsh.

## A schedule works the phone it names

A scheduled run works the phone with nobody watching, after
[ready.py](../src/dvara/ready.py) checks the phone is free: in use is
waited on, locked asks its person, asleep is woken
([note 33](33-the-phone-on-a-schedule.md)). With several phones, that
check has to be of a particular phone. `phone` in a delivery (and in
`/phone/ready`) can now be a name as well as `true`:

* a name: that phone, when it is theirs. A phone that isn't theirs is
  refused with a sentence for the logbook;
* `true`, and they have one phone: that one;
* `true`, and they have several: **REFUSED, NOT GUESSED** — *"this
  schedule doesn't say which phone, and owner has 2 (nexus, iphone):
  make it again naming one"*. A run that took whichever phone answered
  would open WhatsApp on the Nexus for a job set up on the iPhone;
* `true`, and they have every phone (`phone = true`): unnamed, as before.

The phone checked free is the only one the run gets. `sparsh state` and
`sparsh wake` are asked with `--phone NAME`, and the run's Sparsh is
started with that phone alone.

## LIVE RECEIPT

The Nexus 6P on the cable and the Android 15 emulator, named in
`SPARSH_PHONES`. Two people, one phone each, with `qwen3.8-64k:latest`
on Ollama and `examples/agents/phone`:

```toml
[actor.asha]
phones = ["nexus"]
agents = ["phone"]

[actor.ravi]
phones = ["pixel"]
agents = ["phone"]
```

```
$ dvara ... --sparsh $SPARSH say --actor ravi --agent phone \
    "Which phones can you work? Then open Settings on it and tell me the first item in its list."
dvara: the phone through sparsh 0.1.0 (...); phone: nexus: 84B7N16128001616, pixel: emulator-5554
Done — here's what I found:

**Which phones can I work?** For now just one: the **Pixel emulator** (`emulator-5554`).
It's the only device connected to the service, so it's the one I opened Settings on.

**First item in the Settings list:** **Network & internet** (subtitle: Mobile, Wi‑Fi, hotspot).
[end_turn · $0.0000 · 21158in/511out · run 8e210eff842d]

$ dvara ... say --actor asha --agent phone "/phone pixel"
pixel isn't one of your phones (nexus).

$ dvara ... say --actor asha --agent phone "/phone"
Your phone (nexus) now shows com.android.systemui:
1 image "Calendar notification: ..."
```

The startup line lists both phones, because the service has both. Ravi's
agent was given only his, and believed it was the only phone there:
from inside his turn, that is true.

## What is not here yet

* ~~Samay naming a schedule's phone.~~ `samay add --phone nexus`, the
  agent's `phone_name`; sent to Dvara as `phone: "nexus"` (Samay's
  notes/06).
* A real iPhone and a real Android with two people at once.

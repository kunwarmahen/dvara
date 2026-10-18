# 39 — while nobody is writing

*[Note 38](38-what-they-said-in-passing.md) looked back over a
conversation at `/new`, and [note 19](19-their-own-accounts.md) let each
person keep their own sign-ins. Both waited on somebody doing something:
sending `/new`, or asking for the account that had stopped working. This
note is two things Dvara now does on its own, beside the channels, for
as long as it runs.*

## The problem, as you would meet it

Priya talks to the greeter on Telegram most days. She has never sent
`/new`, and never will: a Telegram chat has no end anybody marks. So the
look back at `/new` never ran for her, and everything she said in
passing about where she lives and when she works went with the turn.

Her work Gmail's sign-in ran out on a Sunday. Nobody asked for it until
Tuesday morning, when she wanted a summary of her inbox before a
meeting, and heard instead that she had to sign in again.

## A conversation gone quiet is looked back over

A conversation nobody has written in for **30 minutes** is looked back
over once, as `/new` does, but the conversation is kept: she can carry
on where she left off. What the look back noticed is sent to her as a
notice (on Telegram, on the page, and with ntfy on her phone, note 40),
numbered for `/remember`, under the agent's name:

```
greeter: Looking back over our conversation, I noticed this about you:
1. Lives in Raleigh (near RDU airport).
2. Works night shifts at a hospital.
Send /remember with the numbers to keep them (/remember 1 2), or /remember all. Nothing is kept unless you do. /remember not 1 2 (or /remember none) and I won't offer those again.
```

* **ONCE, UNTIL THEY WRITE AGAIN.** The look back is a run of its own
  (`looked_back`), so the conversation's last run says it was looked
  back over, and it leaves the list until she says something new
  (`RunStore.gone_quiet`). A `/new` right after lists what is waiting
  without asking the model again.
* **ONLY NEWS IS A MESSAGE.** A look back that found nothing sends
  nothing: an unasked message saying "nothing to remember" is noise.
* **A PERSON'S CONVERSATION, NOT A PROGRAM'S.** A conversation whose
  last run was a program's (Samay's) is not looked back over, and
  neither is one quiet for more than a day, so a service started for
  the first time doesn't look back over its whole past.
* **WHAT IT COSTS.** One call to the agent's own model, on the person's
  allowance, recorded like any turn. A package that keeps no memories
  asks no model. `--quiet-for MINUTES` changes the wait; `0` means only
  at `/new`, as before.

## Every sign-in, checked once a day

Once a day (the first a few minutes after start-up), Dvara runs
`setu check --json` in every Setu folder it reads: each person's own,
and a folder the owner pointed people at. Setu refreshes each sign-in
that can run out, marks the refused ones, and says which (Setu's
README). Dvara tells each new one to whoever can fix it:

```
Your gmail sign-in (priya@example.com) stopped working on 2026-10-12: the site refused it. Send /connect gmail as work to sign in again.
```

* **TO WHOEVER CAN FIX IT.** A person's own folder: them, with the words
  that fix it from the chat. A folder the owner shared: whoever may
  manage it from the chat (`setu_manage`); when nobody may, a line for
  the owner on Dvara's log with `setu connect … --as …`, and no message
  to somebody who can do nothing about it.
* **TOLD ONCE.** What was told is kept in `<state>/signins.json`, by the
  time Setu first marked it. The same refusal tomorrow is not news; a
  sign-in that came back and ran out again is.
* **NOTHING ELSE TOUCHED.** Browser profiles, apps on the phone, locked
  folders and long-lived tokens are skipped by Setu; a site that did not
  answer is not a refusal. A check that fails is a line for the owner,
  and tomorrow tries again. `--check-sign-ins HOURS` changes how often;
  `0` turns it off.

## Receipt

A scratch Dvara on `gemma4:12b`, its greeter package with
`[memory] via = "local"`; the owner pointed at the machine's real Setu
folder (`setu_manage`), and priya given her own folder with one made-up
Google sign-in, so Google itself refused it:

```
TURN: Welcome to the neighborhood.

(I noticed 2 things about you worth remembering. Send /remember to see what's waiting.)
QUIET LOOK BACKS: 1 | again 15 min later: 0
SIGN-INS TOLD: 1 | again: 0
```

Both notices read as quoted in the two sections above. The owner's own folder (two Gmails, Home Assistant) was
checked too and told nothing: all three were fine. The first run of this
told priya's refusal twice, a minute apart: Setu wrote the mark's time
afresh on every refused refresh. Setu now keeps the first time
(`429da5c`), and the run above is after it.

## What the tests hold

`tests/test_chores.py`: a quiet conversation is looked back over once,
the person told, and the conversation kept; a look back that found
nothing sends nothing; a package that keeps no memories asks no model;
`0` turns it off; `/new` after a quiet look back lists without asking
again. A refused sign-in is told once with the words that fix it; one
back and refused again is news; a shared folder nobody manages is a line
for the owner; nothing refused tells nobody.

## What is not here yet

* **A warning before it runs out.** Google's seven days for an app in
  Testing could be counted down; a published app's sign-ins don't run
  out on a clock, so a check finds what happened rather than guessing
  what will.
* **Browser sign-ins.** Amazon or X signing a profile out is seen only
  when a site's tools next open it (Setu's health line).

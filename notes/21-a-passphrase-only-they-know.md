# 21 — a passphrase only they know

*Notes [19](19-their-own-accounts.md) and
[20](20-signing-in-from-the-chat.md) gave each person their own Setu
folder and let them sign in to it from their phone. Both said the same
uncomfortable thing: a person's tokens sit on the owner's disk, and the
owner could read them. This note lets a person lock their folder with a
passphrase only they know.*

## What "the owner can't read it" can honestly mean

Whatever computer *uses* a token can read it. A person's agent runs on
the owner's computer, so while it's reading their mail, the token is in
a process the owner (as that machine's administrator) could look inside.
And the mail it reads passes through the owner's machine as well. No
lock changes that, and this design doesn't pretend otherwise.

What a lock *can* do is keep the folder unreadable **at rest**: to the
owner browsing their own files, to a backup, to a stolen disk, to
anything that reads the folder while the person isn't using it. That's
what this is.

## Three words more

```
/lock              the first time: choose a passphrase (your next message)
                   after that: lock now
/unlock            open it for 7 days (your next message is the passphrase)
/unlock 2          ...for 2 days (30 at most)
```

Locked, Setu seals every key in the folder (its `setu lock`, with the
passphrase): refresh tokens, Home Assistant tokens, and the browser
sign-ins too, Amazon's and X's cookies packed and sealed. What stays
readable is *which* accounts exist, so the person can be told which one
is locked:

```
/accounts
  Connected for you here:
  gmail:personal -- raj@example.com -- Read only
  Locked with your passphrase: send /unlock to open it.
```

## The passphrase is a message that goes nowhere

After `/lock` or `/unlock`, the person's next message is the passphrase.
It is handled before any turn, like the other account words: handed to
`setu lock` on its standard input (never on a command line, where any
process could read it), and dropped. No agent sees it. It isn't kept in
the conversation's history, in the run log, or in the bot's outbox,
which notes "(a passphrase)" where a message preview would be. On
Telegram the bot deletes the message from the chat once Setu has it.

A command sent instead (`/accounts`, say) means "never mind": the wait
is cancelled, and the next ordinary message goes to the agent as usual.

## The key lives in memory, for as long as they said

Unlocking gives dvara the folder's key, and dvara holds it **in memory
only**, for the days the person chose. It's handed to Setu for that
person's turns, both chat and scheduled, so their schedules keep running
while they're away. Setu never passes it on to a connector or a browser.
When the time is up:

* the folder's browser sign-ins are packed and sealed again,
* the key is dropped,
* and they're told: *"Your accounts locked again: the 7 days you opened
  them for are up. Send /unlock when you want them back."*

**A RESTART LOCKS EVERYONE.** The key is never written down, so a
service that stops forgets every key it held. At start-up it seals any
browser sign-in a crash left unpacked (sealing needs only the folder's
public half, never the passphrase; Setu's seal.py). The person finds out
at their next turn, where the agent says their accounts are locked and
how they open:

```
How many unread emails do I have in Gmail?
  I can't check your Gmail unread count — the account gmail:personal is
  connected but currently locked with your own passphrase. ... To unlock,
  you'd need to send /unlock on my side (unlocking isn't something I can
  do for you).
```

**FIVE WRONG PASSPHRASES IN AN HOUR**, and `/unlock` stops asking for the
rest of that hour. Someone holding somebody's phone gets five guesses,
not a script.

**FORGET IT AND IT'S GONE.** Nobody can get a passphrase back: not the
owner, not Setu. The accounts have to be connected again. `/lock` says
so before they choose one.

## Only their own folder

As with `/connect`, a person pointed at the owner's folder can't lock it
from the chat. Otherwise a chat message would lock the owner out of
their own accounts.

## Receipt

Real Setu, a scratch dvara over HTTP, raj with `setu = true` and one
connection in his folder:

```
/lock                 → Send the passphrase you want as your next message ...
blue kettle on a hill → Locked with your passphrase. Your accounts are open until
                        Mon 12 Oct, 22:28 ...
  vault.json: the refresh token no longer appears in it (0 matches)
/accounts             → ... Locked with your passphrase, and open now (/lock closes it).
/lock                 → Locked. /unlock opens them again.
/unlock 2             → Send your passphrase as your next message ... for 2 days.
red kettle on a hill  → That didn't open them: that is not this folder's passphrase.
/unlock 2, then the right one → Your accounts are open until Wed 07 Oct, 22:28 ...
  the passphrase: on disk nowhere under the service's state
```

And the turn above, with `qwen3.8:latest`, on the folder locked.

## What was deliberately not built

* **Remembering the key across a restart.** Anywhere it could be kept,
  the owner could read it, which is the thing this exists to prevent.
* **A key the owner's machine never holds.** That would mean the
  person's own computer making every request, and their computer would
  have to be on for any turn. A different design, for another day.
* **Recovery.** A passphrase someone can recover for you is a passphrase
  someone else can use.

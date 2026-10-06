# 23 — is the door open?

*[Note 09](09-a-process-you-walk-away-from.md) made a running dvara hold
a lock on its state directory, so a second one is refused. This note
turns the same lock into an answer for whoever asks: is a dvara serving
from here, and where?*

## The problem, as you would meet it

A program that starts this service for you (Sarathi is one) has to say
whether the door is open. Before this, all it could say was that it
*found* dvara: a program on disk. Whether anything was serving behind
it, whether that was the HTTP surface or a bot, and on what address,
were all guesses. A guess from a pid goes wrong in exactly the cases
that matter: after a crash, and from another container.

## Asked of the lock, never the file

```
$ dvara status
dvara 0.1.0 · state /home/you/dvara/state
serving at http://127.0.0.1:8765 (dvara serve, since 2026-10-06T02:56:39+00:00)
agents: greeter, minder, scribe  ·  people: 2
```

`dvara status --json` prints the same thing as `dvara.status.v1`, the
shape Setu's and Samay's `status --json` already use: a `format` field
naming the version, which a reader refuses rather than guesses at.

**THE LOCK IS THE ANSWER.** `dvara serve` and `dvara telegram` hold the
claim for as long as they run, and the file under it says who they are,
since when and, for `serve`, the address it listens on. Status tries a
shared lock on that file. Getting it means nobody holds the claim, so
nothing is running, whatever the file says. This is the same argument as
Samay's note 05, and it is right in the same two places a pid is wrong:

* **after `kill -9`** the file is still there, naming a dead pid and an
  address. The kernel let the lock go, so status says *not running*:

  ```
  $ cat ~/dvara/state/dvara.lock
  pid 3500480
  dvara serve
  since 2026-10-06T02:56:39+00:00
  at http://127.0.0.1:8799
  $ dvara status
  ...
  not running (start it: dvara serve)
  ```

* **from another container** mounting the same folder, the lock is the
  same lock. Its pid means nothing there; the lock still does.

**SERVING IS NOT THE SAME AS BUSY.** `dvara say` and `dvara resume` hold
the claim too, for one turn at a keyboard. Status reports them as
*busy*, not *serving*: nobody else can reach a `say`.

## Asking starts nothing

Status never builds a `Service`. It doesn't open the ledger, doesn't make
the state directory, and doesn't take the claim, so asking while the bot
answers somebody refuses nobody. What it can't read, a missing agents
folder or an actors file with a typo, comes back as a problem in words,
with exit 0:

```json
"problems": ["agent root is not a directory: /home/you/dvara/agents",
             "no actors file at /home/you/dvara/actors.toml"]
```

A status that failed on a broken file would hide the one thing the owner
was asking it to show.

**NO SECRET IS IN IT.** No token, and no names of people: a count.

## What was deliberately not built

* **Probing the port.** A port that accepts a connection says nothing
  about which program is behind it, and Sarathi's own containers publish
  ports before the program inside listens. The lock is dvara's own word.
* **The held questions, the day's spending, the last turn.** `dvara
  held` and `dvara runs` answer those, and both open the ledger. Status
  stays a read of three files.

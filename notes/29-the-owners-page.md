# 29 — the owner's page

*[Note 23](23-is-the-door-open.md) answered "is the door open?" in a
terminal. [Note 08](08-what-the-turn-actually-did.md) gave every run its
shape. This note puts both in a browser for the owner, and draws a line
around whose words go on it.*

## The problem, as you would meet it

You run a door for a household. Priya has a $0.50 day, your own phone is
on it, and a scheduled check runs every two hours. To know how it's going
you open a terminal and type `dvara runs`, then `dvara status`, then work
out each person's spend from the cost column. Nothing shows it all at
once: who's on the door, which agents they may use, what they've spent
today against their allowance, and what their agents have been trying to
do.

## A page beside the door, not inside it

```
$ dvara page --as owner
dvara's page for owner:
  http://127.0.0.1:8785/#token=…
(the part after # is its key: open it once, the page keeps it. Ctrl-C stops.)
```

The page has a card for each person: what they've spent today against
their daily allowance (with a meter), the past seven days, which agents
they may use, and how they're reached. Below that are the agents and who
may use each, then every turn newest first, filtered by person or agent,
with the tools each called and the refused ones in red.

**A SEPARATE PROCESS, AND IT ONLY READS.** `dvara page` reads what `dvara
serve` writes (the actors file, the runs ledger) and claims nothing
([note 09](09-a-process-you-walk-away-from.md)). It runs whether or not
the door does, and it can't stop or slow a turn. Changing who's served or
what they may spend stays in the actors file, which the door already
re-reads without a restart. A page that edited that file would be a
second way to change it, and the owner reviews the file, not the page.

**THE OWNER'S WORDS ON THE OWNER'S PAGE, NOBODY ELSE'S.** Every run is
listed: who, which agent, when, what it cost, which tools it called and
which were refused. That's what an owner watching a bill or an agent
needs. What a person typed and what the agent told them are theirs, so a
run's message and reply appear only for `--as`'s own runs. Everyone
else's card says *"What was said stays theirs."* The ledger holds the
words, and `dvara runs` prints the first 48 characters of them. The page
was the moment to decide whether a browser tab left open on the kitchen
laptop should show them too, and it doesn't. How someone is reached
follows the same rule: `reached on telegram`, never their Telegram id.

**UNPRICED IS COUNTED, NOT ROUNDED** ([note 06](06-a-number-you-can-act-on.md)).
A turn with no list price is shown as "2 turns, 1 with no price", never
added in as $0.00. `RunStore.turns_since` is the new query: the count,
and how many of those had no price.

**ITS OWN TOKEN, NEVER THE DOOR'S.** `DVARA_TOKEN` lets a caller speak as
anyone in the actors file, so it never reaches a browser. The page has its
own token, `$DVARA_PAGE_TOKEN` or one made once in the state folder at
0600, printed after the `#`, which a browser never sends to a server.
Three static files, `script-src 'self'`, `frame-ancestors 'self'`, every
value drawn as text: what a person typed can be shown on the page but
never run.

## Live receipt

The host's own door folder (the owner, three agents, 32 turns this week
on `qwen3.8:latest` through Ollama):

```
$ curl -s -o /dev/null -w "%{http_code}\n" localhost:8785/api/people
401

$ curl -s -H "Authorization: Bearer $T" localhost:8785/api/status
{"format": "dvara.page.status.v1", "version": "0.1.0", "owner": "owner",
 "serving": false, "url": null, "since": null, "state": "/home/…/dvara/state",
 "agents": 3, "people": 1, "problems": []}

$ curl -s -H "Authorization: Bearer $T" "localhost:8785/api/runs?limit=3"
owner minder end_turn 0.0 ['x_open', 'x_open', 'x_follow', 'x_scroll'] Can you get me the latest post from @Kob…
owner minder end_turn 0.0 [] Hey what's up, what is your name
owner minder end_turn 0.0 ['x_open', 'x_open', 'x_scroll'] Can you get me the latest post from @Kob…
```

The page drew the owner's card ("2 turns today · $0.00 over 7 days (32
turns)", no daily limit, reached on telegram, a shared Setu folder), the
three agents, and the turns, with the earlier `web_fetch` calls on x.com
marked refused. The door itself was running in Sarathi's containers on
their own state folder, so this one said *door not running*, which was
right for this folder.

## What was deliberately not built

* **Answering from the page.** That's next ([below](#what-is-not-here-yet)),
  and it will be the owner's own questions only. A question is addressed
  to one person ([note 02](02-a-question-that-can-wait.md)), and the page
  doesn't speak for anyone else, not even read-only.
* **Editing the actors file.** Above: one place to change the household,
  and it's the file.
* **Inside `dvara serve`.** In-process would answer live questions more
  simply. But it would put a browser-facing page in the process that
  holds the door's token and every conversation's lock, and the page
  would stop whenever the door did.

## What is not here yet

* **The owner's approvals and held turns, answered in the browser.** The
  page will send them to the running door's `/asks` and `/holds` as the
  owner. It holds `DVARA_TOKEN` server-side and never takes an actor from
  the browser.
* **Each person's files and schedules**: names, sizes and dates for
  everyone; contents only for the owner's own.
* **Started by Sarathi** beside the door, and linked from Sarathi's home
  page.

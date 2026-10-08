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

## Answering your own, through the door

The page has one kind of write: **Waiting for you**, at the top. It shows
the questions your agents are asking you now (*"scribe asks to use
write_file: NEW FILE owner-rain.txt (2 lines)"*), with **Allow** and
**Refuse**. It also shows turns that stopped because nobody answered in
time, each waiting call with Allow or Refuse (and an optional reason),
and **Carry on**.

**THE ANSWER GOES THROUGH THE DOOR.** A question waiting for you lives in
`dvara serve`'s memory ([note 02](02-a-question-that-can-wait.md)), and a
held turn is carried on by running the rest of it
([note 16](16-kept-for-when-you-are-back.md)). Neither can be done from
another process. So the page asks the running door, over the same
`/asks` and `/holds` every adapter uses, with `DVARA_TOKEN` held in the
page's process. Your answer is then the same as pressing the button in
your chat: the copies on your other channels are taken down
([note 12](12-taken-down-everywhere-it-went.md)).

**YOURS ONLY, AND THE DOOR STILL CHECKS.** The page asks the door for
`--as`'s questions, filters the answer again for `--as`, and sends every
answer as `--as`. A name in the browser's request is ignored. Somebody
else's question never reaches the page, not even to be shown. And the
door's own rule ([note 02](02-a-question-that-can-wait.md)) is unchanged:
an answer must name the person asked, so a page started with the wrong
`--as` gets *"that question was put to somebody else"*. As in `http.py`,
**only a JSON `true` approves**: `"yes"` is refused before it reaches
the door.

**NO DOOR, NOTHING TO ANSWER.** With no door running, nothing is
waiting, and the page says so. Held turns stay on disk until the door is
back. The page doesn't open the holds file itself, because listing it
drops the expired ones, and that's the door's job. Without
`DVARA_TOKEN`, the page says what to set.

A held turn carried on can run for minutes on a slow model, so the page
has no lock of its own around requests (the ledger has its own). The
rest of the page keeps working while one turn runs. A write must also
come from the page itself (`Origin`), on top of the token.

## Live receipt: an answer from the page

A scratch door (`dvara serve --ask --ask-timeout 300`, `qwen3.8:latest`
through Ollama), two people each asking scribe to *"Write a two-line poem
about rain into <name>-rain.txt"*:

```
$ curl -s -H "Authorization: Bearer $DVARA_TOKEN" localhost:8799/asks
priya write_file NEW FILE priya-rain.txt (2 lines)
owner write_file NEW FILE owner-rain.txt (2 lines)

$ curl -s -H "Authorization: Bearer $PAGE" localhost:8786/api/waiting
{"door": {"reachable": true, "why": null}, "asks": [{"actor": "owner",
 "agent": "scribe", "tool": "write_file", "summary": "NEW FILE owner-rain.txt (2 lines)", …}],
 "holds": []}
```

In a browser, the page showed one card. Priya's question wasn't on it.
**Allow** released the turn:

```
owner reply: True end_turn 'Done — owner-rain.txt now holds the two-line rain poem.'
$ cat owner-rain.txt
Grey fingers tap the window's glass, and the sky leans low to borrow light.
By noon the gutters wear the whole sky's silver, and the rain has gone home.
```

The first try found a bug the Python tests couldn't: a name declared
twice in `page.js`, which stopped the whole script from loading. A test
now runs `node --check` on it.

## What was deliberately not built

* **Answering for somebody else.** A question is addressed to one person
  ([note 02](02-a-question-that-can-wait.md)), and the page doesn't speak
  for anyone else, not even read-only.
* **Editing the actors file.** Above: one place to change the household,
  and it's the file.
* **Inside `dvara serve`.** In-process would answer live questions more
  simply. But it would put a browser-facing page in the process that
  holds the door's token and every conversation's lock, and the page
  would stop whenever the door did.

## Files and schedules

Each person has a folder per agent (`state/work/<person>/<agent>`,
note 25), and their schedules live in Samay. The page shows both, on
the same line as the runs.

**FILES BY NAME FOR EVERYONE, OPENED ONLY FOR YOU.** Every folder is
listed: the name, size and date of each file, newest first, and the
folder's total. An owner whose disk is filling needs to know whose
folder is doing it. Only your own files open on the page, as text. The
walls are `/file`'s from the chat (files.py): a name that leaves the
folder, a name under a dot (`.yantra/`, the agent's bookkeeping) and a
name that isn't there all get the same `no such file`, so a refusal
says nothing about what is out there.

**SCHEDULES IN SAMAY'S WORDS.** The page asks `samay list --json` (the
program from `--samay`, `$DVARA_SAMAY`, or PATH) and shows each
person's schedules as Samay says them: the sentence with its next
times, when it runs next, whether it is paused and why, and how the last
run ended. What a schedule asks the agent to do is the person's words,
so it is on the page only for your own schedules. A schedule whose owner
the door doesn't serve isn't shown. Changing one stays on Samay's page,
which is linked from here. No Samay on the computer is a sentence on the
page, not an error.

Live, two schedules and a folder each for the owner and the guest
(`examples/actors.toml`):

```
$ curl -s -H "Authorization: Bearer …" http://127.0.0.1:8799/api/schedules
{"samay": {"found": true, "why": null, "page": null},
 "schedules": [
  {"person": "owner", "agent": "scribe",
   "sentence": "at 08:00, Mon–Fri -- next: Thu 8 Oct 08:00, Fri 9 Oct 08:00, …",
   "next_at": "2026-10-08T12:00:00+00:00", "last": null,
   "prompt": "add basil to the shopping list"},
  {"person": "guest", "agent": "scribe",
   "sentence": "every 3 hours -- next: Thu 8 Oct 02:05, 05:05, 08:05 …",
   "next_at": "2026-10-08T06:05:29+00:00", "last": null, "prompt": null}]}

$ curl -s … "/api/file?agent=scribe&path=notes/shopping.md"
{"agent": "scribe", "path": "notes/shopping.md", "size": 18,
 "text": "Milk, eggs, basil\n", "binary": false, "truncated": false}

$ curl -s … "/api/file?agent=scribe&path=../../guest/scribe/journal.txt"
{"detail": "no such file"}
```

The guest's `journal.txt` is on the page as a name and 24 bytes. Its
words aren't.

## What is not here yet

* ~~**The owner's approvals and held turns, answered in the browser.**~~
  Above: [answering your own](#answering-your-own-through-the-door).
* ~~**Each person's files and schedules**~~: above, [files and
  schedules](#files-and-schedules).
* ~~**Started by Sarathi** beside the door~~: `sarathi up` starts it, and
  Sarathi's home page links it.
* **A file that isn't text** opens nowhere on the page. `/file NAME` in
  the chat sends it.

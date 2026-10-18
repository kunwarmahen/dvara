# 42 — seeing the work

*Every channel got one thing from a turn: its answer. This note gives
them the work too — the steps as they happen, a skill offered when a job
took several of them, and what the agent can use and has scheduled —
and gives it to all of them the same way.*

## The problem, as you would meet it

Yantra's own page shows a turn as it runs: each tool call as it is made,
the answer word by word, and once it is answered a look behind it that
offers to keep a five-step job as a one-step skill. Talk to the same
package through this service and none of that existed. A page showed
"helper is working…" for a minute and then the whole answer. Telegram
showed "typing", which says nothing about working versus stuck. A job
done every Monday in five steps was done in five steps every Monday,
and "what can you do?" got the model's own guess.

## A turn watched

`deliver(..., watch=)` and `resume(..., watch=)` take a plain function
(`watch.py`). It is called inline, from the loop already reading the
turn's events, with small dicts: `text` (part of the answer, as
written), `using` (the model chose a tool), `step` (it ran, or was
refused).

**THE PERSON SEES WHAT THEIR AGENT DOES, NEVER WHAT IT READ.** A step is
the tool and its own one-line summary — the same words a question about
it would show — and whether it worked. The output stays out: it can be a
whole inbox, a page of somebody's site, or the owner's rule that refused
it. The answer is where the agent says what of it mattered.

**A WATCHER CANNOT COST THE TURN.** One that raises is dropped for the
rest of the turn; the answer still arrives. A turn nobody is at (a
schedule's) is watched by nobody.

Each channel shows it in its own way:

* **The web channel** keeps the running turn in memory and puts it in
  every look as `live`: the answer so far and the steps between. The
  answer line is still the record; a page reloaded mid-turn picks the
  view up again.
* **Telegram shows steps, not words.** A "Working…" message appears at
  the first step, shows the last six, is edited at most every three
  seconds, and is deleted when the answer comes as a message of its own,
  so the phone buzzes for the answer. Word by word would be an edit a
  second, and Telegram limits edits as it limits messages.
* **HTTP streams only when asked.** `POST /message` with
  `"stream": true` answers with one JSON object a line, the events above
  and then `{"kind": "reply", ...}` with exactly what the plain request
  answers. Callers here are programs; one that reads a single JSON body
  keeps getting one.

## Skills offered, and kept on the person's word

For a package with skills, Yantra's learner runs behind every answered
turn the person typed (`learning.py`). The learner counts the learned
skills the turn followed, and if the job is worth it (four steps or more,
Yantra's rule) it writes the recipe and tests it. A find is told to the
person as a notice: the words say `/skills keep ID`, and a channel that
can draw buttons draws Keep and Not now.

**THE LOOK RUNS BEHIND THE ANSWER.** The answer goes out first. The look
is a Run of its own (`looked_for_skill`), on the person's allowance, and
a new message from them stops it.

**NOBODY IS ASKED FROM BEHIND.** A test call that would need a yes is
refused unasked (`gate.NOBODY_ASKED`, a context variable, so it holds
for that look alone in a process serving many people), and the offer
says its test waits. `/skills keep` is the yes: the test runs then, and
asks if it must, while the person is there to answer.

**A KEPT SKILL IS THEIRS ALONE.** One package serves several people. A
skill one of them keeps is saved in their own folder for that agent,
never beside the package and never in the computer's own skills, so one
person's yes never changes the agent for anyone else. Making a recipe
everybody's is the owner's job, done by hand: a folder in the package's
`skills/`.

**AN AGENT SEES TWO KINDS OF SKILL, AND ONLY TWO.** The package's own
(its `skills/` folder, there for everyone who uses it) and the person's
own (what they kept). Never the computer's: `~/.yantra/skills`, where
Yantra's page keeps what the owner learned, and `$YANTRA_SKILLS_PATH`.
Both belong to whoever runs the process, and this process serves
everybody. Every agent here is built with Yantra's `own_skills_only`,
the owner's own chat included; a recipe the owner wants here goes into
the package.

What waits is kept on disk in Yantra's own tray format,
`state/skills/<person>/<agent>.json`, beside the staged files in their
folder, so a restart loses nothing. `YANTRA_LEARN=off` stops the looks;
uses are still counted.

## Tools and schedules, by asking

`/tools` and `/schedules` are not turns: no model, no allowance spent
(`seen.py`).

**TOOLS AS THEY WERE ON YOUR LAST TURN.** What an agent may use depends
on the package, the owner's rules, the person's accounts, the phone and
which servers started, all settled while a turn is built. Starting every
server again just to list them would cost seconds and sign-ins. So each
turn writes down the tools it was given, and `/tools` reads that, grouped
by where each tool came from.

**SEEING, NOT CHANGING.** What a package may use is the owner's to set,
in its files and on Sarathi's settings. A chat word that widened it
would be a way around them. A schedule is paused or removed by asking
the agent, which asks the person first (Samay's tools), so there is one
way to change one. `/schedules` lists theirs from `samay list`.

## The words are the way in

`/skills`, `/skills keep N`, `/skills drop N`, `/skills forget NAME`,
`/learn`, `/tools`, `/schedules`. They are answered the same on Telegram, a page
and HTTP, as `/memory` is. A page's buttons send these words, so there is
one implementation, and three channels can't drift. Telegram's `/` menu
offers them where they mean something: `/skills` for a package with
skills, `/schedules` with Samay on.

## Asked for now

`/learn` is the person saying the job was worth keeping. It starts the
same look, on the conversation so far, with Yantra's `forced`: two steps
are still a recipe once someone has asked for it. The reply is at once
(*"Looking at how I did that…"*); the offer follows as the same notice
with Keep and Not now, and a look that finds nothing says why, since
they asked. A new message stops it as it stops the other looks. Before
any job there is nothing to read, and it says to do the job first.

Live, a scratch web channel with `qwen3.8:latest` and a package with
`read_file`, `write_file` and skills: "Write a file shopping.txt with
three lines… then read it back and tell me how many lines it has" (two
steps, under the four a look needs by itself), then `/learn`:

```
mailer Looking at how I did that, to keep it as a skill. I'll send you
       what I find.
notice I could keep what I just did as a skill, so next time it's one step:
       write-file-and-count-lines — Write a text file with specified
       lines, then read it back to confirm the line count. …
       Test: nothing to run
       Send /skills keep 6d32 to keep it, or /skills drop 6d32.
```

## Receipt

A scratch Dvara on 8798 (`serve --web`, `--yolo`, `qwen3.8:latest`
through Ollama) with Sarathi's home page in front of it on 8797, and a
`helper` package allowed `bash`, `read_file`, `write_file`, `load_skill`,
with `[skills] enabled = true`.

A three-step job, watched through the page's looks:

```
LIVE 0 steps [] using bash
LIVE 1 steps ["bash: $ printf 'name,age\nAisha,34\nBob,41\nChen,29\n' > people.csv"]
LIVE 2 steps ['bash: $ tail -n +2 people.csv | wc -l']
LIVE 3 steps ['bash: $ tail -n +2 people.csv | sort -t, -k2,2nr | head -n 1']  text 'Done. Summary of the three steps:'
LINE agent 'Done. Summary of the three steps: ... **Bob, 41**.'
```

Three steps is under the learner's four, so nothing was offered and no
model call was made. A five-step report of the same file was answered,
and then this arrived as a notice:

```
I could keep what I just did as a skill, so next time it's one step:

csv-people-report — Generates a short Markdown report (headcount, average age,
youngest person) from a two-column name,age CSV. ...
Test: passed

Send /skills keep 080a to keep it, or /skills drop 080a.
```

`dvara runs` shows the look as a run of its own:

```
2026-10-15 03:19  web  owner/helper  looked_for_skill  '(looked at the turn for a skill to keep)'
2026-10-15 03:17  web  owner/helper  end_turn          'Make a small report of people.csv in report.md: '
                  bash -> bash -> bash -> bash -> bash
```

`/skills keep 080a` answered *"Kept csv-people-report. I'll use it the
next time you ask for this — only for you."*, and the skill was in
`work/owner/helper/.yantra/skills/learned/csv-people-report`. Asked for
the same report again, the agent answered *"Used the project's
csv-people-report skill script to regenerate the report"*. `/tools`
listed `bash`, `load_skill`, `read_file` and `write_file` under *built
in*. `/schedules` said *"Schedules aren't switched on here."*, because
this scratch Dvara had no Samay.

## Found by the run

`/skills` listed four skills under the package that the package doesn't
have: `linkedin-top-posts`, `whatsapp-send-message` and two for X. They
were the owner's learned skills, in `~/.yantra/skills`, which Yantra
scanned for any agent built on the computer, so every person's agent
here got them. And a package's own `skills/` reached Yantra through the
environment, so in this one process it would have reached every other
package too. Both are closed by the rule above. The owner's real
`minder`, built both ways:

```
own_skills_only=False: ['linkedin-top-posts', 'whatsapp-send-message', 'x-latest-post', 'x-profile-posts-by-date']
own_skills_only=True: []
```

## What is not here yet

* ~~**A list of past conversations.**~~ `/chats`
  ([notes/45](45-going-back.md)).
* **Telegram word by word.** Steps only, for the rate limit above.
* ~~**A job taught one message at a time.** `/learn` keeps the last
  answer, so a walk-through is learned as its last step.~~ A lesson,
  `/learn start` to `/learn done` ([notes/49](49-a-job-taught-step-by-step.md)).
* ~~**`/learn`**, asking for a skill now~~ -- below, *Asked for now*.
  ~~A kept skill becoming a tool~~ -- the owner's, from the settings
  page ([notes/46](46-a-tool-from-their-skill.md)).
* ~~**Sending a file from a page into the person's folder.**~~ The
  paperclip, and a photo or document to the bot
  ([notes/44](44-what-they-send.md)).

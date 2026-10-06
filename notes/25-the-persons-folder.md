# 25 — the person's folder

*[Note 24](24-a-conversation-nobody-will-continue.md) let a scheduled
run's conversation go once it was over, and found that a file a run
wrote went with it. This note moves the files out of the conversation:
each person has one folder per agent, and every turn they have with that
agent works there.*

## The problem, as you would meet it

You ask minder to check a site every hour and keep a record in
`uptime-log.txt`. A week later you ask, from your phone, what the log
says. Before this note the answer was nothing, for two reasons:

* every run of the schedule wrote a **new** `uptime-log.txt`, because
  each run is a conversation of its own and each conversation had its
  own folder;
* your chat has a folder of its own too, so even one log, kept in one
  place, was somewhere your chat couldn't see.

Samay's direct road never had the first problem: it gives each schedule
one folder, shared by every run. On this road the folder followed the
conversation. Nobody chose that; it fell out of the session key
([note 01](01-the-door.md)).

## One folder per person per agent

**THE PERSON'S, NOT THE CONVERSATION'S.** Every turn a person has with
an agent (a chat message, a scheduled run, a held turn answered the next
morning) works in `state/work/<person>/<agent>/`. Conversations keep
separate *histories* and share *files*, the way sessions do on a desktop.

The reason is who can reach a file. On the direct road the person is the
owner, at the machine, and can open a folder. Here the person is on
Telegram, and **the only way they ever see a file is by asking the agent
in their chat.** A folder per schedule, the smaller fix, would have kept
the log in one place, in a place their chat couldn't read: a record for
the owner and nobody else.

The walls that matter stay where they were. The person is in the path,
so another person never sees the folder; the agent is in the path, so
another agent doesn't either. The escaping that keeps a name from
climbing out of `work/` is unchanged.

**TIDY LETS THE CONVERSATION GO AND KEEPS THE FILES.** Note 24's sweep
now deletes only a finished run's history. There is no per-run folder
any more, and the files in the person's folder are theirs.

## What the agent needs to keep a record

Two things, both in the `minder` example now:

* **File tools.** `read_file` and `write_file`. Reading is never asked
  about. Writing from a chat is a question; in a schedule it runs only
  when the card the person approved listed it. Yantra has no append, so
  minder reads the file and writes it back with the new line.
* **The date.** A record is only as good as its timestamps, and an agent
  that isn't told the date makes one up. The first live run wrote
  `2026-06-15 07:04` on 6 October. `[env] context = "local"` gives the
  agent this machine's clock and time zone, and nothing that leaves the
  machine. Every turn here builds the agent again, so it's read fresh
  each turn.

## Live receipt

`qwen3.8:latest` through Ollama, dvara with `--samay`, priya allowed only
minder. The schedule, made in the chat:

```
when:      every hour -- next: Tue 6 Oct 08:06, 09:06, 10:06 (America/New_York)
tells you: only when there is something new
without asking, it may also use:
  web_fetch
  write_file
does:      Check https://example.com with web_fetch … read the file uptime-log.txt
           in your folder … and write it back with one new line appended at the end …
```

Two `samay run-now`s, each a conversation of its own, then the file on
disk:

```
Tue 6 Oct 07:08  quiet  NOTHING NEW.
Tue 6 Oct 07:10  quiet  NOTHING NEW.
--- the file, on disk:
2026-10-06 07:09 America/New_York example.com UP
2026-10-06 07:10 America/New_York example.com UP
```

Then priya, in a new conversation:

```
priya: What does my uptime log say so far?
minder: Your uptime log has two entries so far, both from today — example.com
        was UP at 07:09 and again at 07:10 (America/New_York). No downtime
        recorded yet.

11:10  priya/minder  'What does my uptime log say so far?'
                     read_file -> mcp__samay__list_schedules -> read_file
11:10  priya/minder  '(A scheduled run -- every hour. Nobody is watchi'
                     web_fetch[ahead] -> read_file -> write_file[ahead]
```

**FOUND ON THE WAY: THE CARD IS WHAT HOLDS.** In the first turn, qwen
called `create_schedule` before priya had said yes, against minder's
prompt. The card still came: on a real channel she would have read it
and could have refused. The test driver approved every card, so the
schedule was made; in the next turn qwen replaced it with a better one.
A prompt asks a model to wait; the gate is what makes it.

The tests (`tests/test_one_folder.py`) write from a scheduled run and
read from a chat, then check that another person and another agent find
nothing. Put back to a folder per conversation, all three fail.

## What was deliberately not built

* **A folder per schedule**, sent by Samay. It's what the direct road
  does, and it's smaller. On this road it keeps a record nobody but the
  owner can read.
* **Moving the old per-conversation folders.** They stay where they
  were. A file an earlier conversation wrote is still on disk, in a
  folder no turn uses now.
* **Guarding two turns writing one file at once.** Yantra's file leases
  guard one agent's tools, and each turn here builds its own agent. A
  scheduled run and a chat writing the same file in the same second
  could lose one write. It takes that exact moment, and it isn't covered.

## What is not here yet

* **Deleting a schedule doesn't touch its record.** The log stays in the
  person's folder, which is usually what they want, and nothing tidies
  it if they don't.
* **The person can't download a file.** They read it through the agent.
  A channel that sends files (Telegram can) would be the next step.

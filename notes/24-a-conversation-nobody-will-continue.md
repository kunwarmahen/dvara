# 24 — a conversation nobody will continue

*[Note 17](17-nobody-wrote-first.md) let a program ask for a turn on a
person's behalf, and Samay asks for one every time a schedule is due.
Each of those turns is a conversation of its own, and before this note
nothing ever let one go.*

## The problem, as you would meet it

Samay gives every run a fresh thread, `samay-<schedule>-<time>`, so the
four-hundredth run of a schedule doesn't carry the last 399 answers in
its prompt. That's the right call for the run. It leaves two things
behind every time:

* the conversation's checkpoints, in `sessions.sqlite3`;
* its workspace folder, `work/<person>/<agent>/samay-…`.

Nothing writes to that thread again. A check every two hours is twelve
of each a day, and after a few months the owner has thousands of
conversations nobody can reach. Each one is small. It's a slow leak,
and on a service meant to be left running for months it gets bigger
the longer things go right.

## Only a thread nobody started

`Service.tidy` lets these go. Which threads it may touch is the whole
design, because a sweep that reached into somebody's own chat would be
far worse than the leak.

**THE FIRST RUN DECIDES.** The ledger now records whether each turn was
`unattended`. A thread whose *first* turn was unattended was started by a
program, and that thread is a candidate. A thread a person started never
is, even if a program later wrote into it; a morning summary posted into
someone's Telegram thread doesn't make that conversation disposable. And
a person answering a question a scheduled run held doesn't make the run's
thread theirs.

**NEVER WHILE IT COULD GO ON.** A thread with a question still waiting
for its person (a hold, [note 16](16-kept-for-when-you-are-back.md)) is
skipped, and so is one with a turn running on it right now. Both are
looked at again next time.

**KEPT A WHILE FIRST.** A thread goes a week after its last turn
(`--keep-unattended DAYS`), so an owner who wants to see what a run left
in its folder still can. `0` lets it go at the next chance.

**THE RECORD STAYS.** Only the conversation and the workspace go. Every
run stays in the ledger: `dvara runs` still lists it, `dvara case` can
still turn it into an eval case, and a day's spending still counts it.
The ledger also notes which threads were tidied, so none is looked at
twice.

## When it runs

After every unattended turn. That's when there is something new to
tidy, so nobody has to remember a cron job, and a service that runs no
schedules never sweeps anything. A sweep that fails is a line for the
owner on stderr. The turn's reply still goes out.

Deleting a conversation needed a verb Yantra didn't have. Its
`SessionStore` is append-only by design, and that promise is about a
conversation that may continue: no save rewrites what came before.
`SessionStore.forget(session_id)` drops a whole session and nothing
else. It's Yantra's own feature, argued there, for any host that knows
a conversation is over.

## Live receipt

`dvara serve --keep-unattended 0` on `gemma4:12b` through Ollama, three
scheduled-style turns over HTTP and one from a person:

```
end_turn 'Good morning.'
end_turn 'Good morning.'
end_turn 'Good morning.'
end_turn 'Welcome, how may I help you?'
-- sessions kept:
owner/greeter/samay-demo-1003
owner/greeter/telegram-42
-- workspaces:
samay-demo-1003
telegram-42
-- tidied:
samay-demo-1001|2026-10-06T03:03:00+00:00
samay-demo-1002|2026-10-06T03:03:03+00:00
-- runs:
2026-10-06 03:03  owner/greeter  end_turn  $0.0000  'hello'
2026-10-06 03:03  owner/greeter  end_turn  $0.0000  '(A scheduled run) Say good morning.'
2026-10-06 03:02  owner/greeter  end_turn  $0.0000  '(A scheduled run) Say good morning.'
2026-10-06 03:02  owner/greeter  end_turn  $0.0000  '(A scheduled run) Say good morning.'
```

The first two runs' threads are gone. The third waits for the next turn,
because its own turn was running when the sweep happened. The person's
thread is untouched, and all four runs are in the ledger.

The tests (`tests/test_tidy.py`) pin the parts that must stay: a
person's thread a program wrote into, a held question, and the runs.

## What was deliberately not built

* **Guessing from the thread's name.** `samay-` is Samay's convention,
  not this service's, and another program could pick any name. The
  ledger knows who started a thread; a prefix would only be a guess.
* **A `once` flag on the request,** so the caller says the thread is
  disposable. It would tidy right away, but it needs every caller to
  remember, and an older Samay never sends it. The ledger already knew.
* **Pruning the ledger.** It's the audit, and the daily allowance is
  summed from it. A year of runs is a few megabytes.

## What is not here yet

* **A file a scheduled run writes lives in that run's own folder.** A
  schedule that "appends a line to log.txt every six hours" writes a
  different `log.txt` each time, and after the keep window each one goes
  with its thread. What a person wants kept from a run should reach them
  (a notice), or go somewhere that belongs to the schedule rather than
  to one run. Neither exists yet.

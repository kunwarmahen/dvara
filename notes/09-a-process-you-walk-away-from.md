# 09 — a process you walk away from

*Eight notes built a service. This one is about the difference between a
service and a program you run: three things that were fine while somebody
was watching the terminal and stopped being fine the day the terminal was
somewhere else. All three were on the "not here yet" list, and one of
them [note 07](07-four-thousand-and-ninety-six.md) created.*

## The one that would have been fixed wrongly

Note 07 left this bullet:

> **`dvara serve` and `dvara telegram` are two processes over one state
> directory.** Two SQLite writers, which works until it does not. Running
> both is not yet a supported thing to do, and nothing stops you.

Which is a true description of a visible symptom. Run both, send two
messages at once, and the second turn stalls for five seconds and dies:

```
sqlite3.OperationalError: database is locked
```

There is an obvious fix, it is three lines long, and it is the worst
available outcome. Switch the journal to WAL, raise the busy timeout, and
both processes carry on — having silenced the one signal that anything
was wrong.

**THE SQLITE ERROR WAS THE SYMPTOM, NOT THE DISEASE.** A SERVICE IS A
PROCESS, and the things that make this one correct do not live in the
state directory at all:

* **The per-session lock.** `Service` holds one `asyncio.Lock` per
  `(actor, agent, thread)` so two messages in one conversation serialize
  ([note 01](01-the-door.md)). Two processes have two sets of locks and
  neither knows about the other's — so both rehydrate the same
  checkpoint, both run a turn against it, and both save. `SessionStore`
  appends versions, so **nothing raises**: one of those turns simply is
  not in the history any more. Found weeks later, by somebody wondering
  why their agent forgot something.
* **The ask desk.** Questions live in memory and die with the process
  ([note 02](02-a-question-that-can-wait.md)), so a question raised in
  the bot's process is invisible to `GET /asks` in the served one. A
  person asked on Telegram, with nothing to answer over HTTP — which is
  exactly the split queue [note 05](05-one-person-two-channels.md)
  refused to let one actor have.

Neither is a locking problem and neither has a short fix. So the
directory is **claimed**, and a second process says so and stops.

```
$ dvara --state ~/dvara/state say --actor owner --agent greeter "hello"
error: another dvara is already using /home/me/dvara/state (pid 3641987
running dvara serve). A service is a PROCESS, not a directory: the lock
that serializes two messages in one conversation, and the questions
waiting for you to answer them, both live in memory and cannot be shared.
Stop that one, give this one its own --state, or run both jobs in one
process (dvara serve --telegram AGENT).
```

**`fcntl.flock`, not a pid file, because THE KERNEL RELEASES IT.** A
service killed with `SIGKILL` runs no handler and writes no tombstone;
with a lock file you are then writing the "is pid 4032 still the same
process?" heuristic, and getting it wrong after a reboot recycles the
number. The pid is written into the file anyway — not to decide anything,
only because it is what the message needs.

What it does not cover, said rather than implied: two machines over one
network filesystem, where `flock` is advisory at best. Clustering was
never in this service and this does not pretend otherwise.

### A refusal needs a way out

Forbidding both processes takes away something somebody wanted — a bot
*and* an HTTP surface — so the note has to give it back in the only
arrangement that is correct:

```bash
dvara serve --telegram researcher
```

One process, one event loop, one ask desk, one set of conversation locks.
The bot's long poll is started by the server's own lifespan and cancelled
when it shuts down. This is not a convenience; given the paragraph above,
it is the only way to have both.

### Who claims, and who does not

**A COMMAND THAT RUNS A TURN CLAIMS THE DIRECTORY; ONE THAT ONLY READS IT
DOES NOT.** `say`, `serve` and `telegram` take it. `runs`, `case` and
`agents` do not:

```
$ dvara runs                      # while the bot is answering somebody
2026-09-18 01:19  owner/scribe  end_turn  $0.0007  'write a haiku…'
```

Looking at your own ledger while the service runs is the most ordinary
thing an owner does, and a service whose history you cannot read while it
is up is a worse service than one that occasionally contends on SQLite.

And **`Service` claims nothing.** A host that has composed this into
their own process is not a second dvara, and a library that took a lock
on import is a library nobody can compose. The claim belongs to the
*command*, which is the thing that knows it is a whole service.

### The bug the claim had, for about ten minutes

Worth recording because it is the kind that does not announce itself. The
first version read:

```python
Claim(Path(args.state)).take(f"dvara {args.command}")
```

Nothing holds the `Claim`. CPython collects it immediately, collecting it
closes the file, and **closing the file releases the lock** — so the
service runs on believing it holds a claim it gave away microseconds
after taking it. What caught it was `filterwarnings = ["error"]` in
`pyproject.toml` turning an unclosed-file `ResourceWarning` into a test
failure, which is the entire reason that line is there.

The claim is a local in `main` now, alive for exactly as long as the
command is.

## A guest added at a party

The second bullet, carried since note 05 and made real by note 07:

> **A channel identity cannot be added without a restart.** The roster
> and its reverse index are read once at startup. Fine for a file one
> person edits; a papercut the first time a guest is added at a party.

It was a papercut when the only way in was your own terminal. It is a
different thing when somebody is standing in front of you holding a phone
with your bot's @handle on it and the answer is "hold on, I have to
restart the service".

So an `ActorBook` remembers the file it came from and that file's stamp,
and `Service.refresh` rereads it when it changes — two `stat` calls
against a model round trip. The same for `policy.toml`, including one
that did not exist at startup and does now.

**A BAD FILE KEEPS THE LAST GOOD ONE.** This is the decision, and it is
the reason the reload lives in the service rather than in either parser.
An owner adding a guest at midnight who leaves a bracket off is one typo
away from a service that refuses everybody — including themselves,
including the person who would fix it. So a reread that raises is a
complaint on the way past and nothing else:

```
/home/me/dvara/actors.toml: Expected ']' at the end of a table
declaration (at line 3, column 13)
  -- keeping the roster already loaded; nothing changed for anybody
     talking right now
```

The opposite reading is right at **startup**, and that is what happens
there: a broken file is exit 2 and nothing serves. The difference between
the two answers is whether there is already something to lose.

The complaint is made once per distinct problem, not once per turn. A
file that has stopped parsing has stopped parsing for every turn after
it, and a service that printed the same paragraph a hundred times an hour
is a service whose log nobody reads.

A file that has been **deleted** gets the same treatment, and that is
deliberate rather than incidental: some editors save by truncating and
rewriting, so a file that is briefly gone or briefly empty is something
an owner does by accident. Carrying on with what is loaded is correct for
the accident *and* for the deliberate deletion.

The parsers themselves decide none of this. `reread()` returns a new book
or raises; what to do about a file that has stopped parsing is policy,
and policy belongs to whoever owns the conversation.

## A question you can walk away from

The smallest of the three, carried since note 02:

> **A blocked keyboard survives its own deadline.** When a terminal
> question times out, the prompt is still sitting in a thread waiting on
> `stdin`, and the process will not exit until somebody presses enter.
> Harmless where it happens — a person is standing right there — and it
> would need a cancellable read to fix properly.

`asyncio.to_thread(input, ...)` parks a worker inside a blocking read.
The default executor's threads are not daemons and the interpreter joins
them at exit — so after a question times out, the process sits there
wanting a keypress that nobody now has any reason to give it.

The fix is not a bigger hammer on the thread. It is not using one:

```python
loop.add_reader(fileno, readable)
```

The descriptor goes to the event loop, which is what an event loop is
for. Cancellation removes the reader and returns, leaving nothing behind.
The tty is still in canonical mode, so it does the line editing and this
gets a whole line on Enter, exactly as `input` did. Where stdin cannot be
watched — a closed descriptor, a platform without `add_reader` — it falls
back to the thread, because a front end that is the *only* place a
question could go must not stop asking.

The test asserts the **thread count**, because that is the bug. "The
answer was a refusal" passed before this was fixed too.

## What it looks like

A served dvara on one state directory, and a second one trying to join
it:

```
$ DVARA_TOKEN=… dvara --state ./state serve --port 8771
dvara · 2 agent(s) · 1 actor(s) · http://127.0.0.1:8771

$ dvara --state ./state say --actor owner --agent greeter "hello"
error: another dvara is already using ./state (pid 3641987 running dvara
serve). A service is a PROCESS, not a directory: …

$ dvara --state ./state runs
no runs recorded yet

$ cat state/dvara.lock
pid 3641987
dvara serve
since 2026-09-18T01:40:40+00:00
```

Refused for the one that would have run a turn, allowed for the one that
only reads.

Then, against that same process, a guest who is not in the file —
`qwen3.8-64k:latest` on Ollama throughout:

```
$ curl -s …/message -d '{"actor":"guest", …, "text":"who are you, in one sentence?"}'
  ok=False · you are not on this service's list of people
```

Add them, with nothing restarted:

```toml
[actor.guest]
agents          = ["greeter"]
max_usd_per_day = 0.05
receipt         = "remaining"
```

```
  ok=True · I'm the doorkeeper's greeter, here to say hello and point you
            in the right direction.
  receipt: $0.0500 left today
```

The allowance and the receipt came with them, because the whole entry is
one edit to one file. And then the typo — a `[actor.guest` with no
closing bracket, written while that guest is mid-conversation:

```
  ok=True · Yep, still here—what can I help you with?
```

They never noticed. The owner's terminal did:

```
reloaded ./actors.toml (2 actor(s))
./actors.toml: Expected ']' at the end of a table declaration (at line 3,
column 13)
  -- keeping the roster already loaded; nothing changed for anybody
     talking right now
```

## What is deliberately not here

* **WAL, or any other way of making two writers work.** Argued at the
  top. It would have hidden a split ask desk and a split session lock
  behind a working database.
* **A lock that waits.** `flock` with `LOCK_NB`, so a second dvara is
  refused now rather than starting some indeterminate time later when the
  first one stops. A service that eventually starts is harder to reason
  about than one that does not.
* **SIGHUP to reload.** The mtime check costs two `stat` calls per turn
  and needs nobody to know a pid. A signal would be the Unix answer and
  it is a worse one here: the owner editing the file is the event, and
  making them announce it is a second step to forget.
* **Reloading the agent ROOT.** Packages are already reread per turn — an
  agent built fresh each time picks up an edited `agent.toml` — and
  whether that is desirable is §11.2, still open and still not this
  note's to settle.
* **A content hash instead of (mtime, size).** The honest version, and it
  costs a read of the whole file every turn to catch an edit that changed
  nothing, which is a case where the reload is a no-op anyway.
* **Claiming the agent root.** It is read, never written, and two
  services sharing a directory of packages is a reasonable thing to do.

## What is not here yet

* **`flock` on a network filesystem does not protect anything.** A state
  directory on NFS is outside what this can see, and nothing checks for
  it — a filesystem-type check that guessed wrong would be worse than the
  honest silence.
* **A reload cannot remove somebody mid-conversation.** It can, in the
  roster — but a turn already running holds the `Actor` it started with,
  so revoking access takes effect on their next message rather than on
  this one. Right for the turn in flight and worth knowing.
* **Nothing reloads the ask timeout, the provider or the model.** Those
  are command-line flags, and a flag is a thing you restart for.
* **An approval still cannot be pinned to the call it approved**,
  unchanged from [note 08](08-what-the-turn-actually-did.md).
* **Nothing counts what the rules are doing**, unchanged from
  [note 03](03-standing-answers.md).
* ~~**Locks are still never evicted**~~ — shipped in [note 11](11-only-while-somebody-is-waiting.md); unchanged from notes 01–08 — and now
  slightly funnier, since this note is about a process that stays up for
  months.

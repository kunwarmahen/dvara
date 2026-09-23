# 11 — only while somebody is waiting

*Every note from 01 to 10 ended with the same bullet: locks are never
evicted. It sat there because the fix was small and the way to get it
wrong was silent. This note is the small fix, and most of it is about
the silent way.*

## What a lock is doing here

Two messages can arrive in the same conversation at once — you send a
question, then a correction before the answer comes back. If both turns
ran together, each would load the conversation as it stood, each would
add its own exchange, and each would save. The second save wins. Nothing
errors; one of your two messages is simply gone from the history, and
you find out days later when the agent has no idea what you told it.

So `Service` keeps one lock per conversation — per `(actor, agent,
thread)` — and a turn holds it from start to finish. The second message
waits its turn. [Note 01](01-the-door.md) built that, and it has held up
through every note since.

The Telegram bot has the same thing at a smaller scale
([note 07](07-four-thousand-and-ninety-six.md)): one lock per chat, so
the four parts of a split reply go out in order instead of shuffled in
with another reply's parts.

## The leak

Both tables made a lock the first time they saw a key and kept it
forever. A few hundred bytes each. For a process you start, poke and
stop, that is nothing. For the process [note 09](09-a-process-you-walk-away-from.md)
was about — the one you start and walk away from for months — it is one
entry for every conversation anybody has ever had with it, in memory,
for as long as it runs. The Telegram pacer also kept a "next send not
before" timestamp per chat, forever, for the same reason.

## The obvious fix is wrong

"Drop the lock when the turn that held it finishes" sounds right, and it
reintroduces exactly the bug the lock exists to prevent:

1. Turn **A** holds the lock for conversation `t`.
2. Turn **B** arrives, finds A's lock, and waits on it.
3. A finishes. Nobody *holds* the lock now, so it is dropped from the
   table. B has been woken but has not run yet.
4. Turn **C** arrives, looks up `t`, finds nothing, makes a brand new
   lock, and takes it straight away.
5. B runs, holding the *old* lock. B and C are now both inside `t`.

That is two turns in one conversation, and one lost message. It needs a
third message to arrive in a window a few microseconds wide, which means
no test written by hand finds it, and a busy group chat eventually does.

## The fix: count the waiters too

**AN ENTRY LIVES WHILE ANYBODY HOLDS IT OR WAITS FOR IT.** Every caller
adds one to the entry's count *before* it starts waiting and takes one
off when it leaves. The entry goes only when the count reaches zero. In
the story above, B's count is already on the entry at step 3, so the
entry stays, and C at step 4 finds the lock B is waiting on and queues
behind it.

**THE EVENT LOOP IS THE MUTEX FOR THE TABLE.** Checking the count and
deleting the entry happen with no `await` in between, and in asyncio
nothing else can run until you `await`. So the count needs no lock of
its own. That is also why `KeyedLocks` is not safe to share between
threads, and nothing in dvara does.

**A CANCELLED WAITER GIVES ITS COUNT BACK.** A turn that is cancelled
while it waits in the queue — at shutdown, say — leaves through the same
`finally` as one that finished. Otherwise one cancellation would pin its
conversation's entry for the life of the process, and the leak would be
back, one entry at a time.

That is the whole of [`locks.py`](../src/dvara/locks.py): a dict, a
counter per entry, and a context manager. `Service` and the Telegram
pacer both use it. The pacer's timestamps are simpler still: a timestamp
that is already in the past does exactly what no timestamp does (send
now), so each send clears out the ones that have passed.

One side effect is worth having. A lock is now made fresh for each burst
of use, so no lock outlives the event loop it was first used on — which
the old table could not promise to a caller that runs each message under
its own `asyncio.run`.

## How the test knows

The test that matters is the five-step story above, acted out: hold the
lock, queue B, release, check the entry is still there, send C, and
check the order came out `B in, B out, C in, C out`. To be sure the test
can actually tell, it was run against the obvious-but-wrong version —
counting only after the lock is acquired — and that version fails it,
and only it. The other eight tests pass either way, which is the point:
the table emptying is easy, and the table not emptying *too soon* is the
test to trust.

## Receipt

The real service, against `qwen3.8:latest` on Ollama. Six conversations
at once, plus a second message into `t0` while its first is still
running, and a watcher sampling the table every 50 ms:

```
 t0  0
 t1  1
 t2  2
 t3  3
 t4  4
 t5  5
 t0  100
locks held at the busiest moment: 6
locks held after every turn ended: 0
```

Seven messages, six conversations, six locks at the peak — the second
`t0` message waited on the first one's lock rather than getting its own,
and answered after it. When the last turn ended, the table was empty.

## Deliberately not built

* **A time-to-live.** "Drop locks idle for ten minutes" is a timer, a
  sweep, and an approximation of what the count already knows exactly.
  Eviction on the last release is precise and costs nothing while idle.
* **A cap on the table.** The table is now as big as the number of
  conversations *in flight*, which is bounded by what the model provider
  can serve at once. A cap would need a policy for what to refuse, and
  there is nothing here that wants refusing.

## The other tables, checked

Every other dict the service keeps in memory was read for the same
leak. None has it: the ask desk forgets a question in a `finally`,
whether it was answered, timed out or abandoned; its routes are keyed by
channel *kind* (`telegram`, `terminal`), and providers by provider name
— a handful each, not one per conversation; and the channel-to-actor map
is rebuilt from the actors file, so it is exactly as big as that file.

## What is not here yet

* **A question answered on one channel still sits on the others**,
  unchanged from [note 07](07-four-thousand-and-ninety-six.md).
* **A crash loses the message that was in flight**, unchanged from
  [note 07](07-four-thousand-and-ninety-six.md).

Continues [note 01](01-the-door.md), which named the problem, and
[note 07](07-four-thousand-and-ninety-six.md), which added the second
table.

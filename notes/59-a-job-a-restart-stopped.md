# 59 — A job a restart stopped, offered back

Someone asks on Telegram for the blue kettle to go back. The agent is six
taps into the return when the owner runs `sarathi down && sarathi up`.
Before this note, they saw *Working…*, then nothing. The return form sat
half filled. The conversation was saved as it had been before their
message, so even the request was gone.

Yantra now saves every step of a turn and can carry a stopped one on
(its note 144). This note is Dvara's part: when to save, who to tell, and
whose decision it is.

## Every step, under the conversation's own key

`_run_turn` sets the agent's `on_step` to save into the session store,
under the same key as everything else (`actor/agent/thread`, note 03).
The turn's start, every batch of tools and its end each add a version.
The store is append-only, so a stopped turn's last version is the job
as far as it got. Finished schedule threads are let go after a week
(`tidy`), and that already covers the extra versions.

A shutdown cancels the turns in flight. Yantra treats a cancelled task
as a shutdown, so the turn stays open. Dvara's own `finally` save
then writes it with its `unfinished` block. The same goes for a turn
whose HTTP caller hung up mid-way: it too stopped part way through.

## Told once, as the door starts

`Service.chores` begins with `tell_stopped`. `SessionStore.unfinished()`
lists every session whose newest version is a turn still going. Each one
in a person's chat gets one message on their channels:

```
I stopped part way through "return the blue kettle" (6 steps done:
phone_open_app, phone_tap) when I was restarted (minder). Send /carry to
carry on from there -- I'll look again before I do anything. Anything
else leaves it.
```

**Once.** `carry-told.json` keeps each key with the time its job was
saved. A door restarted three times in an evening says it once. A job
stopped again later, at a new save time, is told again.

**Not a schedule's, not a watch's.** A `samay-…` or `prahari-…` thread
belongs to the program that started it. Samay asks for its own
carry-on (below), and a person told about a run they never started
would only be confused.

## Theirs to decide

`/carry` in the same conversation carries it on: `deliver` finds the
stopped job, and the Run is recorded under the job's own words rather
than `/carry`. Yantra's `carry_on` first tells the model it stopped and
that the screen may have moved, so it looks before it acts. The gate
asks for what it would have asked for.

**Nothing carries on by itself.** An hour later the kettle may have been
returned some other way. Anything else the person sends starts a turn
normally and leaves the job. `/carry` with nothing stopped answers
*"Nothing stopped part way here."* and asks no model.

### One press on Telegram

On a phone, typing `/carry` is the step people get wrong, the same
lesson as `/connect` ([note 20](20-signing-in-from-the-chat.md)). So on Telegram the message has a
**Carry on** button under it, and a press is `/carry` SENT AS IF TYPED,
by whoever pressed: the same turn, the same refusals, and, with nothing
stopped any more, the same *"Nothing stopped part way here."* The
button comes off once pressed.

The notice names its job (`extra["carry"]`: the agent and the
conversation). A Telegram bot answers for one agent, and its `/carry`
reaches only that agent's conversation in that chat, so **THE BUTTON
IS DRAWN ONLY WHERE IT WORKS**. A job stopped in the home page's chat,
or another agent's, is told in words alone: a button that answers
"nothing stopped" would be worse than none. The press carries no id:
the bot and the chat already say whose job it is.

There is no **Leave it** button. Anything else the person sends leaves
the job, and a button for not doing something is a second way to say
nothing.

## Samay's road

`POST /message` takes `carry_on: true` beside `unattended: true`. Samay
names each run's thread after the run (`samay-<schedule>-<run>`), so
after a restart it can ask for the same one. With no stopped turn there,
the answer is `stop_reason: "nothing"` and nothing runs. Samay then
leaves its run `interrupted`, as before (Samay's note 10).

## Receipt

`qwen3.8:latest` on Ollama, a scratch state folder, a `reader` agent and
three files (17, 25, 8). `dvara say` asked it to read them one at a time
and add them up, and was killed with `SIGKILL` once the first step was
saved:

```
killed with 1 step(s) saved
owner/reader/chat 1
```

Then, in the same conversation:

```
$ dvara say --actor owner --agent reader --thread chat "/carry"
Reading them in order: a.txt = 17, b.txt = 25, c.txt = 8.
**The sum is 50.**
[end_turn · $0.0000 · 6809in/134out · run ce74531ce0de]

$ dvara runs
2026-10-23 15:38  cli  owner/reader  end_turn  $0.0000  'Read a.txt, then b.txt, ...'
                  read_file -> read_file
```

The carried-on run read b and c, not a again. The session's newest
version is finished now.

The Telegram button, on the house's own bot after a real restart: the
notice came with **Carry on** under it, one press picked the job up where
it stopped, and the button came off.

## What was deliberately not built

* ~~**A Carry on button on Telegram.**~~ Built: *One press on
  Telegram*, above. Was: `/carry` is in the `/` menu. The notice now
  names its job, so the button is drawn only where it works.
* **Telling the owner about everyone's stopped jobs.** Each job is its
  person's. The owner sees the runs in `dvara runs` and on the page as
  ever.

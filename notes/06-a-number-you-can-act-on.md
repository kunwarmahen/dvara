# 06 — a number you can act on, or none at all

*Every turn this service runs already knows what it cost. The `Run` row
has carried `cost_usd` since [note 01](01-the-door.md) and the reply
object has carried it since the HTTP surface existed. What none of it
ever decided is whether the person who asked the question should be told
— which is a decision you cannot defer past the day you write a bot,
because a chat reply has a bottom and something either goes there or does
not.*

## The problem, as you hit it

It looks like a checkbox. The owner wants to see what their agents are
costing them; a person in a chat does not want `$0.0031` under every
answer they receive. So: a flag in the actors file, on for you, off for
everybody else.

Then you write the flag and notice it does not fit either of them.

The owner's number is what the turn **cost** — they are watching a bill
accumulate, and each turn is a line on it. But a guest has no bill. A
guest has an *allowance*, and the only figure they can do anything with
is what is **left** of it: "can I ask the follow-up now, or have I used
today up?" Told `$0.0031`, they would have to know their ceiling, know
what they had spent before, and subtract — three facts they do not have
to produce one they wanted.

Yantra reached the same conclusion from the other end, building a budget
bar for its browser (its note 43):

> **What is left, not what is spent.** `$0.07 left` is the figure
> somebody acts on — "do I ask the follow-up now or start a new turn?" —
> and `$0.43 spent` is the figure they would then have to do arithmetic
> on.

TWO READERS WANT TWO DIFFERENT NUMBERS, WHICH IS WHY THIS IS NOT A FLAG.
A boolean can offer one of them, and the one it would offer is the one a
guest cannot use.

```toml
[actor.mahen]
receipt = "cost"            # $0.0013

[actor.guest]
max_usd_per_day = 0.05
receipt = "remaining"       # $0.0489 left today
```

Absent is the third option and the default, because most people in a chat
did not ask to be shown a meter, and a footer under every answer is a line
everybody reads forever.

`receipt = "remaining"` on somebody with no `max_usd_per_day` is refused
at load rather than quietly rendering nothing. There is no allowance for
anything to remain of, and an owner who wrote that meant something they
have not said:

```
error: actors.toml: [actor.guest] asks for what is left of a daily
allowance and has no max_usd_per_day to have anything left of; set one,
or use receipt = "cost"
```

## Beside the answer, never inside it

`Reply.receipt` is its own field. Appending it to `Reply.text` would have
been one line shorter and wrong twice over.

**`run.reply` is the archive of what the agent SAID.** It is what
`dvara runs` prints and what somebody reads back in six months asking why
a turn answered badly — which [note 04](04-the-failure-loop.md) argued is
the failure only a person can see. A footer stored in there is a sentence
the agent did not say, in the one record kept precisely so that what was
said can be examined later.

**And a separator is not this service's to choose.** Telegram wants
italics on a new line; a terminal wants a plain line; something else
wants a second message entirely. Picking one here picks it for every
channel there will ever be.

The rendered line rides *beside* the raw number rather than instead of
it, which is Yantra's note 43 again — the browser gets fields and draws a
bar, the terminal gets the sentence and prints it. Parsing the first back
out of the second is how the two drift apart.

```
POST /message -> {"text": "...", "cost_usd": 0.0013, "receipt": "$0.0013"}
```

## A service that bills nothing says nothing about money

Half this project's readers run Ollama, where every turn costs $0.0000
and no allowance can ever move. A receipt there is a meter that is not
metering — a line under every answer, forever, telling its reader
something they already know.

So under a free provider both kinds render nothing at all. **This
diverges from Yantra's note 43**, which draws that state as an empty bar
labelled `free` rather than hiding it, and the divergence is the point
rather than an oversight: a bar is ambient and costs nothing to keep on
screen, where a chat footer is a line appended to every message anybody
ever receives. Same fact, different medium, different answer.

The opposite case is the one where silence would be dangerous:

```python
if cost_usd is None:
    return "unpriced"
```

A hosted model with no list price is not free, it is unknown, and an
owner who asked for a receipt asked to *watch a bill*. `$0.00` there is a
guess wearing a number's clothes — the same refusal to guess that
`_cost` makes one layer down, and that Yantra's `bills_nothing` exists to
make possible.

## The receipt is the number the next turn is gated on

The order of two lines decides whether this feature is honest.

What is left of an allowance is computed at the *start* of a turn, by
`_ceiling`, because that is when it is needed to build the budget. Using
that same figure in the receipt would show a person what they had before
the answer they are reading — stale on arrival, and by exactly the amount
they just spent.

So the receipt is built *after* `runs.record(run)`, and it asks the
ledger again rather than subtracting in memory:

```python
remaining = money.remaining_today(
    who.max_usd_per_day,
    self.runs.spent_since(who.id, money.day_start()))
```

One more query, and what it buys is that the number a person READS is the
same number the next turn will be JUDGED against. A meter that can
disagree with the gate behind it is worse than no meter — it is a
promise, made in dollars, that something else is free to break. An
unpriced turn contributes nothing to either figure, so the two cannot
drift apart there either.

## What it looks like

Against `qwen3.8-64k:latest` on Ollama, reached through the OpenAI-
compatible endpoint so that a price exists to be charged (the rate is a
stand-in; the tokens, the turns and the arithmetic are real):

```
$ dvara say --actor guest --agent greeter "who are you, in one sentence?"
I'm the greeter at the door—here to welcome you and point you in the right direction.
$0.0489 left today

$ dvara say --actor guest --agent greeter "and what can you help with?"
I can answer simple questions, give directions, or let you know what I *can't* do if it requires tools or files.
$0.0474 left today

$ dvara say --actor mahen --agent greeter "who are you, in one sentence?"
I'm the greeter at the door, here to help you find your way in or turn you away politely.
$0.0013
```

The allowance moves, and it moves by what the turn actually cost. The
same commands against `--provider ollama`, where nothing is billed:

```
$ dvara say --actor mahen --agent greeter "who are you, in one sentence?"
I'm the greeter at the door, here to say hello and help you find your way in.
```

Nothing under it. The roster still says `receipt = "cost"`.

`say` prints the receipt where a chat would put it, under the answer and
above the operator's own `[end_turn · $0.0013 · …]` banner, for the
reason `--as` exists ([note 05](05-one-person-two-channels.md)): an owner
should be able to see what their guest will see without standing up a bot
to find out.

## What is deliberately not here

* **A per-turn token count.** `83in/56out` is on the operator's banner
  and does not belong under an answer. Nobody in a chat has ever made a
  decision with it.
* **A receipt on a refused turn.** Nothing ran and nothing was spent;
  a refusal already says why, and "$0.0000" under it would be the
  service answering a question nobody asked in the middle of saying no.
* **Per-agent or per-channel receipts.** The key is on the actor, because
  it is a fact about what a PERSON wants to see. An owner who wants cost
  in one chat and silence in another is asking for a preference, and
  preferences want somewhere to live that is not the security file.
* **A running total in the receipt.** "$0.0013 (today: $0.0412)" is two
  numbers where the whole argument was about choosing one.

## What is not here yet

* **No way to ask for what it cost AND what is left.** Two numbers is a
  third kind, and nobody has wanted it yet; the guest has an allowance
  and the owner has a bill, and neither has both.
* **Nothing shows a receipt mid-turn.** A long turn that spends most of
  an allowance says nothing until it finishes, where Yantra's bar moves
  on every tool result. A channel is turn-shaped and this is the cost of
  that, unchanged from [note 01](01-the-door.md).
* **An unpriced turn is invisible to the allowance**, not just to the
  receipt: `spent_since` sums what it can price. A model nobody can price
  is therefore free of its ceiling, which is a gap in the meter rather
  than in this line under it.
* **Locks are still never evicted**, unchanged from notes 01–05.

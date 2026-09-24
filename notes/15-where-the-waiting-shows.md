# 15 — where the waiting shows

*[Note 14](14-a-days-worth-of-being-asked.md) gave each person a daily
allowance of waiting and wrote every turn's `waited_seconds` into the
ledger. Nobody could see either one: not the person, whose receipt line
only knew about money, and not the owner, whose `dvara runs` printed
everything about a turn except how long somebody was kept on the hook.*

## Under the answer

`receipt = "remaining"` already put what is left of today's money under
each answer ([note 06](06-a-number-you-can-act-on.md)). It now adds what
is left of today's waiting, from the same ledger, read at the same
moment:

```
Nobody answered in time — the call was denied by timeout, not by an explicit refusal. ...
20s of waiting left today
```

**ONLY UNDER A TURN THAT WAITED.** Every answer spends money, so the
money figure earns its line every time. Most turns ask nobody anything,
and "4m 40s of waiting left" under each of them would be a line about
something that did not happen. So the waiting half appears only when
this turn kept the person waiting.

**A FREE ROAD SILENCES THE MONEY, NOT THE WAITING.** Under a local model
the money half of the receipt says nothing, because nothing is billed
([note 06](06-a-number-you-can-act-on.md)). Waiting on a person costs
the same on every road, so that half still shows. The receipt above is a
local run.

**`"remaining"` MAY NAME EITHER ALLOWANCE.** It used to require a
`max_usd_per_day`. A person with only `max_wait_per_day` has something
left too, so either one now satisfies it. With neither, it is still an
error at load.

## In the ledger

`dvara runs` marks a turn that kept somebody waiting:

```
2026-09-24 15:38  owner/scribe  end_turn         $0.0000  'Write the word hello into hello.txt. Try once on'
                  write_file(refused)[asked]  [waited 10s]
```

Only when it is at least half a second. A question answered instantly
is not the turn an owner is scanning for.

## What was deliberately not built

**No waiting total in `dvara runs`.** The listing is per turn, like the
money column. A day's sum is what the gate reads, and a separate
summary command would be a second place to keep that arithmetic.

## Receipt

A fresh state directory, `scribe`, `qwen3.8:latest`, a 10-second ask
timeout, and a day of 30 seconds:

```toml
[actor.owner]
permissions      = "ask"
max_wait_per_day = 30
receipt          = "remaining"
```

```
$ sleep 90 | dvara --ask --ask-timeout 10 ... say --actor owner --agent scribe "Write the word hello into hello.txt. Try once only."

scribe wants to run write_file:
  NEW FILE hello.txt (1 lines)
approve? [y/N] [end_turn · $0.0000 · 1234in/254out · run c81efb508849]
Nobody answered in time — the call was denied by timeout, not by an explicit refusal. As you asked, I won't retry; the write simply didn't go through.
20s of waiting left today

$ dvara ... runs
2026-09-24 15:38  owner/scribe  end_turn         $0.0000  'Write the word hello into hello.txt. Try once on'
                  write_file(refused)[asked]  [waited 10s]
```

No dollar figure: the provider bills nothing.

`494 passed` (was 489).

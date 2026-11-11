# 84 — Changed from the chat

`/schedules` and `/watches` showed a person what they had, and the only
change a chat word could make was how often a watch looked, or whether.
"Make the morning brief 8" or "the guestroom one should be 80" went to
the agent: a model turn, a card, a yes. That's a lot of ceremony for a
number the person can see right there in the list.

Continues [42 — seeing the work](42-seeing-the-work.md).

## Three words, no turn

```
/schedules when 1 at 08:00
/schedules does 1 the weather and my calendar
/watches when 2 above 80
```

`/schedules` now numbers each schedule the way `/watches` does, and says
how to change one under the list. Whoever has only one schedule or one
watch can leave the number out: `/schedules when at 08:00`.

**THEIR OWN, BY NUMBER.** A number is found among the person's own
schedules (Samay's `owner` is their id) or their own watches. A number
from somebody else's list finds nothing, the same as `/watches every`.

**IN PLACE, THROUGH THE PROGRAM'S OWN EDIT.** A schedule changes through
`samay edit` (Samay's notes/17): same id, its runs kept, and the tools it
was allowed unchanged. That's why a new prompt needs no card. Rewording
a schedule can't reach anything the old words couldn't. A *when* Samay
can't read comes back in Samay's words (*Samay said: cannot read
'sometimes'; …*).

**A LINE MOVES WITH ITS WORDS.** `/watches when 2 above 80` runs
`prahari edit ID --when='above 80' --carry-words`. In a chat there are no
boxes to show the new name in before it's saved, so the name, what it's
for and the thing that said 70 are changed with it, and the answer names
the old name (*Done. "Cool the guestroom above 80" (was "Cool the
guestroom above 70"): …*). Prahari's notes/13 argues the swap.

## What stays with the agent

Pausing or removing a schedule, and changing a watch's check, pick or
then. Those change what runs, or end it. The agent asks first, on the
person's channel.

## Receipt

`tests/test_seeing_the_work.py::TestChangingByHand` drives a fake
`samay` and `prahari`. Each command is the person's own, by number, as
one `--flag=value` word (a prompt beginning with dashes is still a
prompt). Samay's refusal is passed on in its words. Someone else's
number finds nothing. The underlying edits ran for real in Samay's
notes/17 and Prahari's notes/13.

# 87 · A child or a guest, in one word

Setting a child up safely took six settings: the hours their agents
answer, a day's messages, a day's dollars, asking before anything
changes, who is asked, and which accounts they get
([notes/61](61-limits-for-a-child.md)). Each one is right, and an owner
adding their daughter for the first time knows none of their names.
Leave one out and the gap is quiet: a child with an approver but no
`"ask"` rung is never asked anything, and a guest with no ceiling has the
owner's.

```toml
[actor.anya]
role = "child"

[actor.ravi]
role  = "child"
hours = "06:30-20:00"      # an earlier bedtime: what you write wins

[actor.sam]
role = "guest"
```

## What a role fills in

| | child | guest |
|---|---|---|
| hours | 07:00-21:00 | every hour |
| messages a day | 60 | 30 |
| dollars a day | 1.00 | 0.25 |
| rung | asked before anything changes | read only: never changes anything |
| who is asked | the house's owner | nobody (nothing to ask) |
| accounts | none (the default) | none (the default) |

`adult` fills nothing; it's there so the page can say so.

WHAT THE OWNER WROTE WINS. A role only fills keys left out of the
person's table. A child with `hours = "06:30-20:00"` keeps that bedtime
and gets the rest of a child's settings.

A CHILD'S QUESTIONS GO TO THE OWNER. The owner's name is known to the
service (`--owner`), not to the people file, so a child with no
`approver` has their questions sent to the owner when they are asked
(`Service._desk_for`). A spend, or anything that unlocks, is the owner's
yes; the child is never the one asked. An approver written by hand
(`approver = "mum"`) wins, as everywhere else.

A GUEST ONLY LOOKS, AND THE RUNG DOES IT. A guest can ask the puck
what the weather is and never turn anything on, unlock anything or buy
anything. That isn't a list of forbidden tools: a list would be out of
date the day a new connector arrived. It is the read-only rung, the same
gate every call already goes through. A change isn't a question for a
guest at all, so nobody is woken by one either.

## The page keeps the role's values the role's

Sarathi's **Settings → People** form has *Who they are* at the top. A
role's values show greyed in the boxes they fill (*07:00-21:00 (the
child's)*) and the boxes stay empty. Saving leaves them empty, so the
file says `role = "child"` and nothing else. Switch the role to guest
later and every one of those values changes with it. Without that, the
first Save would have written the child's defaults out as if they'd
been typed, and the role would have meant nothing after.

One trap was waiting in Sarathi: under `[dvara] yolo`, a person saved
with no rung was written as `"ask"` (Dvara reads no rung as no ceiling
of their own under `--yolo`). For a guest that would have replaced
read-only with asking. A child or guest role now keeps its own rung.

## Receipt

A scratch people file through Dvara's parser and the page's view:

```
anya: role=child hours=07:00-21:00 turns=60 usd/day=1.0 rung=ask  page boxes blank for ['hours', 'max_turns_per_day', 'max_usd_per_day', 'permissions']
ravi: role=child hours=06:30-20:00 turns=60 usd/day=1.0 rung=ask  page boxes blank for ['max_turns_per_day', 'max_usd_per_day', 'permissions']
sam: role=guest hours=None turns=30 usd/day=0.25 rung=read_only  page boxes blank for ['max_turns_per_day', 'max_usd_per_day', 'permissions']
```

The child's bedtime showed up while the tests were being written: run
at eleven at night, the first test of a child's question to the owner
waited for a question that never came, because the child's turn was
refused before any model was asked. The test now gives its child all-day
hours, and a separate test checks the refusal.

## What was deliberately not built

* **A guest whose access ends.** A rule's `until` and the grants page
  cover when things end ([notes/85](85-who-may-do-what.md)); a person's
  own end date waits until someone hosts a guest for a week.
* **More roles.** A teenager or a grandparent is a child or an adult
  with a box or two changed, and the form shows which boxes.
* **Tool lists per role.** The rung is the guard; see above.

## Tests

`tests/test_roles.py`: a child gets hours, messages, dollars and asking;
a guest only looks; what the owner wrote wins; adult or no role fills
nothing; a role that isn't one is an error, not no limits; after hours a
child's turn is refused before any model; a child's question goes to
the owner with no approver named, and to a named approver when there is
one; a guest's questions are not sent to the owner; the page shows a
role's values beside blank boxes, and saving writes the role, not its
defaults. Sarathi's `tests/test_dvara_yolo.py`: a child or guest keeps
its role's rung under yolo.

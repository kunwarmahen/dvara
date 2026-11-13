# 85 — Who may do what, unasked

A yes that never needs asking again is written in five places. The
owner's standing rules are in `policy.toml`. Each person's rung and the
sources they trust are in `actors.toml`. Each agent's own mode is in its
`agent.toml`. A schedule has the tools it was granted when it was made
(Samay). A watch has the one tool it calls with no model, plus whatever
its follow-up turn may use (Prahari). Each one was a sensible yes on the
day it was given. Nobody could see them side by side, so nobody could
spot the one that had grown too wide, or the one nothing had used since
spring. And none of them ever ran out.

Continues [10 — what decided this](10-what-decided-this.md) and
[03 — standing answers](03-standing-answers.md).

## One list

```
dvara grants              every standing yes, and what each was used for
dvara grants --days 7     counted over the last week (0: everything kept)
dvara grants --json       the same, as dvara.grants.v1
```

The owner's page shows it too, under *Who may do what unasked*.

**READ FROM WHERE EACH YES LIVES.** Nothing in this list is a copy. The
rules and the people come from this service's own files. Schedules and
watches are whatever `samay list --json` and `prahari list --json`
answer (readings come from `prahari indriya list --all`, which lists every
person's). The house's rung comes from the running `dvara serve` itself.
It now writes its rung into its claim beside its address (`rung yolo`), so
anything that reads the claim knows what the door is answering under.
If a sibling doesn't answer, the list names it (*Samay: didn't answer*)
and leaves its rows empty instead of guessing.

**WHAT A TURN REALLY RUNS UNDER.** A turn runs at the strictest of three
rungs: the house's, the person's and the agent's (`gate.stricter`). So the
list shows the result for each agent, not the three settings that go
into it. A person written as `yolo` who talks to an agent that ships `ask`
gets *asks before a change* beside that agent.

**BESIDE EACH YES, WHAT WAS DONE WITH IT.** For every call, the ledger
already keeps what settled it (notes/10). That could be a rule, a
person's yes, a schedule's grant made ahead, or one yes for the task. So
each rule shows how many calls it settled and when it last did. Each
person shows how many calls ran, how many of those ran in turns nobody
typed, and how many were asked, settled by a rule or refused. These are
counts, never arguments, because the ledger keeps shapes on purpose.

**WORTH A LOOK, NOT AN ALARM.** At the bottom are the lines an owner
would want to hear about:

* a rule whose last day has passed;
* a rule ending within a week;
* an `allow` that settled nothing in the window;
* a schedule or a watch granted a pattern (`mcp__setu__*`) instead of
  named tools;
* a person whose agent changes things without asking.

Each line says where it's changed. Nothing is changed from the list
itself.

## A yes that ends

```toml
[[rule]]
tool    = "bash"
args    = { command = "podman ps" }
verdict = "allow"
until   = 2026-12-31
```

`until` is the last day a rule answers. It takes a TOML date, or the same
day as a string, which is what Sarathi's rules editor sends from its new
*Until* box.

**A GRANT THAT RUNS OUT FALLS BACK TO A QUESTION.** From the day after
`until`, the rule is read as if it weren't written. An `allow` that ended
is asked again. A `deny` that ended is left to the rung. An ended rule can
never turn a question into a yes. The day is the computer's own, because
the person who wrote the date was thinking of their own calendar. A time
of day is refused rather than rounded down to a day.

**MOVING THE DATE KEEPS THE COUNT.** A rule's id is a hash of what it says
(notes/10), and `until` is left out of that hash, the same as `reason`.
Pushing the end date back isn't changing the standing answer, so its
history carries on.

## Live receipt

`dvara grants` against this house's real files: its own actors file, its
runs ledger, and the host's `samay` and `prahari` reading the same stores
the containers use (read-only `list` calls):

```
The house: asks before a change (ask)  -- assumed: the running Dvara was started before it wrote its rung down; it says after its next start
Counts cover the last 30 days.

Standing rules (0)
  none: every change is decided by the rung alone

People
  owner (owner): own rung yolo
      minder: asks before a change
      morning: asks before a change
      scribe: asks before a change
      trusts samay, homeassistant-home; shared folder
      926 calls ran (383 with nobody watching), 65 asked, 0 by a rule, 0 by a schedule's grant, 0 by a yes for the task, 13 refused

Schedules with tools of their own (0)

Watches (6)
  owner: Mayfield ice cream under $6.19 [active] looks with mcp__sparsh__open_url, then a line to you
  …
  owner: Guestroom heat when below 70°F [active] senses outside-temp, then agent

Readings (1)
  owner: outside-temp [active] looks with web_fetch, shared with nobody

Nothing worth a look.
```

The first run showed three things, and each was fixed before this one:

* *Dvara isn't running*. It was running. Its claim had been written
  before claims carried a rung, so the list now tells apart "not running"
  and "running, rung not written yet".
* A watch that senses a reading was shown by the reading's id
  (`0421878b`). It now uses the name.
* No readings were listed at all, because `prahari indriya list` shows
  one person's view. `--all` was added for this list.

A once-only schedule that had already run was listed with its grant.
Grants are now listed only for schedules that are active or paused.

## What is deliberately not here

* **No end date on a person's rung or trusted sources yet.** Rules are
  the yes an owner writes for one tool. A rung is the shape of a person's
  whole day, and ending it quietly is a bigger surprise than asking again
  about one tool.
* **Nothing is changed from the list.** Each line names the page or
  command that owns the yes. One place to change each one is what keeps
  `.bak` files and validation in one place (notes/41).
* **Arguments are not shown.** The counts come from the ledger's shapes;
  what a call was given stays in the conversation it belongs to.

## Tests

`tests/test_grants.py`: an ended rule answers nothing, and on its last
day still answers. An ended deny never hides a live allow. Moving the date
keeps the id. A bad `until` is refused with the fix. The claim carries the
house's rung. `grant_use` counts by what settled each call. Per-agent
rungs are the strictest of the three. Ended, ending and unused rules are
worth a look, and so are pattern grants. A silent sibling is named.
`tests/test_page.py`: the page's `/api/grants` names people and rules and
never anyone's words. `tests/test_settings.py`: a hand-written `until`
reaches the page as text and is saved back the same.

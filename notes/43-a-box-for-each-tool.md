# 43 — A box for each tool

[notes/41](41-the-owners-files-from-a-page.md) put every file on
Sarathi's page, and an agent's `[tools] allow` became a text box: "one
per line, e.g. web_fetch, mcp__gmail*, ask_user". That is the file with
a frame around it. The owner who wanted minder to follow a link out of
an email had to know that the tool is called `browser_open`, that it
exists only where the browser extra is installed, and that leaving
`remember` out of the list silently takes memory's own verb away even
though the package says `[memory] via = "local"`. Nobody types their way
to that.

## What a box needs to know

A checkbox needs three things a name doesn't carry: what the tool does
in words a person uses, whether ticking it means "a question on your
chat" or "it just happens", and which tools there are to tick at all.

**The words and the bit come from Yantra.** Its `tools/catalog.py` reads
each built-in's class -- `name` and `read_only`, nothing instantiated, no
browser or server started -- and pairs it with a sentence written for the
person, not the model ("Open a page in its own browser (no sign-in)").
`asks` is `not read_only`, the same bit the gate turns into a question
under "ask", so a box can't promise one thing while the gate does
another. A standing rule may still answer the question; the page says so
under the boxes.

**The rest comes from here.** `toolbox.py` adds Dvara's own `send_file`
and the two families a server brings: `mcp__samay__*` and
`mcp__sparsh__*`. A family is ONE BOX AND A PATTERN, because the allow
list matches patterns and a tool Samay gains next month shouldn't need a
new tick.

## Members from what a turn met

What's inside a family is only known once its server has listed its
tools, and starting Samay and Sparsh on every page load costs seconds.
So each turn already wrote down what it was given (`/tools`,
[notes/42](42-seeing-the-work.md)); it now also writes what the package
TURNED AWAY. Yantra's registry kept only the names of refused tools; it
now keeps the tools (`turned_away()`), so the record has their words and
their `read_only`. The page reads every person's last turn with every
agent: a phone tool one package refused still shows for the owner
deciding whether to let it in. Before any turn, a family shows its
sentence alone.

## What the page is handed

For each agent, `show` says which boxes start ticked -- by exact name or
by a pattern the owner wrote, so `browser_*` ticks all five browser
boxes -- and which allow entries NO BOX STANDS FOR (`amazon_*`,
`x_*`, an old `mcp__homeassistant*`). Those go under **Advanced** as
written and are saved back with the boxes, so a save from the page never
drops what the owner typed.

**Accounts are not boxes.** A Setu account arrives with its need
(`[connections] needs`, `"*:read"`), and a need lets its own tools past
the allow list. Ticking them here too would be a second way to say the
same thing, and two ways disagree.

**No box ticked is refused.** Yantra refuses a package whose allow list
is present but empty ("would leave the agent no tools at all"), and the
page says it before asking: *"Tick at least one tool, or "Every tool it
has"."* An empty list never quietly turns into "every tool", which is
what the old text box did with an empty field.

## Live receipt

`dvara settings show` on this machine's real agents, after a turn or two
had been recorded:

```
mcp__samay__*  members: allow_for_schedule, create_schedule, delete_schedule,
               list_schedules, pause_schedule, preview_schedule,
               resume_schedule, schedule_runs
mcp__sparsh__* members: confirm, describe_hold, list_apps, look, open_app,
               press_key, scroll, tap, tap_at, type_text
minder   ticked: read_file, write_file, web_fetch, load_skill,
                 mcp__samay__*, mcp__sparsh__*
         advanced: amazon_*, x_*, mcp__homeassistant*
greeter  ticked: ask_user
```

On Sarathi's page at phone width (420 px wide, Chrome), minder's
**Change** showed nine groups -- Files, Web, Its own browser, Commands,
Notes and to-dos, Talking and skills, Memory, Schedules (Samay), Your
phone (Sparsh) -- each line ending *asks you first* or *runs unasked*,
the two families with their members listed under them. It also showed
what the text box had hidden: minder remembers people, but `remember`
and `recall_memory` were not ticked, so the model had never been able to
call either.

## What the tests hold

`tests/test_toolbox.py`: every built-in, `send_file` and both families
are offered; a box is ticked by its name or a pattern; a name no box
stands for is handed back; a family's members are what some turn met,
given or turned away, across people; before any turn a family is its
sentence alone; `show` ticks each agent from its own list; no box ticked
is refused with nothing written. Yantra's `tests/test_tool_catalog.py`:
every tool the default registry carries has a row, `asks` is the
opposite of `read_only` for every row, and a turned-away tool can still
be described.

## What is not here yet

* **Tools from a package's own `tools/` folder or a pip pack.** They're
  the package's, always admitted under the same policy; they show under
  Advanced if the list names them.
* **Members of a family nobody has used.** Until a turn has started
  Sparsh, its box is its sentence.

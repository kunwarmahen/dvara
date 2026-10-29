# 72 — Asked less, not never

[Note 58](58-outside-text-asks.md) made a change after outside text a
question that no rule and no yolo rung answers. The house's own record
showed what that cost. Since the middle of the month, 67 of 343 tool
calls stopped to ask the owner. Some of those were rightly asked. Many
came after the agent had read the owner's own schedules or lights, and
one browser job asked six times about one page.

There was a second cause too, and it had nothing to do with outside
text. It's at the end of this note.

## Approve all for this task

A question asked only because the turn read something has a third
answer:

```
  ┌─ message to chat 8675309
  │ minder wants to run mcp__prahari__create_watch:
  │
  │ Asked because this turn read text you didn't write (https://x.com (web_fetch)). ...
  │ [approve] [refuse]
  │ [approve all for this task]
  └─
  ← pressed: t:Rbo_PR_OLYsQsVEMGMm86A
  ← the question now reads: ...— approved, and the rest of this task
```

Every later question in the same turn that is asked only because of
those same reads then runs without asking. The run's record says
`for_turn` against each one it covered, next to `asked:telegram` on the
one you pressed.

Three things it won't do:

* **It doesn't cover anything read after the yes.** The desk keeps what
  the turn had read when you pressed (`AskDesk.yes_for_turn`). If the
  agent then reads a new page or an email, the next change asks again,
  and its card names the new read.
* **It doesn't cover a spend or a phone's confirm.** Those ask for
  themselves. Yantra marks them `only_after_reading = False`, so the card
  doesn't even offer the button (`Ask.for_turn`).
* **It doesn't reach another turn.** Your next message starts a new
  task, and the yes is gone. The desk keeps the newest 256 turns' yeses
  in memory, like the questions themselves, and nothing on disk.

Every channel shows it, and only on a card that offers it:

* **Telegram**: a third button on its own row.
* **Dvara's page**: *Allow all for this task*.
* **Sarathi's chat**: *Yes to all for this task*.
* **Vaani's puck**: say *yes to all* along with your PIN.

Over HTTP it's `"for_turn": true` beside `"approve": true` on
`POST /asks/ID` or `/web/asks/ID`. Anything but a real `true` is refused
with a 400, the same rule as `approve`. A `for_turn` on a question that
didn't offer it is a plain yes.

## Sources a person trusts

`trusted` in `actors.toml` names servers whose answers are that person's
own words:

```toml
[actor.owner]
trusted = ["samay", "homeassistant-home"]
```

A read from one of them isn't outside text, so a change after it asks
nothing new (Yantra's notes/148). It's checked by Yantra's own rule
when the file loads. A wildcard is refused with the fix in the error,
and only a server's tools can be named, never the web:

```
error: actors.toml: [actor.owner] trusted 'mcp__samay__*' has a wildcard;
name the server (samay) or the one tool (mcp__samay__list_schedules) instead
```

The server's name is what follows `mcp__` in its tools' names, so
`mcp__homeassistant-home__call_service` means `homeassistant-home`. The
page's person form has a box for it, *Sources they trust*.

## Live receipt

A scratch Dvara on `qwen3.8:latest`, with an agent holding `web_fetch`
and `write_file`. The owner was asked for three steps: fetch a page,
write its title to one file, write its first sentence to another. The
first question that offered it was answered "for this task":

```
ASKED web_fetch for_turn=None            -> approved (plain yes)
ASKED write_file for_turn=True           -> approved (approve all for this task)
questions put: 2

[["web_fetch", null, "asked:http"], ["write_file", null, "asked:http"],
 ["write_file", null, "for_turn"]]
```

The second write ran without asking, and the record says why.

## The other cause: the house's own rung

`web_fetch` was asked about at all in that run because the scratch
service was started with `--ask` and no `--yolo`. The house rung was then
`ask`, and a turn runs under the strictest of the house, the person and
the agent. The live house was started the same way by Sarathi. So
`permissions = "yolo"` in its `actors.toml` and `mode = "yolo"` in
minder's package had never been in effect, and every change was asked.

Nothing here was wrong. `--yolo` is the owner's half of yolo on purpose
(§ the policy file), and a ceiling that a file can lift is not a
ceiling. But it was invisible. Sarathi now has a switch for it,
`[dvara] yolo` (*Let "Never asked" work* on its home page). With the
switch on, Sarathi writes `"ask"` for anyone saved from the page with no
setting of their own. Dvara reads a person with no setting as "no
ceiling of their own", and under `--yolo` that would hand them whatever
their agent says.

## Tests

`tests/test_outside_text.py` (17, up from 5): the card offers it only
when reading is the only reason; a yes for the task covers the next
question in that turn and records `for_turn`; a plain yes covers nothing
after it; something read after the yes is asked again; it never reaches
another turn; it never covers a spend; `for_turn` on a card that didn't
offer it is a plain yes; a no is never for the task; and `trusted` is
read as written, empty by default, and refuses a wildcard or a non-list.
`tests/test_telegram.py`: the third button only where it's offered, and
a press lands as a yes for the task. `tests/test_http.py`: a `for_turn`
that isn't a boolean is a 400.

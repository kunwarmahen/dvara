# 41 — the owner's files, from a page

*Every choice an owner makes here lives in a file they wrote: who may
talk to which agent (`actors.toml`), the standing answers
(`policy.toml`), and each agent (`agent.toml`, `prompt.md`). That keeps
them reviewable, and it means an owner who installed Sarathi had to open
a TOML file to add their sister. This note lets a page change them,
without the files stopping being the record.*

## The problem, as you would meet it

You want Priya to use the greeter, with a dollar a day and her own
Gmail. The home page can invite her, but only if she's already in the
actors file, and putting her there meant opening `~/dvara/actors.toml`,
finding the commented example, getting `[[actor.priya.channel]]` right,
and hoping a typo didn't stop the bot.

## `dvara settings`

```
dvara settings show                      every file's text, and what it says, as JSON
dvara settings person NAME               add or change them (JSON on stdin) | --remove
dvara settings rules                     all the standing answers (a JSON list)
dvara settings agent NAME                its tables and prompt | --from-example X | --remove
dvara settings text KIND [--agent NAME]  a whole file as text (actors, policy, agent, prompt)
```

Sarathi's home page calls these (its note 16). Each answers
`{"ok": true, ...}`, or `{"ok": false, "error": ...}` with exit 2.

* **CHECKED BY THE CODE THAT READS IT.** A change is applied to the
  text, then parsed exactly as Dvara parses it: `ActorBook` for people,
  `RuleBook` for rules, Yantra's `load_package` (on a copy of the
  folder) for an agent. Only a file that loads is written, so a
  change that would stop the bot is refused, with the words the bot
  would have printed at start-up:

  ```
  {"ok": false, "error": "…/actors.toml: telegram id '1234567' is claimed by both [actor.priya] and [actor.priya2]; one channel identity is one person, and there is no right way to guess which"}
  ```

* **THE REST OF THE FILE IS KEPT.** Python reads TOML and doesn't write
  it, and a writer that dumps the whole file again drops every comment.
  `tomledit.py` treats a table as the span from its header to the next
  header that isn't its own sub-table, and swaps only that span. Every
  other line stays byte for byte. The file before is kept as `.bak`, and
  the new one replaces it in one step, so Dvara rereading it mid-write
  sees one file or the other.
* **WHAT A FORM DOESN'T SHOW IS LEFT ALONE.** A person's change starts
  from their table as it is, so a key the page doesn't edit
  (`max_wait_per_day`, a channel of another kind) is carried over. A key
  sent as null, false or empty is taken out, since each of those is that
  key's default.
* **NAMES, NEVER PATHS.** A person or agent name is letters, digits, `-`
  and `_`, so a page can't reach outside Dvara's folders. A removed
  agent's folder is moved aside (`.removed-NAME`), never deleted, and not
  listed: Settings lists only the folders the roster would load
  (a name that can't start with a dot).

## The rules file sits beside the people

`--policy` defaults to `policy.toml` beside the actors file
(`~/dvara/policy.toml` by default, as before). A page that writes the
rules and the running service then always mean the same file. A rules
file that appears after start-up is picked up without a restart.

## Receipt

On a copy of the machine's real `actors.toml` and agents, through
Sarathi's page in Chrome (its note 16): Priya added with one agent, her
own accounts, $0.50 a day and a Telegram id; `@ravi` as a Telegram id
refused (*"a Telegram id is a number (the bot shows it), not
'@ravi'"*); a second person with Priya's id refused as above; greeter
given memory; one rule saved. The owner's comments and the commented
example were unchanged above the new table, and `actors.toml.bak` held
the file before.

## What the tests hold

`tests/test_settings.py`: a new person leaves the file before them byte
for byte and keeps a backup; a change keeps the keys and channels the
form doesn't show, and the comments of other tables; a change Dvara
couldn't load is not written; a name is never a path; removing a person
takes their table and nothing else, and the last person can't go; the
rules are written, and a wildcard Allow is refused; an agent is changed
as Yantra loads it, comments kept, a bad table refused; an agent is
added from an example and removed aside; a whole file as text is checked
first; the command speaks JSON and refuses with exit 2; a `[table]`
inside a multi-line string isn't taken for a header.

## What is not here yet

* **Comments inside a changed table.** They go with the table: the page
  rewrites a person whole. Comments everywhere else stay.
* ~~**Tools as a text box.**~~ Checkboxes, each in plain words and
  marked asks / runs unasked ([notes/43](43-a-box-for-each-tool.md)).
* **Every Yantra key in a form.** The agent form covers what people
  change (model, memory, tools, accounts, budget, rung, instructions).
  Sub-agents, MCP servers and skills folders are edited as text.

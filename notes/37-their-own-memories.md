# 37 — their own memories

*[Note 19](19-their-own-accounts.md) gave each person their own
accounts: their Gmail, never the owner's. This note does the same for
what an agent remembers about the people it talks to.*

## The problem, as you would meet it

A package asks Yantra for memory with `[memory] via = "local"`, and
Yantra remembers things about *the person talking*: where they live,
how they like answers. Yantra decides who that person is from
`$YANTRA_USER`, else the login name. At your own terminal that is you.
Behind this door it was still the login name of the process running
Dvara, which is the owner's. So Priya telling the greeter about her cat
filed *"has a cat called Biscuit"* under the owner. And the next person
to ask *"what do you know about me?"* got the owner's facts, Priya's
and everybody's.

## Their name on every turn

Each turn now names its person to Yantra (`build_async(memory_user=...)`,
Yantra's seam for a service that serves many people). The name is their
id in the actors file, or the name `memory.json` gives them in the store
(below). The built-in file keeps one row per name, so Priya's memories
are hers in the file too, and the owner's stay the owner's.

**THE PACKAGE DECIDES WHETHER.** Nothing changes for a package that
never asked for memory: it gets none, whatever else is set.

## The owner decides where

```bash
dvara --memory smritikosh-mcp.json serve ...        # or DVARA_MEMORY=FILE
```

`--memory` names one MCP server, in the format of Yantra's
`--mcp-config`, that keeps memories somewhere better than the built-in
file: Smritikosh, which finds them by meaning. A package that asks for
memory gets that store. The server starts beside each turn, for that
turn's person, and stops when the turn ends, the same as Samay's
([note 18](18-a-schedule-asked-for-in-the-chat.md)). Its settings may say
`${DVARA_MEMORY_USER}` and `${DVARA_MEMORY_KEY}`:

```json
{"servers": {"smritikosh": {
  "command": "/path/to/smritikosh-mcp",
  "env": {"SMRITIKOSH_API_KEY": "${DVARA_MEMORY_KEY}",
          "SMRITIKOSH_USER_ID": "${DVARA_MEMORY_USER}",
          "SMRITIKOSH_BASE_URL": "http://127.0.0.1:8080"}}}}
```

**ONE KEY EACH.** `<state>/memory.json`, readable by the owner alone,
holds each person's name in the store and their own key:

```json
{"people": {"owner": {"user": "asha", "key": "sk-smriti-..."},
            "priya": {"user": "dvara-priya", "key": "sk-smriti-..."}}}
```

A Smritikosh key opens only its own account's memories. So the store
itself, not only Dvara, keeps Priya's agent out of the owner's facts. A
store key that read everybody's would leave one model mistake between
one person and another's memories. A key per person removes that
possibility. Sarathi writes this file (`sarathi smritikosh`, its note 13),
and the owner gets their own account there. What they told Yantra's page
is what their agents know about them on Telegram.

**NO KEY, NO MEMORY.** A person with no entry, or no key, gets no memory
this turn, never somebody else's. The owner is told once:

```
dvara: priya: no memory this turn -- no key of their own for 'smritikosh' in …/state/memory.json
```

A store that won't start costs the turn its memory, never the turn, the
same as Samay and the phone. A broken `--memory` file stops the start,
where the owner is looking.

## Receipt

A scratch Dvara (`--memory`, Smritikosh on 8098 with its own database)
with the owner and `priya`, `gemma4:12b` through Ollama, and the
`greeter` package asking for `[memory] via = "local"`. One fact was
stored for each with their own key. Priya's key asked for the owner's
memories got `HTTP 403: Access denied` from Smritikosh. Then each asked
the greeter *"What do you remember about me?"* over `POST /message`:

```
priya: You have a cat named Biscuit and you prefer tea over coffee.
owner: You live in Pune and bank with First Federal.
```

Smritikosh's log for those two turns:

```
GET /memory/dvara-priya?app_ids=default&limit=20 HTTP/1.1" 200 OK
GET /memory/dvara-priya?app_ids=default&limit=100 HTTP/1.1" 200 OK
GET /memory/asha-scratch?app_ids=default&limit=20 HTTP/1.1" 200 OK
GET /memory/asha-scratch?app_ids=default&limit=100 HTTP/1.1" 200 OK
```

## What is not here yet

* ~~**A look back at the end of a conversation.**~~ At `/new`, and what
  Yantra notices on the way, listed for the person to keep with
  `/remember` ([note 38](38-what-they-said-in-passing.md)).
* ~~**`/memory` in the chat.**~~ `/memory` lists what is kept about
  them, `/memory forget ID` takes one back
  ([note 38](38-what-they-said-in-passing.md)).
* **The example packages.** None of them asks for memory, so turning
  `--memory` on changes nothing until a package says `[memory] via`.
* ~~**Facts for everyone in the house.**~~ The owner's, shown whole in
  every agent's turn, beside each person's own and never in their store
  ([note 62](62-what-everyone-knows.md)).

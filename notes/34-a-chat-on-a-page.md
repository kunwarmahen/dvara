# 34 — a chat on a page

*[Note 17](17-nobody-wrote-first.md) gave a finding nobody asked for a
way to reach a person: `POST /notify`, onto the channels the actors
file lists. For most people that list was Telegram or nothing. This
note adds a channel that every person has, a page, and makes it a chat
as well.*

## The problem, as you would meet it

You make a schedule on Yantra's page at your computer: "every morning,
tell me the weather". It runs at 08:00 and the answer is good, but it
reaches nobody. It isn't on Yantra's page, and it isn't on Telegram,
because the schedule was made at the computer and not in a chat.
Samay's page has it, if you think to look there. A person on the
roster with no Telegram is worse off: every notice sent to them comes
back `nowhere: true`.

The other half: the only way to talk to an agent behind this service
without Telegram was `curl` with the service's token. There was no way
to try the HTTP road by hand, or to use it at all from a browser.

## One channel, two jobs

`dvara serve --web` turns on the web channel (`web.py`). Each person
gets a list of lines, kept on disk:

* what they said on the page,
* what their agent answered,
* every notice sent to them: a schedule's answer, or a file a scheduled
  run sent.

A page draws the list. **A notice "waits until they open the page"
because it is simply a line they haven't scrolled to yet.** Telegram's
notices go out at once and are gone; these stay, so somebody away for
a week finds the week.

**EVERY PERSON HAS IT, WITH NO LINE IN THE ACTORS FILE.** A notice for
anyone goes to their listed channels *and* to their lines. So with
`--web` on, `nowhere` is never true. Telegram becomes one channel of
several, not the only door.

**ON WHEN ASKED FOR.** Without `--web`, nothing is kept and a person
with no channel is still told about nowhere, as before. Sarathi starts
the door with it.

## The conversation is the page's own

Turns from the page run under the thread `web:chat`, beside Telegram's
`telegram:<chat>`. **A chat on Telegram does not continue on the page,
and the reverse.** Each place keeps its own history. Everything else is
one person: the same allowance, the same rules, the same folder, the
same Setu sign-ins, and one queue of questions.

A question that a page turn raises goes to the person's Telegram as
well, if they have one, and the page lists it too (`asks` in the look).
The first answer anywhere settles it, as it always has (note 12).

## A turn runs behind the request

`POST /web/message` writes the line down, starts the turn, and answers
at once with the line it wrote. The agent's answer is a later line.
That is not just about speed: a turn can take minutes, and **a page
reloaded mid-turn must not lose the answer**. While a turn runs, the
look's `busy` names the agent that is working, so the page can say so.

A held turn answered from the page (`POST /web/holds/{id}`) works the
same way: the two refusals that need no turn, "not yours" and "gone",
come back on the request, and what the turn comes to is a line.

## The surface

```
GET  /web?actor=&after=N         -> {lines, agents, busy, asks, holds}
POST /web/message  {actor, agent, text}         -> {line}
POST /web/asks/{id}  {actor, approve}           -> {answered, approved}
POST /web/holds/{id} {actor, answers}           -> {started}
GET  /web/file?actor=&line=&n=   -> the file a line carried
```

**ONE LOOK, EVERYTHING THE PAGE DRAWS.** A page polls one endpoint and
gets the new lines, the agents this person may use, what's running, and
what's waiting for their yes. Questions and held turns come back whole
on every look, so one answered on Telegram disappears from the page by
itself.

**THE CALLER SAYS WHO, AS EVERY CALLER DOES.** These endpoints take
`actor` from a trusted caller holding the token, like `/message`. The
page in front of them decides who is talking (Sarathi's home page: the
owner), and the browser never holds this service's token. A file is
asked for by line and number; the path on this machine never leaves
the process.

**KEPT ON DISK, AND CAPPED.** One SQLite file, `web.sqlite3`, beside
the ledger. A person keeps their newest 2000 lines; older ones go.

## Receipt

A scratch door with the example agents and `qwen3.8:latest` through
Ollama, `dvara serve --port 8798 --web`, with Sarathi's home page in
front of it on 8797. A notice to a person with no Telegram:

```
$ curl -H "Authorization: Bearer $DVARA_TOKEN" -d '{"actor":"owner","text":"Your 08:00 check: 2 new mails from the bank."}' localhost:8798/notify
{"actor":"owner","sent":["web"],"kept":[],"failed":{},"nowhere":false}
```

A message through the home page, answered as a later line eight
seconds on:

```
POST /api/chat {"agent":"greeter","text":"Hello! In one short sentence, what can you do?"}
{"line": {"id": 2, "who": "you", "agent": "greeter", ...}}
GET /api/chat?after=2   (busy: ["greeter"] until it finished)
{"id": 3, "who": "agent", "agent": "greeter",
 "text": "I greet folks at the door and chat a little — that's about it."}
```

A write, asked about and approved from the page:

```
POST /api/chat {"agent":"scribe","text":"Write the word hello into a file called a.txt."}
ASK: write_file - NEW FILE a.txt (1 lines)
POST /api/chat/asks/<id> {"approve": true}  ->  {"answered": true, "approved": true}
agent : Done — `a.txt` now contains the word `hello`, verified by reading it back.
```

## What was deliberately not built

* **Signing in.** The page in front of this channel says who is
  talking. Today that is Sarathi's home page, and it speaks as the
  owner. One sign-in per person in the house is its own piece of work,
  done in front of this channel, not inside it.
* **Push to a phone.** Lines wait until a page asks for them. A page
  installed on a phone with notices pushed to it may come later.
* **Streaming.** An answer arrives whole, as a line. The page polls
  every few seconds; a turn's words as they are written would need a
  connection held open, and the page doesn't need it yet.
* **One conversation across channels.** Deliberate, as above.

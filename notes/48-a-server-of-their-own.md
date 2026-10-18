# 48 — A server of their own

*Someone has an MCP server of their own: a notes server at home, a docs
server at work. Yantra on their desktop could use it, because they had
pasted it into Yantra's config. Asked on Telegram, the agent had never
heard of it: dvara starts what Setu holds for a person, and nothing
else.*

## Setu holds it, so every road has it

Setu can hold a server like that now (Setu's `setu connect --server`):
it tries the server, writes down which of its tools only read, and keeps
the token in the person's vault. A server held there is a connection
like Gmail is. `setu status --json` lists it, and each turn starts it
with `setu run`, in the person's own folder. So dvara needs nothing new
to *use* one: Yantra's page, the Sarathi portal's chat and Telegram all
see it once it's added. What was missing was a way to *add* one from
the chat.

## `/connect server`

```
/connect server https://docs.example.com/mcp            a server needing no token
/connect server https://docs.example.com/mcp wiki read as work
                                                        a name, a level, an account
/connect server                                         their page, to add one with a token
/connect docs read                                      a server they have, at a new level
```

The first runs `setu connect --server URL --json` in their folder and
answers with what came back:

```
Connected docs:personal (docs.example.com/mcp) at All its tools, 3 tools. Tools
that change things are asked about first. The agent here doesn't use it yet: its
package has to name it ([connections] needs = ["docs:write"]) -- ask the owner.
```

The last sentence is there because the package rule hasn't changed
([notes/19](19-their-own-accounts.md)). An agent somebody else wrote
sees a person's connection only when its package asks for it, and a
server they just added isn't in anyone's `needs`. A household's own
agent with `needs = ["*:read"]` sees it at once, with only its reading
tools. The reply says which case it is, so a server that seems to do
nothing has its reason given.

## No token in the chat

A token typed into Telegram stays in the chat's history, on Telegram's
computers as well as the phone. So a server that asks for one isn't
asked for it here. The reply sends them to their own page instead:

```
https://docs.example.com/mcp asks for a token (HTTP 401). A token shouldn't be
typed into a chat: it stays in the chat's history. Add it on your accounts page,
under Add your own server: its address, and its token if it needs one. The token
goes straight to Setu.

http://192.168.1.44:8775/#link=raj.…
```

That's the one-time link `/accounts page` sends ([notes/31](31-their-own-page.md)),
to Setu's page for their folder, where the token goes from the form to
`setu connect` and is never shown again. `/connect server` with no
address gives the same link.

A program as a server (`setu connect --server-command`) is never added
from here. Setu would run it on the computer running dvara, as dvara's
user, and that's the owner's to decide at that computer. Setu's page
refuses it from a person's page too.

## A folder that isn't theirs

A person pointed at the owner's folder with `setu_manage`
([notes/27](27-your-folder-from-your-phone.md)) can connect Gmail into
it from their phone, but a server there is the owner's to add, on Setu's
page at the computer. A narrowed folder (`setu_accounts`) is the owner's
to change in every way, as before.

## Changing its level

`/connect docs read` is what changing a level always was: connect again.
For a server there's no sign-in page to link to. Setu tries it again with
the address and token it holds, and the answer is the outcome itself, with
no link and no paste.

## The package's own servers

There are two kinds of server, and they belong to different people. A
person's server is theirs, in their Setu folder. A package author's server
is declared in `agent.toml` (`[[mcp]]`), and Yantra starts it in every
session. A turn here used to leave those out, so an agent answered with
fewer tools than its author gave it, and nobody was told. Each turn now
starts them too (`Service._packaged`), and three rules come with that:

- **Last.** A name the turn already has (the person's accounts, Samay,
  the phone, memory) keeps it. The package's server is skipped, and the
  owner is told.
- **The package's `[tools] allow` still decides**, as it does for every
  tool: `mcp__docs__*` lets them in, and a list that leaves them out keeps
  them out.
- **A server that won't start** costs the turn those tools, never the
  turn, and the owner's log says why.

## Not here

- A token typed into the chat, ever.
- ~~A server added to a package's own `[[mcp]]` list~~ — started for each
  turn now; see above.

# 53 — The tools a turn is sent

*[Note 19](19-their-own-accounts.md) gave each person's turn their own
accounts, and [note 48](48-a-server-of-their-own.md) let them add a server
of their own from the chat. A package that needs `"*:read"` admits every
one of them. This note is about what that does to a turn once a person
has connected enough of them.*

## A greeting for an answer

After Robinhood, Notion and a server of their own were connected, the
household agent had 227 tools: 55 built in, 52 Robinhood, 51 from the
person's own server, 36 Notion, and the rest. `/tools` listed Notion's.
Asked on Telegram to search Notion for their tasks, the agent answered:

```
Hey Mahen — what do you need? I can dig through your mail, check a site,
look up a flight, work the phone, or set up a repeating check.
```

The model's thinking, kept in the conversation's history, said why. It
listed the Notion tools it could see. They were the last few of the 36
(sessions, calendar, backlinks), with no search and no fetch, and it
concluded Notion had no search tool. Every tool's description goes into
every request. Together, 227 of them were more than `qwen3.8-64k`'s
window, and Ollama keeps a prompt that is too long by cutting its top.
That top held the system prompt and most of the tool list. By the next
turn the question had gone the same way, and the greeting is what the
package's prompt says when nothing has been asked.

## Yantra's rule, on this road too

Yantra already had the cure ([its notes/17](https://github.com/kunwarmahen/yantra/blob/main/notes/17-tool-selection.md)).
Past twenty tools, each model call is sent the dozen that match the
conversation, a few pinned ones, and `list_available_tools` for the rest.
A tool that wasn't sent can still be called by its exact name. But the
rule ran in Yantra's own start-up, after its servers were in, and this
road builds a fresh agent for every message and adds the person's
servers itself. It never applied the rule.

Now it does, through the same function Yantra's terminal and page use
(`select_when_many`). It runs once every server for the turn is in: the
person's accounts, Samay, the phone, their memory and the package's own.
The width is the package's `[tools] per_turn` when it sets one (`0` sends
every tool), else `YANTRA_TOOLS_PER_TURN`, else on past twenty.

**THE PERSON DOESN'T MANAGE THIS.** Connecting an account is not a
decision about the prompt's size, and the package can't know how many
accounts a person will have. Nobody ticks tools in or out as accounts
come and go. The turn's own words choose them.

## Receipt

The same question, the same package, the same Setu folder and
`qwen3.8-64k:latest`, through a scratch Dvara after the fix:

```
$ dvara --root ~/dvara/agents --actors ~/dvara/actors.toml --state /tmp/scratch \
    --provider ollama --model qwen3.8-64k:latest \
    say --actor owner --agent minder "Search my Notion for my tasks"
Here's what I found. You have two task databases:

**1. Yantra Task Manager** (has 3 tasks):

| Task | Status | Priority | Due |
|---|---|---|---|
| Improve website copy | ✅ Done | High | Feb 3, 2025 |
| Update help center & FAQ | 🔄 In progress | Medium | Feb 20, 2025 |
| Publish release notes | ⬜ Not started | Low | Feb 28, 2025 |

**2. My Tasks** (Notion's synced task database) — empty, no active tasks.
...
[end_turn · $0.0000 · 206705in/3166out]
```

Seven minutes on a local model, over several calls to Notion, but an
answer to the question asked. `tests/test_many_tools.py` holds the rule:
a few tools and the way to the rest, a tool not sent still called by
name, and a package that asks for every tool.

## Not here

- A ceiling on the prompt itself, measured against the model's window.
  Selection keeps the tool list small. A very long system prompt or
  history could still overflow, and Yantra's compaction handles history.
- Choosing tools with a model. The ranking is the same keyword match
  Yantra's terminal uses: no extra call, and nothing to run on a GPU
  that is already busy answering.

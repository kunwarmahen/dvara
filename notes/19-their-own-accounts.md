# 19 — their own accounts

*[Setu](https://github.com/kunwarmahen/setu) keeps a person's sign-ins —
Gmail, Home Assistant — and hands an agent their tools without the agent
ever seeing a key. At a keyboard that person is whoever is typing. Behind
this door there are several people, and until now none of their agents
got any accounts at all. This note is about giving each person their
own.*

## The problem, as you would meet it

You put a mail agent behind the door for your family. Your partner asks
it on Telegram, "anything from the school today?" The agent has no
Gmail: agents here are built per turn with no MCP servers but Samay's,
so it says so, or worse, guesses. The obvious fix is to give every turn
Setu's accounts. But Setu's accounts are *yours*: the one folder of
sign-ins on this machine. Wiring them in would hand your partner's agent
your inbox, and your guest's agent too.

Three things have to be true at once:

* **A person's agent reaches that person's accounts.** Not the owner's,
  and never another person's.
* **The owner decides who has any.** Accounts on this machine are the
  owner's to hand out, even when they're somebody else's sign-ins.
* **An agent reaches only what it asked for.** A sign-in is not a reason
  for a recipe agent to read somebody's mail.

## A folder of their own

Setu keeps one person's sign-ins per folder (`SETU_HOME`). So each
person gets one, named in the actors file:

```toml
[actor.raj]
setu = true                        # a folder of his own: <state>/setu/raj, his alone (0700)

[actor.priya]
setu = "~/.local/state/setu"       # an existing folder -- here, the owner's own
setu_accounts = ["gmail:personal"] # ...but only this account of it
```

Absent, or `false`, means no accounts: the default, so nothing changes
for anyone the owner didn't name. `setu_accounts` narrows a folder to
the accounts meant. It's for the case above: sharing one inbox of yours
with your partner without sharing the other. A value that isn't `true`,
`false` or a path is refused at load, like every other typo in this
file, rather than read as a yes.

**Signing in happens at the machine**, for now:

```bash
SETU_HOME=~/dvara/state/setu/raj setu connect gmail --as personal --level read
```

Google's sign-in comes back to a port on the machine running Setu, which
a phone somewhere else cannot reach. Doing it from the chat is planned
(paste the failed page's address back to the bot), not built.

## Per turn, in their folder

Each turn reads Setu's report *in that person's folder*, starts their
connections as MCP servers with `SETU_HOME` set to the same folder,
and stops them when the turn ends, like Samay's server
([note 18](18-a-schedule-asked-for-in-the-chat.md)). Every pass a
connector asks for comes from that folder's sign-ins, so the only inbox
it can open is theirs.

**BOTH MUST ALLOW.** A connection is used only when the package's
`[connections] needs` names its connector, and only up to the package's
level: `needs = ["gmail:read"]` gets search and read, never send, even
when the person signed in with send. A package that needs nothing gets
nothing.

**A SCHEDULED TURN GETS THE SAME.** A schedule the person made runs as
them (note 17), so it reads what their chat turns read; the schedule's
card said so when they approved it. Writes still need to have been
allowed ahead of time.

**SAID AS IT IS.** An account the package needs that the person hasn't
connected is named in the agent's prompt, with how it gets connected
*here*: not "run `setu connect`", which nobody in a chat can do, but
that the service's owner connects it for them.

**A SETU THAT CAN'T BE READ COSTS THE ACCOUNTS, NOT THE TURN**, and the
owner hears about it once.

## Receipt

`qwen3.8:latest` on Ollama, `dvara say`, real Setu. priya points at the
owner's folder (two Gmail accounts connected) narrowed to
`gmail:personal`; raj has a fresh folder of his own with nothing in it.
The package asks for `gmail:read`. Both ask *"How many unread emails do
I have in Gmail?"*:

```
priya: 1 unread email — account checked: gmail-personal
raj:   I can't check your Gmail inbox — the Gmail account isn't connected
       to this agent … It would need to be connected by the owner of this
       service on their end.

$ dvara runs
raj/mailer    end_turn   list_dir -> glob -> bash(refused)
priya/mailer  end_turn   mcp__gmail-personal__list_labels -> mcp__gmail-personal__search_threads
```

priya's turn started only `gmail-personal`; the owner's other account
was never started at all. raj's folder was made `drwx------`. The first
version of raj's answer said he'd need "Google API credentials or an MCP
email tool": he had been told nothing, because his empty list of
accounts also hid what wasn't connected. That's what the "said as it
is" line above fixed.

## Trust, said plainly

A person's tokens sit on the owner's disk. Setu keeps them in a file
only the account running the service can read, but that account is the
owner's: the owner can read them. For a family or a small team on the
owner's own machine, that's the situation anyway. For people who
wouldn't hand the owner their mail password, it isn't good enough, and
this design doesn't pretend otherwise.

## What was deliberately not built

* **Signing in from the chat.** Google's sign-in returns to the machine.
  Pasting the failed page's address back to the bot would let a person
  finish it from their phone; it needs a change in Setu and a relay
  here, and is the first thing planned next.
* **Owner's accounts by default.** The owner's own actor gets them only
  by naming the owner's folder, like anybody else.
* **A per-person approval of each package.** At a keyboard, a package's
  needs are asked about once. Here the owner already chose the roster,
  which agents each person may use, and who has a folder; asking the
  person again about a package the owner put in front of them would be a
  question with only one answer.
* **Tokens the owner can't read.** Encrypting each folder with a key only
  the person holds would mean a scheduled run, with nobody there, could
  not open it. A real tradeoff against "scheduled turns get the same",
  and it needs its own design.

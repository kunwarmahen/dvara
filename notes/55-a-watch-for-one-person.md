# 55 — A watch for one person

Prahari is a new sibling: it watches for what a person is waiting for (a
mail from the bank, a price under a line) with no model, and wakes their
agent only when the thing happens. Its tools reach Dvara the same way
Samay's did ([note 18](18-a-schedule-asked-for-in-the-chat.md)): one
`prahari mcp` per turn, for that turn's person, on this road. A watch
made in the chat is asked about on the person's channel with Yantra's
card in words, and when it fires with work to do, the work runs here, as
them, labelled `prahari` on the page.

One thing is different from schedules, and it shapes the whole switch.

## A look runs with the owner's accounts

A schedule's run, on Dvara's road, *is* a Dvara turn: Dvara builds that
person's agent with that person's Setu folder ([note 19](19-their-own-accounts.md)),
so a schedule made by a guest reads the guest's mail. A watch's look is
not a turn. Prahari runs `yantra --call` on this computer, with this
computer's accounts: the owner's Gmail, the owner's signed-in sites. If
a guest could make a watch, the guest could have Prahari read the
owner's inbox every half hour and report what it found to the guest.

Two fixes were on the table:

1. **Look through Dvara as the person.** A `POST /call` here that builds
   that person's agent, with their folder, and runs one read tool. That
   is the right shape for a household where everybody has their own
   accounts, and it is real work: a new endpoint, the person's folder
   unlocked for it, and Prahari taught a second way to look.
2. **One person's watches, named.** The service is told whose watches
   these are, and only that person's turns get the tools.

This is the second, for now. `--prahari` refuses to start without
`--prahari-for ACTOR` (or `DVARA_PRAHARI_FOR`): *"a watch looks with
this computer's accounts, so it is one person's -- the person whose
accounts these are"*. Dvara has no other word for "owner"; a setting
that names a person is clearer than a guess at which actor holds the
keys. Sarathi passes its own owner.

The first fix is recorded as not built, in Prahari's README too.

## On the Dvara road, the look is plain Yantra

A watch made here wakes `--agent <roster name> --runner dvara`: when it
fires, Dvara runs that agent by name. But a look can't use a roster
name; it is a Yantra program started by Prahari, and `--agent` there
takes a package *folder*. So on the Dvara road, Prahari looks with plain
Yantra and this computer's accounts, and only the then-turn uses the
named agent. That is the same set of accounts the one person has, which
is why it is safe. A tool only that package brings isn't there for a
look; the accounts, sites and `web_fetch` are.

## What the person sees

The same as in a session at the computer, delivered to their channel:
the card with the call, how often, when it tells them, and what happens
then. The `watches` prompt layer is told the person sees their watches
by asking (`mcp__prahari__list_watches`), and that a Prahari that isn't
running is the owner's to start, never the person's. In the tool picker
the family is *Watches (Prahari)*, and a package with `[tools] allow`
must list `mcp__prahari__*`, as for Samay.

A turn that fires arrives with `came_by: prahari`, so Dvara's page and
`dvara runs --came-by prahari` set it apart from the person's own
messages and from Samay's runs.

## Tests

`tests/test_watches.py` drives a fake `prahari` speaking the real
contract: the named person's turn starts the server `--for` them on this
road and is told how to ask; a guest's turn on the same service starts
nothing; a scheduled turn starts nothing; no server outlives its turn; a
Prahari that won't start costs the tools, not the turn; and the switch
refuses to start without naming whose watches these are.

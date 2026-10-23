# 62 — What everyone in the house knows

Note 37 made every memory one person's: their name in the store, their
own key, and nobody else's facts one model mistake away. That is right
for "Priya flies from RDU". It is wrong for "the wifi is called Banyan"
or "bins go out Tuesday night". Those the owner had to tell each
person's agent separately, and then keep in step by hand.

```
/remember for everyone the bins go out Tuesday night
/household              what everyone's agents know, numbered
/household forget 2     that one, gone          (the owner)
/household yes 1        keep what was offered   (the owner)
/household no 1         and not that            (the owner)
```

## The owner writes it; anyone may offer

A fact every agent in the house reads is a fact every person in the
house is told. So the owner's word puts it there. Dvara learns who the
owner is from `--owner` (`$DVARA_OWNER`), which Sarathi passes. When
anybody else says `/remember for everyone …`, it is an offer instead.
The owner is sent it with its number on their channels:

```
kid offers this for everyone's agents to know:
"bins go out Tuesday night"
/household yes 1 to keep it, /household no 1 to not.
```

With no owner named, an offer has nobody to go to, and it is refused
with that reason. Only the owner forgets one or answers an offer:
*Only owner changes what everyone knows.*

## A file beside the people, not a store

Each person's memories live in the store the owner chose (note 37),
searched by meaning because a person's facts pile up. The household's
facts are the opposite on every count. They are few, written on purpose
and true for everybody. So every turn of every agent is shown them
**whole**, in Yantra's `household` prompt layer, the way a note on the
fridge is seen without being searched for. A search could miss one, and
a missed "bins go out Tuesday" is the whole failure.

That is also why the household is not in Smritikosh. A shared account
there would need a key every person's turn could use, which is the
key-per-person wall from note 37 with a door cut in it. A file needs no
key and no store, so a house on Yantra's built-in memory has it too.
`<state>/household.json` holds the facts and the offers waiting,
readable by the owner alone.

## Every agent, not only one that remembers

`[memory]` in a package says whether its agent keeps what **people**
tell it, which is about them. These are the owner's own notes to every
agent in the house, so a package that keeps nothing about anybody is
still told them. None of Dvara's examples has a `[memory]` table, and
the greeter answered from the household anyway (below).

## Small on purpose

At most 40 facts, each under 300 characters. The layer goes into every
turn, and a small local model's window is where an overgrown one gets
paid for. A fact past either limit is refused with the reason, never
cut. The same fact twice (case aside) is one.

## From the home page

`dvara settings household` takes `{"add"}`, `{"forget"}`, `{"yes"}` or
`{"no"}` on stdin, the same way the page changes people and rules
(`settings.py`), and `dvara settings show` lists the facts and the
offers. Sarathi's Settings has a **Household** tab on top of it. At
this computer, `dvara household [list|add|forget|yes|no]` does the same.

## Receipt

`gemma4:12b` on Ollama, a scratch Dvara (`--ask --owner owner`), the
example `greeter`, which keeps no memories:

```
--- owner keeps a fact
memory | Kept for everyone's agents: The wifi is called Banyan and the password is on the fridge.
--- kid offers one
memory | Offered to owner to keep for everyone: bins go out Tuesday night
--- owner lists
memory | What everyone's agents know here:
1. The wifi is called Banyan and the password is on the fridge.

Offered, waiting on you (/household yes N, /household no N):
1. bins go out Tuesday night -- from kid
--- owner says yes
memory | Kept for everyone's agents: bins go out Tuesday night
--- kid tries to forget
memory | Only owner changes what everyone knows.
```

Then the kid asked the greeter, a fresh conversation:

```
end_turn | The wifi is called Banyan and the bins go out Tuesday night.
```

## What was deliberately not built

* **Facts for some people and not others.** "Everyone" is the one group
  a house always has. Groups inside it ("the adults") would be a second
  actors file, and something the owner would get wrong once and never
  see.
* **The agent writing household facts.** A model's `remember` is always
  the person's own (note 37). Only a person's words make a household
  fact, and only the owner's keep one.
* **Searching household facts.** They are few, so they're all shown. A
  house that needs searching has outgrown a fridge note and wants an
  agent of its own, with a store.

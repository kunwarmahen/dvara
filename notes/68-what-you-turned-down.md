# 68 — What you turned down

`/remember not 2` turns a fact down for good: it is dropped from the
list, and the look back never offers it again, however often it reads
the same person the same way ([note 38](38-what-they-said-in-passing.md)).
That was the point, and it was also a trap. The list is numbered, the
numbers shift as facts are kept, and a "not 2" meant for the dog and
sent for the nurse's shifts was never again for good. Nothing showed
what had been turned down, and the only way back was the owner opening
`<state>/offered.json` with an editor.

## Seen and taken back, from the chat

```
/remember declined   what you turned down, newest first
/remember undo 1     that one may be offered again
```

**NEWEST FIRST**, because a slip is almost always the last thing you
did: the one just turned down is number 1. Every decline now ends with
the way back — *(A slip? /remember declined, then /remember undo 1.)* —
and the `/remember` list says `/remember declined` shows what you
turned down.

**UNDONE IS NOT KEPT.** Undo takes the fact off the declined list and
puts it back on the waiting one, where `/remember N` keeps it and
nothing else does. The other reading — undo means keep — would make a
second word that writes to a person's memories, and the rule in note 38
is that one word keeps a fact and the person says it. So undo answers
*"Back on your list (not kept yet)"* and says how to keep it.

**NO STORE, NO MODEL.** Declining never opened the memory store or asked
a model, and neither does seeing or undoing: only the list in
`offered.json` changes. It costs nothing and works when the store is
down.

## And from the home page

Sarathi's home page has a **Turned down** button beside **Memory**. It
opens the same list, each fact with an **Undo** beside it, and after an
undo says it's back on your list and how many are waiting. Behind it
are two routes on Dvara's web channel, the person's own as every
`/web` route is:

```
GET  /web/declined?actor=A      {"declined": [newest first], "waiting": N}
POST /web/declined              {"actor": A, "undo": ["the fact's words", …]}
```

**UNDO BY THE WORDS, NOT A NUMBER.** A page's list was drawn when it was
opened; a number sent a minute later could name a different fact if
the person declined another on Telegram in between. The page sends the
fact's own words, and only words that are on that person's declined list
come back. Words that aren't — somebody else's, or one already undone —
are ignored, never an error: the answer's `back` says what came back.

## Live receipt

A scratch Dvara with the example agents, `greeter` given `[memory] via =
"local"`, on `qwen3.8:latest` through Ollama. Two turns as the guest
(*"I just moved to Pune last month, and my dog Bruno…"*, *"I work night
shifts as a nurse…"*), then `/new`, whose look back listed three facts:
Pune, Bruno, the night shifts. Then:

```
$ dvara … say "/remember not 2"
I won't offer these again:
- Has a dog named Bruno (affects any pet-related questions: species is dog, name is Bruno).
(A slip? /remember declined, then /remember undo 1.)
$ dvara … say "/remember not 2"
I won't offer these again:
- Works as a nurse on night shifts, so their active "morning" is the one after a shift; …
$ dvara … say "/remember declined"
You turned these down, so I don't offer them again (2, newest first):
1. Works as a nurse on night shifts, so their active "morning" is the one after a shift; …
2. Has a dog named Bruno (affects any pet-related questions: species is dog, name is Bruno).
Send /remember undo 1 to take one back: it goes back on your list, and /remember keeps it from there.
$ dvara … say "/remember undo 2"
Back on your list (not kept yet):
- Has a dog named Bruno (affects any pet-related questions: species is dog, name is Bruno).
Send /remember to see the 2 waiting, and /remember N to keep one.
$ dvara … say "/remember 2"
Kept:
- Has a dog named Bruno (…).
$ dvara … say "/memory"
What I remember about you (1):
#1  Has a dog named Bruno (…).
```

Then the same Dvara served with `--web`, and a scratch Sarathi home page
in front of it as the guest. *Turned down* listed the night-shift fact;
**Undo** answered *"Back on your list, not kept yet: … 2 waiting"*, the
list read *"Nothing turned down"*, and `offered.json` had both facts
waiting and no `declined` key. The phone-width screenshot showed the
dialog over the chat, the Undo under the fact.

## What the tests hold

`tests/test_remembering.py`: the list is newest first; undo puts the
fact back on the waiting list and keeps nothing until `/remember N`; a
number not on the list, or none, is said; undo by words ignores words
never declined and another person's; the page's routes show and undo
only the person's own, refuse a body that isn't a list, and keep
nothing. None of it asks a model. `sarathi/tests/test_home.py`: the
home page passes both through as the signed-in person, never as whoever
the browser names.

## Not here

* **Undo and keep in one press.** On purpose (above). A person who wants
  it kept sends `/remember N` after, one word more.
* **Matching by meaning.** A fact reworded past the head-words check
  (`same`) can still come back once, as before.
* **The owner's page.** It still shows nothing of a person's memories,
  turned down or kept: they are the person's words.

# 86 · What every conversation is told about you, seen and put right

An agent that remembers people starts each conversation with what it
knows about the person, and much of that isn't their words any more. A
memory store like Smritikosh reads the memories it keeps and makes
**facts** of them ("Lives in Cary, North Carolina") and **guesses**
("prefers a chart to a table, 70% sure"). Those facts and guesses go
into every prompt (Yantra's [notes/152](../../yantra/notes/152-what-the-store-made-of-you.md)).

Until now a person on Telegram or the page could see only the memories:
`/memory` listed them, `/memory forget ID` took one back. The facts and
guesses an agent was actually told were not on that list. And a memory
that was nearly right could only be forgotten, then hoped for again in
better words.

## What /memory shows now

```
/memory              the memories, as before, and then:
                       What every conversation is told about you:
                       F1  Lives in Cary, NC  (85% sure, said 3 times, always told)
                       F2  Banks with Fidelity  (60% sure, told when it fits)
                       What I guess about you (from many memories, not said by you):
                       B1  Prefers short answers  (70% sure)
/memory forget F2    never told again, and never drawn again
/memory forget B1    never guessed again
/memory fix F1 Lives in Apex, NC
/memory fix 2ad6b855 Has a dog called Biscuit
```

**How sure, and how often.** A fact says how sure the store is and how
many memories said it. A guess says how sure it is and is headed as a
guess, *not said by you*, so it reads as what it is. *Always told* is a
fact every conversation gets (who you are, where you live, what you
prefer). *Told when it fits* is one that comes in only when the question
touches it.

**The same numbers the list showed.** F2 is found again when it is used,
in the same order and with the same filter, so the number means the line
the person read. A number that is no longer there changes nothing and
says so.

## Turned down, not deleted

FORGETTING A FACT OR A GUESS MARKS IT REJECTED. Smritikosh draws facts
from memories again at every consolidation and mines guesses again, so a
fact deleted outright would come back by morning. A rejected fact keeps
its status when consolidation draws it again (the status is set only
when the fact is new), and a retracted guess is never inferred again.
The memories it was drawn from stay, so turning down one wrong fact
doesn't take the right ones made from the same words with it.

Smritikosh's MCP server does this through the verb that was already
there: `forget` takes a profile fact's id (`fact:<category>/<key>`) or a
guess's (`belief:<id>`) as well as a memory's. Nothing new for an agent
to learn, and the key that does it is the person's own, so it can only
ever turn down their facts.

## Put right: written first, let go after

A FIXED MEMORY IS WRITTEN IN THE OLD ONE'S PLACE BEFORE THE OLD ONE
GOES. It takes the old memory's topic and place (so it answers the same
question) and is filed as a correction. If the store fails between the
two writes, both are kept and the person sees both on `/memory`. Neither
being kept is the failure that can't be seen, so it's the one ruled out.

A FIXED FACT IS TURNED DOWN AND THE RIGHT WORDS KEPT AS A MEMORY. The
store makes the fact again from those words at its next consolidation;
until then the memory goes into the prompt as itself. A guess can be
forgotten but not fixed: it is the store's reading of many memories, and
the words to fix are in those.

Yantra's own `/memory fix ID WORDS` (terminal and page) does the same for
a memory. On Yantra's built-in store the facts *are* the memories that
have a single place, so `/memory` doesn't list them twice: there are no
F lines there, and no guesses.

## Live receipt

The house's real Smritikosh, read only (nothing forgotten or fixed on
real memories), its profile put through the new listing:

```
What every conversation is told about you:
F2  Does not want hyphens or dashes in their text.  (always told)
F7  05:45  (always told)
…
What I guess about you (from many memories, not said by you):
B2  prefers visual chart representations over text-based data for financial analysis  (70% sure)
Send /memory forget F1 to stop it being told, /memory fix F1 <the right words> to put it right.
```

Fifteen facts, three guesses. The running server was built before facts
carried how sure and how often, so those parts appear after a rebuild.
The run found one thing the person would want to see straight away: two
facts are a bare value (`05:45`, a date) with nothing saying what they
are. Every conversation is told them anyway. `/memory fix F7 Born at
05:45` is the way to put that right.

## What was deliberately not built

* **Correcting a guess.** Its words are the store's. Forget it, and
  `/remember` the right thing in your own words.
* **Every fact the store holds.** The list is what a conversation is
  told: the core facts, and none of the ones that come in only when a
  question touches them, because `/memory` asks with no question.
  Smritikosh's own dashboard has the whole graph.
* **An undo for a turned-down fact.** Smritikosh's dashboard can set it
  back to active. A chat word for it waits until someone needs it.

## Tests

`tests/test_remembering.py`: the facts and guesses are listed with how
sure; a fact is turned down by the number shown and no model is asked;
a fixed fact is turned down and the right words kept; a guess can be
forgotten and not fixed; a number that isn't there changes nothing; a
kept memory is put right in its place; on the built-in store a fact is
not listed twice. Yantra's `tests/test_memory_seen_and_mended.py` and
Smritikosh's `tests/test_mcp_server.py` cover the verbs underneath.

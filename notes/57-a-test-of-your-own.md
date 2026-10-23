# 57 — A test of your own

*Naina asked minder on Telegram what time the school trip leaves, and
the answer was right. Next month the owner swaps minder's model for a
faster one. Nobody will think to ask about the trip again until the day
it matters.*

Yantra keeps a conversation that went well as a test (Yantra's note
141): its last turn, replayed every night with the tools answering from
what they said then, so nothing real runs. Its words, its tools and the
model's own judgement check the answer. Through Dvara, the person in
the chat keeps one the same way:

```
/keep test 7:45, coach            the conversation we're in, as a test
/chats test 2                     one from the list
```

The words after the command, comma-separated, are what the answer must
say. None is fine: the tools it used and the judge still check it. An
earlier answer in a conversation is kept by its turn, counting what the
person asked: `/chats test 2 turn 1 7:45`.

```
/tests                            your kept tests of this agent, and how each did
/tests delete 2                   take one back; the conversation stays in /chats
```

A failed one shows its first reason (*judge: the reference says 8:15*).
That is usually how a person finds out the answer they kept was wrong
and deletes it. Telegram's `/` menu lists `/tests`.

```
you:    when does the school trip leave?
minder: The coach leaves at 7:45 from the front gate.
you:    /keep test 7:45, coach
minder: Kept “when does the school trip leave?” as a test (kept-3f0a9c21).
        Each time the tests run, I'm asked it again with the tools
        answering from what they said then (nothing real runs), and I
        must say 7:45, coach, and give the same facts as last time.
```

YOURS, IN THE ONE PLACE THE NIGHT READS. A person's tests are kept in
Yantra's tests folder under `people/<person>/<agent>/`, beside
`agent.json` naming the agent's package and whose they are. Dvara's
state holds nothing of them. Yantra's `--tests` walks that folder, the
owner's tests and everyone's together, and runs each suite against its
own agent. One person can't reach another's: the conversations a
person can keep are their own (`/chats test 1` from someone else finds
no conversation 1), so nothing of theirs is ever written into another
person's folder.

THE CONVERSATION AS IT IS, FROM THE PERSON'S OWN LOG. `/keep test`
keeps the one open in this chat, read from the person's file
(`state/past/<person>.sqlite`, [note 50](50-every-conversation-kept.md)),
which every turn has already written. Nothing is asked of the model,
and like `/chats` it is not a turn. A chat with nothing said yet has
nothing to keep, and says so.

## Tests

`tests/test_past.py`, seven more:

* `/keep test` keeps this one in the person's own tests, with its
  words, agent and package;
* `/chats test N` keeps one from the list, and a number not there is
  said;
* nothing to keep yet is said;
* one person's number never reaches another's conversations;
* only those words are the command;
* `/tests` lists and takes one back, and the conversation stays;
* `/chats test N turn K` keeps that turn, and a turn not there is said.

## What is not here yet

* ~~**Seeing your tests and their nights.**~~ Built: `/tests` and
  `/tests delete N` (above).

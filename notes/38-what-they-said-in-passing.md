# 38 — what they said in passing

*[Note 37](37-their-own-memories.md) filed each person's memories under
their own name, with their own key. It left two things open: nothing
looked back over a conversation here, and a person couldn't see or take
back what was kept about them. This note closes both, in the person's
own words in their chat.*

## The problem, as you would meet it

Priya tells the greeter she just moved to Pune and walks her dog at
7 am because she works nights. A good answer comes back. Next week she
asks for a weekend plan, and the agent knows none of it. Nobody says
"remember that I live in Pune"; they say it in passing. At Yantra's own
page, a look back at the end of a conversation catches those (Yantra's
memory/reflect.py). Behind this door, only what the model happened to
write down mid-answer with `remember` was kept.

Yantra does notice things mid-turn here: before it shortens a long
conversation, and in the write-up of a task its skill learner keeps.
Those wait on `memory.pending` for a host to offer. Dvara never offered
them, so they went when the turn ended.

And if a person wanted to know what was kept about them, or to take one
fact back, only the owner could, in the store itself.

## The words

```
/memory              what is kept about you, with each one's id
/memory forget ID    that one, gone
/remember            what I noticed, numbered, waiting for your word
/remember 1 3        keep those
/remember all        keep all of it
```

Like `/files` and `/new` ([note 28](28-starting-over.md)), these are
answered by Dvara, never by the model, and cost nothing. The store is
opened for the person exactly as a turn opens it (their name, their own
key) and closed again. On Telegram they're in the `/` menu for an agent
whose package keeps memories, and nowhere else. On the web channel
([note 34](34-a-chat-on-a-page.md)) they work in the same box as any
message.

## The look back, at `/new`

**A CONVERSATION HERE ENDS WHEN THEY SAY SO.** A Telegram chat has no
end anybody marks, except `/new`. So before Dvara lets the conversation
go, it asks the agent's own model once, through Yantra's look back, what
the conversation showed about the person. The answer is listed under
"Starting fresh", numbered. It is one call, on their allowance, recorded
as a Run (`looked_back`) like any turn. A person with nothing left in
their allowance gets no look back. A look back that fails is a line for
the owner, and the conversation still goes.

**WHAT A TURN NOTICES IS ONE LINE.** What Yantra noticed mid-turn joins
the waiting list, and the answer gets one line: *(I noticed 2 things
about you worth remembering. Send /remember to see what's waiting.)*
Not the list itself: a model offers much the same facts turn after turn,
and a numbered list under every answer is a chat nobody reads. A run
nobody started (a schedule's) lets its finds go, since nobody is there
to say which.

**THE WHOLE CONVERSATION REPLACES ITS PARTS.** The look back at `/new`
read everything the turns read, at once, so its list takes the place of
what the turns noticed on the way. And one fact never waits twice: two
candidates with the same head ("Lives in Pune", whatever follows the
first comma) are one fact. The first live run without this rule listed
"Lives in Pune" three ways and the night shifts three ways, eight lines
for four facts.

## Nothing kept without their word

**LISTED, NOT KEPT.** Candidates wait in `<state>/offered.json`,
readable by the owner alone, at most twelve per person, until the person
sends `/remember` with the numbers. A list nobody answers is replaced by
the next look back. Nothing goes to the store until they say so.

**NOT A BUTTON THAT WAITS.** A yes/no question on Telegram would have
been the obvious shape, since the queue of questions already exists
([note 12](12-taken-down-everywhere-it-went.md)). But a question waits
on something, and here that would be the store, held open for as long
as the person takes to answer. A fact is no less true tomorrow, so the
list waits instead and the store opens only when they answer.

**THEIR OWN, AS EVER.** What `/remember` keeps goes under the name and
key note 37 gave them. `/memory` lists that person's memories and
nobody else's. `/memory forget` takes the start of an id and refuses
when it names two memories rather than guessing, as Yantra's `/memory`
does. A package that keeps no memories answers *"greeter doesn't keep
memories about the people it talks to"*, and its `/new` asks no model.

## Receipt

A scratch Dvara with the example agents, `greeter` given `[memory] via =
"local"`, the built-in file in a scratch folder, and `qwen3.8:latest`
through Ollama. Three turns as the guest, then the words:

```
$ dvara … say --actor guest --agent greeter "Hi! I just moved to Pune last month, and my dog Bruno hates the monsoon. …"
Hide-and-seek works great—scatter a few kibble pieces around a room and let Bruno's nose do the tracking, …

(I noticed 2 things about you worth remembering. Send /remember to see what's waiting.)
$ dvara … say … "I work night shifts as a nurse, so I walk Bruno at 7am. …"
… (I noticed a thing about you worth remembering. …)
$ dvara … say … "I'm learning Marathi on my days off. How do I say good morning?"
… (I noticed a thing about you worth remembering. …)

$ dvara … say … "/new"
[new]
Starting fresh: I won't remember what we said before. Your files, schedules and accounts are all still here.

Before we started over, I noticed this about you:
1. Lives in Pune, India (relocated there in the recent past).
2. Their dog is named Bruno.
3. Works night shifts as a nurse, which shapes their daily schedule (e.g., a 7 a.m. dog walk before the rest of the day wakes up).
4. Is learning Marathi, so language questions they ask are most likely in Marathi rather than another Indian language.
Send /remember with the numbers to keep them (/remember 1 2), or /remember all. Nothing is kept unless you do.

$ dvara … say … "/remember 1 3"
Kept:
- Lives in Pune, India (relocated there in the recent past).
- Works night shifts as a nurse, which shapes their daily schedule (…).
$ dvara … say … "/memory"
What I remember about you (2):
#2  Works night shifts as a nurse, …
#1  Lives in Pune, India (relocated there in the recent past).
Send /memory forget ID to remove one (/memory forget 2).
$ dvara … say … "/memory forget 2"
Forgot #2.
$ dvara … say --actor owner … "/memory"
I don't remember anything about you yet. When something is worth keeping, I'll ask you first.
$ dvara … say --actor guest … "What do you know about my work?"
I don't have any information about your work — the only thing I remember is that you live in Pune.
```

The built-in file held one row afterwards, `guest | Lives in Pune, India
(relocated there in the recent past).`, under the guest's id and not the
login running Dvara.

## What the tests hold

`tests/test_remembering.py`: `/new` looks back and lists but keeps
nothing; `/remember` keeps the chosen ones under that person's own name
and leaves the rest; numbers never listed are refused; `/memory` lists
one person's own and forgets by id with no model asked; a package that
keeps none says so and its `/new` asks no model; a look back that fails
still starts over; what a turn noticed is one line, and the same fact
said again makes none; the look back's list replaces the turns'; the
waiting file is the owner's alone. `tests/test_telegram.py`: the menu
offers the two words only where the package remembers.

## What is not here yet

* **The owner's page.** It shows who used which agent, never the words,
  and a person's memories are words. Nothing about them is on it.
* **Kept as it was said.** `/remember` keeps the sentence as the model
  worded it. A person who wants it said differently tells the agent
  ("remember I moved here in August"), which asks before it writes.
* **A look back without `/new`.** A conversation that goes on for months
  is looked back over only at `/new`, plus what Yantra notices on the
  way.

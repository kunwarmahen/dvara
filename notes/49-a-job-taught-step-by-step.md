# 49 — A job taught step by step

*Someone wants their agent to send a WhatsApp message on their phone
the way they do it. They walk it through on Telegram: "open WhatsApp",
"tap Mom", "type running late". Then `/learn`. The skill that came back
was "type a message": `/learn` reads the last answer, and the last
answer was the last step.*

## A lesson

Yantra keeps a walk-through as one task now (Yantra's notes/129): a
**lesson**, opened with `/learn start`, filled with every turn after
it, written down by the same one-call write-up when it ends. Dvara
gives it the same words on every channel:

```
/learn start send a WhatsApp message    opens it; the agent says it's ready
open WhatsApp                           one step: it does only that, says
tap Mom                                 what's on the screen, asks what's next
/learn done                             the whole walk, offered as one skill
/learn stop                             dropped, nothing kept
/learn watch send a WhatsApp message    the same, with their own hand on the
                                        phone; they say "next" after each step
```

`/learn start` is a word and a turn at once. The lesson is opened, and
its opening (*do ONLY the step I tell you, then tell me what's on the
screen and ask what's next*) goes to the agent in place of the word, so
the first thing it hears is that it is being taught. A capable model
told nothing runs ahead and finishes the job its own way, which is
exactly the job it wasn't shown.

## On disk, because the agent isn't kept

Dvara builds the agent anew for every message. A lesson kept on the
agent would be gone by the second step. So it is a file,
`state/skills/<person>/<agent>.lesson.json`, beside the offers waiting
for them, and each turn is added to it as it ends (`after_turn`), each
result clipped the way the write-up would clip it anyway. A long lesson
on a small context window also loses its early steps to compaction;
the file still has them.

ONE PERSON'S LESSON IS THEIRS. It is kept per person per agent, so the
owner teaching the minder a job changes nothing for anyone else, and
the skill it becomes is saved in their own folder like any kept skill
(note 42).

NOTHING IS OFFERED HALFWAY. While a lesson is open, the look after a
turn doesn't run. Each step of a walk would otherwise come back as a
skill of its own: "tap Mom", offered with Keep and Not now.

`/learn done` is the old `/learn` pointed at the lesson: the look runs
behind the reply, on the person's allowance, a new message from them
stops it, and the offer comes as any other. The reply says what is
being written (*Writing down what you taught me (3 step(s)) as one
skill*). With no lesson open, `/learn done` says so, and plain `/learn`
still keeps the last answer.

## Receipt

Through the service, scripted model, real learner (`tests/test_lessons.py`):

```
/learn start send a WhatsApp message  -> "Ready. What's first?"
                                         (the agent heard "teach you how to send
                                          a WhatsApp message")
open WhatsApp                         -> one call, "WhatsApp is open. Next?"
tap Mom                               -> one call, "Mom's chat is open. Next?"
                                         no look ran after either step
/learn done                           -> "Writing down what you taught me
                                          (2 step(s)) as one skill. I'll send it
                                          to you to keep."
the write-up saw                         PERSON: open WhatsApp
                                         1. bash {"command": "echo opened whatsapp"}
                                         PERSON: tap Mom
                                         2. bash {"command": "echo tapped mom"}
offer on the page                        send-a-whatsapp-message, Keep / Not now
```

The same lesson on a real iPhone, from Yantra's terminal with
`qwen3.8-64k`, is Yantra's notes/129 receipt.

## Found in use

The owner's first lesson on Telegram (a Coinbase portfolio, on the
iPhone) came back with nothing to keep. The steps had been done by hand
in a `start` lesson, a second `/learn start` had been answered with the
first one's status, and `/new` in between had left the lesson open with
its opening gone. Now a new start replaces an empty lesson, `/learn
done` on one says how to teach (and keeps it), and `/new` and `/chats N`
drop an open lesson and say so (Yantra's notes/129).

## What is not here yet

* **A lesson run for real through Telegram, start to skill.** The first
  try found the mix-ups above; the next one is the owner's, after the
  rebuild.
* **A Teach button.** The words only; a page could open a lesson from
  the skills panel.

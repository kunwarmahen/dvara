# 79 — Each conversation its own chat

## The problem, as you would meet it

[Note 78](78-carried-on-where-it-was-written.md) made words written
under an old conversation go into that conversation. But they still
waited. The owner asked something long on Sarathi's home page, pressed
**New chat**, and asked something short. The short question sat behind
the long one until it was done. A chat app answers both.

The cause was the page's one chat. Every page turn for one person and
one agent ran under one thread, `web:chat`, so one key, one lock and one
session. That chat moved from conversation to conversation, and it could
only be in one of them at a time.

## A chat for each conversation

**EACH CONVERSATION ON THE PAGE RUNS UNDER ITS OWN THREAD,
`web:chat.<id>`.** That gives it its own session, its own lock and its
own questions waiting, so two of them run side by side. Words for a
conversation that is still answering wait in that conversation's own
chat, as a second message always did. Nothing else is split: the
folder, the sign-ins, the allowance and the schedules are still the
person's (the folder is per person and agent, never per thread).

**A NEW CHAT GETS ITS ID FROM DVARA, ON THE LINE.** A new chat's first
words go as `new: true`. Dvara makes the conversation's id, opens its
chat under that id (`deliver(begin=True)`), and returns it on the line
it writes, so the page knows which conversation it just began before
any answer arrives.

**EVERY LINE SAYS ITS CONVERSATION.** The person's words, the answer, a
refusal and a failure all carry `conversation`. `look` lists `working`
(the conversations answering now), and each `live` view says which one
it is. The page draws only the conversation it shows. The others are
marked *working…* in the list until their answer lands, and opening one
shows its answer.

**A CALLER WITH NO LIST STILL HAS ITS ONE CHAT.** Words with neither
`conversation` nor `new` go to `web:chat`, the page chat every message
went to before. A page from before this, or `curl`, keeps working, and a
conversation still open there is carried on by its id like any other.

**A CONVERSATION IS NOT HELD OPEN BY ITS OWN PAGE CHAT.** Every page
conversation now has a chat it is open in, so "open in a chat" no longer
means "can't be deleted". A row is `open` only when a chat elsewhere
(Telegram, a puck) holds it, since that chat's next turn would write it
again. Deleting closes its page chat with it (session, current
conversation, questions waiting). The one exception is a conversation
that is answering right now: the delete is refused with *"that
conversation is answering now"*.

**NEW CHAT DOESN'T WAIT EITHER.** The page clears the window at once. It
sends `/new` to the conversation it leaves only when that one is quiet,
for the look back over it; one still answering goes on in its own chat,
and its look back comes when it goes quiet ([note 39](39-while-nobody-is-writing.md)).

## What it costs

Two turns of one agent at once can both want the same browser profile.
Yantra's profile lock already covers that: the second waits a while,
then says who has it (Yantra's `profile_lock.py`). Both turns share the
same model. On Ollama they run side by side only while it has a free
slot (`OLLAMA_NUM_PARALLEL`); when every slot is busy, Ollama finishes
one before the other, even though Dvara started both.

Telegram is unchanged. Its window has one conversation at a time, and a
reply to an old answer carries that one on (note 78).

## Live receipt

A scratch Dvara on port 8798, an agent `talker` (`greeter`'s package
with a prompt that answers at length) on `qwen3.8:latest` through
Ollama, two new chats sent over `/web/message`, the second two seconds
after the first:

```
  0.0s asked A 6eaba2f49070
  2.0s asked B 62043f2abd52 working: ['62043f2abd52', '6eaba2f49070']
  6.3s answer in B | 51 | still working: ['A']
 22.3s answer in A | The history of lighthouses stretches back to the ancient civilizations ... | still working: []
```

Then Sarathi's home page on a scratch port (8812), in a headless
browser at 1280 and 390 px. The script asked for the essay, pressed
**New chat** while it was being written, and asked for 17 × 3:

```
  0.3s A asked; state: talker is working…
  2.1s after New chat: title = New chat | lines in window: 0 | state: ''
  4.7s both asked: rows marked working: 2 | state: 'talker is working…' | live in window: 1
 19.9s B answered in the window: 51 | lighthouse text in window: False
 21.4s opened A from the list: Write a 400-word essay on the history of lighthouses. | past has essay: True
 28.3s follow-up in A answered: From the Pharos to the Present: A Brief History of Lighthouses
 29.0s page errors: []
```

Dvara's run log for that run shows both turns started at 01:06:32 and
01:06:34, each under its own thread (`web:chat.08d9…`, `web:chat.35a9…`).
Here the short answer still came at 19.9 s, after the essay. Ollama ran
the two one after the other that time: the same pair of requests sent
straight to Ollama, with no Dvara involved, came back at 16.4 s and
17.2 s. The first run above had a free slot and came back at 6.3 s.

## What the tests hold

`tests/test_page_chats.py`, with a model that holds any question
starting "slow" until the test lets it go: a new chat gets its own
conversation and its id on the line, and a chat under that id; a second
conversation answers while the first is still working; each live view
says its conversation; words with a conversation's id carry it on in its
own chat; words for one still answering wait in its chat and land in
it; a conversation answering is not deleted from under itself, and once
it has answered it is deleted with its page chat; `/new` in a
conversation clears that window only; a caller that names no
conversation has the one page chat it always had. `tests/test_past.py`:
a conversation open only in its own page chat is `here` and not `open`,
and is deleted with that chat closed. Sarathi's `tests/test_home.py`: a
new chat's first words reach Dvara as `new`, and only `true` is passed on.

## What is not here yet

* **A conversation's tab of its own.** The window shows one conversation
  at a time, and another one's progress shows only as *working…* in the
  list until you open it.
* **Two answers at once on a busy Ollama.** That is Ollama's slots, not
  Dvara. A cloud model answers both on its own.

Continues [note 78](78-carried-on-where-it-was-written.md) and
[note 34](34-a-chat-on-a-page.md).

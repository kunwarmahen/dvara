# 83 — Routines, from the chat

Vidhi keeps routines a person drew once, and some of them stop to ask:
*"It's 61.8°F outside. Want a line on what to wear?"* (Vidhi's notes/02).
The person is in a chat, on Telegram or Sarathi's home page. The
question has to reach them there, and their answer has to come back
from there, from whichever channel they happen to be on, hours later.

Continues [42 — seeing the work](42-seeing-the-work.md) and
[80 — one menu, and a Keep button](80-one-menu-and-a-keep-button.md).

## A notice with buttons

`POST /notify` takes `taps`: at most three `{word, label}` a channel
draws as buttons under the notice. A press sends `word` as if the person
typed it, by the person who pressed.

**A BUTTON CAN ONLY SAY A SLASH WORD.** Each `word` must start with `/`
and be short, or the notice is refused. Whatever the caller is, a button
it puts on someone's phone can't say anything to their agent in their
name: only a word that does what typing it does. Telegram also takes a
press only for words it knows (`/routines` among them).

Telegram draws them side by side under the notice's last part; Sarathi's
home page draws them under the notice, and a press goes to the agent
chosen in the chat, since a notice has none of its own. ntfy draws the
same buttons (below).

## `/routines`

None of these is a turn: no model, no allowance spent.

```
/routines
Waiting for your answer:
  It's 61.8°F outside. Want a line on what to wear?  (/routines yes F9SEKQ  or  /routines no F9SEKQ)

Your routines:
1. Morning brief — 1 model ask per run
2. Coat check — 1 model ask per run

/routines N for how one went, /routines run N to start it. …
```

`/routines 2` is the second one's last three runs, step by step;
`/routines run 2` starts it (`--by dvara:telegram`); `/routines stop RUN`
stops one.

**AN ANSWER IS FOR ITS OWN PERSON, ONCE.** `/routines yes CODE` asks
Vidhi to answer as this person (`vidhi answer --as`). Someone else's code
answers *"no question … waiting for you"*, the same as a code that
doesn't exist. A second answer says what the first one decided.

**THE COMPUTER'S ROUTINES ARE THE OWNER'S.** A routine installed at the
computer is filed under `local`, and its questions come to the owner's
chat (`VIDHI_DVARA_ACTOR`). For the owner, `/routines` lists both, and an
answer not theirs by name is tried as `local`.

## Their agent

With `--vidhi`, each turn starts `vidhi mcp --for <them> --agent <this
agent> --runner dvara` (`_routines`): the agent can run a routine or
install a ready one, after a yes on their channel with a card that lists
everything it touches (Yantra's notes/155). A routine installed this way
runs as them, through here, with their accounts. A scheduled turn gets
none. The `/` menu offers **routines** when Vidhi is on.

## Live receipt

Tested here with a stand-in `vidhi` that prints what Vidhi prints
(`tests/test_routines.py`): the owner sees the computer's question,
answers it as `local` after their own name finds nothing, and a guest
pressing the same code is refused. The real Vidhi was run through its
own page and CLI (Vidhi's notes/02 and 03). The buttons haven't been
pressed on a real phone yet; that comes with the house's rebuild.

## Not here

* **Drawing a routine from a chat.** That's Vidhi's page.
* ~~**Buttons on ntfy.**~~ Drawn (below).

## Choices, words, and the same buttons on ntfy

A question can offer two or three choices, or take a few typed words
(Vidhi's notes/05). Their words are `/routines pick CODE N` (the
buttons, one a choice, labelled with it) and `/routines say CODE the
wifi is HouseGuest` (no buttons: typed). `/routines` lists a waiting
question with the words that answer its kind.

**ON A NOTIFICATION, A MARK, NEVER A KEY.** ntfy's buttons are sent from
the phone, so whatever they carry is in the notification for anyone who
reads the topic. A notice with taps gets them as ntfy http actions to
the home page's `/api/push/answer`, each carrying a mark: an HMAC under
`ntfy.key` over this person and that exact word, in the `tap` offer's
place (push.py). Only `/routines` words are drawn. A press is checked
(`tapped`), then answered by `/routines` as if the person typed it, never
a turn, and the answer goes back to the phone. A copied button answers
that one question the one way its words say, which is what reading the
notification already lets one do by typing. Tested with Dvara's own
test client and a stand-in Vidhi; not yet pressed on a real phone.

## A reply, or the code alone

The first real run on Telegram found two ways a person who had just been
asked was told no. Question 3 of a test routine took typed words; the
answer sent was `/routines W2R7ZH blue door`, the verb left out, and
the code was read as a routine's name: *"You have no routine W2R7ZH."*
Pressing reply on the question and typing the words was a message to
the agent, which knew nothing of it. The run waited out its half hour
and said *"Got: yes / Cool /"*.

**THE CODE ALONE IS ENOUGH.** `/routines W2R7ZH blue door` answers the
waiting question with that code the way its kind takes: the words, a
choice (`/routines SUCT7N Cool`), or yes or no (`/routines BAFP4F
yes`). A code with nothing it takes says how to answer it. A code
nobody was asked is still read as a routine's name.

**A REPLY IS AN ANSWER.** On Telegram, a reply to the question's own
message answers it: the code is in the words the question gave to
answer it (`/routines say W2R7ZH your words`), so nothing is kept to
match a reply to a question, and Vidhi still checks the answer is this
person's (`replied_answer`). A yes-or-no question takes yes or no (y,
yep, nope...); anything else typed back is left as a message to the
agent, as is a reply starting with `/`.

**TELEGRAM'S OWN NOTE ISN'T ANSWERED.** With topics on (notes/82),
typing outside a topic makes a new one, and Telegram sends *"topic
created"* as a message with no words. Dvara answered it *"I can read
words, pictures and files, not this."*, which read as if the person's
own words couldn't be read. Only a sticker, a video, a location, a
poll and the like get that sentence now (`UNREAD`); any other message
with no words is Telegram's and gets nothing.


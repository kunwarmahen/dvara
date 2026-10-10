# 32 — the ring in the chat

*[Note 30](30-do-this-on-my-phone.md) brought the phone to the chat,
with a held step's card as Yes and No buttons. Sparsh now taps by
position on a screen the list can't read, holding every such tap, and
Yantra's card for it carries the screenshot with the spot ringed
([Yantra's note 123](https://github.com/kunwarmahen/yantra/blob/main/notes/123-a-tap-you-say-yes-to-by-looking.md)).
This note is that picture reaching the person, wherever they answer.*

## The problem, as you would meet it

"Rename my phone to Trial Phone", sent from Telegram, comes back as a
question: *tap the spot ringed on the picture (x 200, y 365 of 1000) in
com.android.settings*. There's no picture in the chat, only the words,
so the buttons ask for a yes to a number. A person can only guess, and
a yes given that way is not a yes to anything.

## The picture rides on the question

**AN ASK MAY CARRY A PICTURE.** `Ask` gains `picture`, PNG bytes,
filled by the gate from Yantra's `PermissionRequest.picture` (an image
the card shows beside its words, never sent to the model). The desk
passes it along like the summary: one question, one picture, every
channel it goes out on.

Each channel shows it in its own way:

* **Telegram:** the picture first, as a photo captioned *"The phone's
  screen: a tap lands where it is ringed."*, then the question with its
  buttons under it, as before. The buttons stay on a text message, so
  taking them down once the question is over works as it always did
  ([note 12](12-taken-down-everywhere-it-went.md)).
* **The owner's page:** above the question's words. `/asks` lists a
  question only to the person it was put to, and the picture with it.
* **The terminal** (`dvara say`): it can't draw one, so the picture is
  saved to a file and the path printed under the question.

A question in words carries no picture and looks exactly as before.

## Live, on the emulator

`dvara say` on the phone agent, `qwen3.8:latest` on Ollama, every
question answered `y` at the keyboard by a script that doesn't look.
The terminal is the channel here; Telegram was not pressed from a real
chat.

```
phone wants to run mcp__sparsh__confirm:
  Do this on the phone?
On the phone emulator-5554: tap the spot ringed on the picture (x 200, y 365
of 1000) in com.android.settings -- held because it is a tap by position: ...
(The picture shows the screen; a tap is where it is ringed.)
  the screen, the spot ringed: /tmp/dvara-ask-2wxe4fjx.png
approve? [y/N]
```

That picture ringed "Device name". Every question in the run came with
its picture: the row, the text field, the typing, OK. The fourth tap
was meant for OK on Android's "your device name is visible" warning,
and its picture rings the warning's text instead, well above the
button. A person looking would have said no. The script said yes, the
tap landed on nothing, and the model pressed back and started over.
Stopped after seven questions with the phone not renamed. The run shows
the picture reaching the person, and shows why the yes has to come from
someone who looks at it.

## What the tests hold

`tests/test_gate.py`: a card's picture rides on the question, and
`as_dict` carries it; a question in words has none.
`tests/test_telegram.py`: a question with a picture sends the photo
first and the buttons under it; one in words sends no photo. 705 tests
before, 709 after.

## What is not here yet

* **A real Telegram chat.** The photo goes through the same Bot API
  upload a file already uses ([note 26](26-the-file-itself.md)), and is
  untried from a real chat, like the rest of the phone road there. On a
  real 6P no tap by position came (Maps' places were blank in the list,
  but no picture went with a list that had anything); now a partly
  blank screen sends one, and every held step brings its picture, so
  the photo comes with the next Send or Call (Sparsh's notes/10). A
  ring card from a tap by position has been seen through `dvara say`
  on the 6P: a map pin, ringed, opened on yes. The same from a real
  chat is still to be pressed.
* ~~**A phone in a scheduled run.**~~ [Note 33](33-the-phone-on-a-schedule.md):
  a tap by position there is never granted, so it is asked, ring and all.

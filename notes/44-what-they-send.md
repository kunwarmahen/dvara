# 44 — What they send

*A photo sent to the bot got "I can only read text", and the page had
nothing to attach with. The things people most want to hand an agent
are things they have, not things they can type: a photo of a receipt, a
screenshot of an error, the PDF the school sent.*

## Kept in their folder

Each person has one folder per agent ([note 25](25-the-persons-folder.md)),
shared by their chat and their schedules. What they send lands there,
under `from-you/`:

* Telegram: a photo (its largest size) or a document, downloaded through
  the Bot API (up to its 20 MB for a bot), the caption as the words.
* The page: the paperclip beside **Send**; the files go to
  `POST /web/message` as `files: [{name, data}]`, data in base64.

The agent is told in the message itself: *"(They sent
from-you/IMG_2041.png (a picture), kept in your folder.)"* That line is
also what the turn's record keeps, so "what did I send you on Monday?"
has an answer, and `/files` lists the file and `/file` sends it back.

A NAME NEVER LEAVES THE FOLDER AND NEVER REPLACES ONE. Only the file's
own last part is kept, made safe (`../../etc/passwd` is `passwd`, a
leading dot is dropped so nothing hides from `/files`), and a second
`receipt.jpg` is `receipt-2.jpg`. Ten files at once at most, 20 MB each;
too many or too big keeps none of them and says so.

## A picture is shown, when the model can see

A png, jpeg, gif or webp up to 5 MB also goes into the turn as an image,
the way Yantra's own page sends one. Before it does, Dvara asks Yantra's
`sees_pictures`: a cloud model takes pictures; a local one only when
Ollama lists "vision" among its capabilities. A picture sent to a model
that can't take one fails the whole turn, so instead the agent is told
the picture is in the folder and to say it can't look.

Sending a person's own picture to a cloud model is not the screenshot
question Sparsh has (a phone's screen, taken without anyone choosing
it): the person chose to send this one to their agent.

## Receipt

A scratch Dvara on the web channel, `qwen3.8:latest` (Ollama lists it
with "vision"), a package with only `read_file`. A 360×220 picture of a
café receipt, sent as `IMG_2041.png` with "how much did I spend here,
and on what?":

```
you    how much did I spend here, and on what?        📎 IMG_2041.png
mailer You spent **£12.50** at Corner Cafe (paid by card on 16 Oct). That
       was for **2 × Masala chai (£6.00)** and **1 × Samosa (£6.50)**.

state/work/raj/mailer/from-you/IMG_2041.png
```

Every figure is right; the pound sign is the model's guess (the receipt
names no currency).

## What the tests hold

`tests/test_attached.py`: a name can't leave the folder or hide; the
same name twice keeps both; too many or too big keeps nothing; only a
picture type is a picture; the message names what came.
`tests/test_telegram.py`: a document is kept and named, a photo is its
largest size and needs no caption, a file too big is said before any
download. `tests/test_web.py`: a file from the page is kept and named on
its line; data that isn't base64 is refused before any line.

## What is not here yet

* ~~**Voice notes.**~~ Heard into words before the turn by a local model
  that hears ([notes/47](47-a-voice-note.md)).
* **A file the person sends to a scheduled run.** Only a chat turn keeps
  what came with it; a schedule has nobody sending.
* **Deleting from `from-you/`** from the chat (as for every file there,
  note 26).

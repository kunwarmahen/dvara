# 64 — An answer read aloud

*A voice note came in and was heard ([notes/47](47-a-voice-note.md));
the answer went back as words. Someone who spoke because their hands
were full, cooking or driving or carrying the shopping up the stairs,
then had to stop and read. The answer can come back the way the
question went.*

## Made here, by a small voice model

`spoken.py` reads the answer aloud with Piper, a text-to-speech model
that runs on a CPU at about a second a sentence, from one voice file of
around 60 MB (`en_US-lessac-medium.onnx` and its `.onnx.json`). Nothing
is sent anywhere to be spoken. That is the promise `heard.py` makes for
hearing, kept for the other direction: a house on Ollama with no cloud
key has both.

Which voice: every one found in `$PIPER_VOICES`,
`~/.local/share/piper/voices` or `/usr/share/piper/voices` (where
Sarathi's image puts them); `$DVARA_VOICE` names the house's own, or is
`off`. Each person may have their own, and an answer in another language
is read in a voice for it ([notes/65](65-whose-voice-and-which-language.md)).
Piper is the `piper` command, or the `piper` module in Dvara's own
Python.

## The words first, the voice after

A voice note takes a second or ten to make, and an answer read is
faster than an answer heard. So on Telegram the words are sent as soon
as they exist, and the voice note follows them, as an OGG Opus file
(the one kind Telegram shows as a voice note with a play button and a
waveform; ffmpeg converts Piper's WAV). It is never sent instead of the
words: a misheard name, a link or a number to copy are all in the
message.

It isn't owed either, any more than a file is (`outbox.py`): the words
were the answer, and they went. No Piper, or no voice: the words go
alone, and the owner's log says why, once per answer.

## What is read is not everything written

A table, a block of code and a web address are things nobody wants read
to them. `aloud` keeps the sentences:

| written | read |
|---|---|
| a code block | "(some code, in the message)" |
| a table | "(a table, in the message)", once |
| `[the order](https://…)` | "the order" |
| `https://example.com/a?b=c` | "a link" |
| `**Tuesday**`, `- item`, `## Heading` | Tuesday, item, Heading |

A line with no full stop at its end gets one, so a list is read as a
list and not run together. A long answer stops at a sentence near 1,200
characters (about a minute and a half) with "The rest is in the
message."

## Each person chooses

```
off           never
when-spoken   when they sent a voice note (the default)
always        every answer, and what's sent unasked (notes/65)
```

The owner sets one per person in the actors file (`speak =`, or
Settings → People → **Answers read aloud** in Sarathi). The person
changes their own with `/voice off`, `/voice when-spoken` or
`/voice always` (`/voice` alone says what holds, and whether this
machine can speak at all); theirs is kept in `<state>/voice.json` and
wins over the file. `/voice default` goes back to the file's.

When-spoken is the default because it asks nothing of anyone: a person
who never speaks to it never hears it, and one who does is answered in
kind. A held turn carried on with a button is read aloud only under
`always`: a tap isn't speaking.

## On the page

Every answer gets **▶ Listen** when this machine can speak (`GET /web`
says `voice: true`). The voice is made the first time it is asked for,
`GET /web/spoken?actor=&line=`, as WAV (every browser plays it, Safari
included), and kept beside the state under
`voice-cache/<person>/<line>-<voice>.wav`, so a second press doesn't make it
again (a backup leaves it out: it is made again when asked for). An answer whose line says
`speak` (they sent a voice note, or chose always) plays by itself when it
arrives, never one already there when the page was opened. Pressing ▶ on
another answer stops the first.

## Receipt

A scratch Dvara with `--web`, `qwen3.8-64k:latest` answering, the
person's choice left at the default. The question was made with Piper
("When do the bins go out? Answer in one sentence.") and sent as
`voice-note.ogg`:

```
-- answered in 24.1s, voice here: True
{"text": "I'm sorry, I don't have that information and no way to look it up for you.",
 "heard": "When do the bins go out?", "speak": true}
-- spoken: 187436 bytes b'RIFF' in 1.0s
-- answered in 3.0s, voice here: True
{"text": "I don't have that information either.", "heard": null, "speak": null}
```

The second message was typed, so it had no `speak`. The 4.2-second WAV,
heard back by `gemma4:12b` through `heard.py`, came out word for word:
*"I'm sorry, I don't have that information and no way to look it up for
you."*

Then Sarathi's home page in Chrome, its microphone fed the same question
from a file: 🎤, talk, 🎤, Send. The answer arrived with *I heard: "When
do the bins go out?"* and played by itself (the page's own security
policy in force, `media-src blob:`). A typed message after it didn't
play; pressing its ▶ did, and the button went back to ▶ Listen when it
ended. No errors on the page.

Telegram's half (`sendVoice` after the words) is held by the tests below
against a stand-in Telegram, and hasn't been run on a real bot yet.

## What the tests hold

`tests/test_spoken.py`: code, links and tables aren't read out; a long
answer stops at a sentence and says the rest is written; each choice
reads aloud only when it says; a misspelled `speak` is an error that
lists the choices; `/voice` wins over the file, is kept on disk, and
can be taken back; `/voice` says when the machine can't speak; `off` in
the environment is off. On Telegram a voice note is answered with words
and then a voice note, in that order; a typed message gets none by
default; `always` reads a typed answer and `off` reads nothing; no Piper
still sends the words and tells the owner; `/voice` isn't a turn. On the
page an answer is made into a voice once and kept, the person's own line
is a 404, and a page with no voice says why (503). Settings writes
`speak` and blank removes it. One test runs the real Piper, where it is
installed, and checks a WAV and an OGG come out.

## What is not here yet

* ~~**Notices read aloud.**~~ Under `always`, a schedule's answer and
  every other notice are read aloud too ([notes/65](65-whose-voice-and-which-language.md)).
* ~~**A voice per person, or per language.**~~ Each person may have
  their own, and an answer in another language is read in a voice for
  it ([notes/65](65-whose-voice-and-which-language.md)).
* **A cloud voice.** Nothing here sends text out to be spoken, by
  choice.

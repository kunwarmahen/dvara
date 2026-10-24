# 47 — A voice note

*A Telegram voice message got "I can read words, pictures and files,
not this". People on a phone talk: saying "remind me Monday at nine to
call Ravi" on the stairs is exactly what they want instead of typing it.*

## Words, before the turn

The agent's model mostly can't hear. Most local models and every cloud
model Yantra speaks to take text and pictures only, and Yantra's loop
has no audio block. So `heard.py` hears the note first, with a local
model that can: Ollama lists "audio" among some models' capabilities
(gemma4's). `$DVARA_HEARING` names one; otherwise the smallest such
model Ollama has. Ollama takes WAV, not Telegram's OGG/Opus (it answers
*"Failed to load image or audio file"*), so `ffmpeg` converts it first,
mono 16 kHz, the first five minutes.

The turn is the words, with a line that says where they came from:

```
(a voice note, heard as: "Remind me on Monday at 9 in the morning to call Ravi.")
```

A model told so knows a name may be misheard, and the record of the run
says what the agent was given.

## What was heard is shown

Only the person knows what they said, so they are shown what was heard:
*I heard: "…"* as its own message before the answer on Telegram, and
under the answer on the page. A misheard name is caught there and then.

The recording is kept in their folder under `from-you/`, like any file
sent. With nothing that can hear (no such model, or no ffmpeg), the
agent is told plainly it can't listen to it and to ask them to type it,
never a guess at what was said, and the owner's log says why.

## On the page

🎤 beside the paperclip records with the browser's MediaRecorder (webm,
or ogg / m4a where that's what the browser makes); the recording joins
the files for the next message. A browser allows the microphone only on
this computer or over https, so a phone on the house address
(`http://192.168…`) uses Telegram for voice.

## Receipt

A test note made with espeak-ng ("Please remind me on Monday at nine in
the morning to call Ravi the plumber"), converted to OGG/Opus as
Telegram sends it. Straight to Ollama as OGG: *Failed to load image or
audio file*. As WAV, `gemma4:e4b` heard *"Please remind me on Monday at
8 in the morning to call Ravi the plumber."* Then through a scratch
Dvara's web channel, `qwen3.8:latest` answering, the hearing model
chosen by itself (`gemma4:12b`):

```
you    📎 voice-note.ogg
mailer Got it — Monday, 9:00 AM, call Ramu. …
       I heard: "Remind me on Monday at 9 in the morning to call Ramu."
```

espeak's robot voice is hard to hear: "Ravi" came back as "Ramu" and
"nine" once as "8". A person's voice does better, and either way the
heard line shows it before anyone relies on it.

## What the tests hold

`tests/test_heard.py`: the agent reads that it was a voice note; a named
model is used as named; without ffmpeg it says so; on Telegram a voice
note is heard, shown first and kept; a note nothing can hear is said
plainly, with no "I heard". The hearing model is stood in for; the
tests need no Ollama.

## What is not here yet

* **A cloud model that hears.** None of the cloud roads Yantra speaks
  takes audio today; a cloud-only house has no hearing without a local
  model.
* ~~**Answers spoken back.**~~ Read aloud on this machine and sent after
  the words, by each person's choice ([notes/64](64-an-answer-read-aloud.md)).
* **Recording on a phone's browser over plain http.** Browsers forbid
  it; Telegram, or https on the house address, is the way.

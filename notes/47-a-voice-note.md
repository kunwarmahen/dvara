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

**A WHISPER, WHEN THERE IS ONE, FIRST.** A model asked to write a note
down is a general model doing a narrow job; Whisper is made for it, and
a house that runs voice for Home Assistant often has one already.
`$DVARA_WHISPER` gives its address -- any server with the OpenAI
transcription road (`faster-whisper-server`, whisper.cpp's): the WAV is
posted to `/v1/audio/transcriptions` (`$DVARA_WHISPER_MODEL`, default
`Systran/faster-whisper-small`). One that doesn't answer falls back to
the Ollama model above, and both reasons are kept for the line that
says nothing could listen. Sarathi sets it from `[dvara] whisper`.
Live: a Telegram-style OGG/Opus note of Piper saying *"What's on my
calendar tomorrow? See the list."* came back word for word from
`faster-whisper-server` (`Systran/faster-whisper-small`, CUDA) in 0.8 s.

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

A NAME IS WHAT THEY SAID. A conversation is named by its first words,
and a voice note's first words are this note's wrapping. So Dvara names
it from the words inside (`heard.plain`): the list, `/chats` and the
*Back in* line say *🎤 "how cold is it tonight?"*, typed words first
when there were some. The agent is still given the wrapping; only the
name and the lines a person reads change. Yantra's conversation log
takes the naming from its host (`titled=`), since only Dvara knows the
wrapping.

## On the page

🎤 beside the paperclip records with the browser's MediaRecorder (webm,
or ogg / m4a where that's what the browser makes); the recording joins
the files for the next message. A browser allows the microphone only on
this computer or over https, so a phone on the house address
(`http://192.168…`) uses Telegram for voice.

WHAT WAS HEARD GOES ON THEIR OWN LINE. On Telegram *I heard* is a
message of its own, before the answer. On a page it belongs where they
spoke, at the top, not under an answer that may be minutes away. The
turn tells its watcher `{"kind": "heard", "text": …}` once the note is
heard and before the model is asked (watch.py), so the running turn's
`live` carries `heard` and the page writes it on their line at once.
The web channel also stamps it onto that line (`heard` in its extra),
so a page opened later draws it there too.

```
line you voice: to minder · 08:37 PM 🎤 "fetchexample.com and tell me the page title." 📎 voice-note.webm
```

That was a scratch Dvara on `qwen3.8:latest` with the house Whisper, a
Piper-made question sent as `voice-note.webm`: the words were on the
line 2 s in, while minder was still thinking. (*"fetchexample.com"*:
Whisper ran "example dot com" together.)

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
* **Hindi heard well.** A Piper-made Hindi question was misheard by both
  `gemma4:e4b` and `gemma4:12b`, its second sentence lost, while the
  same models heard Piper's Hindi answers word for word
  ([notes/65](65-whose-voice-and-which-language.md)). A real person's
  Hindi voice note is still to be tried.
* **Recording on a phone's browser over plain http.** Browsers forbid
  it; Telegram, or https on the house address, is the way.

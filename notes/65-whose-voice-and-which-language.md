# 65 — Whose voice, and which language

*Answers read aloud ([notes/64](64-an-answer-read-aloud.md)) came in
one voice, the house's, and only as answers. A Hindi answer went to an
English voice, which can't say the words. A person who'd rather listen
than read still had to read the morning brief, because a schedule's
answer is a notice, not an answer.*

## The answer's language picks the voice when it has to

Before anything is read, `spoken.languages_of` looks at the words that
will be read:

* **By script**, when most letters are in one: Devanagari (Hindi, then
  Marathi, Nepali), Bengali, Telugu, Malayalam, Arabic (Arabic, Persian,
  Urdu), Cyrillic (Russian, Ukrainian, ...), Greek, Hebrew, Georgian,
  Armenian, Thai, Japanese kana, Korean, Han. An English name inside a
  Hindi sentence ("आपका Wi-Fi पासवर्ड ...") doesn't outvote it.
* **By the commonest small words**, for the Latin alphabet: *the, and,
  is* against *der, und, ist*, *le, et, est*, and Spanish, Italian,
  Portuguese and Dutch. Two hits at least, and half again as many as the
  next language, or it can't be told.

`spoken.pick` then chooses. Their own voice reads it when it speaks
that language, or when the language can't be told ("OK.", "Tuesday").
Otherwise the first voice here that speaks it. With none, nothing is
read, and the owner's log says *"the answer is in German and there's
no German voice here (add one from https://huggingface.co/rhasspy/piper-voices)"*.
Reading German in an English voice would be sound without words.

Each voice says its language in its own card (`.onnx.json`:
`"language": {"family": "hi", "name_english": "Hindi"}`), so nothing
here keeps a list of voices.

## Whose voice

A person may have a voice of their own: `voice = "hi_IN-pratham-medium"`
in the actors file (Settings → People → **Their voice** in Sarathi), or
`/voice use 2` in the chat, kept in `<state>/voice.json` beside their
*when*, and winning over the file. `/voice use default` goes back.
Without one, the house's: `$DVARA_VOICE` if it names one, else the first
English voice found, else the first voice.

`/voice` now lists what's here:

```
I read every answer aloud, and what I send you unasked, in
en_US-lessac-medium (English). Voices here: 1. en_US-lessac-medium
(English); 2. hi_IN-pratham-medium (Hindi). Send /voice off, /voice
when-spoken or /voice always to change when, and /voice use N for
another voice.
```

The actors file names a voice by name only (letters, digits, `_ . -`):
whether it's installed is the machine's business, and one that isn't
reads in the house's voice, with `/voice` saying so.

## What's sent unasked, read aloud too

`always` now covers notices: a schedule's answer, the morning brief, a
skill offered, a sign-in that ran out. The notice desk asks the service
once per notice (`NoticeDesk.aloud`) and puts `speak` and their `voice`
in what every channel is handed; Telegram sends the voice note after
the words, and the page's line plays by itself. `when-spoken` doesn't:
nobody spoke to start a schedule.

On the page, a voice made once is kept as `voice-cache/<person>/<line>-<voice>.wav`,
so changing voice makes it again rather than replaying the old one.

## Receipt

The GPU was busy with a training run, so this used no model for the
turn: a scratch Dvara with `--web`, the person set to `always`, and two
notices through `POST /notify`:

```
notify: {'actor': 'mahen', 'sent': ['web'], ...}
notify: {'actor': 'mahen', 'sent': ['web'], ...}
1 notice speak: True 225836 bytes in 2.4s
2 notice speak: True 166956 bytes in 1.4s
voice-cache/mahen/1-hi_IN-pratham-medium.wav
voice-cache/mahen/2-en_US-lessac-medium.wav
```

The Hindi one (*"सुप्रभात! आज दो नए ईमेल आए हैं, और कूड़ा मंगलवार को जाता
है।"*) was read by `hi_IN-pratham-medium`, the English one by
`en_US-lessac-medium`, each without being told. `gemma4:e4b`, run on the
CPU (`num_gpu: 0`, 182 s), heard the Hindi recording back as *"सुप्रभात
आज दो नए इबेल आए हैं और कूड़ा मँगलवार को जाता है।"*: every word but
"ईमेल" (email), heard as "इबेल". `/voice` and `/voice use 2` on the
same page answered as above, and `voice.json` kept
`{"mahen": {"voice": "hi_IN-pratham-medium"}}`.

## What the tests hold

`tests/test_spoken.py`, with a folder of stand-in voices so the voices
on the machine running them never count: the language told by script
or by small words, an English name inside Hindi not outvoting it, and
"OK." not told; the house's voice English first, `$DVARA_VOICE` naming
another; a voice reading its own language and another reading the
rest; a language with no voice not read, and read once one is added;
`/voice use` by number or name, kept beside *when*, an unknown name
listing the voices, `default` going back to the file's; the first
`voice.json` (a bare word) still read; `voice =` refused when it isn't a
name; Settings listing the voices and keeping a person's; a Hindi answer
on Telegram read in the Hindi voice; a notice marked only for `always`
and carrying their voice; a notice on Telegram as words then a voice
note; a notice on the page playing by itself.

## What is not here yet

* **Romanised Hindi.** "kal kya hai?" is Latin letters with no small
  words this knows, so it is read in their own voice. Piper's Hindi
  voices read Devanagari.
* **Two languages in one answer, each in its own voice.** The answer's
  main language picks one voice for all of it.

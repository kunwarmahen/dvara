# 73 — Hindi in Latin letters

Continues [65](65-whose-voice-and-which-language.md), whose first "not
here yet" this is.

## The problem, as you would meet it

Most people type Hindi on a phone in Latin letters: *"kal kya hai?"*.
An agent answers the way it was asked, *"Kal subah 9 baje aapki meeting
hai."*, and that answer, read aloud, was noise. The answer's language
was told by its script or by its commonest small words, and Hindi's
weren't among them, so it couldn't be told and went to the person's own
voice, English. Sent to the Hindi voice instead it was no better: Piper's
Hindi voice reads only Devanagari, and given Latin letters it dropped
the words it couldn't place.

Whisper, listening back, heard each:

```
Hindi voice, as typed:    "kal kya hai? aaj mausam bahut accha hai, aap kaise hain?"
                          → अद मुस्म बहत खाहा है आप किसे
English voice, as typed:  → काल काया हाई, आज मोसम बहादा काहाई, अपकीज हीन
Hindi voice, Devanagari:  "कल क्या है? आज मौसम बहुत अच्छा है, आप कैसे हैं?"
                          → कल क्या है, आज मुसम बहुत अच्छा है, आप कैसी है?
```

Only the last is Hindi a person can follow.

## Told, then written

**HINDI'S SMALL WORDS VOTE.** *hai, kya, nahi, aap, mujhe, bahut* join
the small words the Latin-alphabet languages are told by. Only words
that are rarely English vote: *to*, *is*, *main* and *the* are both, so
*"The main thing is to go"* stays English.

**WRITTEN IN DEVANAGARI BEFORE IT IS READ.** When the voice chosen is a
Hindi one and the words are mostly Latin letters, each word is written
in Devanagari first (`romanised.py`). Numbers, marks and anything
already in another script are left as they were.

**THE COMMON WORDS FROM A LIST, THE REST BY RULE.** Romanised Hindi has
no one spelling (*nahi, nahin, nai*), and the same letter stands for two
sounds (*t* is त or ट). A rule alone gets the words said most often
wrong in ways a listener notices: *hain* as हैन, not हैं. So the
commonest few hundred words come from a list, each spelling of them,
with the English words said inside Hindi among them (*meeting* मीटिंग,
*check* चेक, *phone* फ़ोन), whose *t* and *d* no rule can guess. Every
other word is spelt by how people type: two letters for a long vowel
(*aa, ee, oo*), *h* after a consonant for its breathy form (*kh, bh*),
*n* before a consonant as the nasal mark (अंदर), any other consonant
before another joined to it (क्या), and a final *a* or *i*, or an *a*
before another vowel, read long (रहा, रही, चलाओ), which is how it is
typed.

The tradeoff: a name or a word the list doesn't have may come out a
little wrong (*gaadi* is गादी, not गाड़ी; *samjhe* is सम्झे). Telling a
word from its look is a model's job, and this is the step just before a
voice, where no model runs. A wrong letter in a rare word still reads
as Hindi; the whole answer read as English didn't.

## Receipt

`spoken.make` on three answers, for a person whose own voice is
`en_US-lessac-medium`, with this machine's Piper and both voices, then
heard back by `faster-whisper-small`:

```
a hi_IN-pratham-medium | Kal subah 9 baje aapki meeting hai.
b hi_IN-pratham-medium | Aaj mausam bahut accha hai, baarish nahi hogi.
c hi_IN-pratham-medium | Haan, main abhi check kar raha hoon.
a heard: कल सुबहनाबर्या अपकी बीटिंग है
b heard: आज मुसम बहुत अच्छा है, बारिश नहीं होगी
c heard: हा, मैं अभी चेक रहा हूँ
```

The same two answers as they were read before, by the English voice:

```
काल सबनाई भेज अपकी मीटिंगाई
आज्मास्म बहुधका है बारिष्ना है होभी
```

## What the run found

The *9* in *"subah 9 baje"* is read by the Hindi voice as something
Whisper couldn't place (*सुबहनाबर्या*). Numbers are left as digits, and
Piper's Hindi voice says them its own way. Writing them as Hindi words
(नौ) would be the next step.

## Tests

`tests/test_spoken.py`: romanised Hindi told as Hindi, and an English
sentence sharing its spellings still English; the list's words and the
rules' (long final *a* and *i*, *a* before a vowel, *n* before a
consonant) spelt as said, a number and Devanagari left as they were; a
Hindi voice handed Devanagari by `make`, an English answer handed to its
voice as written.

## What is not here yet

* **Numbers said in Hindi.** Above.
* **Romanised Hindi heard.** This is the voice. A voice note *spoken*
  in Hindi is heard as the hearing model writes it, in Devanagari
  ([notes/47](47-a-voice-note.md)).

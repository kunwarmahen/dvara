# 70 — Bold, not asterisks

A model writes Markdown. Asked what was new in a WhatsApp group, it
answered:

```
**Bad Company — 20:39**
Ajay: *"Rhyme karo @Sarika...do you need balm for your palm?"*

So there's **new activity in the Bad Company group**: someone named **Ajay** …
```

and Telegram showed every asterisk, because Dvara sends plain text.
That was on purpose ([note 07](07-four-thousand-and-ninety-six.md)):
Telegram's Markdown and HTML modes make the model's punctuation a syntax
error, and one unmatched `*` costs the person the whole answer.

## Entities, not a parse mode

Telegram takes a third way: the text, plain, with a list beside it —
*these 19 characters are bold, these 79 italic*. **THERE IS NOTHING FOR
TELEGRAM TO PARSE, SO NOTHING TO REFUSE.** `marked.py` reads the
answer's Markdown here, takes the marks out and sends the list:

| written | shown |
|---|---|
| `**bold**`, `__bold__` | bold |
| `*italic*`, `_italic_` | italic |
| `~~struck~~` | struck through |
| `` `code` `` and a fenced block | code, the block with its language |
| `[words](https://…)` | the words, as a link |
| `# A heading` | a bold line |
| `- an item`, `* an item` | `• an item` |
| `> a quote` | a quote; lines one after another are one quote |

Tables and everything else go as written.

**WHAT ONLY LOOKS LIKE A MARK STAYS AS TYPED.** A mark counts only when
it opens against a word and closes against one: `snake_case_name`,
`rm *.log`, `2 * 3 * 4` and an asterisk with no partner are left alone,
and nothing inside code is read as a mark. A wrong guess costs one word
in italics, not the answer.

**PLACES ARE COUNTED IN UTF-16**, as Telegram counts them — the same
arithmetic as the 4096 cap. An emoji before a bold word is one character
here and two units there; counted in characters, the bold would land one
letter late.

**A REFUSAL SENDS THE WORDS AS WRITTEN.** The one thing Telegram can still
say no to is a link it won't take. A 400 on a marked message sends it
again, plain, with the asterisks — what every answer looked like before —
and the owner's log says *"telegram: an answer went without its bold and
italics — …"*. A flood wait is not a refusal of the marks and isn't
retried this way.

## Which messages

The agent's words: an answer, a notice (a schedule's finding, a watch,
the morning brief), an answer owed from before a restart, the reply to
**Keep** / **Not now**. Not Dvara's own sentences, a question's
summary — a `bash` command with `*` in it is shown exactly as it will
run — or the *Working…* steps.

Splitting happens first, on the Markdown, so each part is marked on its
own. A part is never longer once its marks are out. A cut through a code
block leaves its fence as typed in both halves, as before.

## What the tests hold

`tests/test_marked.py`: each mark and its place; what only looks like a
mark comes back unchanged with no entities; a mark inside a mark; places
after an emoji counted in UTF-16; headings, items, a two-line quote and a
fenced block with its language. `tests/test_telegram.py`: the answer
above goes out as plain words with bold and italic beside them; a plain
answer is sent exactly as before, with no `entities` at all; a 400 on the
marks sends the words again as written.

## Not here

* **Marks across a line.** A `**` opened on one line and closed on the
  next is left as typed. Models close their marks on the line they open
  them.
* **Tables.** Telegram has no table; a pipe table goes as written.
* **The receipt in italics.** It is still the plain line [note
  07](07-four-thousand-and-ninety-six.md) settled on.

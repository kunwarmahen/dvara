# 69 — A picture in the chat, and a PDF made here

Two things a phone couldn't show. A picture an agent sent — a screenshot
of a page, a chart it drew, a scheduled run's photo of the porch — went
to Telegram as a document: a grey file icon with a name, to be tapped,
downloaded and opened in another app. And `/chats export N` sent a
conversation as Markdown ([note 50](50-every-conversation-kept.md)): on a
computer a file any notes app opens, on a phone a page of asterisks. The
home page's **Save as PDF** prints through the browser, but Telegram has
no print window.

## A picture is a photo

`.jpg`, `.jpeg`, `.png` and `.webp` files up to 10 MB go by `sendPhoto`,
and show in the chat as the picture, with the words as its caption —
whether an answer sent it (`send_file`), a notice carried it, or a
scheduled run did. Everything else is still a document.

**THE FILE ITSELF STAYS THE FILE.** Telegram makes a photo smaller on the
way. `/file NAME` is a person asking for the file, so it still sends the
document — the original, to the byte ([note 26](26-the-file-itself.md)).

**REFUSED AS A PHOTO, SENT AS A DOCUMENT.** Telegram refuses some
pictures as photos: wider and taller than 10,000 pixels together, or
thinner than 1 in 20. Rather than read the picture's size here with an
image library, it is tried, and a refusal sends the document instead, as
before. The owner's log says *"telegram: receipt.jpg went as a file, not
a photo — …"*. Over 10 MB isn't tried.

## A conversation as a PDF

```
/chats export 2 pdf     that one as a PDF, to share
```

**THE BROWSER THAT IS ALREADY HERE PRINTS IT.** A PDF library draws the
letters it has fonts for, and the first Hindi answer or emoji is a row
of boxes. That's why the home page used the browser's print window and
not a library. Dvara does the same, without the window: the conversation
is written as a small HTML page (title, when, then You and the agent turn
by turn — the home page's printed layout), and Chrome, headless, prints
it (`--print-to-pdf`). Sarathi's image already ships Google Chrome for
the browser tools, and a desktop has its own, so nothing new is
installed. Which browser: `YANTRA_BROWSER_EXECUTABLE` when it names one
(the browser tools' own setting, which the image sets), else the first of
`sarathi-browser`, `google-chrome`, `chromium` on the PATH. `printed.py`.

**ONLY WHAT THE MARKDOWN FILE HOLDS.** The person's words, the agent's
answers as written, and the tools' names — never what a tool returned.
The same walk as Yantra's `export_markdown`. Answers keep their Markdown
marks rather than being half-read by a renderer of our own.

**A PAGE WITH NOTHING TO FETCH.** Every word is escaped, there is no
script, and the page's own policy (`default-src 'none'`) forbids loading
anything. Chrome runs with a throwaway profile, gone afterwards, and
without its sandbox, as Playwright runs it for the browser tools (a
container runs as root, where Chrome refuses the sandbox). That is why
the page itself is the wall.

**ON THEIR CLOCK.** The date under the title is in the person's own time
zone ([note 66](66-their-own-clock.md)) when they have one.

**NO BROWSER, THE MARKDOWN FILE, AND WHY.** With no browser, or one that
fails or takes over a minute, the person still gets the conversation —
as the Markdown file — with *"I couldn't make a PDF where I run (it
needs a browser here), so this is the Markdown file."* The owner's log
names the reason.

The PDF is kept in the person's folder under `shared/` like the Markdown
file, named the same with `.pdf`. A page asks for it with
`GET /web/chats/ID/export?as=pdf` (503 when there's no browser).

## Live receipt

The scratch Dvara of [note 68](68-what-you-turned-down.md), on
`qwen3.8:latest`, with this machine's `/usr/bin/google-chrome`:

```
$ dvara … say "/chats export 1 pdf"
Here is “Hi! I just moved to Pune last month, and my dog Bruno hates the monsoon. Any in…” as a PDF, to share: your words, my answers and the names of the tools I used (never what they returned). It's kept in your files too, as shared/2026-10-25-hi-i-just-moved-to-pune-last-month-and-my-dog-br.pdf.
[files]
  file: …/state/work/guest/greeter/shared/2026-10-25-hi-i-just-moved-to-pune-last-month-and-my-dog-br.pdf
```

23 KB, one A4 page; `pdftotext` read the title, *Sun 25 Oct 2026, 10:03
· on here · qwen3.8:latest*, and both turns under YOU and GREETER. The
same conversation over `GET /web/chats/ID/export?as=pdf` came back as
`application/pdf`, the same 22,966 bytes. A made-up conversation with
*नमस्ते*, an emoji and a `<script>` in the question printed in 1.4 s:
the Devanagari and the emoji drawn, the script shown as text.

The photo half isn't run against a real bot here: the fake Telegram in
the tests answers as Telegram does, including the 400 for a picture it
won't take as a photo.

## What the tests hold

`tests/test_photos_and_pdf.py`: a picture in a notice goes as a photo,
caption and all; a file that isn't a picture is still a document; a
picture Telegram refuses as a photo arrives as a document; one over the
photo limit isn't tried as one; `/file NAME` for a picture sends the
original document. The PDF is printed from the words only, escaped, with
nothing to fetch, kept in `shared/`; a tool's output never reaches the
page; with no browser the Markdown file comes and says why; the page's
`?as=pdf` answers with a PDF; and a real browser, where there is one,
prints Devanagari and an emoji.

## Not here

* **The answers' Markdown, read.** Bold, lists and headings print as
  their marks. A renderer that got them half right would be worse than
  none; the home page's print does render them.
* **A PDF in the terminal or on Yantra's page.** Both have a browser in
  front of them, and its print window already does this.
* **A photo album.** Several pictures in one answer go one by one, not
  as one `sendMediaGroup`.

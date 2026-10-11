# 36 — which way it came in

*[Note 29](29-the-owners-page.md) put every turn on the owner's page.
[Note 34](34-a-chat-on-a-page.md) added a second way in that wasn't
Telegram, and [note 17](17-nobody-wrote-first.md) a third that nobody
typed. This note makes each turn say which of them it came by.*

## The problem, as you would meet it

Your agent did something odd at 3 a.m. You open the page and find the
turn: owner → minder, two tools, a cost. Was that you on Telegram,
half asleep? The page chat on your laptop? A schedule Samay ran? Or
something you typed at the terminal while testing? The row couldn't
say. Every way in ends in the same `Service.deliver`, and the row only
kept `unattended` and a thread name you never see.

## One word, written where the turn begins

Every run now has `came_by`: `telegram`, `web`, `samay`, `cli` or
`http`. The page shows it as a label at the front of each turn and adds
a third filter, **Came by**, beside Person and Agent. `dvara runs`
prints it as a column and takes `--came-by WAY`.

THE CHANNEL SAYS IT, NOT THE THREAD. Each way in names itself when it
calls `deliver`: a turn that came `via` a channel takes the channel's
kind, the web chat says `web`, the terminal says `cli`. Over HTTP a
caller may name itself — Samay sends `"came_by": "samay"` — and one
that says nothing is `http`. An answer to a held turn is its own turn
and is marked with the way the ANSWER came, since that's what started
it.

`dvara say --as telegram:8675309` is still `cli`. It runs as the person
that Telegram id belongs to, but you typed it at a terminal, and the
label says where the turn came from, not whose it was.

A CALLER'S WORD IS A WORD. HTTP accepts one short lowercase word
(`[a-z][a-z0-9_-]{0,23}`) and refuses anything else with a 400. The page
shows a word it doesn't know as-is, so a bridge of your own can label
its turns. Markup or a sentence would go straight onto the owner's page,
so it isn't accepted.

## Old rows: only what they already said

The column is added the way every other one was: added, never
rebuilt. Once, when it's added, rows whose thread already recorded the
way in are filled in. A channel's turn is keyed `telegram:…` or
`web:…`, and Samay names every run's thread `samay-<schedule>-<time>`
and marks it unattended. Everything else stays empty and shows no
label. A turn typed at the terminal before this existed looks exactly
like one from a Python caller, and guessing would put a wrong label
into an audit.

## Live receipt

A scratch door on `gemma4:12b`: one turn from the terminal, one over
HTTP the way Samay sends it, one from the page chat, then a caller that
tried to name itself with markup:

```
$ dvara --provider ollama --model gemma4:12b say --actor owner --agent greeter "say hello in five words"
I say hello to you.
[end_turn · $0.0000 · 83in/1168out · run 28b6cba2d71a]

$ curl … /message -d '{…, "unattended": true, "came_by": "samay"}'
end_turn Good morning.
$ curl … /web/message -d '{"actor":"owner","agent":"greeter","text":"one word for blue"}'
$ curl … /message -d '{…, "came_by": "<b>"}'
{"detail":"came_by is one short lowercase word, like samay"}

$ dvara runs
2026-10-11 01:00  web       owner/greeter  end_turn         $0.0000  'one word for blue'
2026-10-11 01:00  samay     owner/greeter  end_turn         $0.0000  'good morning in one line'
2026-10-11 00:59  cli       owner/greeter  end_turn         $0.0000  'say hello in five words'

$ dvara runs --came-by samay
2026-10-11 01:00  samay     owner/greeter  end_turn         $0.0000  'good morning in one line'
```

On the page, each card starts with a label (Telegram, Web, Samay, CLI),
and **Came by: Samay** leaves only the schedule's turn.

## What was deliberately not built

* **Telegram's label from a live chat.** The code path is the one every
  Telegram turn has always taken (`via=Channel("telegram", …)`), and a
  test covers it. This receipt didn't send a real Telegram message.
* **Samay's direct road.** A schedule that runs Yantra without Dvara
  never becomes a Dvara run, so it has no row to label. Samay's own log
  is where that one lives.

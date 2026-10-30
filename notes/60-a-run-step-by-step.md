# 60 — A run, step by step

The ledger (note 01) keeps a run's shape on purpose: who, which agent,
what it cost, the tools by name and which were refused. Never what a
tool was given or what it read, because a ledger that grows with
arguments ends up holding a file, a key, or somebody's afternoon.

So when a run goes wrong, the ledger says *which tools*, not *what
happened*. What happened is in the run's conversation, in the session
store, where it always was. Yantra now notes each step's time, its wait
for a yes and who gave it, beside that conversation (its note 145).
This note is how Dvara finds a run's own turn there, and who may see
what.

## A run finds its own turn

`_run_turn` sets `agent.turn_tag = run.id`. Yantra files the turn's
notes under that tag, so `runsteps.timeline` opens a run's own turn by
its id, never by position in the conversation. A run from before the
tags is found by its message. If its conversation is gone, the run says
so: a schedule's thread is let go a week after it ran (`tidy`), and a
person's is gone after `/chats delete`. One whose chat only moved on
(`/new`, another conversation opened) is still in the person's kept
conversations under its run id, and the page's **Steps** find it there
([notes/71](71-one-conversation-two-chats.md)).

## Who sees what

| reader | what it gets |
|---|---|
| the door, `GET /runs/{id}/steps` (its own token) | the whole turn: what each tool was given, what came back, pictures, the answer. Samay shows its runs from here |
| the owner's page, the owner's own runs | the same, and **File for a bug report** |
| the owner's page, anybody else's run | its **shape**: which tools, when, how long, who said yes, what was refused. Not the arguments, results, pictures, message or answer |
| a person in their chat, `/steps [N]` | their own conversation's last turn (or turn N), as text |

The third row follows the page's own rule (note 29): what a person typed
and what their agent read are theirs. A step-by-step view holds far
more of that than a reply does: a mail, a page, a phone's screen.

**Steps** sits on each run card on the page. `/steps` is in Telegram's
menu as *What my last answer did, step by step*. It's answered at once,
without the model.

## Receipt

From the tests (`tests/test_run_steps.py`), on a scripted model:

```
read a.txt   -> run 1: [read_file {"path": "a.txt"}], answer "first"
and now?     -> run 2: [], answer "second"
a guest's run on the owner's page: tools named, arguments None, message None
the guest's run as a file: 403 "only your own runs make one"
/steps       -> "1. read_file ... -> ..." and no model call
```

## What was deliberately not built

* ~~**The guest's own Steps on their page.**~~ Built: every answer in
  Sarathi's home chat has **Steps** folded under it, the person's own run
  whole, with its file for a bug report. The web channel keeps each
  answer's run id on its line and serves it only to that line's person
  (`GET /web/steps?actor=&line=`, `/web/steps/export`); the id never
  reaches the page.

  Live, a scratch Dvara on `qwen3.8:latest` and a scratch home page: the
  answer *"Couldn't fetch it: this session is running unattended …"*
  opened to `1 step · 19s · end_turn`, `1. web_fetch 18:37:08 · refused
  (unattended)`, and its file began *"This file holds what the agent's
  tools were given and what they read"*.

  A step's pictures (a screenshot, the phone's screen) come too: the
  steps say each one's kind, and the page fetches each by its line,
  step and number (`GET /web/steps/picture?actor=&line=&step=&n=`), for
  that line's person only and only as a PNG, JPEG, GIF or WebP. A step
  folded shut fetches none.
* **A step's pictures on Telegram.** `/steps` is words, and a picture
  per step would be a burst of photos in a chat.

# 28 — starting over

*[Note 24](24-a-conversation-nobody-will-continue.md) let go of the
conversations a program started, once nobody would continue them. A
person's own chat it never touches, and still doesn't. This note gives
the person a way to let go of it themselves.*

## The problem, as you would meet it

A chat with an agent is one conversation for as long as the chat lasts.
Each message you send, each answer, and each tool result goes back to
the model on the next turn. That's what lets *"and the one before
that?"* work. When it grows too long, Yantra summarizes the oldest part
rather than dropping it, so the summary keeps what happened.

That also lets a habit stick. You ask minder for the latest post from an
account on X, and it reads the page with `web_fetch`. That works. You ask
about another account, and it does the same. Then the package is given
X's own tools, which read the site signed in as you, and its prompt says
to use them for X. You ask again, and it still calls `web_fetch`. The
earlier turns in the conversation, and the summary of them, say that
`web_fetch` on x.com worked, and a small local model follows what already
worked in front of it. The same question in a conversation with nothing
behind it went straight to `x_open`.

You had no way to clear that from the chat. Telegram's "Clear history"
clears your phone's copy; the bot is never told.

## One word, and it is the person's

```
/new        start this conversation over
```

**THE PERSON'S WORD, NOT THE MODEL'S.** Like `/files`
([note 26](26-the-file-itself.md)) and `/accounts`
([note 20](20-signing-in-from-the-chat.md)), it's answered by dvara before
any turn. No model reads it, nothing is spent, and it works the same
whatever model is behind the door. Asking a model to "forget everything"
puts the request inside the very conversation it's meant to clear.

**THE CONVERSATION GOES, NOTHING ELSE DOES.** Only the saved
conversation goes, through Yantra's `forget`, the same call that lets
go of finished scheduled runs. Everything else stays:

* the ledger: every run's message, reply, tools and cost, so `dvara runs`
  and the day's allowance are unchanged;
* the person's folder with this agent and the files in it
  ([note 25](25-the-persons-folder.md));
* their schedules and their accounts, which were never part of a
  conversation.

A question the conversation was still holding for them (a held turn,
[note 16](16-kept-for-when-you-are-back.md)) goes with it. A new message
would have set it aside anyway.

**NEVER UNDER A RUNNING TURN.** A turn still working on the conversation
would save it again when it finished, and the person would think they
had started over when they hadn't. So while one runs, `/new` says *"I'm
still working on your last message. Send /new again once I've answered
it."* and changes nothing.

`/start` mentions it: *"Send /new to start our conversation over."*

## Live receipt

`qwen3.8:latest` through Ollama, the `greeter` example, `dvara say`:

```
$ dvara say --actor owner --agent greeter "My name is Mahen and my favourite colour is teal."
[end_turn · $0.0000 · 87in/48out · run fe0c38de5da8]
Welcome, Mahen, and teal is a fine choice.

$ dvara say --actor owner --agent greeter "What is my favourite colour?"
[end_turn · $0.0000 · 119in/52out · run 2a697b599e77]
You told me earlier that teal is your favourite colour.

$ dvara say --actor owner --agent greeter "/new"
[new]
Starting fresh: I won't remember what we said before. Your files, schedules and accounts are all still here.

$ dvara say --actor owner --agent greeter "What is my favourite colour?"
[end_turn · $0.0000 · 81in/68out · run 9c68800ecb70]
I have no idea—no one has ever told me.

$ dvara runs
2026-10-06 23:33  owner/greeter  end_turn         $0.0000  'What is my favourite colour?'
2026-10-06 23:32  owner/greeter  end_turn         $0.0000  'What is my favourite colour?'
2026-10-06 23:31  owner/greeter  end_turn         $0.0000  'My name is Mahen and my favourite colour is teal'
```

The same question, 119 tokens in before and 81 after: the model was
shown only the question. `/new` isn't in the ledger because it wasn't a
turn, and the three turns that were are all still there.

## What was deliberately not built

* **Starting over after a quiet spell.** A conversation that clears
  itself after a day of silence would break *"and what about the other
  one?"* the next morning, and the person would have no way to tell which
  kind of morning it was. Starting over is theirs to ask for.
* **`/start` as starting over.** Telegram sends `/start` when someone
  first opens the bot, and again after they delete the chat and press
  Start. That second case reads like starting over, but the first is a
  greeting, and the bot can't tell them apart. `/start` stays an
  introduction that mentions `/new`.
* **Keeping the old conversation somewhere.** The ledger already keeps
  what was said and done. A second, archived copy would be a store that
  nothing reads.

## What is not here yet

* **Telegram's command menu.** The bot doesn't register its words with
  Telegram (`setMyCommands`), so typing `/` shows no list. `/start` names
  them instead.

# 80 — One menu, and a Keep button

## The problem, as you would meet it

A look back after a quiet chat put this under the owner's 🔔 on
Sarathi's home page:

> minder: Looking back over the conversation we just ended, I noticed
> this about you: 1. … a recurring "Akshi Math" session at Mathnasium
> (Mondays 7–8 pm) … Send /remember with the numbers to keep them …

They asked how to run that. The answer was to type `/remember 1` into
the chat, but nothing on the page said so: typing `/` there listed
eleven words, and `/remember` wasn't one of them. Telegram's `/` menu,
for the same agent, had it, along with `/household`, `/voice`,
`/accounts`, `/connect`, `/carry`, `/steps`, `/tests` and `/files`.

There were two causes. Telegram's menu was built here, for each agent,
from what its package can do ([note 28](28-starting-over.md)). The
page's was a short list written once in its own script, and every word
added after that reached Telegram and never the page. The words always
worked when typed on the page, because its chat runs the same turn
Telegram's does; only the menu was out of date. And a notice that asks
you to type a number is asking a lot. A skill offered on a notice
already had **Keep** and **Not now** ([note 42](42-seeing-the-work.md));
a fact noticed about you only had words.

## One list, asked for

**ONE LIST, ASKED FOR.** The menu moved out of `telegram.py` into
`menu.py`, unchanged: `words_for(service, spec)` is the bot's menu, as
it was. The web channel's look now hands the same list to a page,
`{"words": {agent: [["/word", what it does], …]}}`, for every agent the
person may use. The page draws its + menu and its `/` list from it,
names the words it knows in its own way, and keeps its two extras,
**Teach…** and **Turned down…**, which open boxes on the page. A word
added to `menu.py` is on both roads at once.

**ON THE FIRST LOOK, NOT EVERY POLL.** A page looks every few seconds.
The words come only on the look with `after=0`, the one a page makes
when it opens, since working out whether the phone is let in builds a
tool registry for each agent. A package that changed shows its new words
when the page is opened again, as Telegram's menu changes at the bot's
next start.

**AN AGENT WHOSE PACKAGE WON'T LOAD IS LEFT OUT OF THE LIST, NEVER THE
LOOK.** The page falls back to its own short list for that one.

## Keep and No, by the words

**THE NOTICE CARRIES WHAT IT LISTED.** A look back's notice, whether at
`/new` ([note 51](51-starting-over-at-once.md)) or after a quiet while
([note 39](39-while-nobody-is-writing.md)), now carries
`remember: {agent, items: [fact, …]}` beside its words. `GET
/web/notices` adds `waiting`: those of its items still on the person's
list now. The page draws **Keep** and **No** beside each one waiting,
and **Keep all** and **None of these** when there are several.

**BY THE WORDS, NOT A NUMBER.** A button sends
`POST /web/remember {actor, agent, keep: [fact, …]}` (or `decline`).
A notice is read later than it was sent. Keeping one moves the rest up,
and a newer look back replaces the list, so the number printed in an old
notice can belong to a different fact by the time it is pressed.
`Service.answer_offered` finds the numbers again, now, by exact words,
then says `/remember N` or `/remember not N` exactly as typing them
would. A fact no longer waiting is never matched to another one. The
answer is *"That's already answered: nothing from this notice is
waiting any more."* The match is exact, not `same`'s looser "one head
inside the other": a button that keeps the wrong fact is the failure
this exists to prevent.

**ONLY THEIR OWN.** The actor comes from the page's sign-in (Sarathi
sets it; the browser's is ignored), and the numbers are found in that
person's list alone. The owner pressing with the guest's words reaches
the owner's list and finds nothing.

## What it costs

The words still say what to type, so Telegram and a phone's ntfy notice
are unchanged: on those, a memory notice is still answered by typing
`/remember 1`. Buttons there would need marks like the skill offer's
(push.py) and callback handling; they were left for when someone asks.

## Live receipt

A scratch Dvara (`serve --web --quiet-for 0.5`), the `greeter` package
with `[memory] via = "local"`, on `qwen3.8:latest`. The page's first
look:

```
$ curl -s -H "$AUTH" "localhost:8798/web?actor=owner&after=0"
{..., "words": {"greeter": [["/new", "Start our conversation over"],
  ["/carry", ...], ["/steps", ...], ["/chats", ...], ["/tests", ...],
  ["/doctor", ...], ["/memory", "What I remember about you"],
  ["/remember", "Keep what I noticed: /remember 1 2; /remember declined"],
  ["/household", ...], ...]}}
```

One message (*"My daughter Akshi goes to Mathnasium every Monday 7 to 8
pm, and I live in Cary, NC"*), then quiet. The look back's notice:

```
"text": "greeter: Looking back over our conversation, I noticed this about you:\n1. Lives in Cary, NC (...)\n2. Their daughter Akshi attends Mathnasium every Monday from 7 to 8 pm, so Monday evenings are occupied for the person.\nSend /remember ...",
"remember": {"agent": "greeter",
             "items":   ["Lives in Cary, NC (...)", "Their daughter Akshi attends Mathnasium ..."],
             "waiting": ["Lives in Cary, NC (...)", "Their daughter Akshi attends Mathnasium ..."]}
```

The second fact's Keep, the same press again, then the first's No:

```
{"said":"Kept:\n- Their daughter Akshi attends Mathnasium every Monday from 7 to 8 pm, so Monday evenings are occupied for the person.","waiting":[]}
{"said":"That's already answered: nothing from this notice is waiting any more. Send /remember to see what is.","waiting":[]}
{"said":"I won't offer these again:\n- Lives in Cary, NC (...)\n(A slip? /remember declined, then /remember undo 1.)","waiting":[]}
```

The store then held the Mathnasium fact alone. Kept second while
numbered 2, it was found by its words; typing `/remember 2` after the
first had gone would have named nothing.

Sarathi's home page in a headless browser, against the same Dvara:
+ listed *New chat, Carry on, Steps, Conversations, Tests, Check what's
mine, Memory, Remember, Turned down…, Household, Tools, Voice*; typing
`/re` listed `/remember — Remember`. A second look back's notice (*is
vegetarian*, *Arjun has swim practice every Saturday at 9 am*) showed
**Keep** and **No** under each and **Keep all** / **None of these**;
pressing the first Keep left the swim fact with its buttons and *Kept: -
The person is vegetarian, …* under it, and the older notice said
*Answered: nothing here waits any more.* No page errors.

## What is not here yet

* **Keep and No on Telegram and on a phone's ntfy notice.** The page
  has them; the other roads still take the typed word.

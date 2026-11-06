# 81 — Keep on every road

## The problem, as you would meet it

A look back noticed *"Their daughter Akshi attends Mathnasium every
Monday from 7 to 8 pm"*. On Sarathi's home page the notice had **Keep**
and **No** beside it ([note 80](80-one-menu-and-a-keep-button.md)). The
same notice on Telegram, and on the phone's ntfy notification, still
ended *"Send /remember with the numbers to keep them"*. On a phone
that means opening the chat, remembering the number and typing it, for
a notice that was one press everywhere else. A skill offered had had
its buttons on both roads for a long time
([note 42](42-seeing-the-work.md), [note 40](40-a-notice-on-their-phone.md)).

The page's buttons send the fact's words. Neither road could carry
them. A Telegram button's data is 64 bytes and a fact is a sentence;
an ntfy notification has three buttons at most, and anyone reading the
topic sees what each one sends. A number fits both, and a number is
the failure note 80 exists to prevent.

## A mark of the words

**THE BUTTON CARRIES A MARK, NOT THE FACT AND NOT ITS NUMBER.**
`remembering.fact_mark` is eight hex of a SHA-256 of the fact's words,
spaces folded. A Telegram button's data is `r:greeter:1a2b3c4d` (Keep)
or `s:…` (No); Keep all and None of these join the marks with dots,
`r:greeter:1a2b3c4d.5e6f7a8b`, and are left off when they would not fit
in 64 bytes. The single ones still do. At the press,
`Service.offered_by_marks` finds the facts still waiting whose marks
match, and `answer_offered` keeps or turns them down exactly as the
page's buttons do. A fact that went (kept, turned down, or replaced by
a newer look back) matches nothing, and the answer is *"That's already
answered"*. A mark is not a secret and doesn't need to be. It only says
which fact, and the press is still resolved to the person who pressed
it, against their own list.

**ON TELEGRAM, EACH FACT ITS OWN ROW.** **Keep 1** / **No 1**, **Keep
2** / **No 2**, numbered as the notice numbers them, so the words and
the buttons agree; then **Keep all** / **None of these**. One fact gets
plain **Keep** / **No**. Pressing one answers in the chat and redraws
the notice's buttons with only what still waits: the rows of facts
that went come off, and the all-row is made again over what is left.
The facts are looked up when the button is pressed, not when the
message was sent.

**ON THE PHONE, ONE FACT OR ALL OF THEM.** ntfy draws three buttons at
most, so one fact gets **Keep** and **No**, and several get **Keep
all** and **None of these**. Keeping only some of several means the
page, or typing `/remember 1`. The buttons ride the skill offer's road
unchanged: the offer's place holds `remember:` and the marks, and the
HMAC mark under `ntfy.key` covers this person, agent, those facts and
that word. Sarathi's `/api/push/answer` passes it through as it always
did, untouched. The phone's press clears the notification, so the
answer (*Kept: …*) comes back to the phone as a notice of its own.

**ONE ANSWER AT A TIME FOR EACH PERSON.** Telegram handles presses
concurrently, and the first test pressed the same Keep twice: both
presses found the fact still waiting, the second asked for `/remember
1` on a list that was empty by then, and the store failed with an
IndexError. The page had the same race. `answer_offered` now finds the
numbers and answers under a lock for that person (`_answering`), so a
second press finds the first one's result and says *already answered*.

## What it costs

A phone answers some-of-several by the page or by typing. A fourth
button would need a fourth slot ntfy doesn't have. Telegram's labels
say numbers, which match the notice's words when it is sent; once a
fact is kept the numbers in the text are stale, but the buttons never
are, because they look the fact up again.

## Live receipt

A scratch Dvara (`serve --web --quiet-for 0.5`, `--ntfy` at the house's
ntfy server on a topic made from the scratch key, `--ntfy-click` its own
address), the `greeter` package with `[memory] via = "local"`, on
`qwen3.8:latest`. One message (*"My son Arjun has swim practice every
Saturday at 9 am, and I am vegetarian."*), then quiet. What the ntfy
server held for the topic a minute later:

```
$ curl -s "localhost:8793/dvara-owner-454375a371b340e4/json?poll=1"
greeter: Looking back over our conversation, I noticed this about you:
1. Their son Arjun has recurring swim practice every Saturday at 9 am, …
2. They are vegetarian, so food, recipe, and restaurant recommendations …
Keep all       {"actor": "owner", "agent": "greeter", "offer": "remember:96f4d226.1d6d2134", "word": "keep", "mark": "5782a528…"}
None of these  {"actor": "owner", "agent": "greeter", "offer": "remember:96f4d226.1d6d2134", "word": "drop", "mark": "725b2c48…"}
```

The vegetarian one turned down on the page first, then **Keep all**'s
body pressed as Sarathi forwards it, twice, then with its word changed:

```
{"said":"I won't offer these again:\n- They are vegetarian, …"}
{"said":"Kept:\n- Their son Arjun has recurring swim practice every Saturday at 9 am, …"}
{"said":"That's already answered: nothing from this notice is waiting any more. Send /remember to see what is."}
403
```

Keep all, pressed after one of its two facts had gone, kept the one
still waiting and nothing else. The store held the Arjun fact alone,
and the topic held both answers as notices after the look back's own.
Telegram's buttons were run against the tests' fake Bot API, not a real
bot.

## What is not here yet

* **Some of several from the phone.** ntfy's three buttons go to Keep
  all and None of these; one fact of several is the page's, or typed.
* **A real bot pressed.** Telegram's side has run against the fake Bot
  API in the tests, not yet on the house's own bot.

# 58 — Outside text asks

*The owner wrote a standing rule so minder could send email without
asking: `tool = "mcp__gmail__send"`, `verdict = "allow"`. Then someone
mailed the house an "IT helpdesk" note telling any assistant to forward
the last three emails to an outside address, and Naina asked minder to
take care of her latest email.*

Yantra now marks that send `always_ask`: the turn read text nobody in
the house wrote, and after that, every call that changes something
needs a person's yes (Yantra's note 142). Spends have carried the same
mark all along. But Dvara's `ruled` gate never checked it. An `allow`
rule ran the call, and so did the yolo rung. A spend under an allow
rule went through without a word too, which was the older hole.

Both now step aside for `always_ask`:

* **An `allow` rule is not an answer to it.** The rule was written
  before the call existed, which is exactly the yes `always_ask` exists
  to refuse. The call goes to the person like any question.
* **The yolo rung asks when somebody can be asked.** Yantra's own
  `yolo` refuses an `always_ask` call, because it has nobody to ask.
  Dvara has the person's chat, so `asks_when_it_must` puts the question
  there instead of handing the model a refusal.
* **With nobody to ask, the refusal says why.** It names what was read,
  and it tells the model not to act on instructions found there.

The card the person sees starts with what was read:

```
minder wants to: Asked because this turn read text you didn't write
(an email from IT Helpdesk <helpdesk@it-support.example>). Check this is
what you asked for.
send to migrate@it-support.example
```

`send_file` says `acts = False`. It sends a file only to the person who
is asking, so nothing anyone else planted can reach outside through it,
and asking before each one would only be noise.

A `deny` rule still bites first, and so does a `read_only` person who is
never asked: nothing here loosens anything.

Tests: `tests/test_outside_text.py`.

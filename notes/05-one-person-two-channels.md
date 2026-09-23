# 05 — one person, two channels: an actor is a person, not a seat

*The channel was next. It still is — but a bot cannot be written until
this is settled, because the first line of a Telegram adapter has to
decide who the person on the other end of a chat id is, and dvara had two
different answers to that. This note picks one, and it is the last thing
standing between [note 02](02-a-question-that-can-wait.md)'s escalation
and somewhere real to escalate to.*

## The problem, as you hit it

You have a service running. You talk to it from a terminal and through a
small HTTP bridge. Today you decide to add a bot, and the first thing the
bot needs is a table:

```python
ACTORS = {8675309: "mahen"}     # telegram user id -> dvara actor
```

Three lines in, and something is already wrong. That table is an
*assignment* — it decides who a message is allowed to be — and the whole
of [`actors.py`](../src/dvara/actors.py) exists on the premise that
assignments live in one file the owner reviews. Half of the decision is
now in a bot's environment, where nobody diffs it.

So you do the honest thing instead, and write the person down twice:

```toml
[actor.mahen]
max_usd_per_day = 2.00

[actor.mahen_tg]        # the same human being
max_usd_per_day = 2.00
```

And now you own a service where **that person's daily allowance is
$4.00**.

That is the argument. Not the queues — the money. An owner wrote one
number, reviewed one number, and the ceiling doubled because they
installed a bot. Everything else that splits along with the actor id is
real and none of it is as bad as a ceiling that is not one:

| keyed on the actor id | what two ids does to it |
|---|---|
| `runs.spent_since(who.id, ...)` | two allowances out of one number |
| `desk.pending(actor)` | a question raised in one place is invisible in the other |
| `actor.agents` | two whitelists to keep in step, and no error when they drift |
| `actor.permissions` | ditto, for the rung that decides whether you get asked at all |

## An actor is a person; a channel is a way of reaching them

```toml
[actor.mahen]
max_usd_per_day = 2.00

[[actor.mahen.channel]]
kind = "telegram"
id   = 8675309
```

One person. One allowance. One queue of questions. Several doors.

The table reads in both directions, which is exactly why it is one table
and not two:

* **Inbound**, `book.resolve("telegram", 8675309)` hands back the actor.
  The adapter brings a native id and gets a name; there is no argument in
  that signature through which a message could nominate who it is.
* **Outbound**, the same `id` is the address a question is delivered to.

Those two being the same string is not a coincidence worth designing
around — a channel that cannot send you a message at the identity it
received one from is not a channel a person can be *asked* on, which is
this service's whole reason for knowing about channels at all. (Telegram
makes it literal: in a private chat, the user id and the chat id are the
same number.)

**dvara learns that channels exist. It never learns which ones.** There
is no list of known kinds anywhere in the service, and no branch on the
string `"telegram"`. `kind` is checked for *shape* — a lower-case token,
the same rule Yantra applies to refusal codes, so it can be a dict key
and a log field without being quoted by everyone downstream — and
otherwise passed through untouched. A second channel is an adapter and
three lines of TOML.

### One identity, one person, checked at load

```
error: actors.toml: telegram id '8675309' is claimed by both
       [actor.mahen] and [actor.guest]; one channel identity is one
       person, and there is no right way to guess which
```

First-wins would hand somebody another person's history because of the
order two tables happen to appear in — the same failure
[`keys.py`](../src/dvara/keys.py) percent-escapes its components to
prevent, arriving through a different door. Both names are in the error
because the owner has to know which two lines to look at.

Against a real file, with `qwen3.8-64k:latest` on Ollama behind it:

```
$ dvara say --as telegram:8675309 --agent greeter "who are you, in one sentence?"
[end_turn · $0.0000 · 83in/59out · run bb7bd7b7a9d3]
I'm the greeter at the door, here to point you in the right direction.

$ dvara say --as telegram:999 --agent greeter "hello"
[refused]
you are not on this service's list of people

$ dvara runs
2026-09-17 17:55  mahen/greeter  end_turn         $0.0000  'who are you, in one sentence?'
```

The turn ran as `mahen` — the run record says so — and nobody named
`mahen` anywhere on that command line. An unassigned id gets the same
sentence an unknown actor gets, and learns nothing about who is on the
list.

Kinds are separate namespaces, so `telegram:1` and `signal:1` are two
different people and no coincidence joins them.

```
$ dvara --actors dupe.toml agents
error: dupe.toml: telegram id '8675309' is claimed by both [actor.mahen]
and [actor.guest]; one channel identity is one person, and there is no
right way to guess which
```

## The cost of joining the actor, paid here rather than found later

Unifying the person creates one problem, and it is worth being honest
that it is a *new* one:

    mahen + greeter + thread "42"     from Telegram
    mahen + greeter + thread "42"     from an HTTP bridge

Same key. Same conversation. Two channels, interleaved into one history.

Before this note, two actor ids kept those apart — **by accident**, which
is the worst way for a correctness property to hold, because nothing
records that it is load-bearing and removing the accident removes the
property. Note 01 already argued that `(actor, thread)` alone was wrong
and that discovering it later would be a migration. This is the same
argument one level down.

Three ways out, and the one that was taken:

1. **Tell adapters to namespace their own threads.** Nothing to build,
   nothing enforced, and the failure is silent for exactly one person —
   the one who uses two channels, who is the owner.
2. **A fourth component in the session key.** Most explicit; orphans
   every checkpoint already written.
3. **The service qualifies the thread on the channel path.** A turn that
   arrived through `resolve()` is keyed under `kind:thread`.

Three, because it is enforceable and it costs no migration. The path that
has a channel to name uses it; a caller naming an actor directly is
untouched, and so is every key already in the store:

```
$ sqlite3 state/sessions.sqlite3 "select distinct session_id from checkpoints"
mahen/greeter/telegram%3Acli
```

The key stays three components and stays readable, which is what
[`keys.py`](../src/dvara/keys.py) chose it for — an owner should be able
to answer their own question with one `select` and no decoder ring. A
caller naming an actor directly still writes `mahen/greeter/cli`.

A rule that holds only when every adapter remembers it is not a rule.

**Two channels of one person are still two conversations**, and that is
the intended reading rather than a limitation being excused. Thread
identity is channel-native — note 01 refused to invent it, because a
service that renames threads cannot be correlated with the channel's own
logs when something goes wrong. Continuity *across* channels would be a
thread a person names deliberately, not two chats silently spliced.

## The queue is the person's, not the channel's

The identity half alone would fix the allowance and leave the question
where it was: `AskDesk` held **one** notifier, which is right for a
service with one way in and quietly wrong the moment it has two. A
question raised by a turn that came in over HTTP had nowhere to go but
the HTTP poller — with the person sitting in a chat app the service could
have reached.

```python
desk.route("telegram", telegram_notifier)
desk.route("signal", signal_notifier)
```

A question is **put to an actor** and **delivered to every channel that
actor is reachable on**. An answer names the person and the question, and
is not obliged to come back the way it went out. Ask on the laptop,
approve from the phone.

Four consequences, each one a test:

**A delivery that fails is still a denial — but "a delivery" is now "all
of them".** [Note 02](02-a-question-that-can-wait.md) refused
immediately when the notifier raised, because nobody was at the other end
and the deadline would just be two silent minutes. With a person
reachable two ways, refusing on the first exception would let the *least
reliable* channel decide for the person who did get asked. One bridge
down while another is up is a question that arrived; the wait goes on.
Only when nothing got through is there nobody there.

**Nothing to deliver to is still not a refusal.** A desk with no routes
and no catch-all delivers nothing and waits — that is note 02's polling
service, where `GET /asks` is how the question gets found. Denying
because no *push* route existed would have broken the one front end that
never had one.

**`notify` survives untouched, as the catch-all.** The terminal notifier
both asks and collects; it is the only place a question could possibly
go, and handing it an address it cannot use would be noise. It registers
no kind and gets everything.

**The address is delivery's business and nobody else's.** It rides on the
`Ask` as `to`, one copy per channel, and `as_dict` leaves it out — an
unfiltered `GET /asks` would otherwise hand every adapter every person's
chat id. A poller already knows where it is polling from.

One question, raised by a turn that named an actor and no channel at all,
with the same local model behind it:

```
-> delivered to 8675309: write_file | NEW FILE hello.txt (1 lines)
-> delivered to +1555: write_file | NEW FILE hello.txt (1 lines)
one question, addressed to mahen
reply: Done.
```

Two deliveries, two addresses, one question — and it was answered from
*neither* channel, the way `POST /asks/{id}` answers one. That is the
whole shape in four lines: the question knows the person, the delivery
knows the channel, and the answer only has to know the question.

## A bridge that carries no table cannot carry a stale one

The point of moving the mapping into the roster is lost if adapters have
to do the lookup themselves anyway, so all three endpoints that name a
person take either form:

```
POST /message   {"channel": {"kind": "telegram", "id": 8675309}, ...}
             -> {..., "actor": "mahen"}
GET  /asks?channel=telegram&channel_id=8675309
POST /asks/{id} {"channel": {...}, "approve": true}
```

Exactly one of `actor` or `channel` per request. Both is a 400 rather
than a precedence rule: honouring it would mean deciding which wins, and
then a bridge with a stale hard-coded actor id either quietly overrules
the roster or quietly does not, and nobody can tell which from outside.

`/message` answers with the actor it ran as, because a caller that
arrived with a channel identity has never seen an actor id and needs one
the moment the turn raises a question.

The bearer token still authenticates the **caller**, not the person —
unchanged, and the channel form does not weaken it. What changes is that
a trusted caller now has a way to say who is talking that it *cannot get
wrong*, and an owner who removes somebody from `actors.toml` has removed
them, rather than having removed them from one of two files.

## Proving the mapping before wiring a bot to it

```bash
dvara say --as telegram:8675309 --agent greeter "who are you?"
```

`--as KIND:ID` beside `--actor`, mutually exclusive, one of them
required. It exists because a bot that answers nothing tells you nothing
about *which* half is wrong — the token, the long poll, the mapping —
and this takes the mapping out of the list in one line. Split on the
first colon only: a kind is a token and cannot contain one, and plenty of
channels name people with strings that can (`matrix:@me:example.org`).

## What is deliberately not here

* **A channel as a permission dimension.** "Ask me on Telegram but not
  over HTTP" is a real thing to want and it is not a channel property; it
  is a rung, and the rung is per person. Revisit when somebody can say
  what it should mean for a question already in flight.
* **A preferred channel, or an order.** Every channel gets the question.
  Ranking them means deciding how long to wait before trying the next
  one, which is a second deadline living inside the first.
* **Withdrawing a delivered question.** Answer it on your phone and the
  Telegram message is still sitting there. Retracting across N channels
  needs a per-delivery handle the notifier hands back, and every adapter
  then has to implement editing. ([Note
  07](07-four-thousand-and-ninety-six.md) gives this its first real
  instance: the bot edits the copy that was pressed, and only that one.)
* **Secrets in `actors.toml`.** A chat id is an address, not a
  credential. The file holds no tokens, exactly as before, and it is
  still a thing you commit.
* **Merging two channels into one conversation.** Argued above: they are
  two threads, on purpose.

## What is not here yet

* ~~**A channel identity cannot be added without restarting.**~~ Shipped
  in [note 09](09-a-process-you-walk-away-from.md), once note 07 made it
  a real papercut rather than a theoretical one: the file is reread when
  it changes, and a file that has stopped parsing keeps the last good
  roster rather than locking its owner out.
* ~~**Nothing records which channel a question was delivered to**~~ --
  half shipped in [note 08](08-what-the-turn-actually-did.md), and the
  half that shipped is the better one: a `Run` records where an answer
  came BACK from rather than where the question went out to. Per TURN
  rather than per call, because concurrent gating and no id on
  `PermissionRequest` mean an approval cannot be pinned to the call it
  approved.
* **A notifier that hangs holds a delivery task for the whole deadline.**
  It is cancelled in the `finally`, so nothing leaks past the turn, but
  a slow channel cannot be given a shorter clock than a fast one.
* ~~**Locks are still never evicted**~~ — shipped in [note 11](11-only-while-somebody-is-waiting.md); unchanged from notes 01–03.
* **Still no channel.** That is the next note, and it is now the small
  one it was always supposed to be: a long poll, a notifier, a call to
  `answer`, and a 4096-character cap to think about.

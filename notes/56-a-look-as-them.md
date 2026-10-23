# 56 — A look as them

[Note 55](55-a-watch-for-one-person.md) gave Prahari's watches to one
person, named, because a watch's look ran this computer's Yantra with
this computer's accounts. A guest's watch for "new mail from the bank"
would have searched the owner's inbox and told the guest what it found.
That note listed two fixes and built the smaller one. This is the other.

## One tool, as the person

`POST /call` builds a person's agent the way a turn does, with their own
Setu folder ([note 19](19-their-own-accounts.md)) and the package's own
servers, and runs one tool once with no model:

```
POST /call  {actor, agent, tool, args, allow_tools}  -> yantra.call.v1
```

The answer is the shape `yantra --call` prints, so Prahari reads both
the same way. The rule is Yantra's own: a tool that reads, or the one
call the person granted word for word when they accepted the watch.
Both doors call the same function, Yantra's `calling.py`
([its note 139](https://github.com/kunwarmahen/yantra/blob/main/notes/139-one-tool-no-model.md)),
so a look through Dvara can't be let do what a look at the terminal is
refused.

Prahari sends every look of a Dvara-road watch here
([its note 02](https://github.com/kunwarmahen/prahari/blob/main/notes/02-a-watch-for-everyone.md)).
That also ends note 55's other compromise. On this road a look used to
be plain Yantra, because Prahari couldn't open a roster name. Now the
look is made with the watch's own agent, so a tool only that package
brings is there for its looks too.

## Not a turn

A look every half hour must not look like a conversation. So `/call`:

* asks no model, so no allowance is spent and no ceiling applies;
* writes no run. The person's page would otherwise fill with fifty looks
  a day that found nothing;
* has no history, no memory, no schedules, no phone, and no send_file.
  Its servers are the person's accounts and the package's own, the two
  things a look can read with;
* is unattended. A sign-in wall comes back in `needs_person`, never as a
  window opened for nobody, and Prahari pauses the watch and says so.

It works in the person's own folder for that agent, the same one their
chats use. So a `read_file` look reads their files, never someone
else's.

## Everyone, unless the owner names some

With looks made as their person, a watch is safe for anyone, so
`--prahari` alone now gives the tools to everyone on the roster.
`--prahari-for` stays, as a narrowing: a comma list of the people who
get watches. `/call` refuses (404) anyone the switch doesn't cover,
with *"watches are off for asha on this service"*. That covers a
watch made before the owner narrowed the list: its looks stop working,
and it says why.

## Live receipt

A scratch Dvara on 8798 with two people, `mahen` and `asha`, and a
package that may `read_file` and `web_fetch`. Each person's folder held
a `list.txt`:

```
$ curl -X POST .../call -d '{"actor":"asha","agent":"watcher","tool":"read_file","args":{"path":"list.txt"}}'
{"format":"yantra.call.v1","ok":true,"tool":"read_file","text":"     1\tasha's shopping list: dal, rice", ...}

$ curl -X POST .../call -d '{"actor":"asha",...,"tool":"web_fetch","args":{"url":"https://api.coinbase.com/v2/prices/BTC-USD/spot"}}'
{"format":"yantra.call.v1","ok":false,"tool":"web_fetch","text":"",
 "detail":"web_fetch is not read-only; --call runs only tools that read, or one call granted word for word: ..."}

$ curl ... same, with "allow_tools":["web_fetch(url=https://api.coinbase.com/v2/prices/BTC-USD/spot)"]
{"format":"yantra.call.v1","ok":true,"tool":"web_fetch","text":"source: https://api.coinbase.com/v2/prices/BTC-USD/spot ... \"amount\": \"81050.015\" ..."}

$ curl ... '{"actor":"ravi", ...}'
{"detail":"you are not on this service's list of people"}
```

Then Prahari, with a watch made for asha on this road:

```
$ prahari add "BTC under 90k" --check web_fetch --args '{"url": "https://api.coinbase.com/v2/prices/BTC-USD/spot"}' \
      --pick json:data.amount --when 'below 90000' --every 1h --runner dvara --as asha --agent watcher
$ prahari look 9ccf6599
Thu 22 Oct 20:16  fired      81,050.01  then: told
    • the value is now 81,050.01
$ prahari look 9ccf6599
Thu 22 Oct 20:16  quiet      81,050.01
```

Dvara's log showed what each look was: `POST /call`, then `POST
/notify` to asha for the fire, then `POST /call` again. No model was
running anywhere.

## Their mailbox, too

The same reasoning reaches mail that's pushed instead of polled. A
mailbox Prahari keeps open (IMAP IDLE) names a Setu mail account, and
for someone else in the house that account is in their own Setu folder,
under their lock. Prahari can't open that folder, and shouldn't know
where it is. So `POST /mail-login {actor, ref}` runs `setu login <ref>
--json` in the person's folder, with the key they unlocked it with, and
answers with what Setu handed. Setu's refusal (a locked folder nobody
unlocked) comes back as `{"error": ...}`, and the mailbox says it. It's
only for a `mail:` account (Setu refuses the rest anyway), only for a
person whose watches are on, and only when they have a folder of their
own. The token that opens it is the one that already runs whole turns
as them.

Live, on a scratch Dvara where asha has `setu = true`: her account
`mail:home` was added in her folder, `prahari mailbox add home-mail
--account mail:home --for asha` opened it through this endpoint, and a
mail landing fired her watch and only hers (Prahari's notes/02).

## Tests

`tests/test_looks_as_them.py`: a guest's look reads the guest's own
folder and not the owner's; no model is asked and no run is written; a
tool that writes runs only granted word for word; an unknown tool is an
answer, not a crash; the switch covers everyone, or only those named, or
nobody; an agent the person may not use is refused; and the door
answers in Yantra's shape, 404 for a person the switch doesn't cover,
401 without the token; a mailbox login is read from the person's own
folder, only for a `mail:` account, and refused for a person watches are
off for. `tests/test_watches.py` now pins that a person's
server is started `--for` them when nobody is named.

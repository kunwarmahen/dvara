# 40 — a notice on their phone

*[Note 34](34-a-chat-on-a-page.md) gave every person a web channel, and
left push to a phone for later: a notice waited on the page until they
next opened it. This note sends notices to the ntfy app on their phone,
through a server in the house.*

## The problem, as you would meet it

Ravi doesn't use Telegram. He talks to his agents on Sarathi's home
page. His 7 am schedule checks the school's website for a snow day, and
its answer waited on the page until he opened it at 8:15, after the bus
had come and gone.

## ntfy, on the house's own server

ntfy is a small push server and a phone app. The app keeps a connection
to the server and shows what is posted to a topic it subscribed to.

```bash
dvara --ntfy http://192.168.1.44:8793 --ntfy-click http://192.168.1.44:8760/ serve --web
```

With `--ntfy` (or `DVARA_NTFY`), every notice for every person also goes
to their own topic on that server: a schedule's answer, a file a
scheduled run sent (named, not attached), a refused sign-in, what a look
back noticed (note 39). `--ntfy-click` is where tapping one opens.
Sarathi starts the server and passes both (Sarathi's `[dvara] ntfy`).

* **THE HOUSE'S OWN SERVER.** The words never leave the house. The
  price: a phone hears a notice while it can reach that server, which is
  on the home network, or wherever the owner's own network reaches
  (Tailscale). ntfy.sh, the public server, was turned down because every
  notice would pass through somebody else's computer.
* **ONE TOPIC PER PERSON, AND NOBODY CAN GUESS IT.** ntfy's topics are
  open: anyone who knows a topic's name can read it. A person's topic is
  `dvara-<id>-<16 hex>`, the hex an HMAC of their id under a key in
  `<state>/ntfy.key` (the owner's alone). `GET /web/push?actor=` gives it
  to the page in front of that person and no one else. A new key moves
  every topic.
* **ON FOR EVERYONE, HEARD BY WHOEVER SUBSCRIBED.** There is nothing to
  add to the actors file. Like the web channel's lines, every person has
  a topic, and a phone that never subscribed hears nothing.
* **ONLY NOTICES.** The answer to something they just wrote on the page
  appears on the page, where they are.
* **A SERVER DOWN IS NOT A CRASH.** A failed post is recorded as failed
  for that notice, and the other channels still get it.

## Their own Setu page, from the page

The same page now asks for a person's one-time link to their own Setu
page: `POST /web/accounts-page` answers `{"url", "said"}`, made by
exactly the path `/accounts page` takes in the chat, so the button and
the word can't say different things ([note 31](31-their-own-page.md)).

## Receipt

ntfy's own image (`docker.io/binwiederhier/ntfy:v2.11.0`, `serve`) on a
scratch port, and the scratch Dvara of note 39 pointed at it. Then each
person's topic was read back from the server, as the phone app would
read it:

```
NTFY dvara-mahen-4d9c1cb86bb148fa: [Your agents] 'greeter: Looking back over our conversation, I noticed this about you:\n1. Lives in Raleigh (near RDU airport).\n2. Works night shifts at a hospital.\nSend /remember …' click=http://192.168.1.44:8760/
NTFY dvara-priya-630ba828977f2d94: [Your agents] 'Your gmail sign-in (priya@example.com) stopped working on 2026-10-12: the site refused it. Send /connect gmail as work to sign in again.' click=http://192.168.1.44:8760/
```

Each notice went to its own person's topic and to no one else's. This
has not yet been received on a real phone.

## What the tests hold

`tests/test_chores.py`: each person's topic is their own, the same every
time, and different under another key, and the key file is the owner's
alone; a notice is posted to the person's topic with its tap address.
`tests/test_web.py`: the accounts-page button says why when there is no
link, and refuses a stranger. `tests/test_chat_accounts.py`: the button
gets the same link and words as `/accounts page`.

## What was deliberately not built

* **ntfy.sh.** As above: no notice through somebody else's computer.
* **Answers pushed.** An answer to what they wrote on the page is not
  pushed; they are on the page.
* **Web Push from the page itself.** That needs the page on HTTPS, and
  the house's pages are plain HTTP on the home network.
* **iPhones, fully.** ntfy's iOS app is told about a new message through
  Apple, which a server in the house reaches only by forwarding through
  ntfy.sh. Without that, an iPhone shows notices when the app is opened.

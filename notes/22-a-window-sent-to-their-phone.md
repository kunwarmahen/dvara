# 22 — a window sent to their phone

*[Note 20](20-signing-in-from-the-chat.md) let a person connect Gmail or
Home Assistant from their phone by pasting back the address of the page
that wouldn't load. It ended with one thing that still needed someone at
the owner's computer: sites signed in to through a browser window, like
Amazon and X. This note sends the window to them.*

## Why there's nothing to paste

Gmail's sign-in ends with a code the phone can carry back. Amazon's
doesn't end anywhere useful: the connection *is* a browser profile on
the owner's computer, a folder of cookies Setu keeps for that person,
and the person has to sign in to Amazon in a browser using that folder.
A browser on their phone writes cookies on their phone.

So the browser has to run on the owner's computer, and the person has to
be able to see it and use it from wherever they are.

## `/connect amazon`, streamed

When the owner has given the service a window address (below),
`/connect amazon` starts `setu connect amazon --json --remote` in the
person's own folder and sends them a link:

```
To connect amazon:personal (Read only), open this on your phone:

http://192.168.1.44:8767/w/sT5eANwRJyCCH-ZUyUb5sfgGR8Qeq0QX

You'll see Amazon's sign-in page, running in a browser on this
service's computer: tap and type as you would on the page. It opens on
the first device only and works for 10 minutes. Your sign-in stays in
your own folder; I'll tell you when it's done.
```

The page shows a live picture of the browser, sized to their phone and
looking like a phone to the site, plus a box to type in and buttons for
Enter, Backspace, Tab, Back, and "I've signed in". Text sent from the box
goes into the field they tapped on the picture, or, if they tapped none,
the page's first empty field: the first real phone typed an email and
pressed Send without tapping, and nothing happened until Setu learned
that. Setu watches for the
site's sign-in cookie (by name, as at the machine), closes the browser
so the cookies are written, saves the connection, and dvara tells them:

```
Connected amazon:personal (amazon.com) at Read only. Your agents that
need it can use it from your next message.
```

Setu's README and its `remote.py` describe the window itself: Chrome
driven over a private pipe rather than a port, a link bound to the first
device that opens it, gone when the sign-in is done or ten minutes pass.

## Where the window is reachable: the owner's choice

The phone has to reach the owner's computer, and nothing of this service
was reachable from outside before. (Telegram works because the service
calls Telegram, not the other way round.) So the owner says where the
window listens, in the service's environment:

| | |
|---|---|
| `SETU_WINDOW_HOST` | the address it listens on |
| `SETU_WINDOW_PORT` | its port (any free one if unset) |
| `SETU_WINDOW_URL` | the address in the link, when it differs |

With none set, `/connect amazon` says it's done at the owner's computer
and names the setting that would change that. Which address is safe for
what:

* **The home network's address**: works for people at home. It's plain
  HTTP, so what they type crosses the Wi-Fi with only the Wi-Fi's own
  encryption.
* **A Tailscale address**: encrypted end to end, reachable wherever
  they are, as long as they're on the owner's tailnet. The good default
  for a family spread out.
* **The owner's own HTTPS**: listen on `127.0.0.1`, put a tunnel or a
  reverse proxy in front, and give its public address in
  `SETU_WINDOW_URL`.

## What the owner can see

The browser runs on the owner's computer, so the owner's machine handles
everything the person types into it, their Amazon password included.
That's the same position as the agent itself, which runs there too, and
it's why this is offered to a household rather than to strangers. A
locked folder ([note 21](21-a-passphrase-only-they-know.md)) still
applies afterwards: if the person hasn't unlocked it, the new profile is
packed and sealed the moment it's saved. If they have, it stays open
with the rest until it locks.

## Receipt

Real Setu and real Chrome, a scratch dvara over HTTP with
`SETU_WINDOW_HOST=127.0.0.1`, a small local shop standing in for
Amazon (Amazon itself doesn't load from the test machine's network), and
a script playing the phone:

```
/connect testshop  → To connect testshop:personal (Read only), open this on your phone:
                     http://127.0.0.1:8897/w/sT5eANwRJyCCH-ZUyUb5sfgGR8Qeq0QX ...
phone: opens it (200); taps the field; types raj@example.com; presses Enter
the shop received: raj@example.com
/accounts          → Connected for you here: testshop:personal -- 127.0.0.1 -- Read only
log                → dvara: raj connected testshop:personal from the chat
```

In Setu's own run of the same window: a second device opening the link
got 409, a frame arrived as JPEG, and no Chrome was left running after.

**Not tried live:** Amazon or X themselves (they'll be the real test of
robot checks and two-step sign-in on a small screen), and a phone on
Tailscale.

## What was deliberately not built

* **Streaming through Telegram.** A bot can send pictures, but a sign-in
  needs taps where the person means them and typing into the field they
  chose. That's a page, not a chat.
* **A window for a site Setu wrote the rules for itself** (`--site`).
  Its sign-in is checked by reading its page and asking the person
  whether it worked, which needs them at the machine anyway.

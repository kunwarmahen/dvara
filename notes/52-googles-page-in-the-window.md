# 52 — Google's page in the window

*[Note 20](20-signing-in-from-the-chat.md) let a person connect Gmail from
their phone by pasting back the address of the page that wouldn't load.
[Note 22](22-a-window-sent-to-their-phone.md) streamed a browser window to
them for Amazon and X, which have nothing to paste. This note puts
Google's page in that same window, because from Telegram the paste could
not be done at all.*

## The step people couldn't take

Google's sign-in ends by sending the browser to `http://127.0.0.1:<port>/`
with the code. On a phone that address is the phone, so the page fails,
and note 20's road was to copy its address and send it back.

Telegram opens a link in its own browser. That browser shows a title, not
an address bar. Its share button shares the link it *opened*, which was
the first `accounts.google.com` address, not the one the page failed on.
So the person had nothing to send back. Every `/connect gmail` from
Telegram ended the same way, and the paste note 20 was built on was a
step people couldn't take there.

Google won't help from its side. A program on a person's own computer
(Google's "Desktop app" client) may be sent back to `127.0.0.1` or
`localhost` only. Not the house's name, and not an address on the home
network. A "Web application" client wants a public domain over HTTPS. And
the sign-in where you type a code on another device doesn't allow Gmail's
scopes.

## The page runs here, so 127.0.0.1 is here

With a window address set (`SETU_WINDOW_HOST`, `SETU_WINDOW_URL` or
`SETU_WINDOW_NAME`), `/connect gmail` starts

```
setu connect gmail --json --remote --paste
```

in the person's folder. Setu opens Google's page in the window from note
22: a browser on the owner's computer, shown live on the phone. Its
return to `127.0.0.1` lands on this computer, where Setu is listening, and
the code is heard without anybody copying anything. The person is sent
the window's link, exactly as for Amazon:

```
To connect gmail:personal (Read only), open this on your phone:

http://beast.local:8790/w/…

You'll see gmail's sign-in page, running in a browser on this service's
computer: tap and type as you would on the page. …
```

and is told *Connected* as a notice when Setu says so.

Setu's `url` event still comes first, now marked `window: true`, and
dvara skips it: the Google link is no use to the person and would only
invite the old dead end. `--paste` stays on the command, so an address
pasted back still counts if it comes first. Without a window address,
nothing changes: `--paste` alone, and the note 20 road.

**Nothing of it is kept in a browser.** For Amazon the profile *is* the
connection. For Google the connection is the token, as at the machine.
So the window's browser runs on a new, empty profile that is deleted
when the window closes, and no Google session stays behind on the
owner's computer.

## Receipt

Setu's real sign-in, started the way dvara starts it, against the owner's
Google client, in a scratch folder:

```
$ SETU_WINDOW_HOST=127.0.0.1 SETU_WINDOW_NAME=localhost \
    setu connect gmail --json --remote --paste --client-file …
{"event": "started", "ref": "gmail:personal", "level": "read", "level_label": "Read only", …}
{"event": "url", "url": "https://accounts.google.com/o/oauth2/auth?…redirect_uri=http%3A%2F%2F127.0…", "paste": true, "window": true}
{"event": "link", "url": "http://localhost:44531/w/64nIvZW…", "expires_at": 1792373194.6}
```

The link opened, and the stream's frame showed Google's own *Sign in —
to continue to setu* page, drawn at a phone's size, with its email box
ready. The run was stopped there, and no browser or profile was left
behind. Whether Google lets a password through in that window needs a
person and their phone. The tests finish a sign-in against a fake Setu
that speaks the same events, and Setu's own tests drive a fake browser
that follows the page's return to `127.0.0.1`.

## What was deliberately not built

* **A redirect to the house's name.** Google refuses it for this kind of
  client. Moving to a "Web application" client would need a public
  domain with HTTPS, so a door on the internet, to sign in from home.
* **Dropping the paste.** If Google turns the window's browser away
  ("this browser may not be secure"), the address pasted back, from a
  phone's real browser, is still the way in.

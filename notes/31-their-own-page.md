# 31 · Their own page

Note 20 let a person sign in from the chat with three words. Setu's page
lets the owner see every connection, change a level, and read what each
one did. A person with a Setu folder of their own had only the words:
`/accounts` lists, and nothing shows what their Gmail connection asked
Google for last night.

```
/accounts page     a one-time link to their own folder's page
```

## A link that works once

Dvara runs `setu page-link` in the person's folder (`SETU_HOME` at
`state/setu/<person>`, as for every Setu command it runs for them) and
sends what it prints. The rest is Setu's (its people.py):

* **ONCE, ON THE FIRST DEVICE, FOR TEN MINUTES.** The first device to
  open it trades it for a session, and the link is gone. The same address
  read off the chat later, or forwarded, opens nothing. A new
  `/accounts page` replaces a link not yet used.
* **THEIR FOLDER BY ITS NAME, NEVER A PATH.** Setu's page is told where
  people's folders are (`setu serve --people <state>/setu`) and the link
  names one of them. It shows that folder only: their connections,
  Connect, Change level, Disconnect, and the requests each one made. The
  owner's parts (catalog, installs, settings, adding a site) are not on
  it, because they change the owner's computer.
* **Then theirs until they close it.** That device keeps its own key
  (kept by Setu only as a hash) until they press **Close this page on
  this device**.

## One switch, the owner's

**OFF IN ONE PLACE.** The owner turns people's pages off in their own Setu:
`setu config people-page off`. Dvara reads that before making a link
and answers *"The owner has turned this page off. /accounts and /connect
still work here."* Setu's page refuses every person's session while it is
off, and checks on each request, so turning it off works even for a
page already open on someone's phone. There is no second switch in
Dvara to disagree with the first.

**A FOLDER OF THEIR OWN ONLY.** A person pointed at the owner's folder
(`setu = "<path>"`, even with `setu_manage`) gets *"Your accounts here are
in the owner's own folder, so there's no page of yours for them."* That
folder is the owner's, and so is its page.

**AN ADDRESS THEIR PHONE CAN OPEN, OR NO LINK.** The link uses
`SETU_PAGE_URL`, or the streamed window's `SETU_WINDOW_HOST` on Setu's
page port: the same Tailscale or home-network choice as the window (note
22). With neither set, Setu refuses to make a link to `127.0.0.1`, and the
person is told *"Your accounts page can't be reached from your phone
yet"*. The owner's log says why.

## Live

`dvara say` as the guest from `examples/actors.toml` with `setu = "own"`,
and Setu's page started with `--people <state>/setu`:

```
$ dvara … say --actor guest --agent scribe "/accounts page"
[accounts]
Your accounts page:

http://127.0.0.1:8777/#link=guest.Frzwws3dS-9TJmBfAGcKDsbvuLOqtnhv

It opens once, on the first device, within 10 minutes. That device then
stays on your page until you press Close there. Only your own accounts
are on it.
```

Opened in a browser, it showed *Setu · guest* with no connections, the
connectors to choose from, and no catalog or settings. The same link
from a second device:

```
{"detail": "that link has been used, or replaced by a newer one -- ask for a new one in your chat"}
```

With `people-page off` in the owner's Setu, a fresh link was refused at
the page: *"your owner has turned this page off"*. Once it was back on,
the same link worked, because a refused claim doesn't use it up.

No model was asked. Like `/accounts`, the words are answered before any
turn.

## What the tests hold

`tests/test_chat_accounts.py`: the link is made in their own folder;
off in the owner's Setu means no link is made; no address is said
plainly; a shared folder has no page. Setu's own tests hold the rest:
once, ten minutes, no folder outside the people's place, the owner's
parts refused, the switch.

## What is not here yet

* ~~**The owner's page doesn't list people's open pages.**~~ Setu's own
  page now does (Setu `21c222a`): People's pages shows each person's
  devices in two words and since when, an unopened link until when, and
  closes one person's pages from there.
* ~~**On Sarathi's Podman road**, Setu's page container doesn't mount the
  door's people folders yet.~~ It does, with only the people's folders
  mounted, and listens on the door's window address too (Sarathi
  `33365b4`); a link worked once from that address in a real run.

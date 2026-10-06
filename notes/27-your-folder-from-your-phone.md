# 27 — your folder, from your phone

*[Note 20](20-signing-in-from-the-chat.md) let a person sign in from the
chat, but only into a folder of their own. A person pointed at someone
else's folder was told the owner looks after it. This note is about the
one person that answer was wrong for: the owner.*

## The problem, as you would meet it

Your desktop's Setu folder holds your accounts, and Yantra's page uses
it. You want your phone to use the same sign-ins, so you point yourself
at it in the actors file:

```toml
[actor.owner]
setu = "~/.local/state/setu"
```

Your phone can now read your Amazon orders through the door. Then Amazon
asks for the password again, as it does for its orders page once a
sign-in is old enough. You send `/connect amazon`, and the door answers:

```
Your accounts here are looked after by the owner of this service, at their
computer -- ask them to connect, disconnect or lock one
```

The owner is you. The rule was right for the case it was written for: a
guest pointed at your folder must never be able to add accounts to it,
or remove yours. But it couldn't tell a guest on your folder from you on
your folder, so it sent you to your own computer.

The other way out was a folder of your own (`setu = true`), where
`/connect` works. Then the page and the chat each have their own
sign-ins, and you sign in to Amazon twice. Signing into one of them and
reading through the other is easy to get wrong.

## Saying who it's for

```toml
[actor.owner]
setu = "~/.local/state/setu"
setu_manage = true
```

**THE OWNER SAYS SO, PER PERSON.** dvara can't know whose folder a path
is, so it doesn't guess. `setu_manage = true` on one actor lets that
person's `/connect`, `/disconnect` and `/accounts` reach the folder
they're pointed at. Everyone else pointed at a folder is a guest, as
before.

**NEVER WITH `setu_accounts`.** Narrowing a folder to one account is how
the owner shares part of it with someone else. Someone who can see only
`gmail:personal` and can disconnect anything is a contradiction, so the
actors file refuses the pair. `setu_manage` with `setu = true` is refused
too: that folder is already theirs, so the key would mean nothing, and a
key that means nothing is a typo waiting to happen.

**`/LOCK` STAYS AT THE COMPUTER.** A passphrase on a shared folder locks
out everything else that uses it: the desktop, the page, a schedule that
reads your mail at seven. Setting one from a chat is a way to break all
of them from a phone. So on a managed folder, `/lock` and `/unlock`
answer that its passphrase is set at the computer, with `setu lock`.

The agent's instructions follow the same switch. A person who manages
their folder is told an account that isn't connected is theirs to
connect with `/connect`. A guest is told the owner connects it.

## A sign-in page is not a link to send

The same evening turned up a second gap, this one in Yantra. Asked for
your orders, the agent found Amazon's sign-in page and handed it to you,
as the snapshot told it to. Behind a door a handoff is a link, so you got
Amazon's sign-in address in the chat. Opening it signs in your phone's
browser. The connection's own profile, on the computer, stays exactly as
signed out as before. Yantra now says a handoff is a sign-in only when
it's a window on that profile. Anywhere else the snapshot names the
host's own way to sign in again, which here is `/connect amazon`
(Yantra's note 112).

## Receipt

`qwen3.8-64k:latest` on Ollama, the door in Sarathi's Podman container,
`dvara say --as` the owner's Telegram id, with the owner pointed at the
page's folder and `setu_manage = true`. Amazon was asking for its
password again, as above:

```
> /accounts
Connected for you here:
amazon:personal -- amazon.com -- Read and act
gmail:mine -- ... -- Read, draft and send
...
> /lock
These accounts are shared with this computer, so their passphrase is set at the computer: `setu lock` there.
> What were my last three Amazon orders? Just the titles and the dates.
Your Amazon session has expired — I hit the sign-in page (for ...) and I can't sign
in myself. To reconnect, send `/connect amazon` and I'll try again.
```

Before Yantra's change, the same question got an approval card carrying
Amazon's sign-in address.

## What was deliberately not built

* **No "this path is the owner's" detection.** Comparing the folder to
  the service owner's own Setu would work on one machine and break
  across containers and mounts, where the same folder has two names. A
  line in the actors file can't be wrong in that way.
* **No managing part of a folder.** A person either manages the whole
  folder or none of it. Letting them connect one account but not another
  would put a second permission system inside Setu's, which already has
  levels and a package ceiling.

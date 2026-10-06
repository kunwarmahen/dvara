# 20 — signing in from the chat

*[Note 19](19-their-own-accounts.md) gave each person a Setu folder of
their own, but signing in to it meant somebody at the owner's computer
running `SETU_HOME=<their folder> setu connect gmail`. Fine for the owner.
No good for the person it's for, who is on a phone somewhere else. This
note is about that person connecting, listing and disconnecting their
own accounts from the chat they already use.*

## The problem, as you would meet it

Google's sign-in is built for a program on your own computer: the program
listens on `http://127.0.0.1:<port>/`, Google sends the browser back
there with a one-time code, and the program trades the code, plus a
secret it kept (the PKCE verifier), for the person's tokens. Open that
same link on a phone and everything works until the very last step. The
phone's browser goes to `127.0.0.1`, which on a phone is the phone, and
shows "this site can't be reached".

But the failed page's address is still there, in the address bar:

```
http://127.0.0.1:42631/?state=Exxcgjnhi_yj…&code=4/0AbCd…&scope=…
```

and that's everything the sign-in was waiting for.

## Three words, and they're the person's

```
/connect gmail                          sign in, at the level the agent asks for
/connect gmail send as work             a level, and a name for the account
/connect homeassistant http://ha.local:8123
/accounts                               what is connected here, for you
/disconnect gmail:work                  revoke it at Google and forget it
```

dvara doesn't invent a command language for talking to agents, and this
isn't one. **An agent never sees these messages.** They're answered
before any turn starts: no model is asked, nothing is written to the
conversation's history, no run is recorded. A sign-in is a decision about
a person's key, the way an approval is a decision about a call (note 02),
and neither one is a sentence for a model to read. There's also a sharper
reason. A prompt hidden in somebody's mail can ask their agent for
anything; it can't type a slash command into their chat.

What the agent *does* get is one line in its prompt for an account its
package needs that isn't connected yet: the person connects it by sending
`/connect gmail` themselves, and the agent can't do it for them. So when
raj asks "anything from the school?" before he has connected anything,
the agent tells him how.

## The pasted address goes to the sign-in and nowhere else

`/connect gmail` starts `setu connect gmail --as personal --json --paste`
in the person's own folder, and sends them the link:

```
To connect gmail:personal (Read only), open this and sign in:

https://accounts.google.com/o/oauth2/auth?…

After you allow it, your browser will try to open a page starting with
http://127.0.0.1 and fail to load it. That's expected. Copy that page's
whole address and send it to me here. It works once, within 10 minutes,
and it goes to the sign-in, not to any agent.
```

They sign in on the phone, copy the address of the page that failed, and
send it. dvara spots it (an address on `127.0.0.1` or `localhost`
carrying a `code=` or `error=`), and hands it to the waiting sign-in's
input. Setu checks its `state` against the one it sent, and trades the
code using the verifier only it holds:

```
Connected gmail:personal (raj@example.com) at Read only. Your agents that
need it can use it from your next message.
```

**A code read off the chat is worth nothing to anyone else.** It needs the
verifier, which never left the computer, and it works once. Telegram's
record of the message still holds the address; the bot's own outbox keeps
only "(an address pasted back for a sign-in)" in its place.

**A WRONG PASTE DOESN'T END THE WAIT.** An address from an older sign-in,
or a sentence that isn't an address at all, gets *"that address belongs
to a different sign-in. The sign-in is still waiting."* and the right one
can follow.

**ONE PERSON'S PASTE NEVER REACHES ANOTHER'S SIGN-IN.** Sign-ins wait per
person, and a message reaches only its sender's. A paste with nothing
waiting is dropped with a sentence saying so. It isn't passed on to the
agent either, because it carries a code.

**ONE AT A TIME, FOR TEN MINUTES.** A new `/connect` replaces one that's
waiting. A sign-in that ends some other way (Google refused it, the time
ran out, somebody finished it in a browser on the owner's computer)
reaches the person as a notice.

## Only into a folder of their own

A person with `setu = true` connects and disconnects in their own folder.
A person pointed at somebody else's folder (the owner's, narrowed by
`setu_accounts`) can see their accounts with `/accounts`, but `/connect`
and `/disconnect` answer that the owner looks after those, at their
computer. Otherwise a chat would become a way to add accounts to the
owner's own folder, or remove them.

`setu_accounts` still holds for a folder of their own: a person limited
to `gmail:personal` can't `/connect gmail as work`.

**The Google app is the owner's.** A person's fresh folder has no Google
client file, so dvara lends it the owner's: `SETU_GOOGLE_CLIENT_FILE`, or
whatever the owner's own Setu was told with `setu config client-file`.
That also means Google's own rule applies. While the owner's app is in
Google's "Testing" mode, only the people listed as its test users can
sign in, and their sign-ins expire after 7 days. Add each person's Gmail
address under *Audience → Test users* in the Google Cloud console.

## Home Assistant, the same way

Home Assistant's own login page also sends the browser back to
`127.0.0.1`, so it's the same paste:

```
/connect homeassistant http://as6102t.singhs:8123
```

Two computers have to reach that address: the person's phone (to log in)
and the owner's computer (where Setu trades the code). On a home network
both usually can. A Home Assistant only reachable from the person's own
house isn't one the owner's computer can use anyway.

## What can't be done from the chat

**Sites signed in to through a browser window** (Amazon, X): there's no
address to paste back. The person signs in by hand in a window on the
owner's computer, and a phone can't reach that window.
`/connect amazon` says so. That still needs someone at the machine.

## Receipt

Real Setu, a scratch dvara over HTTP, a fresh `raj` with `setu = true`:

```
/accounts                      → You have no accounts connected here. Send /connect gmail to connect one.
/connect gmail                 → To connect gmail:personal (Read only), open this and sign in:
                                 https://accounts.google.com/o/oauth2/auth?…client_id=565723135301-…
                                 &redirect_uri=http%3A%2F%2F127.0.0.1%3A42631%2F&…&code_challenge_method=S256…
http://127.0.0.1:5555/?state=not-this-one&code=4/fake
                               → That didn't work: that address belongs to a different sign-in.
                                 The sign-in is still waiting.
/connect homeassistant http://as6102t.singhs:8123
                               → To connect homeassistant:personal (See only), open this and sign in:
                                 http://as6102t.singhs:8123/auth/authorize?…
/connect amazon                → I couldn't start that sign-in: Amazon is signed in to in a window
                                 on this computer; there is no address to paste back
```

The Google link carried the owner's client, lent to a folder that had
none. The level was the one the package asks for (`gmail:read`). The
wrong paste was turned away by Setu's own `state` check. raj's folder
was made `drwx------`, no model was asked at any step, and no Setu
process was left behind when the service stopped. Finishing a sign-in
for real needs a person and a phone; the tests finish one against a fake
Setu that speaks the same events.

**Is a turn slower with accounts?** Each connection a turn uses is started
for that turn (note 19): about 0.8 s to its list of tools, plus 0.15 s to
read the person's Setu. That's small next to a model's answer, so
connectors aren't kept warm between turns. That would break "nothing
outlives a turn" to save under a second.

## What was deliberately not built

* **An agent tool that connects.** It would let a prompt injection start
  a sign-in, and it would put the conversation, and the model, between
  a person and their key.
* **Pasting a Home Assistant long-lived token into the chat.** A token
  that never expires would then sit in the chat's history for good. The
  login page is the road here; a token is pasted at the machine.
* **Tokens the owner can't read.** Still as note 19 says: a person's
  sign-ins sit on the owner's disk, and a scheduled run with nobody there
  has to be able to open them.

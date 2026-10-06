# 26 — the file itself

*[Note 25](25-the-persons-folder.md) gave each person one folder per
agent, so a log a schedule keeps is one their chat can read. It left one
thing out: they could read it only through the agent. This note sends
them the file.*

## The problem, as you would meet it

minder has been checking your site every hour for a week and writing a
line to `uptime-log.txt` each time. You ask on your phone what the log
says, and you get the model's summary of it: *"two entries so far, both
UP"*. A summary is fine for a question. It's wrong when you want the
record itself: to forward it, to look at the times yourself, or to check
that the summary is right. The only copy of your file you could get was
one a model had retold.

Telegram can send a file. Nothing here asked it to.

## Two words, and they are the person's

```
/files           what is in your folder with this agent, newest first
/file NAME       that file itself
```

**THE PERSON'S WORDS, NOT THE MODEL'S.** The files are theirs (note 25
settled that), so asking for one works like `/accounts`
([note 20](20-signing-in-from-the-chat.md)): answered by dvara before any
turn, never seen by the agent, costing nothing, and the same whichever
model is behind the door. The other design was a tool the agent calls to
attach a file. It would put a model between a person and their own file,
one more thing that has to go right before they get it. On a small local
model, that's a real cost.

This isn't dvara growing a command language for talking to agents. Note
07 refused that, and still does. These words never reach an agent.

**THE FOLDER'S WALLS ARE THE ONLY WALLS.** A name is looked up inside the
person's folder or it isn't found:

* `../../owner/minder/uptime-log.txt` lands outside, and gets the same
  sentence as a name that doesn't exist. The answer doesn't say whether
  anything is out there.
* A link in the folder pointing out of it is listed but never sent. The
  agent can write links; it can't use one to send the person a file from
  somewhere else.
* Nothing under a name starting with a dot is listed or sent. `.yantra/`
  is where Yantra keeps that folder's bookkeeping, MCP settings
  included. It isn't the person's record.

The person and the agent are already in the folder's path (note 25), so
another person's files and another agent's are out of reach for the same
reason they always were.

**A CHANNEL SENDS IT.** `Service.deliver` finds the file and puts its
path on the reply (`Reply.files`). How a file looks is the channel's
call:

* **Telegram** sends it as a document, with its name as the caption.
  Bots can send up to 50 MB; a bigger file gets a sentence saying so
  instead of a failed upload. An empty file gets *"is empty, so there is
  nothing to send"*, because Telegram refuses empty uploads and a
  refusal would look like a broken bot.
* **HTTP** names the path in the reply (`"files": [...]`) and sends no
  bytes. A bridge that wants them is on this machine and can read the
  file.
* **`dvara say`** prints the path under the answer.

**OWED AS A SENTENCE, NOT AS THE FILE.** If dvara crashes between taking
`/file` and sending the document, the next boot sends the name, not the
bytes ([note 13](13-a-reply-that-is-owed.md)). By then the file may have
changed, and the person can just ask again.

`/start` now mentions `/files`, but only for an agent whose package lets
it write files. For any other agent the folder stays empty, and pointing
at it would only confuse people.

## Live receipt

`qwen3.8:latest` through Ollama, the `minder` example, `dvara say` with
the write approved at the keyboard:

```
$ dvara say --actor owner --agent minder "Check https://example.com and write one
  line to uptime-log.txt saying whether it is up, with today's date and time."
2026-10-06 14:32 EDT https://example.com UP

$ dvara say --actor owner --agent minder "/files"
Your files here, newest first:
uptime-log.txt (44 bytes)

Send /file NAME to get one.

$ dvara say --actor owner --agent minder "/file uptime-log.txt"
uptime-log.txt
  file: .../state/work/owner/minder/uptime-log.txt

$ dvara say --actor owner --agent minder "/file ../../../../../etc/passwd"
There's no file called ../../../../../etc/passwd in your folder. Send /files to see them.

$ dvara say --actor owner --agent minder "/file .yantra/mcp.json"
There's no file called .yantra/mcp.json in your folder. Send /files to see them.
```

The Telegram upload was checked against the real Bot API without
sending anything to anybody: `sendDocument` to a chat that doesn't exist.
Telegram reads the upload before it looks for the chat, so a well-formed
upload and a broken one get different errors:

```
with the file    -> sendDocument: 400 Bad Request: chat not found
without a file   -> sendDocument: 400 Bad Request: there is no document in the request
```

Not yet tried from a real phone with a real bot.

The tests are in `tests/test_files.py`: the walls (climbing out, a link
out, the dot folder, another person), and that the words never reach a
model, since every service there has an empty script and a model call
would raise. The Telegram tests (`tests/test_telegram.py`) check that the
file goes out as a multipart document carrying its name and its bytes,
and that one over the limit gets a sentence instead.

## What was deliberately not built

* **A tool for the agent to attach a file.** A weekly report a schedule
  writes would be nicer arriving as a file with the notice than as
  `/file report.md` typed afterwards. That's the agent deciding to send
  something, and it belongs with notices, as a channel feature for
  messages nobody asked for. Not here.
* **A download address over HTTP.** It would be a second way into the
  folder with its own token rules. A bridge on this machine can read the
  path.
* **Sending a folder** (a zip). `/files` lists files in subfolders by
  their path, and `/file sub/name` sends one.
* **Receiving files.** A photo or document sent to the bot still gets
  *"I can only read text."*

## What is not here yet

* **Deleting a file from the chat.** A record grows until the person asks
  the agent to rewrite it, or the owner removes it at the machine.

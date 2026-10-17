"""What a person sends with a message: kept in their folder, a picture shown.

Telegram answered a photo with "I can only read text", and the page had
nothing to attach with. Yet the things people most want to hand an agent
are things they have, not things they can type: a photo of a receipt, a
screenshot of an error, a PDF a school sent.

KEPT IN THEIR FOLDER, UNDER ``from-you/``. The folder is theirs and the
agent's for that conversation (note 25), so a file sent there is one the
agent can open with the tools its package already has (``read_file``),
one ``/files`` lists, and one ``/file`` sends back. A name is the file's
own last part, made safe, and never replaces another: a second
``receipt.jpg`` is ``receipt-2.jpg``.

A PICTURE IS SHOWN, WHEN THE MODEL CAN SEE. A png, jpeg, gif or webp up
to Yantra's 5 MB goes into the turn as an image, the way Yantra's own
page sends one. A local model that can't see (Ollama doesn't list
"vision" for it) is told the picture is in the folder instead: a picture
handed to a model that can't take one fails the whole turn. A cloud
model takes it: the person chose to send it to their agent.

THE MESSAGE SAYS WHAT CAME. The agent reads the person's words and one
line naming each file and where it was kept -- also what the turn's
record keeps, so "what did I send you on Monday?" has an answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Where a person's files land, inside their folder with this agent.
INBOX = "from-you"
#: The largest file kept: Telegram's own limit for a bot downloading one.
KEEP_LIMIT = 20 * 1024 * 1024
#: Files with one message, at most.
AT_MOST = 10
SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


#: A recording, by its name: a voice note (heard.py), not a file to read.
VOICE = {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".webm"}


@dataclass(frozen=True)
class Attachment:
    name: str
    data: bytes

    @property
    def voice(self) -> bool:
        return Path(self.name).suffix.lower() in VOICE


@dataclass(frozen=True)
class Kept:
    path: Path          # inside the folder
    relative: str       # what the agent is told: from-you/receipt.jpg
    picture: bool
    voice: bool = False


def safe_name(name: str) -> str:
    """The file's own last part, without anything that could leave the
    folder or hide in it (``..``, a leading dot, a slash)."""
    base = SAFE.sub("_", Path(str(name).replace("\\", "/")).name).strip(" .")
    return base or "file"


def keep(folder: Path, attachments: list[Attachment]) -> list[Kept]:
    """Each one written into ``folder/from-you``; too big or too many is
    a ValueError in words, and nothing is kept."""
    from yantra.images import MAX_IMAGE_BYTES, MEDIA_TYPES

    if len(attachments) > AT_MOST:
        raise ValueError(f"that's {len(attachments)} files; send at most {AT_MOST} at once")
    for a in attachments:
        if len(a.data) > KEEP_LIMIT:
            raise ValueError(f"{safe_name(a.name)} is over {KEEP_LIMIT // (1024 * 1024)} MB, "
                             "too big to keep here")
    inbox = Path(folder) / INBOX
    inbox.mkdir(parents=True, exist_ok=True)
    out = []
    for a in attachments:
        name = safe_name(a.name)
        target, n = inbox / name, 1
        while target.exists():
            n += 1
            target = inbox / f"{Path(name).stem}-{n}{Path(name).suffix}"
        target.write_bytes(a.data)
        picture = (Path(name).suffix.lower() in MEDIA_TYPES
                   and len(a.data) <= MAX_IMAGE_BYTES)
        out.append(Kept(target, f"{INBOX}/{target.name}", picture, a.voice))
    return out


def said(text: str, kept: list[Kept]) -> str:
    """The person's words, then a line for what came with them."""
    kept = [k for k in kept if not k.voice]       # a voice note is heard.py's
    if not kept:
        return text
    names = ", ".join(k.relative + (" (a picture)" if k.picture else "") for k in kept)
    line = f"(They sent {names}, kept in your folder.)"
    return f"{text.strip()}\n\n{line}" if text.strip() else line


def pictures(kept: list[Kept]) -> list:
    """The pictures, as Yantra's image blocks."""
    from yantra.images import image_block_from_bytes

    return [image_block_from_bytes(k.path.name, k.path.read_bytes())
            for k in kept if k.picture]


async def sees(provider_name: str, base_url: str, model: str) -> bool:
    """Whether this turn's model takes pictures (Yantra's images): asked
    of a local server off the loop, never asked of a cloud one."""
    import asyncio

    from yantra.images import is_local, sees_pictures

    if not is_local(provider_name, base_url):
        return True
    return await asyncio.to_thread(sees_pictures, provider_name, base_url, model)


NOT_SEEN = ("(You can't see pictures with this model: the picture is in their folder, "
            "but say you can't look at it, and ask them what it shows if you need to.)")

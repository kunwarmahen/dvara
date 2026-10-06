"""The person's files, sent to them: two words that are theirs to type.

Note 25 gave each person one folder per agent, and left one thing out:
the person could read a file only by asking the agent what was in it. A
week of an uptime log comes back as the model's summary of the log, and
a report the agent wrote comes back as a retelling of the report. For a
record, the retelling is the wrong thing to be handed.

    /files           what is in your folder with this agent
    /file NAME       that file itself, sent to you

THE PERSON'S WORDS, NOT THE MODEL'S. The files are theirs (note 25), so
asking for one is like ``/accounts``: answered here, never a turn, never
seen by the agent, costing nothing and working the same whatever model
is behind the door. A model that decided what to attach would be one
more thing that has to go right before the person gets their own file.

THE FOLDER'S WALLS ARE THE ONLY WALLS. A name resolves inside the
person's folder or it is not found -- ``..`` and a link pointing out of
it both land outside and are refused with the same sentence as a name
that does not exist, so the answer says nothing about what is out there.
Anything under a name starting with a dot is never listed or sent:
``.yantra/`` is where Yantra keeps its own state for that folder (the
MCP settings among it), and it is the agent's bookkeeping, not the
person's record.

A CHANNEL SENDS IT. This module finds the file and says what it found;
the ``Reply`` carries the path and each channel decides how a file looks
in its medium. Telegram sends it as a document. HTTP names it in the
reply and sends nothing, because a bridge that wants the bytes is on
this machine and can read the folder itself.
"""

from __future__ import annotations

from pathlib import Path

WORDS = ("/files", "/file")

#: The most names ``/files`` lists, so one busy folder is still one message.
LIST_AT_MOST = 40


def is_file_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in WORDS


def _theirs(folder: Path) -> list[Path]:
    """Every file in the folder a person may be sent, newest first."""
    if not folder.is_dir():
        return []
    found = [p for p in folder.rglob("*")
             if p.is_file() and not any(part.startswith(".")
                                        for part in p.relative_to(folder).parts)]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def _size(n: int) -> str:
    for unit in ("bytes", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.0f} {unit}"
        n /= 1024
    return f"{n} MB"


def listing(folder: Path) -> str:
    files = _theirs(folder)
    if not files:
        return "There are no files in your folder here yet."
    rows = [f"{p.relative_to(folder)} ({_size(p.stat().st_size)})"
            for p in files[:LIST_AT_MOST]]
    more = len(files) - len(rows)
    tail = f"\n...and {more} more." if more > 0 else ""
    return ("Your files here, newest first:\n" + "\n".join(rows) + tail
            + "\n\nSend /file NAME to get one.")


def pick(folder: Path, name: str) -> Path | None:
    """The file NAME names inside the folder, or None -- for a name that
    is not there and a name that points out of it alike."""
    if not name or any(part.startswith(".") for part in Path(name).parts):
        return None
    root = folder.resolve()
    target = (folder / name).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def answer(folder: Path, text: str) -> tuple[str, Path | None]:
    """The words to say, and the file to send with them (or None)."""
    word, _, rest = text.strip().partition(" ")
    if word.split("@")[0].lower() == "/files":
        return listing(folder), None
    name = rest.strip()
    if not name:
        return "Which one? Send /files to see them, then /file NAME.", None
    found = pick(folder, name)
    if found is None:
        return f"There's no file called {name} in your folder. Send /files to see them.", None
    if found.stat().st_size == 0:
        return f"{name} is empty, so there is nothing to send.", None
    return name, found

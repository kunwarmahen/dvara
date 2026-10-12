"""Change one table of a TOML file the owner wrote, and leave the rest alone.

The home page lets the owner change a person, a rule or an agent without
opening a file. Python reads TOML and does not write it, and a writer
that re-dumps the whole file throws away every comment the owner (or
the starter file) put there -- the explanations that make the file
reviewable at all.

SPANS, NOT A TREE. A table is the text from its header to the next
header that is not one of its own sub-tables (``[actor.priya]`` owns
``[[actor.priya.channel]]``). Changing a table replaces that span;
adding one appends it at the end; removing one cuts it out. Comments
inside the changed table go with it, and every other line is kept byte
for byte. The values written are the few kinds these files hold:
strings, booleans, numbers, lists of strings, and arrays of tables of
those.

The caller checks the result by parsing it the way its program does
before writing anything (settings.py): this module only edits text.
"""

from __future__ import annotations

import json
import re

_HEADER = re.compile(r"^\s*(\[\[?)\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def _headers(text: str) -> list[tuple[int, str]]:
    """(line index, dotted name) of every table header, in order."""
    out = []
    in_multiline = False
    for i, line in enumerate(text.splitlines()):
        if line.count('"""') % 2 or line.count("'''") % 2:
            in_multiline = not in_multiline
            continue
        if in_multiline:
            continue
        m = _HEADER.match(line)
        if m and not line.lstrip().startswith("#"):
            out.append((i, m.group(2).replace(" ", "")))
    return out


def _owns(name: str, other: str) -> bool:
    return other == name or other.startswith(name + ".")


def span(text: str, name: str) -> tuple[int, int] | None:
    """Line range [start, end) of table ``name`` and its own sub-tables,
    or None. Comment lines right above the next table go with that table."""
    lines = text.splitlines()
    heads = _headers(text)
    start = next((i for i, n in heads if n == name), None)
    if start is None:
        return None
    end = len(lines)
    for i, n in heads:
        if i > start and not _owns(name, n):
            end = i
            while end - 1 > start and lines[end - 1].lstrip().startswith("#"):
                end -= 1
            break
    while end - 1 > start and not lines[end - 1].strip():
        end -= 1
    return start, end


def dump(value) -> str:
    """One TOML value, of the kinds these files hold."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(dump(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_key(k)} = {dump(v)}" for k, v in value.items()) + " }"
    raise ValueError(f"can't write {type(value).__name__} into a settings file")


def _key(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else json.dumps(key)


def render(name: str, values: dict, arrays: dict[str, list[dict]] | None = None) -> str:
    """``[name]`` with ``key = value`` lines (None values left out), then
    ``[[name.key]]`` for each entry of each array of tables."""
    lines = [f"[{name}]"]
    lines += [f"{_key(k)} = {dump(v)}" for k, v in values.items() if v is not None]
    for key, entries in (arrays or {}).items():
        for entry in entries:
            lines.append(f"[[{name}.{key}]]")
            lines += [f"{_key(k)} = {dump(v)}" for k, v in entry.items() if v is not None]
    return "\n".join(lines)


def put(text: str, name: str, block: str) -> str:
    """``text`` with table ``name`` replaced by ``block`` (or appended)."""
    lines = text.splitlines()
    where = span(text, name)
    if where is None:
        body = "\n".join(lines).rstrip("\n")
        return (body + "\n\n" if body else "") + block.rstrip("\n") + "\n"
    start, end = where
    return "\n".join(lines[:start] + block.rstrip("\n").splitlines() + lines[end:]) + "\n"


def drop(text: str, name: str) -> str:
    """``text`` without table ``name`` (and its sub-tables)."""
    lines = text.splitlines()
    where = span(text, name)
    if where is None:
        return text
    start, end = where
    while end < len(lines) and not lines[end].strip():
        end += 1
    return "\n".join(lines[:start] + lines[end:]).rstrip("\n") + "\n"

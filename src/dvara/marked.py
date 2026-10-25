"""An answer's Markdown, as the bold and italic Telegram shows.

A model writes Markdown -- ``**Bad Company — 20:39**``, ``*"a quote"*``,
a fenced block of code -- and Telegram, sent plain text, shows every
asterisk. Telegram's own Markdown and HTML modes are not the answer
(telegram.py says why: the model's punctuation becomes a syntax error,
and the person gets nothing). ENTITIES ARE. The text goes plain, with a
list beside it saying "these 20 units are bold"; there is nothing for
Telegram to parse, so nothing to refuse.

**WHAT LOOKS LIKE MARKDOWN AND ISN'T STAYS AS IT WAS.** An asterisk with
no partner, ``snake_case_name``, ``2 * 3 * 4``, ``rm *.log`` -- each is
left as typed, because a marker counts only when it opens against a
word and closes against one. The worst a wrong guess does is one word in
italics.

What is understood: ``**bold**`` and ``__bold__``, ``*italic*`` and
``_italic_``, ``~~struck~~``, `` `code` ``, fenced blocks, ``[words](https://…)``,
``# headings`` (as a bold line), ``- items`` (as ``•``) and ``> quotes``.
Tables and the rest go as written.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*```\s*([\w+#.-]*)\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_ITEM = re.compile(r"^(\s*)[-*+]\s+(?=\S)")
_QUOTE = re.compile(r"^\s{0,3}>\s?")

#: One inline mark, earliest first; at the same place, the order here wins
#: (code before everything, so nothing inside code is read as a mark).
_INLINE = re.compile(
    r"(?P<code>`(?P<code_in>[^`\n]+)`)"
    r"|(?P<link>\[(?P<link_in>[^\]\n]+)\]\((?P<url>https?://[^\s)]+)\))"
    r"|(?P<bold>\*\*(?=\S)(?P<bold_in>.+?)(?<=\S)\*\*)"
    r"|(?P<bold2>(?<!\w)__(?=\S)(?P<bold2_in>.+?)(?<=\S)__(?!\w))"
    r"|(?P<strike>~~(?=\S)(?P<strike_in>.+?)(?<=\S)~~)"
    r"|(?P<italic>(?<![\w*])\*(?=[^\s*])(?P<italic_in>.+?)(?<=[^\s*])\*(?![\w*]))"
    r"|(?P<italic2>(?<!\w)_(?=[^\s_])(?P<italic2_in>.+?)(?<=[^\s_])_(?!\w))"
)

_KIND = {"bold": "bold", "bold2": "bold", "strike": "strikethrough",
         "italic": "italic", "italic2": "italic"}


def _inline(text: str, at: int, out: list[dict]) -> str:
    """One line's marks taken out; their places (in characters, counted
    from ``at``) added to ``out``. Bold and italic may hold more marks."""
    plain: list[str] = []
    length = 0
    pos = 0
    for found in _INLINE.finditer(text):
        before = text[pos:found.start()]
        plain.append(before)
        length += len(before)
        start = at + length
        name = found.lastgroup
        if name == "code":
            inner = found.group("code_in")
            out.append({"type": "code", "offset": start, "length": len(inner)})
        elif name == "link":
            inner = found.group("link_in")
            out.append({"type": "text_link", "offset": start,
                        "length": len(inner), "url": found.group("url")})
        else:
            inner = _inline(found.group(f"{name}_in"), start, out)
            out.append({"type": _KIND[name], "offset": start, "length": len(inner)})
        plain.append(inner)
        length += len(inner)
        pos = found.end()
    plain.append(text[pos:])
    return "".join(plain)


def _utf16(text: str, entities: list[dict]) -> list[dict]:
    """Character places as Telegram's, which counts in UTF-16 units: an
    emoji before a bold word is one character and two units."""
    units = [0]
    for char in text:
        units.append(units[-1] + (2 if ord(char) > 0xFFFF else 1))
    shown = []
    for entity in entities:
        start, end = entity["offset"], entity["offset"] + entity["length"]
        if end <= start:
            continue                    # an empty mark shows nothing
        shown.append({**entity, "offset": units[start],
                      "length": units[end] - units[start]})
    return sorted(shown, key=lambda e: (e["offset"], -e["length"]))


def marked(text: str) -> tuple[str, list[dict]]:
    """The words to send, and the entities that mark them.

    No marks found is the text itself and an empty list, so a plain answer
    goes out exactly as it did before.
    """
    lines = text.split("\n")
    out: list[str] = []
    entities: list[dict] = []
    at = 0                              # characters in what is written so far

    def put(line: str) -> None:
        nonlocal at
        out.append(line)
        at += len(line) + 1             # and its newline

    index = 0
    while index < len(lines):
        line = lines[index]
        fence = _FENCE.match(line)
        if fence:
            close = next((j for j in range(index + 1, len(lines))
                          if lines[j].strip() == "```"), None)
            if close is not None:       # an unclosed fence stays as typed
                body = "\n".join(lines[index + 1:close])
                if body:
                    entity = {"type": "pre", "offset": at, "length": len(body)}
                    if fence.group(1):
                        entity["language"] = fence.group(1)
                    entities.append(entity)
                put(body)
                index = close + 1
                continue
        heading = _HEADING.match(line)
        if heading:
            words = _inline(heading.group(1), at, entities)
            if words:
                entities.append({"type": "bold", "offset": at, "length": len(words)})
            put(words)
        elif _QUOTE.match(line):
            quoted = _QUOTE.sub("", line, count=1)
            words = _inline(quoted, at, entities)
            if words:
                entities.append({"type": "blockquote", "offset": at,
                                 "length": len(words)})
            put(words)
        else:
            item = _ITEM.match(line)
            if item:
                lead = f"{item.group(1)}• "
                put(lead + _inline(line[item.end():], at + len(lead), entities))
            else:
                put(_inline(line, at, entities))
        index += 1
    plain = "\n".join(out)
    return plain, _utf16(plain, _merged_quotes(entities))


def _merged_quotes(entities: list[dict]) -> list[dict]:
    """Quote lines one after another, as one quote rather than a stack of
    one-line boxes."""
    merged: list[dict] = []
    for entity in sorted(entities, key=lambda e: e["offset"]):
        last = next((e for e in reversed(merged) if e["type"] == "blockquote"), None)
        if (entity["type"] == "blockquote" and last is not None
                and last["offset"] + last["length"] + 1 == entity["offset"]):
            last["length"] += 1 + entity["length"]
            continue
        merged.append(dict(entity))
    return merged

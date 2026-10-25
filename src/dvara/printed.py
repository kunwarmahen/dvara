"""A conversation as a PDF, made here, for a chat with no print button.

``/chats export N`` sent a Markdown file (past.py). On a computer that is
a page any notes app opens; on a phone it is a file of asterisks, and
the one thing a phone opens without asking is a PDF. Sarathi's home page
and Yantra's page already make one -- the browser's own print window,
"Save as PDF" -- but Telegram has no print window, so there the PDF has
to be made before it is sent.

    /chats export 2 pdf     that one as a PDF, to share

THE BROWSER THAT IS ALREADY HERE PRINTS IT. A PDF library draws the
letters it was given fonts for, and the first Hindi answer or emoji is a
row of boxes. Chrome lays out every script the machine has fonts for,
and the browser tools already need one: Sarathi's image ships Google
Chrome (``sarathi-browser``), and a desktop has its own. So the
conversation is written as a small HTML page -- the same layout as the
home page's printed one: title, when, then You and the agent turn by
turn -- and Chrome, headless, prints it to a file. Nothing new is
installed. Which browser: ``YANTRA_BROWSER_EXECUTABLE`` when it names
one (the browser tools' own setting), else the first of
``sarathi-browser``, ``google-chrome``, ``chromium`` on the PATH.

ONLY WHAT THE MARKDOWN FILE HOLDS: the person's words, the agent's
answers and the tools' names, never what a tool returned -- the rule of
Yantra's export_markdown, walked the same way. Answers are printed as
written, Markdown marks and all, rather than half-read by a renderer
of our own.

A PAGE WITH NOTHING TO FETCH. Every word is escaped, there is no
script, and the page's own policy forbids loading anything: what is
printed is the conversation and the browser's fonts, with a throwaway
profile that is gone afterwards. The browser runs without its sandbox,
as Playwright runs it for the browser tools (a container runs as root,
where Chrome refuses the sandbox), which is why the page itself is the
wall.

NO BROWSER, NO PDF, AND SAID. Without one the person gets the Markdown
file and a sentence saying the PDF needs a browser where Dvara runs;
the owner's log says which. A browser that fails or takes over a minute
is the same.
"""

from __future__ import annotations

import asyncio
import html
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

#: The browsers looked for on the PATH, in order, when none is set.
BROWSERS = ("sarathi-browser", "google-chrome", "google-chrome-stable",
            "chromium", "chromium-browser")
#: The longest a browser gets to print one conversation.
TIMEOUT = 60.0

STYLE = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 11pt/1.45 system-ui, "Noto Sans", "Noto Sans Devanagari",
       "Liberation Sans", sans-serif; color: #111; }
h1 { font-size: 16pt; margin: 0 0 2pt; }
.meta { color: #555; font-size: 9pt; margin: 0 0 14pt; }
.turn { margin: 0 0 10pt; break-inside: avoid-page; }
.who { font-weight: 700; font-size: 9pt; text-transform: uppercase;
       letter-spacing: .04em; color: #444; margin: 0 0 2pt; }
.you .who { color: #1a4f8a; }
.text { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
.tools { color: #666; font-size: 9pt; font-style: italic; margin: -4pt 0 10pt; }
"""


class Unprinted(RuntimeError):
    """No PDF this time, and why, in words for the owner's log."""


def _when(stamp: str, zone: str | None) -> str:
    try:
        moment = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return stamp or ""
    if zone:
        from zoneinfo import ZoneInfo
        moment = moment.astimezone(ZoneInfo(zone))
    else:
        moment = moment.astimezone()
    return moment.strftime("%a %-d %b %Y, %H:%M")


def _used(names: list[str]) -> str:
    counted: dict[str, int] = {}
    for name in names:
        counted[name] = counted.get(name, 0) + 1
    return ", ".join(f"{n} ×{c}" if c > 1 else n for n, c in counted.items())


def html_of(kept: dict, *, agent: str = "Agent", zone: str | None = None) -> str:
    """``kept`` (``PastBook.read``) as a page to print. Tools are named,
    never shown; every value escaped."""
    road = kept.get("road") or ""
    said = {"terminal": "in the terminal", "page": "on the page", "web": "on the page"}
    where = [_when(kept.get("started_at", ""), zone),
             said.get(road, f"on {road}" if road else "")]
    if kept.get("model"):
        where.append(kept["model"])
    title = kept.get("title") or "A conversation"
    out = ["<!doctype html><html><head><meta charset='utf-8'>",
           "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; "
           "style-src 'unsafe-inline'\">",
           f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>",
           f"<h1>{html.escape(title)}</h1>",
           f"<p class='meta'>{html.escape(' · '.join(w for w in where if w))}</p>"]
    tools: list[str] = []

    def flush() -> None:
        if tools:
            out.append(f"<p class='tools'>Tools used: {html.escape(_used(tools))}</p>")
            tools.clear()

    for entry in kept.get("entries") or []:
        if entry.get("who") == "tool":
            tools.append(entry.get("name") or "a tool")
            continue
        mine = entry.get("who") == "you"
        if mine:
            flush()
        out.append(f"<div class='turn {'you' if mine else 'agent'}'>"
                   f"<p class='who'>{html.escape('You' if mine else agent)}</p>"
                   f"<p class='text'>{html.escape((entry.get('text') or '').strip())}</p>"
                   "</div>")
    flush()
    out.append("</body></html>")
    return "\n".join(out)


def browser() -> str | None:
    """The browser that prints, or None when this machine has none."""
    from yantra.config import ConfigError, browser_executable, browser_login_command

    try:
        named = browser_login_command(browser_executable())
    except ConfigError:
        named = None
    if named:
        return named
    for command in BROWSERS:
        found = shutil.which(command)
        if found:
            return found
    return None


async def print_pdf(page: str, out: Path, *, timeout: float = TIMEOUT) -> Path:
    """``page`` (HTML) printed to ``out`` by a headless browser."""
    chrome = browser()
    if chrome is None:
        raise Unprinted("no browser to print with here (set YANTRA_BROWSER_EXECUTABLE, "
                        "or put google-chrome or chromium on the PATH)")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dvara-print-") as tmp:
        source = Path(tmp) / "page.html"
        source.write_text(page, encoding="utf-8")
        made = Path(tmp) / "page.pdf"
        command = [chrome, "--headless", "--no-sandbox", "--disable-gpu",
                   "--disable-extensions", "--no-first-run", "--no-default-browser-check",
                   f"--user-data-dir={Path(tmp) / 'profile'}",
                   "--no-pdf-header-footer", "--print-to-pdf-no-header",
                   f"--print-to-pdf={made}", source.as_uri()]
        proc = await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, err = await asyncio.wait_for(proc.communicate(), timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise Unprinted(f"{Path(chrome).name} took over {timeout:g}s to print") from None
        if not made.exists() or made.stat().st_size == 0:
            last = (err or b"").decode(errors="replace").strip().splitlines()[-1:] or [""]
            raise Unprinted(f"{Path(chrome).name} printed nothing "
                            f"(exit {proc.returncode}) {last[0][:200]}".rstrip())
        shutil.move(made, out)
    return out


async def pdf_to(folder: Path, kept: dict, *, agent: str,
                 zone: str | None = None) -> Path:
    """``kept`` as a PDF in ``folder``, named as the Markdown file is
    (``2026-10-18-how-do-i.pdf``); the same conversation shared again
    writes over its own earlier file."""
    from yantra.history import export_name

    name = Path(export_name(kept)).with_suffix(".pdf").name
    return await print_pdf(html_of(kept, agent=agent, zone=zone), folder / name)

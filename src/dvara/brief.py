"""``/brief``: the house's own account of the last day, for one person.

A morning brief written by an agent (a schedule that asks the model for
the news, the calendar, the portfolio) says what the WORLD did. Nothing
said what the HOUSE did: which of their watches fired overnight and what
the agent did about it, which schedules ran and how they ended, what was
kept about them, what's due today, which watch has stopped looking, and
what yesterday cost. All of it is already written down -- Dvara's
ledger, Samay's schedules, Prahari's watches -- so this is read, not
written: NO MODEL IS ASKED, and it costs nothing.

    /brief                       now
    /brief every morning         a Samay schedule that sends it at 07:30 their time
    /brief every morning 6:45    (or 7am, 18:30), moved
    /brief every morning off     stopped

ONLY WHAT IS THEIRS. Runs by their name, schedules and watches whose
owner they are (and, for the house's owner, the ones made at the
computer, filed as ``local``). A watch somebody else made is not in it.

WHAT NOBODY TYPED, FIRST. The runs in the brief are the unattended ones
-- a schedule's, a watch's, a routine's -- because those are what a
person didn't see happen. Each is one line: what started it (as
``/why`` says it), what it was asked, how it ended; ``/why N`` has the
rest. The day is the last 24 hours, not the calendar's, so a brief at
07:30 covers the night before.

EVERY MORNING MEANS EVERY MORNING. Unlike ``/doctor every morning``,
which is told only when something new is wrong, the brief's schedule
sends it each day (Samay's ``notify = always``): a quiet day saying "a
quiet day" is the brief working, and its absence would look like the
house being down.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dvara import why as asked_why
from dvara.checkup import clock_time
from dvara.runs import Run

WORDS = ("/brief",)
MORNING = "every morning"
MORNING_AT = "07:30"
#: The brief covers this far back.
DAY = timedelta(hours=24)
#: At most this many runs nobody typed are listed; the rest are counted.
RUNS_SHOWN = 8
#: How a run ended, as one word or two.
ENDED = {"end_turn": "done", "held": "waiting for your yes", "refused": "refused",
         "error": "failed", "timeout": "ran out of time"}


def word_of(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in WORDS


def morning_word(text: str) -> tuple[str, str | None] | None:
    """``("on", None|"HH:MM")``, ``("off", None)``, ``("bad", words)``, or
    None when the words aren't about every morning."""
    rest = " ".join(text.strip().lower().split()[1:])
    if not rest.startswith(MORNING):
        return None
    after = rest[len(MORNING):].strip()
    if not after:
        return "on", None
    if after in ("off", "stop"):
        return "off", None
    at = clock_time(after)
    return ("on", at) if at else ("bad", after)


def _clock(when: str | datetime | None, now: datetime) -> str:
    if when is None:
        return ""
    try:
        at = when if isinstance(when, datetime) else datetime.fromisoformat(
            str(when).replace("Z", "+00:00"))
    except ValueError:
        return ""
    at = at.astimezone(now.tzinfo)
    return at.strftime("%H:%M") if at.date() == now.date() else at.strftime("%a %H:%M")


def _short(text: str, room: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= room else text[:room - 1] + "…"


def compose(*, runs: list[Run], schedules: list[dict] | None, watches: list[dict] | None,
            now: datetime, schedules_why: str = "", watches_why: str = "") -> str:
    """The brief, from what each program said. ``now`` is in the person's
    zone; ``runs`` are theirs, newest first; a list that couldn't be had
    is None, with why in words."""
    since = now - DAY
    lines = [f"Your house, the last 24 hours ({now.strftime('%a %d %b %H:%M')}):"]

    recent = [r for r in runs if r.started_at.astimezone(now.tzinfo) >= since]
    unasked = [r for r in recent if r.unattended
               and r.stop_reason not in ("looked_back", "new")]
    lines += ["", "What ran that nobody typed:"]
    if not unasked:
        lines.append("- nothing")
    for run in unasked[:RUNS_SHOWN]:
        starter = asked_why.started_by(run).split(" started it")[0].split(" saw what")[0]
        lines.append(f"- {_clock(run.started_at, now)} {starter}: "
                     f"\"{_short(asked_why.asked(run), 60)}\" — "
                     f"{ENDED.get(run.stop_reason, run.stop_reason)} (/why {_place(run, runs)})")
    if len(unasked) > RUNS_SHOWN:
        lines.append(f"- …and {len(unasked) - RUNS_SHOWN} more")

    lines += ["", "Due today:"]
    if schedules is None:
        lines.append(f"- {schedules_why or 'schedules could not be read'}")
    else:
        today = []
        for card in schedules:
            for at in card.get("upcoming") or []:
                try:
                    when = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                except ValueError:
                    continue
                local = when.astimezone(now.tzinfo)
                if now <= local and local.date() == now.date():
                    today.append((local, card))
        today.sort(key=lambda pair: pair[0])
        lines += [f"- {local:%H:%M} {_short(card.get('prompt') or '(no words)', 60)}"
                  for local, card in today] or ["- nothing more today"]
        paused = [c for c in schedules if c.get("state") == "paused"]
        lines += [f"- paused: {_short(c.get('prompt') or '', 50)}"
                  + (f" ({c['paused_because']})" if c.get("paused_because") else "")
                  for c in paused]

    if watches is None:
        lines += ["", f"Watches: {watches_why or 'could not be read'}"]
    elif watches:
        looking = [w for w in watches if w.get("state") == "active"]
        fired = [w for w in watches if w.get("fired_today")]
        stopped = [w for w in watches if w.get("state") == "paused"]
        lines += ["", f"Watches: {len(looking)} looking"
                  + (f", {len(fired)} saw what they wait for" if fired else "")]
        lines += [f"- {w.get('name')}: saw it {w['fired_today']} time"
                  f"{'s' if w['fired_today'] != 1 else ''}" for w in fired]
        lines += [f"- paused: {w.get('name')}"
                  + (f" ({_short(w['paused_because'], 80)})" if w.get("paused_because") else "")
                  for w in stopped]

    kept = [fact for r in recent for fact in r.kept]
    if kept:
        lines += ["", "Kept about you:"] + [f"- {fact}" for fact in kept]

    spent = sum(r.cost_usd or 0.0 for r in recent)
    turns = len([r for r in recent if r.stop_reason not in ("looked_back", "new")])
    lines += ["", f"Model use: {turns} turn{'s' if turns != 1 else ''}"
              + (f", ${spent:.2f}" if spent else ", nothing billed") + "."]
    return "\n".join(lines)


def _place(run: Run, runs: list[Run]) -> int:
    """Which ``/why N`` names this run: its place among their runs."""
    shown = [r for r in runs if r.stop_reason not in ("looked_back", "new")]
    for n, r in enumerate(shown, 1):
        if r.id == run.id:
            return n
    return 1


async def morning(who: Any, agent: str, on: bool, samay: str | None,
                  at: str | None = None) -> str:
    """``/brief every morning`` (or ``off``): a Samay schedule that sends
    ``/brief`` here as them every day at 07:30 their time (or ``at``)."""
    from dvara.seen import ask_json

    if not samay:
        return "Schedules aren't switched on here, so I can't send it every morning."
    cards, trouble = await ask_json([samay, "list", "--json"])
    if trouble or not isinstance(cards, list):
        return trouble or "Samay didn't list its schedules. Try again soon."
    mine = [c for c in cards if isinstance(c, dict) and c.get("owner") == who.id
            and c.get("runner") == "dvara" and (c.get("prompt") or "").strip() == WORDS[0]]
    if not on:
        for card in mine:
            _, trouble = await ask_json([samay, "rm", str(card["id"]), "--json"])
            if trouble:
                return trouble
        return ("Stopped: no more morning briefs." if mine
                else "There's no morning brief to stop.")
    had = ((mine[0].get("when") or {}).get("at") if mine else None) or MORNING_AT
    if mine and (at is None or at == had):
        return (f"Already: {mine[0].get('sentence') or 'every morning'}. "
                f"/brief {MORNING} off stops it; a time after it (7am) moves it.")
    for card in mine:
        _, trouble = await ask_json([samay, "rm", str(card["id"]), "--json"])
        if trouble:
            return trouble
    at = at or MORNING_AT
    made, trouble = await ask_json(
        [samay, "add", WORDS[0], "--when", f"at {at}", "--runner", "dvara",
         "--as", who.id, "--agent", agent, "--notify", "always", "--json"],
        env={"SAMAY_TZ": who.zone} if who.zone else None)
    if trouble or not isinstance(made, dict):
        return trouble or "Samay didn't make it. Try again soon."
    first = "Moved" if mine else "Done"
    return (f"{first}: your house's brief every day at {at} "
            f"({made.get('tz') or 'your time'}). /brief {MORNING} off stops it.")

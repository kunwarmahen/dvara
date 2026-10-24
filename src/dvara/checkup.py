"""``/doctor``: what's wrong with what is yours, in plain words.

Sarathi's doctor (its doctor.py) answers the owner at the computer:
the image, the firewall, every piece's status, the disk. A person in the
house has the same question about a smaller world -- *why didn't my
morning brief come? why can't it read my mail?* -- and none of the
house's answers. They can't run ``sarathi doctor``, and most of what it
says isn't theirs to fix.

So a person asks in their chat, ``/doctor``, and gets the lines that are
THEIRS: their accounts (from their own Setu folder, or the accounts of
a shared one they may use), their schedules' runs of the last day, their
watches, their phones, and their own limits (today's allowance, today's
messages, their hours). Every line comes from the program that knows,
as the house doctor's do: ``setu status --json`` in their folder,
``samay list`` and ``samay runs``, ``prahari list``, ``sparsh status``,
and this service's own ledger. Nobody else's line is ever in it.

RED, AMBER, GREEN, AS AT THE COMPUTER. Red is broken now (a sign-in
the site ended, a day's allowance spent). Amber is worth a look (a
schedule that failed, a watch that paused, a phone not connected, a
Google sign-in ending in its last three days). Green is fine. Each red
and amber line says what fixes it IN THE CHAT when they can
(``/connect gmail as personal``, ``/unlock``), and who to ask when they
can't (an account in a folder the owner looks after).

THE OWNER IS TOLD WHERE THE HOUSE IS. The owner's own ``/doctor`` is
their own lines too, and one more: the whole house is Settings → Check
on the home page, or ``sarathi doctor``. Dvara can't see the image or
the firewall from here, and doesn't pretend to.

A PROGRAM THAT DOESN'T ANSWER IS SAID, NOT HIDDEN. Samay not running is
red for someone with schedules (nothing of theirs runs); a Setu that
won't read their folder is amber with what it said.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

WORDS = ("/doctor",)
LEVELS = ("red", "amber", "green")
MARK = {"red": "🔴", "amber": "🟠", "green": "🟢"}
#: A Google sign-in this close to its end is worth a look (as at the computer).
SIGN_IN_DAYS = 3.0
#: What a schedule's run ended as, that the person should hear about.
TROUBLE = {"failed": "failed", "timed_out": "ran out of time", "needs_person":
           "needed you", "refused": "was refused a tool", "held": "was held for you"}
#: A watch's look that went wrong.
LOOK_TROUBLE = {"failed": "its look failed", "broken": "its pick found nothing",
                "needs_person": "it hit a sign-in"}
#: Of a daily allowance, this much spent is worth a look.
NEARLY = 0.8
ASK_WITHIN = 30
#: Whose things a person at the computer made are filed as (Samay's and
#: Prahari's ``local``): the owner's.
LOCAL = "local"
#: What starts a stopped piece again, for a person who isn't the owner.
STARTS = "tell the owner: it starts again with Sarathi"
#: And for the owner, who can.
OWNER_STARTS = "`sarathi up` at the computer (or Apply on the home page)"


def is_word(text: str) -> bool:
    first = text.strip().split(maxsplit=1)[:1]
    return bool(first) and first[0].split("@")[0].lower() in WORDS


@dataclass
class Line:
    level: str          # red | amber | green
    about: str          # accounts, schedules, watches, phone, limits
    said: str
    fix: str = ""


def _json(argv: list[str], env: dict[str, str] | None = None) -> Any:
    """A program's --json answer; raises RuntimeError in its own words."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=ASK_WITHIN,
                              env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{Path(argv[0]).name} didn't answer ({type(exc).__name__})"
                           ) from None
    if done.returncode != 0:
        said = (done.stderr or done.stdout).strip().splitlines()
        raise RuntimeError(said[-1] if said else f"{Path(argv[0]).name} failed")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"{Path(argv[0]).name} didn't answer in JSON") from None


def _epoch(at: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(at)).timestamp() if at else None
    except ValueError:
        return None


def _when(at: Any, zone: str | None = None) -> str:
    if not at:
        return "some time today"
    try:
        moment = datetime.fromisoformat(str(at))
    except ValueError:
        return str(at)
    if zone:
        from zoneinfo import ZoneInfo
        return moment.astimezone(ZoneInfo(zone)).strftime("%a %H:%M")
    return moment.astimezone().strftime("%a %H:%M")


# ---- each part ---------------------------------------------------------------------

def accounts(data: dict, *, narrowed: tuple[str, ...] | None, own: bool,
             owner: str | None, now: float, zone: str | None = None,
             is_owner: bool = False) -> list[Line]:
    """Their sign-ins, from ``setu status --json`` in their folder. The
    fix is a chat word when the folder is theirs to change from the chat,
    the computer's own words for the owner, and whom to ask for anyone
    else."""
    rows = [r for r in data.get("connections") or []
            if narrowed is None or r.get("ref") in narrowed]
    ask = f"ask {owner} to sign it in again" if owner else "ask the owner to sign it in again"
    out = []
    for r in rows:
        again = (f"/connect {r.get('connector')} as {r.get('account')}" if own else
                 f"setu connect {r.get('connector')} --as {r.get('account')} at the "
                 "computer, or Setu's page" if is_owner else ask)
        if r.get("expired"):
            out.append(Line("red", "accounts", f"{r.get('ref')}: the sign-in stopped "
                            "working (the site ended it); your agents can't use it", again))
            continue
        end = _epoch(r.get("ends"))
        if end is not None and end - now <= SIGN_IN_DAYS * 86400:
            out.append(Line("amber", "accounts", f"{r.get('ref')}: Google ends this "
                            f"sign-in {_when(r.get('ends'), zone)}",
                            f"sign in again before then: {again}"))
    lock = data.get("lock") or {}
    if lock.get("locked") and not lock.get("open"):
        out.append(Line("amber", "accounts", "your accounts are locked with your "
                        "passphrase, so your agents can't use them now",
                        "/unlock" if own else "`setu unlock` at the computer" if is_owner
                        else "ask the owner to unlock them"))
    if not out:
        out.append(Line("green", "accounts", f"{len(rows)} account"
                        f"{'s' * (len(rows) != 1)}, none stopped" if rows
                        else "no accounts connected"))
    return out


def schedules(status: dict | None, listed: list, runs: list, *, person: set[str],
              since: datetime, zone: str | None = None, start: str = "") -> list[Line]:
    """Their schedules' runs of the last day, from Samay's record.
    ``person``: the names their schedules are filed under."""
    mine = {s.get("id"): s for s in listed if isinstance(s, dict)
            and s.get("owner") in person}
    if not mine:
        return []
    out = []
    if status is not None and not status.get("serving"):
        out.append(Line("red", "schedules", "Samay's clock isn't running, so none of "
                        f"your {len(mine)} schedule{'s' * (len(mine) != 1)} runs",
                        start or STARTS))
    for run in runs:
        schedule = mine.get(run.get("schedule"))
        at = _epoch(run.get("ended_at") or run.get("started_at") or run.get("due_at"))
        if schedule is None or run.get("outcome") not in TROUBLE or at is None \
                or at < since.timestamp():
            continue
        why = run.get("summary") or run.get("detail") or ""
        out.append(Line("amber", "schedules",
                        f"\"{schedule.get('prompt') or schedule.get('id')}\" "
                        f"{TROUBLE[run['outcome']]} at "
                        f"{_when(run.get('ended_at') or run.get('due_at'), zone)}"
                        + (f": {' '.join(str(why).split())[:160]}" if why else ""),
                        "/schedules shows it; ask me to change it"))
    for s in mine.values():
        if s.get("state") == "paused" and s.get("paused_because"):
            out.append(Line("amber", "schedules", f"\"{s.get('prompt') or s.get('id')}\" "
                            f"is paused: {s.get('paused_because')}",
                            "ask me to resume it once that's mended"))
    if not out:
        out.append(Line("green", "schedules", f"{len(mine)} schedule"
                        f"{'s' * (len(mine) != 1)}, none failed in the last day"))
    return out


def watches(status: dict | None, listed: list, *, person: set[str],
            start: str = "") -> list[Line]:
    """Their watches, from Prahari's own list. ``person``: the names
    their watches are filed under."""
    mine = [w for w in listed if isinstance(w, dict) and w.get("owner") in person]
    if not mine:
        return []
    out = []
    if status is not None and not status.get("serving"):
        out.append(Line("red", "watches", "Prahari isn't running, so none of your "
                        f"{len(mine)} watch{'es' * (len(mine) != 1)} looks or hears",
                        start or STARTS))
    for w in mine:
        last = w.get("last_look") or {}
        if w.get("state") == "paused" and w.get("paused_because"):
            out.append(Line("amber", "watches", f"\"{w.get('name')}\" is paused: "
                            f"{w.get('paused_because')}",
                            "ask me to mend its check and resume it"))
        elif last.get("outcome") in LOOK_TROUBLE:
            # Prahari's own words when it said any; they say more than ours
            why = " ".join(str(last.get("detail") or "").split())[:200]
            out.append(Line("amber", "watches", f"\"{w.get('name')}\": "
                            + (why or LOOK_TROUBLE[last["outcome"]]),
                            "ask me to look at it"))
    if not out:
        out.append(Line("green", "watches", f"{len(mine)} watch"
                        f"{'es' * (len(mine) != 1)}, all looking"))
    return out


def phones(data: dict, *, mine: tuple[str, ...]) -> list[Line]:
    """Their phones, from Sparsh: connected or not, by name."""
    from yantra.sparsh_link import SparshLinkError, only, ready_phones, standing

    try:
        data = only(data, *mine) if mine else data
    except SparshLinkError as exc:
        return [Line("amber", "phone", str(exc), "ask the owner which phones are yours")]
    named = standing(data)
    if not named:
        return ([Line("green", "phone", "your phone is connected")] if ready_phones(data)
                else [Line("amber", "phone", "no phone is connected",
                           "plug it in, or reconnect its Wi-Fi from the home page")])
    return [Line("green", "phone", f"{n['name']} is connected") if n.get("connected")
            else Line("amber", "phone", f"{n['name']} isn't connected"
                      + (f": {n['note']}" if n.get("note") else ""),
                      "plug it in and unlock it; the owner can bring it back from the "
                      "home page")
            for n in named]


def limits(who: Any, *, spent: float, sent: int, now: datetime,
           reset: datetime) -> list[Line]:
    """Their own limits: today's allowance and messages, and their hours."""
    out = []
    if who.max_usd_per_day is not None:
        cap = who.max_usd_per_day
        line = f"${spent:.2f} of your ${cap:.2f} today"
        back = f"it comes back at {reset:%H:%M} UTC"
        out.append(Line("red", "limits", f"{line}: spent, so your agents won't answer",
                        f"{back}, or ask the owner for more") if spent >= cap else
                   Line("amber", "limits", f"{line}: nearly spent", back)
                   if spent >= NEARLY * cap else Line("green", "limits", line))
    if who.max_turns_per_day is not None:
        cap = who.max_turns_per_day
        line = f"{sent} of your {cap} messages today"
        out.append(Line("red", "limits", f"{line}: that's all for today",
                        "they come back at midnight UTC") if sent >= cap else
                   Line("green", "limits", line))
    if who.hours is not None:
        out.append(Line("green", "limits", f"your agents answer {who.hours}, open now")
                   if who.hours.open_at(now) else
                   Line("amber", "limits", f"your agents answer {who.hours}, and it's "
                        f"{now:%H:%M} for you: closed now", "ask again in your hours"))
    return out


# ---- all of it -----------------------------------------------------------------------

@dataclass
class Programs:
    """Where each program is; None for one this service wasn't given."""

    setu: str | None = None
    samay: str | None = None
    prahari: str | None = None
    sparsh: str | None = None


async def examine(who: Any, *, programs: Programs, setu_home: Path | None,
                  setu_key: str | None, spent: float, sent: int,
                  owner: str | None) -> list[Line]:
    """Every line for this person, red first."""
    from dvara.limits import now_for

    now = now_for(who.zone)
    lines: list[Line] = []
    # What the owner made at the computer (Yantra's page) is filed as
    # "local": theirs too. Nobody else's is.
    is_owner = owner is not None and who.id == owner
    names = {who.id} | ({LOCAL} if is_owner else set())
    start = OWNER_STARTS if is_owner else STARTS

    async def ask(argv: list[str], env: dict[str, str] | None = None) -> Any:
        return await asyncio.to_thread(_json, argv, env)

    if setu_home is not None and (program := programs.setu or shutil.which("setu")):
        env = {**os.environ, "SETU_HOME": str(setu_home)}
        if setu_key:
            env["SETU_VAULT_KEY"] = setu_key
        try:
            data = await ask([program, "status", "--json"], env)
            lines += accounts(data, narrowed=who.setu_accounts, own=who.manages_setu,
                              owner=owner, now=now.timestamp(), zone=who.zone,
                              is_owner=is_owner)
        except RuntimeError as exc:
            lines.append(Line("amber", "accounts", f"your accounts couldn't be read: "
                              f"{exc}", "try again soon; tell the owner if it stays"))
    if programs.samay:
        try:
            listed = await ask([programs.samay, "list", "--json"])
            status = runs = None
            if any(isinstance(s, dict) and s.get("owner") in names for s in listed):
                status = await ask([programs.samay, "status", "--json"])
                runs = await ask([programs.samay, "runs", "--limit", "200", "--json"])
            lines += schedules(status, listed, runs or [], person=names,
                               since=datetime.now(UTC) - timedelta(days=1), zone=who.zone,
                               start=start)
        except RuntimeError as exc:
            lines.append(Line("amber", "schedules", f"Samay didn't answer: {exc}", ""))
    if programs.prahari:
        try:
            listed = await ask([programs.prahari, "list", "--json"])
            status = (await ask([programs.prahari, "status", "--json"])
                      if any(isinstance(w, dict) and w.get("owner") in names
                             for w in listed) else None)
            lines += watches(status, listed, person=names, start=start)
        except RuntimeError as exc:
            lines.append(Line("amber", "watches", f"Prahari didn't answer: {exc}", ""))
    if programs.sparsh and who.has_phone:
        try:
            lines += phones(await ask([programs.sparsh, "status", "--json"]),
                            mine=who.phones)
        except RuntimeError as exc:
            lines.append(Line("amber", "phone", f"Sparsh didn't answer: {exc}", ""))
    from dvara import money
    lines += limits(who, spent=spent, sent=sent, now=now, reset=money.next_reset())
    return sorted(lines, key=lambda line: LEVELS.index(line.level))


def said(lines: list[Line], *, is_owner: bool) -> str:
    """The answer, for any channel: a count, then each line with its fix."""
    counts = {level: sum(1 for line in lines if line.level == level) for level in LEVELS}
    head = ("Nothing of yours is wrong." if not counts["red"] and not counts["amber"]
            else " · ".join(f"{counts[level]} {level}" for level in ("red", "amber")
                            if counts[level]))
    out = [f"Your check: {head}"]
    for line in lines:
        out.append(f"{MARK[line.level]} {line.said}")
        if line.fix:
            out.append(f"   → {line.fix}")
    if not lines:
        out.append("There's nothing of yours here to check yet.")
    if is_owner:
        out += ["", "The whole house (the image, the firewall, every piece): Settings → "
                "Check on the home page, or `sarathi doctor` at the computer."]
    return "\n".join(out)

"""``dvara grants``: every standing yes in the house, and what it was used for.

Who may do what without being asked is written in five places, by
different hands, at different times: the owner's standing rules
(policy.toml), each person's rung and the sources they trust
(actors.toml), each agent's own mode (its agent.toml), the tools a
schedule was granted when it was made (Samay), and the tool each watch
calls with no model, plus the tools its follow-up turn may use (Prahari).
Each one was a sensible yes the day it was given. Nobody could see them
together, so nobody could see the one that had quietly grown too wide,
or the one nothing has used since spring.

ONE LIST, READ FROM WHERE EACH YES LIVES. Nothing here is a copy: the
rules and the people are this service's own files, the schedules and the
watches are what Samay and Prahari answer to ``list --json``, and the
house's rung is what the running ``dvara serve`` wrote into its claim
(claim.py). A program that doesn't answer is named, not guessed at.

WHAT A PERSON'S TURN REALLY RUNS UNDER. A rung is the strictest of three
(gate.stricter): the house's, the person's, and the agent's. A person
written as ``yolo`` talking to an agent that ships ``ask`` is asked; the
list says the answer, per agent, rather than the three ingredients.

BESIDE EACH YES, WHAT WAS DONE WITH IT. The runs ledger already keeps,
for every call, what settled it (runs.ToolStep.decided_by): a rule, a
person's yes, a schedule's grant, one yes for the task. So each rule
carries how many calls it settled and when it last did, and each person
how many calls ran, how many were asked, and how many ran in turns
nobody typed. Counts, never arguments: the ledger keeps shapes on purpose
and this does not undo that.

WORTH A LOOK, NOT AN ALARM. ``look`` lines are what an owner would want
to hear about: a rule whose last day has passed (it no longer answers --
rules.py), one ending within a week, an allow that has settled nothing in
the window, a schedule or watch granted a pattern rather than named
tools, a person whose agent changes things unasked. Nothing is changed
from here; each line says where it is changed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, date, datetime, timedelta
from typing import Any

from dvara.gate import stricter

FORMAT = "dvara.grants.v1"
#: The window the counts cover, unless asked otherwise.
DAYS = 30
#: A rule this close to its last day is worth a look.
ENDING_DAYS = 7
#: What Samay and Prahari call the person at the computer: the owner.
LOCAL = "local"
#: How long Samay or Prahari may take to list.
ASK_SECONDS = 30
#: The rung Sarathi starts the house on, assumed when Dvara isn't running.
HOUSE_DEFAULT = "ask"
RUNG_WORDS = {"read_only": "only reads", "ask": "asks before a change",
              "yolo": "changes things without asking"}


def report(*, book, rules, roster, runs, house_rung: str | None, owner: str | None,
           serving: bool = False, samay: str | None = None, prahari: str | None = None,
           days: int = DAYS, today: date | None = None) -> dict[str, Any]:
    """Every grant, as ``dvara.grants.v1``. ``book`` is the ActorBook,
    ``rules`` the RuleBook, ``roster`` the Roster, ``runs`` the RunLedger;
    ``samay``/``prahari`` the programs to ask (None: not asked)."""
    today = today or date.today()
    since = datetime.now(UTC) - timedelta(days=days) if days > 0 else None
    used = runs.grant_use(since)
    counts = runs.rule_counts(since)
    looks: list[dict[str, str]] = []

    out_rules = []
    for rule in rules:
        settled = counts.get(rule.id, 0)
        state = "on"
        if rule.ended(today):
            state = "ended"
            looks.append(_look(f"The rule {rule.verdict} {_wrote(rule)} ended on "
                               f"{rule.until.isoformat()}: it no longer answers",
                               "take it out, or move its Until day (Settings → Rules)"))
        elif rule.until is not None and (rule.until - today).days < ENDING_DAYS:
            state = "ending"
            looks.append(_look(f"The rule {rule.verdict} {_wrote(rule)} ends on "
                               f"{rule.until.isoformat()}",
                               "move its Until day if it should go on (Settings → Rules)"))
        elif rule.verdict == "allow" and not settled and since is not None:
            looks.append(_look(f"The rule allow {_wrote(rule)} settled nothing in "
                               f"{days} days", "take it out if it isn't needed "
                               "(Settings → Rules)"))
        out_rules.append({"id": rule.id, "verdict": rule.verdict, "tool": rule.tool,
                          "args": {k: list(v) for k, v in rule.args.items()},
                          "until": rule.until.isoformat() if rule.until else None,
                          "state": state, "settled": settled,
                          "last": used["rules_last"].get(rule.id)})

    house = house_rung or HOUSE_DEFAULT
    try:
        names = roster.names()
    except Exception:  # noqa: BLE001 -- a broken roster is the status page's line
        names = []
    modes: dict[str, str | None] = {}
    for name in names:
        try:
            modes[name] = roster.spec(name).permissions_mode
        except Exception:  # noqa: BLE001
            modes[name] = None

    people = []
    for pid in book.ids():
        actor = book.get(pid)
        theirs = [n for n in names if actor.agents is None or n in actor.agents]
        agents = [{"agent": n, "rung": stricter(house, actor.permissions, modes.get(n))}
                  for n in theirs]
        free = [a["agent"] for a in agents if a["rung"] == "yolo"]
        if free:
            looks.append(_look(f"{pid}'s {_list(free)} {'changes' if len(free) == 1 else 'change'} "
                               f"things without asking",
                               "Settings → People (their rung), or the agent's own mode"))
        tally = used["people"].get(pid) or dict.fromkeys(
            ("ran", "asked", "rule", "ahead", "for_turn", "refused", "by_program"), 0)
        people.append({
            "id": pid, "owner": pid == owner, "rung": actor.permissions,
            "agents": agents, "trusted": list(actor.trusted),
            "approver": actor.approver,
            "accounts": ("own folder" if actor.setu == "own" else
                         "shared folder" if actor.setu else None),
            "setu_accounts": list(actor.setu_accounts) if actor.setu_accounts is not None
            else None,
            "connectors": list(actor.connectors) if actor.connectors is not None else None,
            "phones": list(actor.phones) if actor.phone else [],
            "did": tally,
        })

    known = set(book.ids()) | {LOCAL}
    schedules, samay_why = _schedules(samay, known, owner, looks)
    watches, indriyas, prahari_why = _watches(prahari, known, owner, looks)
    return {"format": FORMAT, "days": days, "house": {"rung": house_rung,
            "assumed": house_rung is None, "serving": serving},
            "rules": out_rules, "people": people,
            "schedules": schedules, "watches": watches, "indriyas": indriyas,
            "asked": {"samay": samay_why, "prahari": prahari_why}, "look": looks}


def _assumed(house: dict) -> str:
    """Why the house's rung is a guess, when it is one."""
    if not house["assumed"]:
        return ""
    if house.get("serving"):
        return ("  -- assumed: the running Dvara was started before it wrote its rung "
                "down; it says after its next start")
    return "  -- assumed: Dvara isn't running; this is the rung Sarathi starts it on"


def _look(said: str, fix: str) -> dict[str, str]:
    return {"said": said, "fix": fix}


def _wrote(rule) -> str:
    target = ", ".join(f"{k}={'|'.join(v)}" for k, v in sorted(rule.args.items()))
    return f"{rule.tool} {target}".strip()


def _list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _whose(owner_field: Any, owner: str | None) -> str:
    who = str(owner_field or "")
    return (owner or who) if who == LOCAL else who


def _ask(program: str | None, *argv: str) -> tuple[Any, str | None]:
    """A sibling's ``... --json`` answer, or why there isn't one."""
    found = program and (shutil.which(program) or program)
    if not found:
        return None, "not on this computer"
    try:
        done = subprocess.run([found, *argv, "--json"], capture_output=True, text=True,
                              timeout=ASK_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"didn't answer ({type(exc).__name__})"
    if done.returncode != 0:
        tail = (done.stderr or "").strip().splitlines()[-1:] or ["no answer"]
        return None, tail[0]
    try:
        return json.loads(done.stdout), None
    except ValueError:
        return None, "answered something that isn't JSON"


def _patterns(tools: list[str]) -> list[str]:
    return [t for t in tools if any(c in t for c in "*?[")]


def _schedules(samay, known, owner, looks) -> tuple[list[dict], str | None]:
    if samay is None:
        return [], "not switched on"
    cards, why = _ask(samay, "list")
    if why or not isinstance(cards, list):
        return [], why or "didn't list its schedules"
    rows = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        person = _whose(card.get("owner"), owner)
        tools = [str(t) for t in card.get("allow_tools") or []]
        # a schedule that has run its last time can't use its grant again
        if person not in known or not tools or card.get("state") not in ("active", "paused"):
            continue
        sentence = card.get("sentence") or ""
        wide = _patterns(tools)
        if wide and card.get("state") == "active":
            looks.append(_look(f"{person}'s schedule \"{sentence[:60]}\" may use every "
                               f"tool matching {', '.join(wide)}",
                               f"samay allow / Samay's page: name the tools instead "
                               f"(schedule {card.get('id')})"))
        last = card.get("last_run") or {}
        rows.append({"id": card.get("id"), "person": person, "sentence": sentence,
                     "state": card.get("state") or "", "tools": tools,
                     "last": last.get("ended_at") or last.get("due_at")})
    return rows, None


def _watches(prahari, known, owner, looks) -> tuple[list[dict], list[dict], str | None]:
    if prahari is None:
        return [], [], "not switched on"
    cards, why = _ask(prahari, "list")
    if why or not isinstance(cards, list):
        return [], [], why or "didn't list its watches"
    rows = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        person = _whose(card.get("owner"), owner)
        if person not in known:
            continue
        look = (card.get("check") or {}).get("tool") or ""
        then = [str(t) for t in card.get("allow_tools") or []]
        wide = _patterns(then)
        if wide and card.get("state") == "active":
            looks.append(_look(f"{person}'s watch \"{card.get('name')}\" lets its turn use "
                               f"every tool matching {', '.join(wide)}",
                               f"prahari allow / Prahari's page (watch {card.get('id')})"))
        rows.append({"id": card.get("id"), "person": person, "name": card.get("name") or "",
                     "state": card.get("state") or "", "looks_with": look,
                     "listens": bool(card.get("listen")),
                     "senses": card.get("sense_name") or card.get("sense") or "",
                     "then_tools": then,
                     "then": ("agent" if card.get("then") else
                              "routine" if card.get("routine") else "a line to you")})
    readings, _ = _ask(prahari, "indriya", "list", "--all")
    indriyas = []
    for card in readings if isinstance(readings, list) else []:
        if not isinstance(card, dict):
            continue
        person = _whose(card.get("owner"), owner)
        if person not in known:
            continue
        indriyas.append({"id": card.get("id"), "person": person, "name": card.get("name"),
                         "state": card.get("state") or "",
                         "looks_with": (card.get("check") or {}).get("tool") or "",
                         "share": card.get("share") or "mine"})
    return rows, indriyas, None


def lines(data: dict) -> list[str]:
    """``dvara grants`` for a person at a terminal."""
    out: list[str] = []
    house = data["house"]
    rung = house["rung"] or HOUSE_DEFAULT
    out.append(f"The house: {RUNG_WORDS.get(rung, rung)} ({rung})" + _assumed(house))
    window = f"the last {data['days']} days" if data["days"] else "everything recorded"
    out.append(f"Counts cover {window}.")
    out.append("")
    out.append(f"Standing rules ({len(data['rules'])})")
    if not data["rules"]:
        out.append("  none: every change is decided by the rung alone")
    for r in data["rules"]:
        args = ", ".join(f"{k}={'|'.join(v)}" for k, v in sorted(r["args"].items()))
        until = {"ended": f"  ENDED {r['until']}", "ending": f"  ends {r['until']}",
                 "on": f"  until {r['until']}" if r["until"] else ""}[r["state"]]
        last = f", last {r['last'][:10]}" if r["last"] else ""
        out.append(f"  {r['verdict']:<6} {r['tool']} {args}".rstrip()
                   + f"  -- settled {r['settled']}{last}{until}")
    out.append("")
    out.append("People")
    for p in data["people"]:
        own = f"own rung {p['rung']}" if p["rung"] else "no rung of their own"
        out.append(f"  {p['id']}{' (owner)' if p['owner'] else ''}: {own}")
        for a in p["agents"]:
            out.append(f"      {a['agent']}: {RUNG_WORDS.get(a['rung'], a['rung'])}")
        extra = []
        if p["trusted"]:
            extra.append("trusts " + ", ".join(p["trusted"]))
        if p["approver"]:
            extra.append(f"asks {p['approver']} first")
        if p["accounts"]:
            extra.append(p["accounts"])
        if p["phones"]:
            extra.append("phones " + ", ".join(p["phones"]))
        if extra:
            out.append("      " + "; ".join(extra))
        d = p["did"]
        out.append(f"      {d['ran']} calls ran ({d['by_program']} with nobody watching), "
                   f"{d['asked']} asked, {d['rule']} by a rule, {d['ahead']} by a "
                   f"schedule's grant, {d['for_turn']} by a yes for the task, "
                   f"{d['refused']} refused")
    out.append("")
    asked = data["asked"]
    out.append(f"Schedules with tools of their own ({len(data['schedules'])})"
               + (f"  -- Samay: {asked['samay']}" if asked["samay"] else ""))
    for s in data["schedules"]:
        out.append(f"  {s['person']}: {s['sentence'][:70]} [{s['state']}]")
        out.append(f"      may use {', '.join(s['tools'])}")
    out.append("")
    out.append(f"Watches ({len(data['watches'])})"
               + (f"  -- Prahari: {asked['prahari']}" if asked["prahari"] else ""))
    for w in data["watches"]:
        how = (f"looks with {w['looks_with']}" if w["looks_with"] else
               f"senses {w['senses']}" if w["senses"] else
               "listens" if w["listens"] else "looks")
        tools = f"; its turn may use {', '.join(w['then_tools'])}" if w["then_tools"] else ""
        out.append(f"  {w['person']}: {w['name']} [{w['state']}] {how}, then "
                   f"{w['then']}{tools}")
    if data["indriyas"]:
        out.append("")
        out.append(f"Readings ({len(data['indriyas'])})")
        for i in data["indriyas"]:
            out.append(f"  {i['person']}: {i['name']} [{i['state']}] looks with "
                       f"{i['looks_with'] or '(pushed)'}, shared with "
                       f"{'the house' if i['share'] == 'house' else 'nobody'}")
    out.append("")
    if data["look"]:
        out.append(f"Worth a look ({len(data['look'])})")
        for item in data["look"]:
            out.append(f"  • {item['said']}")
            out.append(f"      {item['fix']}")
    else:
        out.append("Nothing worth a look.")
    return out

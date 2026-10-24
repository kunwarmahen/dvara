"""The owner's files, changed from a page: people, rules and agents.

Who may talk to an agent, what each may spend, which accounts their
agents reach, the standing answers, and each agent's own package all
live in files the owner wrote: ``actors.toml``, ``policy.toml``, and an
``agent.toml`` plus ``prompt.md`` per agent. Those files stay the record
(reviewable, diffable, reread while Dvara runs). But a person who
installed Sarathi should never have to open one: the home page changes
them through ``dvara settings`` (cli.py), which calls this module.

CHECKED BY THE CODE THAT READS IT. Every change is applied to the text,
then parsed exactly as Dvara will parse it -- ``ActorBook`` for people,
``RuleBook`` for rules, Yantra's ``load_package`` for an agent -- and
only a file that loads is written. A change that would not load is
refused with the same words a hand edit would have produced at start-up.

THE REST OF THE FILE IS KEPT. One person, one agent table, or the rules
are rewritten (tomledit.py); every other line, comments included, stays
as it was. The file before is kept beside it as ``.bak``, and the new
one replaces it in one step, so Dvara rereading it mid-write sees the
old file or the new one, never half.

WHAT A FORM DOESN'T SHOW IS LEFT ALONE. A person's change starts from
their table as it is: keys the page doesn't edit (``max_wait_per_day``,
a channel of another kind) are carried over. A key set to null is taken
out. And the whole file may be sent as text, checked the same way, for
anything a form doesn't cover.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path

from dvara import promoting, tomledit, toolbox
from dvara.actors import OWN_SETU, ActorBook
from dvara.errors import ConfigProblem
from dvara.gate import LADDER
from dvara.rules import RuleBook

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}\Z")
STARTER_POLICY = ("# Standing answers for your agents' tools: allow, ask or deny.\n"
                  "# Written from the home page; see dvara's README, The policy file.\n")


# ---- reading ---------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def person(actor) -> dict:
    """One person as the page edits them."""
    telegram = [c.id for c in actor.channels if c.kind == "telegram"]
    setu = ("none" if actor.setu is None else "own" if actor.setu == OWN_SETU
            else actor.setu)
    return {"id": actor.id, "agents": list(actor.agents) if actor.agents is not None else None,
            "permissions": actor.permissions, "max_usd_per_day": actor.max_usd_per_day,
            "max_usd_per_turn": actor.max_usd_per_turn, "receipt": actor.receipt,
            "setu": setu, "setu_accounts": list(actor.setu_accounts or []) or None,
            "setu_manage": actor.setu_manage, "phone": actor.phone,
            "phones": list(actor.phones) or None, "telegram": telegram,
            "hours": str(actor.hours) if actor.hours else None,
            "max_turns_per_day": actor.max_turns_per_day, "approver": actor.approver,
            "speak": actor.speak,
            "other_channels": [f"{c.kind}:{c.id}" for c in actor.channels
                               if c.kind != "telegram"]}


def show(*, root: Path, actors: Path, policy: Path, examples: Path | None = None,
         state: Path | None = None) -> dict:
    """Everything the page draws: each file's text and what it says, and
    the tools an agent could be given (toolbox.py), ticked as each
    agent's allow list says."""
    out: dict = {"ladder": list(LADDER)}
    box = toolbox.toolbox(state)
    out["toolbox"] = box["tools"]
    text = _read(actors)
    try:
        book = ActorBook.from_toml(actors)
        out["people"] = [person(book.get(i)) for i in book.ids()]
        out["actors_problem"] = None
    except ConfigProblem as exc:
        out["people"], out["actors_problem"] = [], str(exc)
    out["actors"] = {"path": str(actors), "text": text}
    ptext = _read(policy)
    try:
        rules = tomllib.loads(ptext).get("rule", []) if ptext else []
        out["rules"], out["policy_problem"] = rules, None
    except tomllib.TOMLDecodeError as exc:
        out["rules"], out["policy_problem"] = [], f"{policy}: {exc}"
    out["policy"] = {"path": str(policy), "text": ptext}
    agents = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        manifest = folder / "agent.toml"
        if not manifest.is_file():
            continue
        raw = _read(manifest)
        try:
            tables = tomllib.loads(raw)
            prompt_name = tables.get("agent", {}).get("prompt", "prompt.md")
            problem = None
        except tomllib.TOMLDecodeError as exc:
            tables, prompt_name, problem = {}, "prompt.md", str(exc)
        allow = (tables.get("tools") or {}).get("allow")
        allow = allow if isinstance(allow, list) else None
        agents.append({"name": folder.name, "path": str(manifest), "text": raw,
                       "tables": tables, "prompt": _read(folder / prompt_name),
                       "prompt_file": prompt_name, "problem": problem,
                       "tools": {"every": allow is None,
                                 "ticked": [r["name"] for r in box["tools"]
                                            if allow is not None
                                            and toolbox.ticked(allow, r["name"])],
                                 "advanced": toolbox.covered(allow, box["tools"]),
                                 "seen": box["seen"].get(folder.name, [])},
                       # what its people kept, for "make it a tool" (promoting.py)
                       "learned": promoting.learned(state, folder.name)})
    out["agents"] = agents
    out["household"] = household(state) if state is not None else None
    out["examples"] = sorted(p.name for p in examples.iterdir()
                             if (p / "agent.toml").is_file()) \
        if examples is not None and examples.is_dir() else []
    return out


def household(state: Path) -> dict:
    """What everyone's agents know, and the offers waiting (household.py)."""
    from dataclasses import asdict

    from dvara.household import Household

    house = Household(state)
    return {"facts": [asdict(f) for f in house.facts()],
            "offered": [asdict(f) for f in house.offered()]}


# ---- writing -----------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    """The old file kept as .bak; the new one in place in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(text)
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp, path)


def _loads(text: str, where: Path) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigProblem(f"{where}: {exc}") from None


def check_actors(text: str, where: Path) -> None:
    ActorBook.from_dict(_loads(text, where), where=where)


def check_policy(text: str, where: Path) -> None:
    RuleBook.from_dict(_loads(text, where), where=where)


def _name(name: str, what: str) -> str:
    if not isinstance(name, str) or not NAME.match(name):
        raise ConfigProblem(f"{what} names are letters, numbers, - and _ "
                            f"(up to 40), not {name!r}")
    return name


def set_person(actors: Path, name: str, fields: dict) -> dict:
    """Add ``name`` or change them; returns them as the page shows them."""
    _name(name, "a person's")
    text = _read(actors)
    raw = dict(_loads(text, actors).get("actor", {}).get(name, {}) if text else {})
    channels = [c for c in raw.pop("channel", []) or []
                if "telegram" not in fields or c.get("kind") != "telegram"]
    if "telegram" in fields:
        for tid in fields.get("telegram") or []:
            tid = str(tid).strip()
            if not tid.isdigit():
                raise ConfigProblem(f"a Telegram id is a number (the bot shows it), "
                                    f"not {tid!r}")
            channels.append({"kind": "telegram", "id": tid})
    for key, value in fields.items():
        if key in ("telegram", "id", "other_channels"):
            continue
        if key == "setu":
            value = (None if value in (None, "", "none") else True if value == "own"
                     else value)
        if value is None or value == [] or value is False or value == "":
            raw.pop(key, None)          # each of these is the key's default
        else:
            raw[key] = value
    block = tomledit.render(f"actor.{name}", raw, {"channel": channels} if channels else None)
    candidate = tomledit.put(text, f"actor.{name}", block)
    check_actors(candidate, actors)
    _write(actors, candidate)
    return person(ActorBook.from_dict(tomllib.loads(candidate)).get(name))


def remove_person(actors: Path, name: str) -> None:
    text = _read(actors)
    if name not in _loads(text, actors).get("actor", {}):
        raise ConfigProblem(f"there's nobody called {name!r} in {actors}")
    candidate = tomledit.drop(text, f"actor.{name}")
    check_actors(candidate, actors)
    _write(actors, candidate)


def set_rules(policy: Path, rules: list[dict]) -> None:
    """The standing answers, all of them, as the page lists them."""
    text = _read(policy) or STARTER_POLICY
    if tomledit.span(text, "rule") is not None:
        text = tomledit.drop(text, "rule")
    block = "\n\n".join(tomledit.render("rule", {k: v for k, v in r.items()
                                                 if v not in (None, "", {})})
                        .replace("[rule]", "[[rule]]", 1) for r in rules)
    candidate = text.rstrip("\n") + ("\n\n" + block if block else "") + "\n"
    check_policy(candidate, policy)
    _write(policy, candidate)


def check_agent(folder: Path, manifest_text: str, prompt: tuple[str, str] | None = None) -> None:
    """Load the package as Yantra will, from a copy with the change in it."""
    from yantra import load_package
    from yantra.errors import ConfigError

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / folder.name
        if folder.is_dir():
            shutil.copytree(folder, copy, ignore=shutil.ignore_patterns(".yantra", "*.bak"))
        else:
            copy.mkdir()
        (copy / "agent.toml").write_text(manifest_text, encoding="utf-8")
        if prompt is not None:
            (copy / prompt[0]).write_text(prompt[1], encoding="utf-8")
        try:
            load_package(copy)
        except (ConfigError, ValueError, OSError) as exc:
            raise ConfigProblem(f"{folder / 'agent.toml'}: "
                                f"{str(exc).replace(str(copy), str(folder))}") from None


def set_agent(root: Path, name: str, tables: dict[str, dict | None],
              prompt: str | None = None) -> None:
    """Change an agent's tables (a key set to null taken out, a table set
    to null removed) and, given, its prompt."""
    folder = root / _name(name, "an agent's")
    manifest = folder / "agent.toml"
    text = _read(manifest)
    if not text:
        raise ConfigProblem(f"there's no agent called {name!r} in {root}")
    current = _loads(text, manifest)
    candidate = text
    for table, values in tables.items():
        if values is None:
            candidate = tomledit.drop(candidate, table)
            continue
        merged = {**current.get(table, {}), **values}
        merged = {k: v for k, v in merged.items() if v is not None}
        candidate = (tomledit.put(candidate, table, tomledit.render(table, merged))
                     if merged else tomledit.drop(candidate, table))
    prompt_file = _loads(candidate, manifest).get("agent", {}).get("prompt", "prompt.md")
    check_agent(folder, candidate, (prompt_file, prompt) if prompt is not None else None)
    if candidate != text:
        _write(manifest, candidate)
    if prompt is not None:
        _write(folder / prompt_file, prompt)


def add_agent(root: Path, name: str, example: Path) -> None:
    """A new agent, copied from an example package and named ``name``."""
    folder = root / _name(name, "an agent's")
    if folder.exists():
        raise ConfigProblem(f"there's already an agent called {name!r}")
    if not (example / "agent.toml").is_file():
        raise ConfigProblem(f"no example agent at {example}")
    text = _read(example / "agent.toml")
    agent = dict(_loads(text, example).get("agent", {}))
    agent["name"] = name
    candidate = tomledit.put(text, "agent", tomledit.render("agent", agent))
    check_agent(example, candidate)
    shutil.copytree(example, folder, ignore=shutil.ignore_patterns(".yantra", "*.bak"))
    _write(folder / "agent.toml", candidate)


def remove_agent(root: Path, name: str) -> Path:
    """The agent's folder moved aside (``.removed-NAME``), never deleted."""
    folder = root / _name(name, "an agent's")
    if not (folder / "agent.toml").is_file():
        raise ConfigProblem(f"there's no agent called {name!r} in {root}")
    aside = root / f".removed-{name}"
    if aside.exists():
        shutil.rmtree(aside)
    folder.rename(aside)
    return aside


def write_text(kind: str, path: Path, text: str, *, root: Path | None = None) -> None:
    """A whole file sent as text, checked as its kind before it's written:
    ``actors``, ``policy``, ``agent`` (an agent.toml) or ``prompt``."""
    if kind == "actors":
        check_actors(text, path)
    elif kind == "policy":
        check_policy(text, path)
    elif kind == "agent":
        check_agent(path.parent, text)
    elif kind != "prompt":
        raise ConfigProblem(f"no kind of file called {kind!r}")
    _write(path, text)

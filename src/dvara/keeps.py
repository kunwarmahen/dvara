"""What Dvara keeps on this computer, for a backup to take.

A backup of the house (Sarathi's ``sarathi backup``) is one file holding
every program's own files, and each program says where its are --
``dvara keeps --json``, asked with the same ``--root``, ``--actors`` and
``--state`` as ``status --json`` -- so the program that packs it knows
nothing of what is inside.

Dvara's are four: the agents (their packages, prompts and skills), the
actors file (everyone in the house, and their channels), the rules
(``policy.toml``, when there is one), and the state folder: each
person's conversations, past chats and run ledger, their folder per
agent, their Setu folder (their own accounts and browser profiles), the
household's facts, everyone's Smritikosh key and the push key. The
SQLite files among them are copied with SQLite's own backup.

WHAT IS LEFT OUT: the browser caches in the people's Setu folders (no
sign-in in them, and most of the bytes), the locks a running Chrome
leaves, the lock a running Dvara holds on its folder, and the answers
read aloud for the page (``voice-cache``, made again when asked for).

A PERSON'S LOCKED SETU FOLDER STAYS LOCKED: carried as it is, sealed,
opened again by their own passphrase after a restore.

A NEW HOME, SAID BY DVARA ITSELF. Each person's ``setu =`` in the actors
file is a whole path, and so are the folders ``signins.json`` is kept
by; each person's Setu folder names their browser profiles the same
way. Restored on a computer whose home is another folder, all of them
point at the old one. ``dvara keeps --rehome OLD NEW`` moves the paths
under OLD to under NEW in Dvara's own files (the actors file, the rules,
``signins.json``) and asks Setu to do the same in each person's Setu
folder (``setu keeps --rehome``, with ``SETU_HOME`` that folder), since
those files are Setu's. ``rehome: true`` in ``keeps --json`` says it can.
A conversation's history keeps the paths it was written with: it is a
record of what happened, not settings.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

FORMAT = "dvara.keeps.v1"

#: Chrome's folders and files with no sign-in in them (Setu's own list),
#: the lock a running dvara holds, and the page's answers read aloud.
LEAVE_OUT = ["BrowserMetrics", "Cache", "CacheStorage", "Code Cache", "Crashpad",
             "DawnCache", "GPUCache", "GrShaderCache", "ScriptCache", "ShaderCache",
             "Singleton*", "vault.lock", "dvara.lock", "voice-cache"]


def report(root: Path, actors: Path, state: Path, policy: Path) -> dict[str, Any]:
    keeps = [
        {"id": "agents", "path": str(root), "leave_out": [],
         "what": "the agents: their packages, prompts and skills"},
        {"id": "actors", "path": str(actors), "leave_out": [],
         "what": "everyone in the house, and how each reaches their agents"},
        {"id": "state", "path": str(state), "leave_out": LEAVE_OUT,
         "what": "each person's conversations, past chats and runs, their folders and "
                 "their own Setu accounts; the household's facts; memory and push keys"},
    ]
    if policy.exists():
        keeps.insert(2, {"id": "policy", "path": str(policy), "leave_out": [],
                         "what": "the rules: what each agent may do unasked"})
    for place in keeps:
        place["exists"] = Path(place["path"]).exists()
    return {"format": FORMAT, "keeps": keeps, "rehome": True}


def _moved(value: Any, old: str, new: str) -> tuple[Any, int]:
    """``value`` (JSON) with every string, key or value, at or under
    ``old`` moved under ``new``."""
    if isinstance(value, str):
        if value == old or value.startswith(old + "/"):
            return new + value[len(old):], 1
        return value, 0
    if isinstance(value, dict):
        out, count = {}, 0
        for key, item in value.items():
            key2, n1 = _moved(key, old, new)
            out[key2], n2 = _moved(item, old, new)
            count += n1 + n2
        return out, count
    if isinstance(value, list):
        moved = [_moved(item, old, new) for item in value]
        return [m for m, _ in moved], sum(n for _, n in moved)
    return value, 0


def _toml_moved(text: str, old: str, new: str) -> tuple[str, int]:
    """A TOML file's quoted paths at or under ``old`` moved under ``new``;
    comments and layout kept, since the owner may have written them."""
    pattern = re.compile(r"""(["'])""" + re.escape(old) + r"""(?=[/"'])""")
    return pattern.subn(lambda m: m.group(1) + new, text)


def _write(path: Path, text: str) -> None:
    spare = path.with_name(path.name + ".rehoming")
    spare.write_text(text)
    os.chmod(spare, path.stat().st_mode & 0o777)
    spare.replace(path)


def rehome(old: str, new: str, *, actors: Path, state: Path, policy: Path,
           setu: str | None) -> list[dict[str, Any]]:
    """Dvara's files with their paths under ``old`` moved under ``new``,
    and each person's Setu folder asked to do the same: one row per file
    changed (``{"file", "paths"}``), and one per folder Setu couldn't do
    (``{"file", "problem"}``)."""
    old, new = old.rstrip("/"), new.rstrip("/")
    if not old.startswith("/") or not new.startswith("/"):
        raise ValueError("--rehome takes two whole paths: the old home and this one")
    rows: list[dict[str, Any]] = []
    for path in (actors, policy):
        if path.is_file():
            text, count = _toml_moved(path.read_text(), old, new)
            if count:
                _write(path, text)
                rows.append({"file": str(path), "paths": count})
    signins = state / "signins.json"
    try:
        data = json.loads(signins.read_text())
    except (OSError, ValueError):
        data = None
    if data is not None:
        moved, count = _moved(data, old, new)
        if count:
            _write(signins, json.dumps(moved, indent=2) + "\n")
            rows.append({"file": str(signins), "paths": count})
    folders = sorted(p.parent for p in (state / "setu").glob("*/vault.json"))
    for folder in folders:
        if setu is None:
            rows.append({"file": str(folder), "problem": "setu isn't on this computer to "
                                                         "move its paths"})
            continue
        try:
            done = subprocess.run([setu, "keeps", "--rehome", old, new, "--json"],
                                  capture_output=True, text=True, timeout=60,
                                  env={**os.environ, "SETU_HOME": str(folder)})
            said = json.loads(done.stdout) if done.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            said = None
        if not isinstance(said, dict):
            rows.append({"file": str(folder), "problem": "setu couldn't move its paths "
                                                         "(an older setu: update it)"})
            continue
        rows += [r for r in said.get("rehomed") or [] if isinstance(r, dict)]
    return rows

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
leaves, and the lock a running Dvara holds on its folder.

A PERSON'S LOCKED SETU FOLDER STAYS LOCKED: carried as it is, sealed,
opened again by their own passphrase after a restore.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

FORMAT = "dvara.keeps.v1"

#: Chrome's folders and files with no sign-in in them (Setu's own list),
#: and the lock a running dvara holds.
LEAVE_OUT = ["BrowserMetrics", "Cache", "CacheStorage", "Code Cache", "Crashpad",
             "DawnCache", "GPUCache", "GrShaderCache", "ScriptCache", "ShaderCache",
             "Singleton*", "vault.lock", "dvara.lock"]


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
    return {"format": FORMAT, "keeps": keeps}

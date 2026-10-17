"""A person's learned skill made a tool: the owner's, from the settings page.

A skill an agent learned for somebody (learning.py) is a recipe: the
model loads it, reads it, and writes the command that runs its script.
Once it has worked again and again, the same script can be offered as
one call with named fields (Yantra's notes/98) -- the shape small local
models get right most often. Yantra's page has a button for it; behind
this service there was no way at all.

THE OWNER'S, NOT THE CHAT'S. A tool is code the agent can run in one
call, and making one runs its script once as a test. That is a decision
about the machine, so it is made on the settings page, never by a word
in the chat (and so never by a prompt hidden in somebody's mail).

PRESSING THE BUTTON IS THE YES. The page says first that the script runs
once as a test; the test then runs unasked, and the tool is kept only
if it passes. Yantra writes the definition (one model call, the rules
it checks, one retry), runs the test and saves it: ``propose_tool`` and
``save_tool``, the same as at its own page.

AND IT CAN BE TAKEN BACK. ``unmake_tool`` removes the tool (its
``tool.json`` and the ``tool:`` line) and leaves the skill a recipe, as
it was before; its counters stay. A tool that turned out wrong is one
press away from gone, never a file to find by hand.

IT STAYS THE PERSON'S. The skill lives in their folder for that agent,
and so does the tool: one person's tool never appears in anyone else's
agent. ``show`` lists every person's learned skills per agent, with how
each has done, for the page to offer the button where it fits.
"""

from __future__ import annotations

import re
from pathlib import Path

#: A skill's name, as Yantra writes one -- never a path.
SKILL_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
#: Where a kept skill lives, inside a person's folder for an agent.
LEARNED = Path(".yantra") / "skills" / "learned"


def learned(state: Path | None, agent: str) -> list[dict]:
    """Every person's learned skills for ``agent``, as rows for the page."""
    from yantra.skills.loader import SkillError
    from yantra.skills.loader import LEARNED_SOURCES, load_skill
    from yantra.skills.promote import _only_script

    rows: list[dict] = []
    if state is None:
        return rows
    for manifest in sorted((Path(state) / "work").glob(f"*/{agent}/{LEARNED}/*/SKILL.md")):
        person = manifest.parents[5].name
        try:
            skill = load_skill(manifest, source=LEARNED_SOURCES["project"])
        except (SkillError, OSError, ValueError):
            continue
        try:
            _only_script(skill)
            script = True
        except SkillError:
            script = False
        record = skill.learned
        rows.append({"person": person, "name": skill.name,
                     "description": skill.description,
                     "worked": record.worked if record else 0,
                     "failed": record.failed if record else 0,
                     "in_a_row": record.in_a_row if record else 0,
                     "script": script, "tool": skill.tool_name or None,
                     "stale": skill.is_stale, "suggest": skill.suggest_tool})
    return rows


def make_tool(*, root: Path, state: Path, agent: str, person: str, skill: str,
              provider: str | None = None, model: str | None = None,
              client=None) -> dict:
    """Write, test once, and keep if it passed. ValueError in words when
    it can't be made; otherwise what was proposed and whether it is kept.
    ``client`` is a provider already built (tests); else one is made from
    ``provider``, as the service would."""
    from yantra import default_model
    from yantra.config import guess_provider
    from yantra.package import load_package
    from yantra.permissions import yolo
    from yantra.skills.learn import Learner

    folder = Path(state) / "work" / person / agent
    if not SKILL_NAME.match(skill or "") or not (folder / LEARNED / skill / "SKILL.md").is_file():
        raise ValueError(f"{person} has no learned skill called {skill!r} with {agent}")
    spec = load_package(Path(root) / agent)
    name = provider or spec.provider or guess_provider()
    built = spec.build(permissions=yolo, cwd=folder, provider=client, provider_name=name,
                       model=model or spec.model or default_model(name),
                       own_skills_only=True)
    learner = Learner(built, "ask")
    offer = learner.propose_tool(skill)
    if offer is None:
        raise ValueError(f"not made a tool: {learner.last_skip}")
    view = offer.view()
    view.pop("tool_json", None)
    if not offer.passed:
        return {**view, "kept": False}
    made = learner.save_tool(offer)
    return {**view, "kept": True, "tool": made.tool_name}


def unmake_tool(*, state: Path, agent: str, person: str, skill: str) -> str:
    """The tool taken back; the skill stays a recipe. Its old tool name,
    or ValueError in words."""
    from yantra.skills.learn import set_tool_line
    from yantra.skills.loader import LEARNED_SOURCES, load_skill
    from yantra.skills.promote import TOOL_FILE
    from yantra.skills.registry import write_atomic

    folder = Path(state) / "work" / person / agent / LEARNED / (skill or "")
    manifest = folder / "SKILL.md"
    if not SKILL_NAME.match(skill or "") or not manifest.is_file():
        raise ValueError(f"{person} has no learned skill called {skill!r} with {agent}")
    found = load_skill(manifest, source=LEARNED_SOURCES["project"])
    if not found.tool_name:
        raise ValueError(f"{skill} isn't a tool")
    write_atomic(manifest, set_tool_line(manifest.read_text(encoding="utf-8"), ""))
    (folder / TOOL_FILE).unlink(missing_ok=True)
    return found.tool_name

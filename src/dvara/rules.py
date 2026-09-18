"""Standing answers: tool + argument patterns -> allow / deny / ask.

[Note 02](../notes/02-a-question-that-can-wait.md) gave a turn one rung
for its whole length. Every tool that could change something became the
same question, and the only dials were which person got asked and how
long they had to answer. That is exactly one bit of judgement applied to
every call an agent will ever make, and the two complaints it produces
are opposite: being asked to approve ``git status`` for the fourth time
this morning, and being asked to approve ``rm -rf`` at all.

A rule is the owner writing an answer down in advance:

    [[rule]]
    tool    = "bash"
    args    = { command = "git status" }
    verdict = "allow"

    [[rule]]
    tool    = "write_file"
    args    = { path = "*.env" }
    verdict = "deny"
    reason  = "secrets are not edited by an agent; ask me and I will do it"

Three sentences hold the whole module up.

**A RULE MAY ANSWER A QUESTION, NEVER CREATE A PERMISSION.** The rung
still decides whether there was a question at all. Under ``read_only`` --
the rung that means "do not wake this person" -- an ``allow`` rule grants
nothing, because there was nothing to answer; the same file gives the
owner a standing yes and a guest nothing, and that is the correct
difference rather than a wrinkle. Tightening composes everywhere: a
``deny`` refuses under ``yolo``, and an ``ask`` turns a call that ``yolo``
would have run straight through into a question.

**THE STRICTEST MATCHING RULE WINS, NOT THE FIRST.** Verdicts rank ``deny
< ask < allow`` and the answer is their minimum, which is the same
arithmetic ``gate.stricter`` uses for the rungs. It costs a little
expressiveness -- there is no "deny everything under here except this one
path" -- and it buys a property worth more in a file somebody edits at
two in the morning: a rule appended at the bottom cannot quietly undo one
at the top. Order does not matter, so a diff of this file means what it
looks like it means.

**PATTERNS WIDEN A REFUSAL, NEVER A PERMISSION.** Wildcards are refused
in an ``allow`` rule, at load time, and this is the sharpest edge in the
format. ``command = "git status*"`` looks like a tighter version of "any
git command" and it matches ``git status; rm -rf ~``. ``path =
"~/notes/*"`` looks like one directory and it matches
``~/notes/../../.ssh/id_rsa``. A glob describes a shape, and the shape of
a dangerous argument is not knowable in advance. The asymmetry is in what
a mistake costs: a ``deny`` that is too wide costs a question, and an
``allow`` that is too wide runs a command nobody saw. So ``deny`` and
``ask`` take patterns and ``allow`` takes exact strings -- as many as you
like, in a list. A near miss is not a refusal; it falls through to being
asked, which is where it started.

One matching rule with no argument in it: ``fnmatchcase``, never
``fnmatch``. The second consults the platform, and a policy file whose
meaning depends on which machine the service woke up on is not a policy
file.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from dvara.errors import ConfigProblem

#: Strictest first, like ``gate.LADDER``, so "the strictest wins" is a
#: minimum over this tuple rather than a paragraph of if-statements.
VERDICTS = ("deny", "ask", "allow")

#: Keys a ``[[rule]]`` table may carry. Unknown keys are errors: a
#: misspelled ``verdict`` that silently means "no opinion" turns a
#: standing denial into a decoration, which is the whole failure this
#: file exists to prevent.
RULE_KEYS = frozenset({"tool", "args", "verdict", "reason"})

#: The characters that make a wildcard dangerous in an ``allow``.
GLOB_CHARS = "*?["


@dataclass(frozen=True)
class Rule:
    """One standing answer, matched against one tool call."""

    tool: str
    verdict: str
    #: argument name -> the alternatives that satisfy it. Every named
    #: argument must match (AND); the alternatives for one argument are
    #: tried in turn (OR).
    args: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: The owner's own sentence, handed to the MODEL when this rule
    #: refuses. "use the deploy agent for that" is worth far more to it
    #: than a second copy of the word "denied".
    reason: str | None = None

    def matches(self, tool: str, arguments: Mapping[str, Any]) -> bool:
        """Whether this rule has an opinion about that call.

        A NON-STRING ARGUMENT NEVER MATCHES. A pattern is a claim about
        text, and ``str()`` of a list or a dict is a Python repr that
        happens to be text -- matching against it would mean the file
        said one thing and the gate did another. The cost is that a tool
        taking a list of paths cannot be constrained here at all, which
        is recorded rather than papered over.
        """
        if not fnmatchcase(tool, self.tool):
            return False
        for name, alternatives in self.args.items():
            value = arguments.get(name)
            if not isinstance(value, str):
                return False
            if not any(fnmatchcase(value, alt) for alt in alternatives):
                return False
        return True


class RuleBook:
    """The owner's standing answers, in one file, in no particular order."""

    def __init__(self, rules: list[Rule] | None = None, *,
                 source: Path | None = None, required: bool = False) -> None:
        self._rules = list(rules or ())
        #: The file this was read from and its stamp, so a running service
        #: can notice the owner adding a standing answer without being
        #: restarted. ``required`` rides along because a reread has to be
        #: as strict as the load was: a NAMED file that has since been
        #: deleted is still the mistake it would have been at startup.
        self.source = source
        self.required = required
        self.stamp = _stamp(source)

    def changed(self) -> bool:
        """Whether the file this came from has been touched since.

        True as well for a named file that has APPEARED since startup: an
        owner who runs with ``~/dvara/policy.toml`` absent and then writes
        one has written it to be used. Both directions are just "the
        stamp is different", which is why this is one comparison and not a
        case analysis.
        """
        return self.source is not None and _stamp(self.source) != self.stamp

    def reread(self) -> RuleBook:
        """The file as it is now, or a ``ConfigProblem``. Just the parse."""
        if self.source is None:
            return self
        return RuleBook.from_toml(self.source, required=self.required)

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules)

    def decide(self, tool: str, arguments: Mapping[str, Any]) -> Rule | None:
        """The strictest rule that matches, or None for no opinion.

        Ties go to the first written, which matters only for the
        ``reason`` the model reads -- two rules of the same verdict agree
        about the verdict by definition.
        """
        rank = {verdict: i for i, verdict in enumerate(VERDICTS)}
        matching = [r for r in self._rules if r.matches(tool, arguments)]
        if not matching:
            return None
        return min(matching, key=lambda r: rank[r.verdict])

    # ---- the owner's file --------------------------------------------------

    @classmethod
    def from_toml(cls, path: Path, *, required: bool = False) -> RuleBook:
        """Parse the owner's rules, or hand back an empty book.

        A MISSING FILE IS NOT AN EMPTY POLICY, IT IS NO POLICY, and those
        are the same thing here on purpose: with no rules the gate is
        exactly the one note 02 built, reduced by construction rather
        than by a test. ``required`` is for the owner who NAMED a file on
        the command line -- being handed silence because of a typo in a
        path is the one case where absence is a mistake.
        """
        path = Path(path).expanduser()
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if required:
                raise ConfigProblem(f"no policy file at {path}") from None
            # An empty book that still remembers where it looked, so a
            # policy file written later is picked up rather than ignored
            # until the next restart.
            return cls(source=path, required=required)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigProblem(f"{path}: {exc}") from None
        return cls.from_dict(raw, where=path, source=path, required=required)

    @classmethod
    def from_dict(cls, raw: dict, *, where: Path | str = "<memory>",
                  source: Path | None = None,
                  required: bool = False) -> RuleBook:
        entries = raw.get("rule", [])
        if isinstance(entries, dict):        # a single [rule] table
            entries = [entries]
        if not isinstance(entries, list):
            raise ConfigProblem(f"{where}: [[rule]] must be a list of tables")
        unknown_tables = sorted(set(raw) - {"rule"})
        if unknown_tables:
            raise ConfigProblem(
                f"{where}: unknown table(s) {', '.join(unknown_tables)} -- "
                f"this file holds [[rule]] entries and nothing else")
        return cls([_rule(entry, index, where)
                    for index, entry in enumerate(entries)],
                   source=source, required=required)


def _stamp(path: Path | None) -> tuple | None:
    """A file's (mtime, size), or None when there is nothing to stamp.

    A file that is not there stamps as None, and so does the absence of a
    path -- so an OPTIONAL policy file that has never existed reads as
    unchanged forever, and one that appears reads as changed exactly once.
    """
    if path is None:
        return None
    try:
        info = path.expanduser().stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _rule(entry: Any, index: int, where) -> Rule:
    at = f"{where}: [[rule]] entry {index}"
    if not isinstance(entry, dict):
        raise ConfigProblem(f"{at} must be a table")
    unknown = sorted(set(entry) - RULE_KEYS)
    if unknown:
        raise ConfigProblem(
            f"{at} has unknown key(s) {', '.join(unknown)}; known: "
            f"{', '.join(sorted(RULE_KEYS))}")

    tool = entry.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise ConfigProblem(f"{at} needs a tool name or pattern")
    # Named from here on, because "entry 4" sends somebody counting tables
    # and "tool = write_file" sends them to the line.
    at = f'{at} (tool = "{tool}")'

    verdict = entry.get("verdict")
    if verdict not in VERDICTS:
        raise ConfigProblem(
            f"{at} needs a verdict of {', '.join(VERDICTS)} (got "
            f"{verdict!r})")
    _refuse_globs(tool, at, verdict, what="tool")

    reason = entry.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ConfigProblem(f"{at} reason must be a non-empty string")
    if reason is not None and verdict == "allow":
        # An approval is silent -- nothing is ever told about it -- so a
        # sentence written here would never be read by anybody.
        raise ConfigProblem(
            f"{at} has a reason, but an allow rule never says anything to "
            f"anyone: a reason is what the model reads when a rule REFUSES")

    return Rule(tool=tool, verdict=verdict, reason=reason,
                args=_args(entry.get("args"), at, verdict))


def _args(value, at: str, verdict: str) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigProblem(
            f'{at} args must be a table: args = {{ command = "git status" }}')
    table: dict[str, tuple[str, ...]] = {}
    for name, raw in value.items():
        alternatives = [raw] if isinstance(raw, str) else raw
        if not isinstance(alternatives, list) \
                or not alternatives \
                or any(not isinstance(a, str) for a in alternatives):
            raise ConfigProblem(
                f"{at} args.{name} must be a string, or a non-empty list of "
                f"strings for several alternatives")
        for alternative in alternatives:
            _refuse_globs(alternative, at, verdict, what=f"args.{name}")
        table[name] = tuple(alternatives)
    return table


def _refuse_globs(pattern: str, at: str, verdict: str, *, what: str) -> None:
    """Wildcards, in an ``allow``, refused with the reason in full.

    The error is long because the mistake is invisible and expensive, and
    because the person reading it wrote something that looks careful.
    """
    if verdict != "allow":
        return
    if not any(char in pattern for char in GLOB_CHARS):
        return
    raise ConfigProblem(
        f"{at} {what} = {pattern!r} is an allow rule with a wildcard in it. "
        f"A pattern describes a shape, and the shape of a dangerous "
        f"argument is not knowable in advance -- \"git status*\" matches "
        f"\"git status; rm -rf ~\", and \"~/notes/*\" matches "
        f"\"~/notes/../../.ssh/id_rsa\". Patterns widen a refusal and never "
        f"a permission: write the exact strings, as a list if there are "
        f"several. Anything that does not match is still ASKED, not "
        f"refused.")

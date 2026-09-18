"""The failure loop: a run that went wrong becomes a case that catches it.

Yantra's authoring arc ends with a package carrying its own acceptance
gate -- ``evals/cases.toml``, run with ``yantra --eval``, exit non-zero
when a promise has stopped being true. What it never had was a supply of
cases. An author writes the ones they can imagine, and the ones that
matter are the ones nobody imagined, which arrive later, in production,
in front of a person.

This service has them. Every turn is a ``Run`` (runs.py), including the
ones that failed, and a Run holds what a case needs: the message that
provoked it, what it cost, and how it ended.

    $ dvara case a8ba6c09f2d9
    [[case]]
    id = "trace-a8ba6c09"
    ...

Four decisions, and the first one is the whole shape of the feature.

**THE SERVICE PROPOSES; A PERSON COMMITS.** The block goes to stdout, and
``--write`` is a flag somebody has to type. A service that appended to
the package it runs would be editing the folder the owner reviews -- the
thing note 01 refused to let a running agent do, for the reason that
survives everything else in this repo: a package you cannot read in a
diff is not reviewable, and a gate that grew on its own overnight is not
a gate anybody trusts. The loop is closed by a human, deliberately, every
time.

**A REFUSED RUN IS NEVER A CASE.** When the service turned the turn away
-- not on the roster, no access to that agent, allowance spent, a ceiling
this machine cannot price -- no agent ran. The row describes this service
and this machine, and pinning it in a package would be pinning a local
fact into a file meant to travel.

**THE SERVICE KNOWS A TURN STOPPED BADLY; ONLY A PERSON KNOWS A TURN
ANSWERED BADLY.** ``error``, ``max_iterations`` and ``over_budget`` carry
their own verdict, so the description writes itself. A turn that ended
``end_turn`` and was simply WRONG is the commoner failure and the service
cannot see it at all -- so those need ``--because``, and the sentence the
owner types is the description. A case whose description is "it was bad"
is a case nobody can act on in six months.

**A CASE CARRIES THE RUN ID AND THE DATE, NEVER WHO SAID IT.** The
message has to travel -- it IS the case -- but the actor does not. A
package is a thing you hand to somebody; the people this service serves
are not part of it. That still leaves the owner committing somebody's
words into a repository, which no code here can decide for them, so the
command says so out loud before they do.

## A trajectory is a description; a prohibition is a judgement

The fifth decision, and it arrived with the trajectory on a Run. A case
can now assert HOW a turn goes and not merely that it finishes, which was
the weakest assertion the format has and the only one this command could
make. Two fields were available and only one of them is this command's to
fill.

``required_tools`` is filled, from the calls that RAN. That is the fossil
rule as Yantra states it: replay the failure, and the fix must still do
the work. A turn that read a file and wrote one, badly, is still a turn
that has to read a file and write one -- an agent that "fixes" it by
doing neither has not fixed it, and without this the case would call that
a pass.

``forbidden_tools`` is NOT filled, including from the calls the gate
turned away, and the refusal is the point rather than an omission. What a
turn DID is a description, and the service watched it happen. What a turn
must never do again is a judgement, and it is exactly the judgement note
04 already said the service cannot make: a call the gate refused might
have been the bug, or might have been the agent correctly asking for
something it should have been given. So the refused calls are PRINTED
beside the block, where the owner reads them and writes the line if that
is what they meant.

Which works because of the first decision: the block is printed, not
written. An assertion a person disagrees with is a line they delete in a
file they were already going to read.
"""

from __future__ import annotations

from pathlib import Path

from yantra import EvalCase, case_from_trace, load_cases, render_case
from yantra.errors import ConfigError

from dvara.errors import ConfigProblem, Refused
from dvara.runs import Run

#: Stop reasons that are the agent's own failure, and say so well enough
#: to be a description on their own.
SELF_EVIDENT = ("error", "max_iterations", "over_budget")

#: The header written into a suite file this command creates. A package
#: that never had a gate now has one, and the next person to open the
#: file should know where its first case came from.
HEADER = """\
# This package's acceptance gate: the behaviours it promises, graded
# against its own prompt and tool list.
#
#   yantra --agent . --eval
#
# Cases below that begin `trace-` were failures in production, written
# here so that they stay fixed.
"""


def case_from_run(run: Run, *, because: str | None = None) -> EvalCase:
    """One Run -> one regression case, or a refusal saying why not.

    The ceiling is Yantra's own heuristic, unchanged and worth restating:
    what the FAILING run spent, times 1.5. The fix must not cost more
    than the bug did. A run that never reached a model spent nothing and
    gets no ceiling at all, which leaves the package's own in force.

    ``max_iterations`` is deliberately not set even for a run that died
    on one: the package's cap is part of what is under test, and a case
    that raised it would be grading a different agent than the one that
    failed.
    """
    if run.stop_reason == "refused":
        raise Refused(
            f"run {run.id} was refused before any agent ran -- roster "
            f"access, an allowance already spent, or a package this "
            f"machine could not build. That is a fact about this service "
            f"and this machine rather than about the agent's behaviour, "
            f"and it would mean nothing in somebody else's copy of the "
            f"package.")
    if run.stop_reason not in SELF_EVIDENT and not because:
        raise Refused(
            f"run {run.id} ended {run.stop_reason!r}, so nothing here knows "
            f"what was wrong with it. A turn that answered badly looks "
            f"exactly like one that answered well from the outside -- say "
            f"what to pin with --because, and that sentence becomes the "
            f"case's description.")
    if not run.message.strip():
        raise Refused(f"run {run.id} has no message to replay")

    spent = run.usage.input_tokens + run.usage.output_tokens
    return case_from_trace(
        run.id, _describe(run, because), run.message.strip(),
        tokens_used=spent,
        # Empty for a turn that called nothing, and empty for a row
        # written before a Run recorded trajectories at all. Both are a
        # case with no trajectory assertion, which is what this command
        # produced for every run until now.
        required_tools=run.ran_tools,
    )


def unasserted(run: Run) -> str | None:
    """The sentence about what this command deliberately did not assert.

    For stderr, beside the block rather than in it: the calls the gate
    refused are the likeliest thing the owner wants a ``forbidden_tools``
    line for, and the likeliest thing they would never think to look up.
    None when there is nothing to say, because an advisory that appears
    every time is an advisory nobody reads.
    """
    refused = run.refused_tools
    if not refused:
        return None
    return (f"This turn also had {', '.join(refused)} refused by the gate, "
            f"which is NOT asserted above: whether the fixed agent should "
            f"stop trying is your call, not the service's. Add "
            f"forbidden_tools = {_toml_list(refused)} if it is.")


def _toml_list(names: list[str]) -> str:
    inner = ", ".join(f'"{name}"' for name in names)
    return f"[{inner}]"


def _describe(run: Run, because: str | None) -> str:
    """The description, which is the only part a reader has in six months.

    Written as prose rather than a field dump: whoever opens this file is
    looking at a case among cases the author wrote by hand, and a row of
    machine values beside those is a thing people learn to skip.
    """
    when = run.started_at.strftime("%Y-%m-%d")
    if because:
        opening = because.strip()
    else:
        opening = _self_evident(run)
    # The VERSION the package declared at the moment the turn ran, when it
    # declared one. A package is edited on disk and takes effect on the
    # next turn, so a case written six months later that did not say which
    # version produced it is a case somebody has to guess about -- and
    # "unrecorded" is a worse thing to write than nothing, because a
    # package with no version key has not lost anything.
    against = run.agent
    if run.agent_version:
        against = f"{run.agent} {run.agent_version}"
    return (f"{opening}\n\n"
            f"Recorded from a real turn against {against} on {when} "
            f"(run {run.id}, model {run.model or 'unrecorded'}). The "
            f"ceiling below is what that turn spent, with half again for "
            f"headroom -- a fix that costs more than the failure did is "
            f"not a fix.")


def _self_evident(run: Run) -> str:
    reason = {
        "error": "This turn crashed in production",
        "max_iterations": ("This turn ran to its iteration cap without "
                           "finishing"),
        "over_budget": "This turn hit its cost ceiling before it answered",
    }[run.stop_reason]
    return f"{reason}: {run.detail}" if run.detail else f"{reason}."


# ---- putting it in the package ---------------------------------------------


def suite_file(package: Path) -> Path:
    """Where a package's cases live, whether or not it has any yet."""
    return Path(package) / "evals" / "cases.toml"


def append(package: Path, case: EvalCase) -> Path:
    """Add one case to a package's suite, and never break the file.

    THE EXISTING SUITE IS PARSED FIRST. An append that produced a file the
    gate can no longer read would break every case in it to add one, and
    it would do so at the exact moment somebody was trying to make the
    package more trustworthy. Loading first also catches the duplicate id
    that Yantra's loader would otherwise refuse on the next run, when the
    person who caused it has gone.
    """
    path = suite_file(package)
    existing: list[EvalCase] = []
    if path.exists():
        try:
            existing = load_cases(package)
        except ConfigError as exc:
            raise ConfigProblem(
                f"{path} does not parse as it stands, so nothing was added "
                f"to it: {exc}") from None
    if any(c.id == case.id for c in existing):
        raise Refused(
            f"{path} already has a case called {case.id!r} -- this run has "
            f"been written down once already")

    block = render_case(case)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{block}")
    else:
        path.write_text(f"{HEADER}\n{block}", encoding="utf-8")
    return path

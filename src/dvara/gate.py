"""The permission gate: who decides, and what happens while they decide.

The contract: dvara consumes a package's ``permissions.mode`` as a FLOOR
IT MAY TIGHTEN BUT NEVER LOOSEN. A package that ships ``mode = "yolo"``
does not get yolo because it asked; it gets yolo only if the owner of the
machine it runs on also said so, and only if the person talking to it is
somebody the owner trusts with that.

THREE RUNGS, AND THE MINIMUM WINS. The ladder is ``read_only < ask <
yolo``, and every input to a turn names one: the package, the owner's
policy, and the actor. ``stricter`` is the whole composition -- a
minimum, not a paragraph of if-statements -- which is what makes "never
loosen" a property of the arithmetic rather than a promise in a comment.
An unrecognised mode ranks as the tightest, so a typo and a mode from a
future version of the format both fail safe.

Yantra's own ladder has two rungs, not three: a package may say "ask" or
"yolo" and nothing else. ``read_only`` is the owner's rung, and it exists
because "do not escalate to this person" is a thing an owner needs to say
about a guest without saying it about themselves.

**"ASK" MEANS TWO DIFFERENT THINGS, AND THE DIFFERENCE IS A ROUTE.** With
a desk -- somewhere a question can be put and an answer can land -- it
means ask, and the turn suspends until a person decides or the deadline
passes. With no desk it means what note 01 said it means: read-only tools
only, because a question with nowhere to go is not a question, it is a
hang. THE ABSENCE OF A ROUTE IS NOT A HANG AND NOT AN APPROVAL; it is a
denial that says there was nobody to ask, which is a fact the model can
act on.

That fallback is also what keeps the default safe. A service built the
way note 01 built one has no desk, so it behaves exactly as it did before
escalation existed: nothing starts waiting on a person who was never
wired up.

One thing this still leaves open, recorded rather than hidden:
``read_only`` is the tool author's own declaration and nothing checks it.
An author who writes ``read_only = True`` on a tool that deletes files has
lied to this gate, and no service can catch that. It is the same trust a
package asks for when it ships ``tools/*.py`` at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from yantra import PermissionFn, PermissionRequest, allow_read_only, yolo

from dvara.asks import AskDesk

#: Strictest first. One order, so that "tighten, never loosen" is a
#: comparison instead of a paragraph.
LADDER = ("read_only", "ask", "yolo")


def stricter(*modes: str | None) -> str:
    """The tightest of the modes given.

    TWO KINDS OF SILENCE, AND THEY ARE NOT THE SAME. ``None`` is no
    opinion and drops out of the comparison -- it is how an actor with no
    ``permissions`` key composes exactly like an actor with no
    ``max_usd_per_turn``: by not being a ceiling. A mode that is present
    but UNRECOGNISED ranks below every real rung, so a typo and a mode
    from a future version of the format both fail closed.

    With nothing to compare at all, the answer is the tightest rung. An
    empty argument list is not permission.
    """
    rank = {mode: i for i, mode in enumerate(LADDER)}
    named = [mode for mode in modes if mode is not None]
    return min(named, key=lambda mode: rank.get(mode, 0), default=LADDER[0])


@dataclass(frozen=True)
class Policy:
    """What the OWNER allows, independent of what any package asks for."""

    mode: str = "ask"

    def effective(self, *modes: str | None) -> str:
        return stricter(self.mode, *modes)

    def gate(self, package_mode: str | None, *, actor_mode: str | None = None,
             desk: AskDesk | None = None, actor: str = "", agent: str = "",
             thread: str = "") -> PermissionFn:
        """The ``PermissionFn`` one turn runs under.

        Yantra's own two functions where they fit, chosen between rather
        than wrapped, because a wrapper here would be a third place a
        permission decision is made. The escalating gate is the one case
        that is genuinely new: it answers with an AWAITABLE, which only
        ``AsyncAgent`` can take, and which is the entire reason a turn
        that waits for a person does not stop every other conversation
        in the process.
        """
        # A PACKAGE THAT NAMES NO MODE IS TREATED AS NAMING THE TIGHTEST,
        # which is the one place silence is read as a decision rather than
        # as an absence. An author who ships code and leaves the
        # permissions table out has not asked to be escalated for, and a
        # service that escalated on their behalf would be putting a
        # stranger's tool call in front of a person on no authority at
        # all. The owner and the actor get the other reading: their
        # silence means they set no ceiling of their own.
        mode = self.effective(package_mode or LADDER[0], actor_mode)
        if mode == "yolo":
            return yolo
        if mode == "ask" and desk is not None:
            return escalating(desk, actor=actor, agent=agent, thread=thread)
        return allow_read_only


def escalating(desk: AskDesk, *, actor: str, agent: str,
               thread: str) -> PermissionFn:
    """A gate that puts the question to a person and waits for the answer.

    Read-only tools are approved without asking, exactly as they are
    everywhere else here -- a service that woke somebody up to confirm a
    directory listing would be a service they turn off. Only the calls
    that can change something become questions.

    The returned gate answers a coroutine, never a bool, for the calls it
    escalates. That is the seam: ``adecide`` awaits it, the coroutine
    suspends on a future, and the event loop goes and serves everybody
    else in the meantime.
    """
    async def ask(request: PermissionRequest) -> bool:
        answer = await desk.put(actor=actor, agent=agent, thread=thread,
                                tool=request.tool_name,
                                summary=request.summary)
        if not answer.approved:
            request.reason = answer.reason
        return answer.approved

    def gate(request: PermissionRequest):
        if request.read_only:
            return True
        return ask(request)

    return gate

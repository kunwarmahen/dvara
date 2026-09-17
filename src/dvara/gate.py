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

**A RUNG IS PER TURN; A RULE IS PER CALL.** Everything above decides
once, for a whole conversation, which is one bit of judgement spread over
every tool call an agent will ever make. ``rules.py`` is the owner
writing individual answers down in advance -- ``git status`` runs,
``*.env`` never does -- and ``ruled`` below is how the two compose. The
short version, and the only sentence needed to predict what happens: THE
RUNG SAYS WHETHER THERE IS A QUESTION, A RULE SAYS WHAT THE ANSWER IS. A
rule may tighten anything, and may only loosen a call this ladder would
have been willing to put to a person.

With no rules -- no policy file, which is every service until somebody
writes one -- the gate below is note 02's, unchanged and by construction.

One thing this still leaves open, recorded rather than hidden:
``read_only`` is the tool author's own declaration and nothing checks it.
An author who writes ``read_only = True`` on a tool that deletes files has
lied to this gate, and no service can catch that. It is the same trust a
package asks for when it ships ``tools/*.py`` at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from yantra import (
    REFUSED_POLICY,
    REFUSED_UNATTENDED,
    PermissionFn,
    PermissionRequest,
    allow_read_only,
    refuse,
    yolo,
)

from dvara.asks import AskDesk
from dvara.rules import RuleBook

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
    #: Standing answers, matched per CALL rather than per turn (rules.py).
    #: An empty book is not a permissive one -- it is no opinion, and the
    #: gate below then reduces to the three functions note 02 built.
    rules: RuleBook = field(default_factory=RuleBook)

    def effective(self, *modes: str | None) -> str:
        return stricter(self.mode, *modes)

    def gate(self, package_mode: str | None, *, actor_mode: str | None = None,
             desk: AskDesk | None = None, actor: str = "", agent: str = "",
             thread: str = "",
             reach: Sequence[tuple[str, str]] = ()) -> PermissionFn:
        """The ``PermissionFn`` one turn runs under.

        Yantra's own two functions where they fit, chosen between rather
        than wrapped, because a wrapper here would be a third place a
        permission decision is made. The escalating gate is the one case
        that is genuinely new: it answers with an AWAITABLE, which only
        ``AsyncAgent`` can take, and which is the entire reason a turn
        that waits for a person does not stop every other conversation
        in the process.

        ``reach`` is where the person can be found, carried through
        untouched: this module decides WHETHER to ask, and the desk
        decides where the question goes. An empty one is ordinary and
        means only that no channel notifier will fire -- a poller still
        finds the question, because it is in the same one queue.
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
        # NO RULES IS NOT AN EMPTY RULEBOOK'S BEHAVIOUR, IT IS NOTE 02'S.
        # Reducing to the old three functions by construction rather than
        # by a test is what makes "a service with no policy file behaves
        # exactly as it did" a property instead of a promise.
        if len(self.rules):
            return ruled(self.rules, mode=mode, desk=desk, actor=actor,
                         agent=agent, thread=thread, reach=reach)
        if mode == "yolo":
            return yolo
        if mode == "ask" and desk is not None:
            return escalating(desk, actor=actor, agent=agent, thread=thread,
                              reach=reach)
        return allow_read_only


def escalating(desk: AskDesk, *, actor: str, agent: str, thread: str,
               reach: Sequence[tuple[str, str]] = ()) -> PermissionFn:
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
    def gate(request: PermissionRequest):
        if request.read_only:
            return True
        return put(desk, request, actor=actor, agent=agent, thread=thread,
                   reach=reach)

    return gate


async def put(desk: AskDesk, request: PermissionRequest, *, actor: str,
              agent: str, thread: str,
              reach: Sequence[tuple[str, str]] = ()) -> bool:
    """Ask the person, and write their answer onto the request.

    The one place a question is put, so the two gates below cannot come to
    differ about what a refusal says. ``refuse`` rather than assignment:
    it is the shape that cannot write a reason and then accidentally
    approve, and it carries the CODE across as well -- refused, timed out
    and undeliverable are three facts a host may want to count separately
    without matching on English (Yantra's note 39).
    """
    answer = await desk.put(actor=actor, agent=agent, thread=thread,
                            tool=request.tool_name, summary=request.summary,
                            reach=reach)
    if not answer.approved:
        return refuse(request, answer.reason or "", code=answer.code)
    return True


def ruled(rules: RuleBook, *, mode: str, desk: AskDesk | None, actor: str,
          agent: str, thread: str,
          reach: Sequence[tuple[str, str]] = ()) -> PermissionFn:
    """The gate when the owner has written standing answers down.

    One function rather than a wrapper around the three above, for note
    02's reason unchanged: a decision made in two places is a decision
    that will eventually be made differently in each. Everything the rung
    and the rules together decide is decided here.

    THE RUNG SAYS WHETHER THERE IS A QUESTION; A RULE SAYS WHAT THE
    ANSWER IS. That single sentence is the whole composition, and the two
    predicates below are all of it:

    * ``rung_allows`` -- this call would have run with no rules at all.
    * ``can_escalate`` -- a person may be put on the spot for this actor.
      False under ``read_only``, which is precisely the rung that means
      "do not wake this person", and false with no desk, because a
      question with nowhere to go was never a question (note 02).

    So ``deny`` bites at every rung including ``yolo``; ``ask`` turns a
    call ``yolo`` would have run into a question; and ``allow`` grants
    nothing the rung would not have been willing to ASK about. One policy
    file, read differently for the owner and for a guest, which is the
    correct difference rather than a wrinkle.
    """
    can_escalate = desk is not None and mode != "read_only"

    def gate(request: PermissionRequest):
        rung_allows = request.read_only or mode == "yolo"
        rule = rules.decide(request.tool_name, request.arguments)
        verdict = rule.verdict if rule is not None else None

        if verdict == "deny":
            return refuse(request, _refused_by_rule(request, rule),
                          code=REFUSED_POLICY)
        if verdict == "allow" and (rung_allows or can_escalate):
            return True
        if verdict == "allow":
            # A standing yes to a question this rung never asks. Said
            # plainly, because "the owner allowed it and it was refused"
            # is otherwise the most confusing sentence in the system.
            return refuse(request, _no_route(request, mode, desk),
                          code=REFUSED_UNATTENDED)
        if rung_allows and verdict != "ask":
            return True
        if can_escalate:
            # Either the rung wanted to ask, or a rule tightened a call
            # the rung would have run through. Both are the same question,
            # and note that this path has no read_only shortcut: a rule
            # that says to ask about a read-only tool gets asked about.
            # "Tell me before this thing reads anything" is a thing an
            # owner is allowed to mean.
            return put(desk, request, actor=actor, agent=agent,
                       thread=thread, reach=reach)
        return refuse(request, _no_route(request, mode, desk),
                      code=REFUSED_UNATTENDED)

    return gate


def _refused_by_rule(request: PermissionRequest, rule) -> str:
    """What the model is told when a standing rule says no.

    NOT A QUESTION THAT WAS ASKED AND LOST -- and the sentence has to say
    so, or the model waits and tries again later, which is what it should
    do about a timeout and exactly the wrong move here. The owner's own
    ``reason`` rides along when they wrote one; it is usually the part
    that tells the model what to do instead.
    """
    sentence = (f"{request.tool_name} was denied: a standing rule of this "
                f"service refuses it. Nobody was asked, and nobody will be "
                f"-- this is not about the present conversation, so waiting "
                f"and retrying will not change it.")
    return f"{sentence} {rule.reason}" if rule.reason else sentence


def _no_route(request: PermissionRequest, mode: str,
              desk: AskDesk | None) -> str:
    """Why nobody is going to be asked, and the two answers are different.

    Note 02 recorded this as an open papercut: a call blocked because the
    ACTOR was tightened borrowed the sentence about nobody being there,
    when somebody was there and simply not for this person. Here both
    facts are in hand, so both get said. It still matters less than it
    looks -- the model's next move is the same either way -- but the
    sentence a person reads in a log should be true.
    """
    if desk is not None and mode == "read_only":
        return (f"{request.tool_name} was denied: this conversation is not "
                f"permitted to put questions to anyone, so nothing here can "
                f"be approved. Somebody may well be available; they are not "
                f"available to this conversation. Carry on with what you can "
                f"reach, and say what you would have done.")
    return (f"{request.tool_name} was denied: this conversation runs with "
            f"read-only tools and there is nobody available to ask. Say what "
            f"you would have done and why, and carry on with what you can "
            f"reach.")

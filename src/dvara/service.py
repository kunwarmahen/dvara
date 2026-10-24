"""The service: one message in, one reply out, for as long as it is up.

Everything else in this package is a noun; this is the verb. ``deliver``
is the whole of dvara's behaviour, and the order of its steps is the
design:

    who is this  ->  may they  ->  which package  ->  what may it spend
    ->  build  ->  rehydrate  ->  run  ->  save  ->  record  ->  reply

Four decisions are worth stating out loud, because each one is a place a
service could reasonably have been built the other way.

**A FRESH AGENT PER TURN.** Not a dict of warm ``AsyncAgent``s. Warm
agents buy latency and cost three things: memory that grows with every
actor who ever said hello, a spec that goes stale the moment a package is
edited on disk, and a crash that loses history nobody wrote down.
Rebuilding is also the only version of this where a restart is a
non-event, which is the entire point of an always-on thing.

**ONE PROVIDER, HELD -- AND GIVEN BACK.** The opposite decision, for the
opposite reason. ``Provider.__init__`` opens an httpx connection pool --
two, in fact, one sync and one async -- so resolving a provider per turn
would leak pools for as long as the process lived. Providers are cached
by name for the life of the service and passed in via
``build_async(provider=...)``, the pre-resolved-provider seam Yantra grew
for its CLI. Held is only half of it: ``aclose`` hands both pools back
through the provider's own ``aclose``, because a process that is asked to
stop should stop owning file descriptors.

**HISTORY IS RESTORED; IDENTITY IS REBUILT.** A checkpoint holds two
different things and only one of them is the conversation. Restoring the
system prompt, the model and ``max_iterations`` along with the messages
is exactly right for ``/load`` at a keyboard and exactly wrong here: a
package whose prompt was fixed this morning must take effect this
afternoon, and an owner who switched models must not be silently
overruled by whatever answered last week. ``apply_payload(...,
history_only=True)`` asks for the half this host wants. What comes out of
the store is the conversation; everything else comes out of the package.

**ONE LOCK PER SESSION KEY.** Two messages in one thread serialize.
Interleaving them would put two user messages into one history with one
assistant reply between them, and Yantra's resumability invariant holds
at prompt boundaries for a reason.
The lock lives only while a turn holds it or a message waits on it
(``locks.py``), so a process that stays up for months holds one per
conversation in flight, not one per conversation it has ever served.

That lock is held while a turn waits for a person to approve a tool call,
and the consequence is worth stating before somebody meets it: A PENDING
QUESTION IS NOT ANSWERED BY SENDING A MESSAGE. Typing "yes" into the
thread queues that message behind the very turn it was meant to release,
where it sits until the deadline passes. Answers arrive through the desk
(``AskDesk.answer``, ``POST /asks/{id}``), which is a separate path on
purpose -- an approval is not a sentence for the model to read, it is a
decision about a call that is already in flight.

A HELD TURN IS NOT ANSWERED BY A MESSAGE EITHER, BUT A MESSAGE ENDS IT.
When the owner has told silence to hold (``--on-timeout hold``), an
unanswered question stops the turn instead of refusing the call, the lock
is let go, and the turn waits in ``holds.py`` -- across a restart, if it
comes to that. ``resume`` carries it on with the person's answers.
Sending something else instead is allowed and means "never mind": the
waiting calls are set aside and the new message is answered.

One message, one reply: channels are turn-shaped. A channel that wants
the turn while it runs passes ``watch`` (watch.py) and draws it its own
way. The reply is still the one record.

**A TURN IS WATCHED, NOT JUST AWAITED.** The event loop here reads two
kinds of event, not one. ``TurnEnd`` is the answer; every ``ToolExecuted``
along the way is HOW the turn got there, and it goes onto the Run --
which is what lets a failure become a case that asserts a trajectory
rather than a case that asserts a turn finished (``cases.py``). It costs
one branch in a loop that was already running, which is the whole reason
it is done here and not by a second pass over anything.

The gate writes what DECIDED each of those calls into a ``Decisions``
(``gate.py``), keyed by the call's own id, and this loop joins the two on
that id. Two halves of one turn, met in the middle: the loop knows what
happened and the gate knows why, and neither of them knows both.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from yantra import (
    HELD,
    AgentSpec,
    PermissionRequest,
    adecide,
    ToolExecuted,
    Provider,
    bills_nothing,
    SessionStore,
    TurnEnd,
    Usage,
    apply_payload,
    default_model,
    get_provider,
    load_settings,
    session_cost,
)
from yantra.config import guess_provider
from yantra.errors import ConfigError, ToolError
from yantra.hold import check_answers, held_task
from yantra.session import snapshot
from yantra.tools.selector import select_when_many
from yantra.unattended import is_unattended
from yantra.unattended import scope as unattended_scope

from dvara import (attached, carrying, files, fresh, heard, household, learning, limits,
                   money, past, patience, phoneview, ready, remembering, seen, signins, spoken)
from dvara.accounts import AccountDesk, is_command, looks_pasted, owners_client_file
from dvara.unlocked import seal_loose
from dvara.actors import OWN_SETU, Actor, ActorBook, Channel
from dvara.asks import Answer, AskDesk
from dvara.errors import ConfigProblem, Refused
from dvara.gate import Decisions, Policy
from dvara.household import Household, HouseholdProblem
from dvara.holds import (DEFAULT_KEEP, Hold, HoldBook, NoSuchHold,
                         NotYourHold, Waiting, waiting_text)
from dvara.carrying import NOTHING as NOTHING_STOPPED
from dvara.keys import parse_key, session_key, workspace_parts
from dvara.learning import Learning
from dvara.locks import KeyedLocks
from dvara.memory import PEOPLE_FILE, MemoryProblem, Person, Store, person
from dvara.notices import NoticeDesk, Sent
from dvara.roster import Roster
from dvara.runs import Run, RunStore, ToolStep
from dvara.seen import Seen
from dvara.watch import Safely, Watcher, shown

#: How long a finished conversation that a program started is kept
#: before ``Service.tidy`` lets it go: a week to look at what it did.
KEEP_UNATTENDED = 7 * 24 * 3600.0
#: How long nobody writes in a conversation before it is looked back over
#: (``Service.look_back_quiet``): long enough that a pause is not an end.
QUIET_FOR = 30 * 60.0
#: How long after the service starts every sign-in is first checked.
FIRST_CHECK_AFTER = 10 * 60.0


#: Where a person on a channel sees their schedules: by asking.
SEEN_HERE = ("The person sees their schedules by asking you: list them with "
             "`mcp__samay__list_schedules`, and pause or delete one when they say so.")


#: How a person here gets an account connected: by sending the command
#: themselves (accounts.py) -- never by an agent, which only says how.
CONNECT_HERE = ("the person connects it by sending, themselves, /connect followed "
                "by its name (/connect gmail); you cannot do it for them -- say so")
#: How a locked folder opens here: by the person, from the chat.
LOCKED_HERE = ("their accounts are locked with their own passphrase; they open them by "
               "sending /unlock themselves, and you cannot")
#: For a person whose accounts live in a folder the owner looks after.
CONNECT_THERE = ("the person cannot connect one from here; the owner of this "
                 "service connects it for them -- say so, and say which")


#: Where a person on a channel sees their watches: by asking.
WATCHES_HERE = ("The person sees their watches by asking you: list them with "
                "`mcp__prahari__list_watches`, and pause, mend or delete one when they "
                "say so.")
#: Prahari not running, on a service: the owner's to start.
WATCH_OFF = ("Prahari is not running on this service right now: when you make a "
             "watch, say it will start looking once the service's owner starts it. "
             "Do not ask the person to run anything.")


#: The thread a watch's look is keyed under: one folder per person per
#: agent (``_workspace``), never a conversation.
LOOK_THREAD = "prahari-look"

#: A stopped clock, on a service: the owner's to start, not the person's.
CLOCK_OFF = ("Samay's clock is not running on this service right now: when you "
             "make a schedule, say it will start running once the service's owner "
             "starts it. Do not ask the person to run anything.")


def _default_provider(name: str) -> Provider:
    """Yantra's own resolution: settings from the environment, one pool."""
    return get_provider(name, load_settings(name))


#: Seconds a scheduled run's questions wait, in all, when its schedule
#: didn't say (Samay's own default is the same thirty minutes).
DEFAULT_SCHEDULE_WAIT = 1800.0


@dataclass(frozen=True)
class PhoneRun:
    """A scheduled run that works the phone, checked free (ready.py)."""

    #: Held taps its person let it do unasked, as they accepted them.
    steps: tuple[str, ...] = ()
    #: The one of its person's named phones it works (() when unnamed).
    phones: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reply:
    """What one turn came to. Everything a channel needs and nothing more."""

    text: str
    run_id: str | None
    agent: str
    stop_reason: str
    detail: str | None = None
    cost_usd: float | None = None
    usage: Usage | None = None
    #: Who the turn ran as. Worth returning rather than assuming, because
    #: a caller that arrived with a channel identity never named an actor
    #: and would otherwise have to ask a second time to answer a question
    #: this turn raised. None only when the resolution itself refused.
    actor: str | None = None
    #: One short line to put under the answer, or None for none -- what
    #: this person's roster entry asked to be shown (money.receipt).
    #:
    #: NOT PART OF ``text``, on purpose. ``run.reply`` is the archive of
    #: what the agent SAID, and a footer appended to it is a sentence the
    #: agent did not say, read back months later by whoever is asking why
    #: a turn answered badly. Keeping it separate also leaves the channel
    #: to decide how a footer looks in its own medium, rather than this
    #: service picking a separator for every channel there will ever be.
    receipt: str | None = None
    #: The turn stopped for approval nobody gave in time and is waiting in
    #: the queue (holds.py) -- what a channel shows, with the id it
    #: answers by. None for every turn that did not stop.
    held: Hold | None = None
    #: An UNATTENDED turn's three lists (Yantra's unattended.py), for the
    #: program that asked for it -- a scheduler: what only a person can
    #: fix (a sign-in), what another process was using (a browser
    #: profile), and which tools were refused. Empty on any other turn
    #: except ``refused``, which is read off the run's own steps.
    needs: tuple[str, ...] = ()
    busy: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()
    #: Files from the person's folder to send with the words (files.py):
    #: ``/file NAME`` answered. Each channel decides how a file looks.
    files: tuple[Path, ...] = ()
    #: A conversation opened again (``/chats N``, past.py): its words, for
    #: a page to draw in place. Empty for every other reply.
    transcript: tuple[dict, ...] = ()
    #: What a voice note sent with the message was heard as (heard.py),
    #: for the channel to show beside the answer.
    heard: str | None = None
    #: Whether the channel reads this answer aloud too (spoken.py): by
    #: the person's choice, and whether they spoke to it.
    speak: bool = False
    #: Whose voice by name, for that (their own, or None for the house's).
    voice: str | None = None

    @property
    def ok(self) -> bool:
        return self.stop_reason == "end_turn"


class Service:
    """Many people, many agents, many conversations, one process."""

    def __init__(self, *, roster: Roster, actors: ActorBook, state: Path,
                 policy: Policy | None = None,
                 asks: AskDesk | None = None,
                 provider_name: str | None = None,
                 model: str | None = None,
                 provider_factory: Callable[[str], Provider] | None = None,
                 log=None,
                 hold_for: float = DEFAULT_KEEP,
                 samay: str | None = None,
                 sparsh: str | None = None,
                 prahari: str | None = None,
                 prahari_for: Sequence[str] = (),
                 keep_unattended: float = KEEP_UNATTENDED,
                 web: bool = False,
                 memory: Store | None = None,
                 quiet_for: float = QUIET_FOR,
                 check_every: float = signins.EVERY,
                 ntfy: str | None = None,
                 ntfy_click: str | None = None,
                 owner: str | None = None,
                 ) -> None:
        self.roster = roster
        self.actors = actors
        self.state = Path(state).expanduser().resolve()
        self.policy = policy or Policy()
        # Escalation is OPT-IN, and its absence is the whole of the old
        # behaviour. No desk means no route to a person, which means "ask"
        # decides by policy alone rather than waiting on somebody who was
        # never wired up. A service that started blocking because a mode
        # string somewhere said "ask" would be a service that hangs the
        # day it is deployed.
        self.asks = asks
        #: Whose word keeps a fact for everyone (household.py); None: nobody
        #: in the chat, only ``dvara household`` at this computer.
        self.owner = owner
        self.household = Household(self.state)
        # The operator's overrides, in the CLI's own resolution order:
        # what the service was told  >  what the package says  >  the
        # environment's default. An Ollama owner must be able to run a
        # package authored against a cloud model without editing it.
        self.provider_name = provider_name
        self.model = model
        #: Where the one thing this service has to tell a HUMAN goes. It
        #: has exactly one use -- an owner's file that has stopped
        #: parsing -- and that message has nowhere else to be: the person
        #: who can fix it is not in the conversation, and the person who
        #: IS in the conversation must not be handed somebody else's
        #: config error. Resolved at the moment of writing rather than
        #: bound now, so a host that redirects stderr later is obeyed.
        self.log = log
        self._complained: str | None = None
        #: The samay program, when the owner turned schedules on
        #: (``--samay``): each person's turn gets Samay's tools, for
        #: that person, on this road (``_schedules``). None: no turn does.
        self.samay = samay
        #: The sparsh program, when the owner turned the phone on
        #: (``--sparsh``): the turns of the one person marked ``phone`` get
        #: its tools (``_phone``). None: no turn does.
        self.sparsh = sparsh
        #: The prahari program, when the owner turned watches on
        #: (``--prahari``), and the people it is for when the owner named
        #: some (``--prahari-for``; none named: everyone). Each person's
        #: watches look with their own accounts, through ``call``.
        self.prahari = prahari
        self.prahari_for = tuple(n.strip() for n in (
            prahari_for.split(",") if isinstance(prahari_for, str) else prahari_for)
            if n.strip())
        #: The owner's memory store (``--memory``, memory.py): a package
        #: that asks for memory gets this one, for its person. None: the
        #: package's own choice, still filed under the person's name.
        self.memory = memory
        #: How long a conversation a program started is kept once it is
        #: over, before ``tidy`` lets its history and workspace go.
        self.keep_unattended = keep_unattended
        #: How long a conversation goes unwritten in before it is looked
        #: back over (``look_back_quiet``); 0: only at /new.
        self.quiet_for = quiet_for
        #: How often every Setu folder is checked (``check_sign_ins``); 0: never.
        self.check_every = check_every
        self._looked: dict[str, str] = {}
        #: Look backs running behind a ``/new`` that has already answered
        #: (``_look_back_behind``); held so none is collected mid-look.
        self._behind: set[asyncio.Task] = set()
        #: Where what such a look noticed goes, as (actor, text); None:
        #: the person's channels (``notify``). ``dvara say`` prints it.
        self.told_behind: Callable[[str, str], Awaitable[None]] | None = None

        self.state.mkdir(parents=True, exist_ok=True)
        self.sessions = SessionStore(self.state / "sessions.sqlite3")
        #: Every conversation, one log per person, for ``/chats`` and the
        #: page's history (past.py). What ``/new`` kept before comes over once.
        self.past = past.PastBook(self.state / "past")
        self.past.bring_in(self.state / "past.sqlite3")
        self.runs = RunStore(self.state / "runs.sqlite3")
        # Always open, even when nothing is configured to hold: a turn
        # held yesterday by a service started with --on-timeout hold can
        # still be answered today by one started without it. Whether
        # silence holds is a policy for new questions, not a way to
        # strand old ones (holds.py).
        self.holds = HoldBook(self.state / "holds.sqlite3", keep_for=hold_for)
        #: What a look back noticed, waiting for the person's /remember.
        self.offered = remembering.Offered(self.state)
        #: Each person's own /voice choice (spoken.py).
        self.voices = spoken.Choices(self.state)
        #: Skills offered after an answer and kept on the person's word
        #: (learning.py); the tools each turn was given, and schedules,
        #: for ``/tools`` and ``/schedules`` (seen.py).
        self.learning = Learning(self)
        self.seen = Seen(self.state)
        #: Each refused sign-in told, so none is told twice (signins.py).
        self.signins_told = signins.Told(self.state)
        #: Telling a person something nobody asked about (notices.py).
        self.notices = NoticeDesk()
        # read aloud too for someone who chose "always" (spoken.py)
        self.notices.aloud = self._notice_aloud
        #: The web channel (web.py), when the owner turned it on: a page's
        #: chat, and every notice kept for the page as a line.
        self.web = None
        if web:
            from dvara.web import KIND, WebBook, WebChannel
            self.web = WebChannel(self, WebBook(self.state / "web.sqlite3"))
            self.notices.route(KIND, self.web.notice)
        #: ntfy on the house's own server (push.py), when the owner gave
        #: one: every person's notices posted to their own topic.
        self.push = None
        if ntfy:
            from dvara.push import KIND as PUSH, Pusher
            self.push = Pusher(ntfy, self.state, click=ntfy_click)
            self.notices.route(PUSH, self.push.notice)
        # The one seam between this service and the network. Injected so
        # tests exercise the real assembly against a scripted provider,
        # and so an embedder that already holds a provider does not open
        # a second connection pool to the same endpoint.
        self._provider_factory = provider_factory or _default_provider
        self._providers: dict[str, Provider] = {}
        self._locks: KeyedLocks[str] = KeyedLocks()
        #: A person's own accounts, from the chat: /connect, /accounts,
        #: /disconnect and the address pasted back (accounts.py). Handled
        #: before any turn, and never seen by an agent.
        self.accounts = AccountDesk(
            notify=lambda actor, text: self.notify(text=text, actor=actor),
            log=self._note, client_file=self._owners_client_file)
        self._client_file: tuple[str | None] | None = None
        # a crash while somebody's folder was open must not leave their
        # browser sign-ins on disk: seal them again before serving anyone
        seal_loose(self.accounts._program(), self.state / "setu", log=self._note)

    def _owners_client_file(self) -> str | None:
        if self._client_file is None:            # asked once, when first needed
            self._client_file = (owners_client_file(),)
        return self._client_file[0]

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Give back the sockets. A service that is asked to stop, stops.

        ``Provider.close()`` is the framework's own promise, which it was
        not when this was first written: shutdown used to reach past the
        provider and close ``.client`` itself, because there was nothing
        else to call. Reaching into another package's attributes works
        right up until the day it does not, and a service that leaks a
        connection pool per provider does not find out for hours.

        THE SYNC HALF CANNOT CLOSE THE ASYNC POOL. An ``AsyncClient`` is
        only closable from inside a running loop, so this closes what it
        honestly can; ``aclose`` is what an async host wants, and what
        every caller in this package uses.
        """
        for provider in self._providers.values():
            provider.close()
        self._providers.clear()
        self.runs.close()
        self.holds.close()
        self.past.close()

    async def aclose(self) -> None:
        """Give back BOTH pools. The shutdown a running service calls.

        Not ``close()`` with an await bolted on the front: the provider
        closes both of its own pools in the right order, and this stays a
        loop over providers rather than a loop over their internals.
        """
        await self.accounts.aclose()
        await self.learning.aclose()
        if self.web is not None:
            await self.web.aclose()
        for provider in self._providers.values():
            await provider.aclose()
        self._providers.clear()
        self.runs.close()
        self.holds.close()
        self.past.close()

    # ---- the owner's files, read again -------------------------------------

    def _notice_aloud(self, actor: str) -> dict | None:
        """What a notice for ``actor`` carries to be read aloud: only under
        "always" -- nobody spoke to start it (spoken.py)."""
        try:
            who = self.actors.get(actor)
        except Refused:
            return None
        if not spoken.wanted(self.voices.choice(who.id, who.speak), spoke=False):
            return None
        return {"speak": True, "voice": self.voices.voice(who.id, who.voice)}

    def _note(self, line: str) -> None:
        """One line for the owner, once per distinct problem.

        Deduplicated because this is called per TURN: a file that has
        stopped parsing has stopped parsing for every turn after it, and
        a service that printed the same paragraph a hundred times an hour
        is a service whose log nobody reads. The state clears when the
        problem changes or goes away, so the NEXT breakage is loud again.
        """
        if line != self._complained:
            self._complained = line
            print(line, file=self.log or sys.stderr)

    def refresh(self) -> None:
        """Pick up an edited actors or policy file, without a restart.

        A BAD FILE KEEPS THE LAST GOOD ONE. That is the whole policy, and
        it is the reason this lives here rather than in either parser. An
        owner adding a guest at midnight who leaves a quote off is one
        typo away from a service that refuses everybody -- including
        themselves, including the person who would fix it -- so a reread
        that raises is a complaint on the way past and nothing else. The
        roster in force stays the one that was in force a second ago.

        The opposite reading is defensible at STARTUP and is what happens
        there: a broken file is exit 2 and nothing serves, because nobody
        is depending on the process yet. The difference between those two
        answers is whether there is already something to lose.

        Cheap enough to do per turn: two ``stat`` calls against a model
        round trip.
        """
        try:
            if self.actors.changed():
                self.actors = self.actors.reread()
                self._note(f"reloaded {self.actors.source} "
                           f"({len(self.actors)} actor(s))")
        except ConfigProblem as exc:
            self._note(f"{exc}\n  -- keeping the roster already loaded; "
                       f"nothing changed for anybody talking right now")
        try:
            if self.policy.rules.changed():
                rules = self.policy.rules.reread()
                self.policy = replace(self.policy, rules=rules)
                self._note(f"reloaded {rules.source} ({len(rules)} rule(s))")
        except ConfigProblem as exc:
            self._note(f"{exc}\n  -- keeping the rules already loaded")

    # ---- telling, unasked ----------------------------------------------------

    async def notify(self, *, text: str, actor: str | None = None,
                     via: Channel | None = None,
                     extra: dict | None = None) -> tuple[str, Sent]:
        """Send ``text`` to a person on their channels (notices.py).

        Who is named the two ways a turn names them, exactly one of the
        two. Refused for nobody on the roster, and for an empty text --
        a blank message on somebody's phone at 08:00 is worse than none.
        """
        self.refresh()
        if (actor is None) == (via is None):
            raise Refused("a notice needs exactly one of an actor or a "
                          "channel identity")
        who = (self.actors.get(actor) if actor is not None
               else self.actors.resolve(via.kind, via.id))
        if not text.strip():
            raise Refused("a notice needs some text")
        return who.id, await self.notices.send(who.id, self._told_at(who), text,
                                               extra=extra)

    async def phone_ready(self, *, actor: str, wait: float, about: str,
                          phone: bool | str = True) -> str | None:
        """Is ``actor``'s phone free for a run Dvara isn't running
        (``POST /phone/ready``)? None: go. Otherwise why it's skipped.

        A schedule made on Yantra's page runs on Samay's direct road, with
        nobody at it; it may still work the phone when its person can be
        asked here. Before it starts, the SAME CHECK a phone schedule here
        gets (ready.py): in use, waited on up to ten minutes; locked, its
        person asked in their chat to unlock it, for ``wait`` seconds;
        asleep, woken. Refused for someone without the phone. ``phone``:
        which of their phones, by name (``phone_for``).
        """
        self.refresh()
        who = self.actors.get(actor)
        if self.sparsh is None or not who.has_phone:
            raise Refused(f"{actor} has no phone this service can work: it needs "
                          "--sparsh and phone = true (or phones = [...]) for them")
        try:
            which = phone_for(who, phone)
        except Refused as exc:
            return f"skipped: {exc}"     # a skip in its logbook, not a missing person
        return await ready.ready(ready.through(self.sparsh, *which),
                                 wait=wait or DEFAULT_SCHEDULE_WAIT,
                                 ask=self._asker(who), about=" ".join(about.split())[:120])

    def watches_for(self, actor: str) -> bool:
        """Whether this person's turns get Prahari's tools: watches are on
        (``--prahari``), and ``--prahari-for`` -- when the owner named
        anyone -- names them."""
        return self.prahari is not None and (not self.prahari_for
                                              or actor in self.prahari_for)

    async def call(self, *, actor: str, agent: str, tool: str, arguments: dict,
                   allow_tools: Sequence[str] = ()) -> dict:
        """One tool, once, as this person, and no model (``POST /call``).

        A WATCH LOOKS WITH ITS PERSON'S ACCOUNTS. Prahari repeats a watch's
        check with no model; at the computer that is ``yantra --call``,
        with the computer's accounts -- the owner's. A watch made by
        someone else in the house must look with THEIR mail, so the look
        comes here: their agent is built as for a turn, with their own Setu
        folder (``_accounts``) and the package's own servers, and the one
        tool runs by Yantra's own rule (its calling.py): a tool that reads,
        or the one call they granted word for word when they accepted the
        watch.

        NOTHING ELSE A TURN HAS. No model is asked, so no allowance is spent
        and no run is written (a look every half hour would bury the
        person's page); no conversation, no memory, no schedules, no phone.
        It is unattended: a sign-in wall comes back in ``needs_person``,
        never as a window opened for nobody.

        Only for a person whose watches are on (``watches_for``).
        """
        from yantra.calling import Called, as_json, call_once

        self.refresh()
        if not self.watches_for(actor):
            raise Refused(f"watches are off for {actor} on this service: it was not "
                          "started with --prahari for them")
        who = self.actors.may(actor, agent)
        spec = self.roster.spec(agent)
        key = session_key(actor, agent, LOOK_THREAD)
        with unattended_scope() as record:
            try:
                looker = self._looker(spec, who, key)
            except ConfigError as exc:
                return as_json(Called(False, tool, detail=f"that agent cannot run: {exc}"))
            servers = await self._look_servers(looker, who=who, spec=spec, key=key)
            try:
                called = await asyncio.to_thread(call_once, looker, tool, arguments,
                                                 list(allow_tools))
            finally:
                if servers is not None:
                    await asyncio.to_thread(servers.shutdown)
        return as_json(called, needs=list(record.needs), busy=list(record.busy))

    async def mail_login(self, *, actor: str, ref: str) -> dict:
        """A person's mail login, for the mailbox Prahari keeps open for them
        (``POST /mail-login``).

        THE PASSWORD IS IN THEIR SETU FOLDER, AND ONLY DVARA KNOWS WHERE.
        A mailbox names a Setu mail account (``mail:home``); the server, the
        address and the app password are in the person's own folder, under
        their lock. This runs ``setu login <ref> --json`` in that folder,
        with the key they unlocked it with, and answers with what Setu
        handed -- only to the caller with Dvara's token, Prahari, which
        already runs whole turns as them.

        Only a ``mail:`` account (Setu refuses the rest anyway), only for a
        person whose watches are on, only with a folder of their own. A
        locked folder nobody unlocked is Setu's refusal, said back."""
        import subprocess

        from yantra.setu_link import home_env

        self.refresh()
        if not self.watches_for(actor):
            raise Refused(f"watches are off for {actor} on this service")
        who = self.actors.get(actor)
        if not ref.startswith("mail:"):
            raise Refused("only a mail account's login is handed out")
        home = self.setu_home(who)
        if home is None:
            raise Refused(f"{actor} has no Setu folder on this service, so no mail "
                          "account to open")
        program = self.accounts._program()
        if program is None:
            raise Refused("setu is not installed where this service can run it")
        env = home_env(str(home), self.accounts.keys.key_for(who.id))
        done = await asyncio.to_thread(
            subprocess.run, [program, "login", ref, "--json"], capture_output=True,
            text=True, env=env, stdin=subprocess.DEVNULL, timeout=30)
        try:
            said = json.loads((done.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            said = {"error": " ".join((done.stderr or "setu said nothing").split())[:300]}
        return said if isinstance(said, dict) else {"error": "setu said something else"}

    def _looker(self, spec: AgentSpec, who: Actor, key: str):
        """The person's agent, for a call: built as a turn's is, around a
        provider that is never asked (one with no key will do)."""
        provider_name = self.provider_name or spec.provider or guess_provider()
        try:
            provider = self._provider(provider_name)
        except ConfigError:
            provider_name = "ollama"
            provider = self._provider(provider_name)
        return spec.build_async(
            permissions=self.policy.gate(
                spec.permissions_mode, actor_mode=who.permissions, desk=self.asks,
                actor=who.id, agent=spec.name, thread=LOOK_THREAD, reach=who.reach(),
                decisions=Decisions()),
            cwd=self._workspace(key), provider=provider, provider_name=provider_name,
            model=self.model or spec.model or default_model(provider_name),
            own_skills_only=True)

    async def _look_servers(self, agent, *, who: Actor, spec: AgentSpec, key: str):
        """A call's servers: the person's accounts and the package's own --
        what a look can read with -- and nothing that a turn alone needs."""
        accounts = who.setu is not None and bool(spec.connections)
        packaged = bool(getattr(spec, "mcp", ()))
        if not (accounts or packaged):
            return None
        from yantra.mcp import MCPManager

        manager = MCPManager(agent.registry, agent=agent,
                             memory_path=self._workspace(key) / ".yantra" / "mcp.json")
        if accounts:
            await self._accounts(agent, manager, who=who, spec=spec)
        if packaged:
            await self._packaged(manager, spec=spec)
        return manager

    async def ask(self, *, actor: str, tool: str, summary: str,
                  arguments: dict, timeout: float, agent: str = "",
                  thread: str = "") -> Answer:
        """One question for a run that is not Dvara's (``POST /ask``).

        Samay's direct road starts Yantra with nobody at it; when that run
        meets a call nobody allowed ahead of time, its person may still
        be a tap away. The question is put THROUGH THE SAME GATE A TURN
        HERE IS GIVEN -- the owner's rules, the person's rung, their
        channels -- built as for a package that asks, because the run on
        the other end already decided this is a call it would ask about.
        So a deny rule still refuses without anybody being asked, an
        allow rule answers it, and a person on ``read_only`` is never put
        on the spot.

        ``timeout`` is the run's own wait, which its person accepted with
        the schedule: a question unanswered in it LAPSES, the way a
        scheduled turn's question here does -- refused, never held, since
        the run on the other end cannot be resumed from here.
        """
        self.refresh()
        who = self.actors.get(actor)
        request = PermissionRequest(tool_name=tool, arguments=dict(arguments),
                                    summary=summary, read_only=False, call_id="ask")
        decisions = Decisions()
        gate = self.policy.gate(
            "ask", actor_mode=who.permissions, desk=self.asks, actor=who.id,
            agent=agent or "samay", thread=thread or "samay", reach=who.reach(),
            decisions=decisions, ahead=(),
            patience=patience.Patience(patience.remaining_today(
                who.max_wait_per_day,
                (0.0 if who.max_wait_per_day is None
                 else self.runs.waited_since(who.id, money.day_start()))),
                scheduled=max(0.0, float(timeout))))
        approved = await adecide(gate, request)
        how = decisions.of("ask") or ""
        via = how.partition(":")[2] if how.startswith("asked:") else None
        if approved:
            return Answer(True, via=via)
        return Answer(False, request.reason or f"{tool} was not approved.",
                      request.code or "unspecified", via=via)

    def _told_at(self, who: Actor) -> tuple[tuple[str, str], ...]:
        """Where a notice for ``who`` goes: their channels, the web
        channel's lines when it is on (web.py), and their ntfy topic when
        there is a server (push.py) -- every person has those two, with no
        line in the actors file."""
        reach = who.reach()
        if self.web is not None:
            from dvara.web import KIND
            reach += ((KIND, who.id),)
        if self.push is not None:
            from dvara.push import KIND as PUSH
            reach += ((PUSH, self.push.topic(who.id)),)
        return reach

    # ---- the verb ----------------------------------------------------------

    def _whom(self, actor: str | None, via: Channel | None,
              thread: str) -> tuple[str, str]:
        """Settle who is talking and under which thread, from either form.

        EXACTLY ONE OF THE TWO, and both mistakes are refused rather than
        resolved. Neither is a caller that forgot to say who it is;
        BOTH is a caller saying it twice, and the only way to honour that
        would be to decide which of the two wins -- at which point a
        bridge with a stale hard-coded actor id quietly overrules the
        roster, or quietly does not, and nobody can tell which from the
        outside.
        """
        if (actor is None) == (via is None):
            raise Refused("a turn needs exactly one of an actor or a channel "
                          "identity to say who is talking")
        if via is None:
            return actor, thread
        return self.actors.resolve(via.kind, via.id).id, f"{via.kind}:{thread}"


    async def deliver(self, *, agent: str, thread: str, text: str,
                      actor: str | None = None,
                      via: Channel | None = None,
                      unattended: bool = False,
                      allow_tools: Sequence[str] = (),
                      phone: bool | str = False,
                      phone_steps: Sequence[str] = (),
                      wait: float | None = None,
                      came_by: str | None = None,
                      watch: Watcher | None = None,
                      attachments: Sequence[attached.Attachment] = (),
                      carry_on: bool = False) -> Reply:
        """Run one turn for one person, and answer them either way.

        ``carry_on`` (or a person's ``/carry``) carries on the job a
        restart stopped part way in this conversation (carrying.py)
        instead of starting ``text``.

        Never raises for anything a person could have caused. A refusal is
        a reply; so is a crash inside somebody's tool. The caller is a
        channel adapter, and an exception there is a message that silently
        never arrives.

        TWO WAYS TO SAY WHO, AND EXACTLY ONE PER CALL. ``actor`` names
        somebody straight off the roster, which is what the CLI does and
        what a trusted bridge that already did its own mapping does.
        ``via`` hands over a channel's native identity and lets the roster
        do the mapping -- the form an adapter should prefer, because it is
        the form in which the adapter cannot get the answer wrong.

        THE CHANNEL QUALIFIES THE THREAD. Two channels resolving to one
        person is the point of ``via``; two channels whose thread ids
        happen to collide sharing one conversation is not, and before the
        roster joined them it was only the differing actor ids keeping
        them apart. So a turn that came in through a channel is keyed
        under ``kind:thread``. It is done here rather than asked of
        adapters because a rule that holds only when every adapter
        remembers it is not a rule, and the cost is one prefix on the
        path that has a channel to name -- keys made by callers naming an
        actor directly are untouched, and so is every checkpoint already
        written under one.

        UNATTENDED IS A TURN NOBODY STARTED BY TYPING. A program (a
        scheduler) asked for it, and the person it runs as may be asleep:
        Yantra is told so for this turn alone (its ``unattended.scope``),
        so a browser hands nothing to a window nobody is at, and the reply
        carries what the turn needed from them. A question that CAN reach
        them still does -- that is what this service is for -- and
        ``allow_tools`` are the questions they answered ahead of time,
        when they accepted the schedule (``gate.put`` says what that can
        and cannot grant).

        A SCHEDULE'S OWN WAIT. ``wait`` is how long, in all, its questions
        may wait for the person (they accepted it with the schedule); one
        it runs out under lapses, refused and named in the reply.

        THE PHONE, ONLY WHEN THE SCHEDULE SAYS SO. ``phone``: the schedule
        works the phone (Samay's, made in a turn that had it). Its person
        must be the phone's; the phone is checked first (ready.py: in
        use, locked, asleep) and the run skipped when it isn't free.
        ``phone_steps`` are the held taps the person let it do unasked,
        handed to Sparsh, which checks each (its rules.py).

        ``came_by`` is the way the turn came in, for the Run (``runs.py``):
        the caller's word for itself, or the channel's kind when it came
        ``via`` one.

        ``watch`` sees the turn as it runs (watch.py): the words as they
        are written and each step as a line. A turn nobody is at is
        watched by nobody, so an unattended one ignores it.

        ``attachments`` are files the person sent with the message
        (attached.py): kept in their folder under ``from-you/``, named in
        the message, and a picture shown to a model that can see.
        """
        started = datetime.now(UTC)
        came_by = came_by or (via.kind if via is not None else None)
        self.refresh()
        try:
            actor, thread = self._whom(actor, via, thread)
            who = self.actors.may(actor, agent)
            spec = self.roster.spec(agent)
            key = session_key(actor, agent, thread)
        except Refused as exc:
            return Reply(text=str(exc), run_id=None, agent=agent,
                         actor=actor, stop_reason="refused")
        kept: list[attached.Kept] = []
        if attachments and not unattended:
            try:
                kept = attached.keep(self._workspace(key), list(attachments))
            except (ValueError, OSError) as exc:
                return Reply(text=f"I couldn't keep that: {exc}", run_id=None,
                             agent=agent, actor=actor, stop_reason="refused")
            text = attached.said(text, kept)
        heard_as: str | None = None
        for note in (k for k in kept if k.voice):
            words, why = await heard.hear(note.path)
            if words is None:
                self._note(f"dvara: {actor}: a voice note wasn't heard -- {why}")
            heard_as = words if words is not None else heard_as
            text = heard.said(words, text, note.relative)
        if not text.strip():
            return Reply(text="say something and I will answer it",
                         run_id=None, agent=agent, actor=actor,
                         stop_reason="refused")
        if not unattended and files.is_file_word(text):
            # The person's own files: theirs to ask for, not a turn.
            said, found = files.answer(self._workspace(key), text)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="files", files=(found,) if found else ())
        if not unattended and fresh.is_new_word(text):
            # Starting over: theirs to ask for, not a turn -- though a
            # package that remembers looks back first (remembering.py).
            said = await self._start_over(key, spec=spec, who=who, thread=thread,
                                          text=text, came_by=came_by, started=started)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="new")
        if not unattended and phoneview.is_word(text):
            # The phone's screen and last steps: its person's, not a turn.
            if self.sparsh is None or not who.has_phone:
                return Reply(text=phoneview.NOT_YOURS if self.sparsh is not None
                             else "There's no phone on this service.", run_id=None,
                             agent=agent, actor=actor, stop_reason="phone")
            said, shot = await phoneview.look(self.sparsh, self._workspace(key),
                                              mine=who.phones, asked=phoneview.asked(text))
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="phone", files=(shot,) if shot else ())
        if not unattended and past.is_tests(text):
            # Their kept tests: listed, or one taken back. Not a turn.
            return Reply(text=self._past_tests(who, agent, text), run_id=None,
                         agent=agent, actor=actor, stop_reason="new")
        if not unattended and (past.keep_test_words(text) is not None
                               or past.test_pick(text) is not None):
            # One of theirs, kept as a test of this agent: not a turn.
            said = self._past_test(key, who, agent, spec, text)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="new")
        if not unattended and past.export_pick(text) is not None:
            # One of theirs, as a file to share: it goes with the answer.
            said, made = self._past_export(key, who, agent, past.export_pick(text))
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="files", files=(made,) if made else ())
        if not unattended and past.is_word(text):
            # Earlier conversations: theirs to list and go back into.
            said = await self._past_words(key, who=who, agent=agent, thread=thread,
                                          text=text)
            said, shown = said if isinstance(said, tuple) else (said, ())
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="new", transcript=tuple(shown))
        if not unattended and learning.is_learn(text):
            verb, _ = learning.lesson_verb(text)
            if verb in ("", "done"):
                # A skill asked for now -- of the last answer, or of the
                # lesson just finished: the look starts; the offer follows.
                said = await self.learning.learn_now(spec, who, key, came_by,
                                                     done=verb == "done")
                return Reply(text=said, run_id=None, agent=agent, actor=actor,
                             stop_reason="skills")
            said, opening = self.learning.lesson_word(spec, who, key, text)
            if opening is None:
                return Reply(text=said, run_id=None, agent=agent, actor=actor,
                             stop_reason="skills")
            # A lesson opened: its opening is the turn, so the agent hears
            # it is being taught and answers that it is ready.
            text = opening
        if not unattended and learning.word_of(text):
            # Skills offered and kept: theirs to see and answer, not a turn.
            said = await self.learning.words(spec, who, key, text)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="skills")
        if not unattended and (word := seen.word_of(text)):
            # What it can use, and what they scheduled: read, not a turn.
            said = (self.seen.tools(actor, agent) if word == seen.TOOLS else
                    await self.seen.schedules(actor, self.samay,
                                              enabled=self.samay is not None))
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="seen")
        if not unattended and (household.for_everyone(text) is not None
                               or household.is_word(text)):
            # What everyone's agents know: the owner's to keep, anyone's to offer.
            said = await self._household_words(who, text)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="memory")
        if not unattended and spoken.is_word(text):
            # Whether their answers are read aloud: theirs to choose.
            said = spoken.voice_words(self.voices, who.id, who.speak, text, voice=who.voice)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="voice")
        if not unattended and remembering.word_of(text):
            # What is kept about them: theirs to see, keep and forget.
            said = await self._memory_words(spec, who, key, text)
            return Reply(text=said, run_id=None, agent=agent, actor=actor,
                         stop_reason="memory")
        if not unattended:
            # The person's own accounts: theirs to act on, not a turn.
            # Nothing of it is kept -- no run, no history -- because a
            # pasted address carries a sign-in's code (accounts.py).
            said = await self._account_words(who, spec, text)
            if said is not None:
                return Reply(text=said, run_id=None, agent=agent, actor=actor,
                             stop_reason="accounts")

        if not unattended and text.strip().lower().split()[:1] == ["/steps"]:
            # what their last turn (or turn N) did, step by step: not a turn
            return Reply(text=self._steps_words(key, text), run_id=None, agent=agent,
                         actor=actor, stop_reason="steps")
        carrying_on = carry_on or (not unattended and carrying.is_word(text))
        if carrying_on:
            stopped = self._stopped(key)
            if stopped is None:
                return Reply(text=carrying.NOTHING, run_id=None, agent=agent,
                             actor=actor, stop_reason="nothing")
            text = stopped.get("message") or text   # the Run is the job's

        scheduled = None
        if unattended and phone:
            if self.sparsh is None or not who.has_phone:
                return Reply(text=f"{actor} has no phone this service can work: it "
                                  "needs --sparsh and phone = true (or phones = [...]) "
                                  "for them",
                             run_id=None, agent=agent, actor=actor, stop_reason="refused")
            try:
                which = phone_for(who, phone)
            except Refused as exc:
                return Reply(text=str(exc), run_id=None, agent=agent, actor=actor,
                             stop_reason="refused")
            if not works_phone(spec):
                # Before the phone is looked at: a person asked to unlock it
                # for a run that can't touch it gets up for nothing.
                return Reply(text=f"{agent} can't work the phone: its package's [tools] "
                                  "allow leaves out mcp__sparsh__* (add it, as "
                                  "examples/agents/phone does)",
                             run_id=None, agent=agent, actor=actor, stop_reason="refused")
            skip = await ready.ready(ready.through(self.sparsh, *which),
                                     wait=wait or DEFAULT_SCHEDULE_WAIT,
                                     ask=self._asker(who), about=" ".join(text.split())[:120])
            if skip is not None:
                return Reply(text=skip, run_id=None, agent=agent, actor=actor,
                             stop_reason="skipped")
            scheduled = PhoneRun(steps=tuple(phone_steps), phones=which)

        async with self._locks.hold(key):
            # Costing zero until something is spent. The distinction the
            # ledger draws is between "nothing was spent" and "tokens
            # were spent that nobody can price", and a refusal is firmly
            # the first: reading "unpriced" against a turn that never
            # reached a model is the store admitting to a doubt it does
            # not have.
            run = Run(actor=actor, agent=agent, thread=thread, message=text,
                      started_at=started, cost_usd=0.0, unattended=unattended,
                      came_by=came_by)
            try:
                if not unattended:
                    reply = await self._turn(spec=spec, who=who, key=key,
                                             run=run, watch=watch, kept=kept,
                                             carrying=carrying_on)
                    speak = spoken.wanted(self.voices.choice(who.id, who.speak),
                                          spoke=any(k.voice for k in kept))
                    return replace(reply, heard=heard_as, speak=speak,
                                   voice=self.voices.voice(who.id, who.voice))
                with unattended_scope() as record:
                    reply = await self._turn(spec=spec, who=who, key=key,
                                             run=run,
                                             ahead=tuple(allow_tools),
                                             phone_run=scheduled, wait_for=wait,
                                             carrying=carrying_on)
                self._tidy_quietly()
                return replace(reply, needs=tuple(record.needs),
                               busy=tuple(record.busy))
            except Refused as exc:
                run.reply, run.stop_reason = str(exc), "refused"
                self.runs.record(run)
                return Reply(text=str(exc), run_id=run.id, agent=agent,
                             actor=actor, stop_reason="refused")
            except asyncio.CancelledError:
                # A dropped connection is not a failure of the agent, and
                # Yantra's loop already left history resumable. Record what
                # happened so the row does not silently go missing, then
                # let the cancellation continue on its way.
                run.stop_reason, run.reply = "cancelled", ""
                self.runs.record(run)
                raise
            except Exception as exc:  # noqa: BLE001 -- see the docstring
                run.stop_reason = "error"
                run.detail = f"{type(exc).__name__}: {exc}"
                run.reply = "that went wrong at my end"
                self.runs.record(run)
                return Reply(text=run.reply, run_id=run.id, agent=agent,
                             actor=actor, stop_reason="error",
                             detail=run.detail)

    async def resume(self, hold_id: str, *,
                     answers: Mapping[str, bool | str],
                     actor: str | None = None,
                     via: Channel | None = None,
                     door: str | None = None,
                     watch: Watcher | None = None) -> Reply:
        """Answer a held turn, and let it carry on (notes/16).

        ``answers`` has one entry per waiting call, by call id: True runs
        it, False refuses it, and a string refuses it in the person's own
        words, which the model reads. ``door`` is where the answer came
        from, for the Run -- the same record ``AskDesk.answer`` keeps.

        A REFUSAL BEFORE THE TURN IS RAISED, NOT REPLIED. Unlike
        ``deliver``, the caller here is an approval path -- a button, a
        POST, a command -- that already has to tell "that is not yours"
        from "that is gone", and a reply-shaped refusal would make every
        one of them parse a sentence. ``NotYourHold`` and ``NoSuchHold``
        say which; any other ``Refused`` is the answers or the person's
        access. Once the turn is running, it answers exactly as
        ``deliver`` does: a reply either way.

        A RESUME IS A NEW TURN. It is checked against today's money
        before anything is used up, so a person whose allowance is spent
        keeps their hold and can answer it tomorrow.
        """
        started = datetime.now(UTC)
        self.refresh()
        actor, _ = self._whom(actor, via, "")
        door = door or (via.kind if via is not None else None)
        hold = self.holds.get(hold_id)
        if hold is None:
            raise NoSuchHold(
                "no held turn with that id is waiting -- it was answered, "
                "set aside by a newer message, or has expired")
        if hold.actor != actor:
            raise NotYourHold(hold_id)
        if self.holds.expired(hold):
            self.holds.drop(hold.id)
            raise NoSuchHold(
                f"that turn was held more than "
                f"{patience.duration(self.holds.keep_for)} ago and can no "
                f"longer be answered; ask again if it is still wanted")
        for call_id, answer in answers.items():
            if not isinstance(answer, bool | str):
                raise Refused(
                    f"the answer for {call_id} must be true, false, or your "
                    f"reason for refusing it")
        who = self.actors.may(actor, hold.agent)
        spec = self.roster.spec(hold.agent)

        async with self._locks.hold(hold.key):
            # Looked up again under the lock: two answers racing for one
            # hold must not both carry it on.
            if self.holds.get(hold_id) is None:
                raise NoSuchHold("that turn was answered a moment ago")
            # The answer's way in, not the held turn's: this turn is the
            # one the answer started. The CLI's door is "terminal".
            run = Run(actor=actor, agent=hold.agent, thread=hold.thread,
                      message="", started_at=started, cost_usd=0.0,
                      came_by="cli" if door == "terminal" else door)
            try:
                reply = await self._turn(spec=spec, who=who, key=hold.key,
                                         run=run, resuming=hold,
                                         answers=answers, door=door, watch=watch)
                # a yes is a tap, not a voice note: read aloud only for "always"
                return replace(reply, speak=spoken.wanted(
                    self.voices.choice(who.id, who.speak), spoke=False),
                    voice=self.voices.voice(who.id, who.voice))
            except (NoSuchHold, NotYourHold):
                raise
            except Refused as exc:
                if self.holds.get(hold_id) is not None:
                    # Refused before the hold was used -- bad answers, a
                    # spent allowance. Nothing ran; nothing to record.
                    raise
                run.reply, run.stop_reason = str(exc), "refused"
                self.runs.record(run)
                return Reply(text=str(exc), run_id=run.id, agent=run.agent,
                             actor=actor, stop_reason="refused")
            except asyncio.CancelledError:
                run.stop_reason, run.reply = "cancelled", ""
                self.runs.record(run)
                raise
            except Exception as exc:  # noqa: BLE001 -- as deliver
                run.stop_reason = "error"
                run.detail = f"{type(exc).__name__}: {exc}"
                run.reply = "that went wrong at my end"
                self.runs.record(run)
                return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                             actor=actor, stop_reason="error",
                             detail=run.detail)

    # ---- one turn, in the order that works ---------------------------------

    async def _turn(self, *, spec: AgentSpec, who: Actor, key: str,
                    run: Run, resuming: Hold | None = None,
                    answers: Mapping[str, bool | str] | None = None,
                    door: str | None = None,
                    ahead: tuple[str, ...] = (),
                    phone_run: PhoneRun | None = None,
                    wait_for: float | None = None,
                    watch: Watcher | None = None,
                    kept: Sequence[attached.Kept] = (),
                    carrying: bool = False) -> Reply:
        provider_name = self.provider_name or spec.provider or guess_provider()
        model = self.model or spec.model or default_model(provider_name)
        run.model = model

        # Written by the gate as calls are decided, read when the Run is
        # assembled. It has to exist before the gate is built, which is
        # why it is here rather than beside the loop that fills the rest.
        decisions = Decisions()
        run.agent_version = spec.version
        ceiling = self._ceiling(spec=spec, who=who)
        if ceiling.amount is not None and ceiling.amount <= 0:
            raise Refused(
                f"your daily allowance is spent; it comes back at "
                f"{money.next_reset():%H:%M UTC on %-d %b}"
            )
        if resuming is None:
            # The other two limits that aren't money (limits.py): the hours
            # bound every turn of theirs, a schedule's too; the count is
            # only of what they sent. An answer to a held question is
            # neither, so a hold made at 20:59 can still be answered.
            if who.hours is not None and (closed := who.hours.closed()):
                raise Refused(closed)
            if who.max_turns_per_day is not None and not is_unattended():
                spent = limits.turns_spent(
                    who.max_turns_per_day,
                    self.runs.asked_since(who.id, money.day_start()))
                if spent:
                    raise Refused(spent)

        # The other allowance, read from the same ledger at the same
        # moment. Not a refusal of the turn when it is spent, unlike
        # money: a turn with no waiting left can still do everything
        # that needs nobody, and gate.put refuses only what would have
        # been asked (patience.py).
        wait = patience.Patience(patience.remaining_today(
            who.max_wait_per_day,
            (0.0 if who.max_wait_per_day is None
             else self.runs.waited_since(who.id, money.day_start()))),
            scheduled=wait_for if is_unattended() and wait_for else None)

        provider = self._provider(provider_name)
        spec, remembers = self._memory_for(spec, who)
        try:
            agent = replace(spec, max_usd_per_turn=ceiling.amount).build_async(
                permissions=self.policy.gate(
                    spec.permissions_mode,
                    actor_mode=who.permissions,
                    desk=self._desk_for(who),
                    actor=who.id, agent=run.agent, thread=run.thread,
                    reach=who.reach(),
                    decisions=decisions,
                    patience=wait,
                    ahead=ahead,
                ),
                cwd=self._workspace(key),
                provider=provider,
                provider_name=provider_name,
                model=model,
                memory_user=remembers.user,
                # The package's skills and this person's own, never the
                # computer's (~/.yantra/skills): see learning.py.
                own_skills_only=True,
            )
        except ConfigError as exc:
            # The commonest one: a ceiling on a model nobody can price.
            # At a keyboard that is a startup error; here it has to become
            # a sentence, or a channel adapter gets a traceback.
            raise Refused(f"that agent cannot run right now: {exc}") from exc

        if layer := self.household.layer():
            # What everyone in the house may know, in every agent's turn
            # (household.py): the owner's notes, shown whole.
            from yantra.prompt import attach_prompt

            prompt = attach_prompt(agent)
            prompt.set("household", layer)
            prompt.apply()
        sent = self._send_file_tool(agent, who)
        servers = await self._servers(agent, who=who, run=run, key=key, spec=spec,
                                      phone_run=phone_run, remembers=remembers)
        # Every tool is in now, MCP's too: past twenty, only those this turn's
        # words point at are sent (Yantra's own rule, as at its terminal). A
        # person's accounts grow without a word to the package: 227 tools sent
        # whole overflowed a local model's window, which then cut the top of
        # the prompt and answered a question it could no longer see.
        select_when_many(agent, width=spec.tools_per_turn)
        if not is_unattended():
            self.seen.tools_were(who.id, run.agent, agent)
        try:
            reply = await self._run_turn(
                agent, key=key, run=run, resuming=resuming, answers=answers,
                door=door, decisions=decisions, wait=wait, ceiling=ceiling,
                provider_name=provider_name, who=who, watch=Safely(watch),
                kept=kept, carrying=carrying)
            return replace(reply, files=tuple(sent)) if sent else reply
        finally:
            if servers is not None:
                await asyncio.to_thread(servers.shutdown)

    def _desk_for(self, who: Actor):
        """Where this person's questions go: to them, or, when the owner
        named an approver for them, to the approver (limits.py)."""
        if who.approver is None or self.asks is None:
            return self.asks
        try:
            approver = self.actors.get(who.approver)
        except Refused:
            return self.asks
        return limits.ForApproval(self.asks, approver=approver.id,
                                  reach=approver.reach(), person=who.id)

    def _send_file_tool(self, agent, who: Actor) -> list[Path]:
        """``send_file`` for this turn (files.py), admitted or dropped by
        the package's tool list like any other tool. Returns the list a
        chat turn's files collect in, to go out with its answer. A
        scheduled run's file goes at once, as a notice: nobody is waiting
        on that run's answer, and the scheduler sends only its text."""
        sent: list[Path] = []
        unattended = is_unattended()

        async def deliver(path: Path, note: str) -> str:
            if not unattended:
                sent.append(path)
                return f"{path.name} will be sent to them with your answer"
            result = await self.notices.send(who.id, self._told_at(who), note, file=path)
            if result.nowhere:
                raise ToolError("they have no channel a file can be sent to")
            return f"sent {path.name} to them"

        agent.registry.register(files.SendFile(deliver))
        return sent

    def _asker(self, who: Actor):
        """A line in the person's own chat, for a run nobody started."""
        async def ask(line: str) -> None:
            await self.notices.send(who.id, self._told_at(who), line)
        return ask

    async def _servers(self, agent, *, who: Actor, run: Run, key: str, spec: AgentSpec,
                       phone_run: PhoneRun | None = None,
                       remembers: Person | None = None):
        """The MCP servers this turn gets, all stopped when it ends: the
        person's own accounts (``_accounts``), Samay's tools
        (``_schedules``), the phone (``_phone``), their memory
        (``_remembering``) and the package's own (``_packaged``). None
        when there are none to start."""
        accounts = who.setu is not None and bool(spec.connections)
        # a scheduled turn gets the schedules to READ (``_schedules``)
        schedules = self.samay is not None
        watching = self.watches_for(who.id) and not is_unattended()
        # A package that only reads the battery and missed calls touches no
        # screen, so it needs no phone job to have the phone (reads_phone).
        works = works_phone(spec)
        phone = (self.sparsh is not None and who.has_phone and (works or reads_phone(spec))
                 and (not is_unattended() or phone_run is not None or not works))
        remembering = (self.memory is not None and spec.memory == self.memory.name
                       and getattr(agent, "memory", None) is not None)
        packaged = bool(getattr(spec, "mcp", ()))
        if not (accounts or schedules or watching or phone or remembering or packaged):
            return None
        from yantra.mcp import MCPManager

        manager = MCPManager(agent.registry, agent=agent,
                             memory_path=self._workspace(key) / ".yantra" / "mcp.json")
        if accounts:
            await self._accounts(agent, manager, who=who, spec=spec)
        if schedules:
            await self._schedules(agent, manager, who=who, run=run)
        if watching:
            await self._watches(agent, manager, who=who, run=run)
        if phone:
            await self._phone(agent, manager, who=who,
                              grants=list(phone_run.steps) if phone_run else None,
                              only=phone_run.phones if phone_run else ())
        if remembering:
            assert remembers is not None
            await self._remembering(agent, manager, who=who, remembers=remembers)
        if packaged:
            await self._packaged(manager, spec=spec)
        return manager

    async def _packaged(self, manager, *, spec: AgentSpec) -> None:
        """The servers the package itself declares (``[[mcp]]`` in its
        agent.toml), as Yantra starts them in every session.

        LAST, SO THIS TURN'S OWN WIN. A name the person's accounts, Samay,
        the phone or the memory already took is theirs: the package's is
        skipped and the owner told, never swapped in under the same tools.
        The package's ``[tools] allow`` admits their tools or drops them
        like any other (``mcp__<name>__*``). A server that will not start
        costs the turn those tools, never the turn. These are the author's,
        shared by everyone who talks to the agent; a server one person
        added is theirs, in their own Setu folder (``_accounts``)."""
        from yantra.mcp import MCPError

        for cfg in spec.mcp:
            if cfg.name in manager.sessions:
                self._note(f"dvara: {spec.name}: mcp {cfg.name!r} (agent.toml) has the "
                           "name of one this turn already has; using that one")
                continue
            try:
                await asyncio.to_thread(manager.connect, cfg, origin="package")
            except (MCPError, ValueError) as exc:
                self._note(f"dvara: {spec.name}: mcp {cfg.name!r} (agent.toml) is off "
                           f"for this turn -- {exc}")

    def _memory_for(self, spec: AgentSpec, who: Actor) -> tuple[AgentSpec, Person]:
        """The spec with the owner's store in it, and whose memories.

        Only a package that asked for memory gets any (memory.py). With
        the owner's store named, it gets that store -- if this person has
        a key of their own there; without one, none this turn, said once.
        """
        try:
            remembers = person(self.state, who.id)
        except MemoryProblem as exc:
            self._note(f"dvara: memory is off for this turn -- {exc}")
            return replace(spec, memory="off"), Person(user=who.id)
        if self.memory is None or spec.memory in (None, "off"):
            return spec, remembers
        if remembers.key is None:
            self._note(f"dvara: {who.id}: no memory this turn -- no key of their "
                       f"own for {self.memory.name!r} in {self.state / PEOPLE_FILE}")
            return replace(spec, memory="off"), remembers
        return replace(spec, memory=self.memory.name, memory_verbs=()), remembers

    async def _remembering(self, agent, manager, *, who: Actor, remembers: Person) -> None:
        """The owner's store, started for this person with their own key.
        A store that will not start costs the turn its memory, never the
        turn (Yantra's memory fails open, and says so)."""
        from yantra.mcp import MCPError
        from yantra.memory.mcp import bind_memory_server

        assert self.memory is not None
        try:
            config = self.memory.config_for(remembers)
            await asyncio.to_thread(manager.connect, config)
        except (MCPError, MemoryProblem) as exc:
            self._note(f"dvara: {who.id}: memory is off for this turn -- "
                       f"{self.memory.name}: {exc}")
            return
        if problem := bind_memory_server(agent, manager):
            self._note(f"dvara: {who.id}: {problem}")

    async def accounts_page(self, actor: str) -> tuple[str | None, str]:
        """(the one-time link to this person's own Setu page, or None; the
        words ``/accounts page`` would answer) -- for a page's button,
        which must say exactly what the chat word says (accounts.py)."""
        self.refresh()
        who = self.actors.get(actor)
        said = await self.accounts.handle(
            actor=who.id, text="/accounts page", home=self.setu_home(who),
            own=who.manages_setu, narrowed=who.setu_accounts, needs={},
            may_lock=who.setu == OWN_SETU)
        found = re.search(r"https?://\S+", said or "")
        return (found.group(0) if found else None), said or ""

    async def _account_words(self, who: Actor, spec: AgentSpec, text: str) -> str | None:
        """``/connect``, ``/accounts``, ``/disconnect`` or a pasted
        address, answered for this person; None for anything else."""
        if not (looks_pasted(text) or is_command(text)
                or self.accounts.keys.expects_passphrase(who.id)):
            return None
        from yantra.setu_link import needs_allow

        return await self.accounts.handle(
            actor=who.id, text=text, home=self.setu_home(who), own=who.manages_setu,
            narrowed=who.setu_accounts, needs=needs_allow(spec.connections),
            may_lock=who.setu == OWN_SETU)

    def setu_home(self, who: Actor) -> Path | None:
        """Where this person's sign-ins live, made (yours alone) when it
        is a folder of their own under this service's state."""
        if who.setu is None:
            return None
        if who.setu != OWN_SETU:
            return Path(who.setu)
        home = self.state / "setu" / who.id
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        return home

    async def _accounts(self, agent, manager, *, who: Actor, spec: AgentSpec) -> None:
        """The person's OWN accounts, as far as the package asked.

        THEIR FOLDER, NEVER ANYBODY ELSE'S. Setu is read in this person's
        home (``SETU_HOME``) and every connector asks there for its pass,
        so one person's agent cannot reach another's inbox or the owner's
        -- unless the owner pointed them at a folder on purpose, and then
        ``setu_accounts`` can narrow it to the accounts meant.

        BOTH MUST ALLOW. A connection is used only when the package's
        ``[connections] needs`` names its connector (or ``*``, every
        one), at the package's level at most: the person's sign-in is
        not a reason for an agent that never asked to read their mail. A scheduled turn gets the
        same, because the person made the schedule (its card said what
        it reads). A Setu that cannot be read costs the accounts, never
        the turn.
        """
        from yantra.mcp import MCPError
        from yantra.setu_link import (Setu, SetuLinkError, account_of, ceiling_of, load,
                                      needs_allow)

        needs = needs_allow(spec.connections)
        home = str(self.setu_home(who))
        key = self.accounts.keys.key_for(who.id)
        try:
            link = await asyncio.to_thread(load, "on", None, home, key)
        except SetuLinkError as exc:
            self._note(f"dvara: {who.id}'s accounts are off for this turn -- setu: {exc}")
            return
        allow = {}
        # locked ones too: named to the agent, never started (setu_link)
        for row in (link.connections + link.locked if link is not None else []):
            account = f"{row.get('connector')}:{account_of(row)}"
            if who.setu_accounts is not None and account not in who.setu_accounts:
                continue
            if level := ceiling_of(needs, row):      # "*:read" reaches every one
                allow[account] = level
        setu = Setu(mode="on", home=home, link=link, allow=allow,
                    package=spec.name, mention=frozenset(needs),
                    connect_how=CONNECT_HERE if who.manages_setu else CONNECT_THERE,
                    locked_how=LOCKED_HERE, vault_key=key)
        try:
            done = await asyncio.to_thread(setu.sync, manager, agent)
        except MCPError as exc:
            self._note(f"dvara: {who.id}'s accounts are off for this turn -- {exc}")
            return
        for note in done.notes:
            self._note(f"dvara: {who.id}: setu: {note}")
        agent.setu = setu        # Samay's card names what a schedule reads

    async def _schedules(self, agent, manager, *, who: Actor, run: Run) -> None:
        """Samay's tools for this turn's person, or None.

        ONE SERVER PER TURN, FOR THAT PERSON. ``samay mcp --for <actor>``
        starts beside the agent and stops when the turn ends, like the
        agent itself (a fresh agent per turn, above): nothing outlives a
        turn that could carry one person's schedules into another's. A
        schedule made here runs this agent, as this person, on this road
        (``--runner dvara``), so their allowance and the owner's rules
        apply to every run. Creating one is a write, asked about on the
        person's channel with Yantra's card in words (its notes/115).

        A SCHEDULED TURN GETS THEM TO READ, NOTHING MORE: nobody is there
        to say yes to a new schedule, and a schedule that made schedules
        would be one nobody approved. Reading is what a morning brief
        needs -- how last night's kept tests went is a schedule's last
        run (notes/63). And a Samay that will not start costs the turn its
        tools, never the turn -- the owner hears about it once.
        """
        from yantra.mcp import MCPError
        from yantra.samay_link import Samay, SamayLinkError, load

        try:
            found = await asyncio.to_thread(load, "on", self.samay)
            assert found is not None
            link = Samay(mode="on", data=found[0], program=found[1],
                         person=who.id, agent=run.agent, runner="dvara",
                         seen_at=SEEN_HERE, clock_off=CLOCK_OFF,
                         # a turn with the phone makes schedules that work it
                         phone=self.sparsh is not None and who.has_phone)
            await asyncio.to_thread(link.connect, manager, agent)
        except (MCPError, SamayLinkError) as exc:
            self._note(f"dvara: schedules are off for this turn -- samay: {exc}")
            return
        if is_unattended():
            for name in [n for n in agent.registry.names() if n.startswith("mcp__samay__")]:
                if not agent.registry.get(name).read_only:
                    agent.registry.unregister(name)
            from yantra.prompt import attach_prompt

            prompt = attach_prompt(agent)
            prompt.set("schedules", "# The person's schedules\nThis run is one of their "
                       "schedules, with nobody watching: list_schedules and schedule_runs "
                       "read the others and how their last runs went. Nothing here makes, "
                       "pauses or deletes a schedule.")
            prompt.apply()

    async def _watches(self, agent, manager, *, who: Actor, run: Run) -> None:
        """Prahari's tools for this turn's person (``watches_for``).

        ONE SERVER PER TURN, as for Samay: ``prahari mcp --for <actor>
        --runner dvara`` starts beside the agent and stops with the turn. A
        watch made here wakes this agent, as this person, on this road:
        their allowance and the owner's rules apply when it fires, and the
        news comes to their channels. Making one is a write, asked about on
        their channel with Yantra's card in words (its notes/140). Its looks
        come back here as them (``call``), with their own accounts.

        A SCHEDULED TURN GETS NONE, and a Prahari that will not start costs
        the turn its watches, never the turn."""
        from yantra.mcp import MCPError
        from yantra.prahari_link import Prahari, PrahariLinkError, load

        try:
            found = await asyncio.to_thread(load, "on", self.prahari)
            assert found is not None
            link = Prahari(mode="on", data=found[0], program=found[1], person=who.id,
                           agent=run.agent, runner="dvara", seen_at=WATCHES_HERE,
                           off=WATCH_OFF)
            await asyncio.to_thread(link.connect, manager, agent)
        except (MCPError, PrahariLinkError) as exc:
            self._note(f"dvara: watches are off for this turn -- prahari: {exc}")

    async def _phone(self, agent, manager, *, who: Actor,
                     grants: list[str] | None = None, only: tuple[str, ...] = ()) -> None:
        """Sparsh's tools, for the phone's own person.

        THEIR PHONE, ASKED THERE. Only the one person the owner marked
        ``phone = true`` gets it: the phone on this machine's cable is
        theirs, messages and all. Its ordinary steps run unasked and
        Sparsh holds the ones that can't be taken back (Send, Pay,
        Delete, a password); ``confirm`` always asks, so the yes comes to
        their channel as buttons, worded as Sparsh's own account of the
        step (Yantra's sparsh_link). A screen the list can't read comes
        with a screenshot when the model is local and can see, as at a
        keyboard (``YANTRA_PHONE_SHOTS``).

        THEIR PHONES, NO OTHERS. With several phones named (Sparsh's
        ``$SPARSH_PHONES``), a person's ``phones`` are all their agents
        get: Sparsh is started with only those (``--phone NAME``), so
        another person's phone is not a phone this turn can reach --
        and a scheduled run, only the one it was checked free on.

        WITH NOBODY THERE, ONLY WHEN ITS SCHEDULE SAYS SO (``deliver``):
        the phone was checked free first, and ``grants`` are the held
        taps its person let it do unasked. And a Sparsh that will not
        start costs the turn its phone, never the turn."""
        from yantra.mcp import MCPError
        from yantra.sparsh_link import Sparsh, SparshLinkError, load, shots
        from yantra.sparsh_link import only as narrowed

        names = only or who.phones
        try:
            found = await asyncio.to_thread(load, "on", self.sparsh, False)
            assert found is not None
            data = narrowed(found[0], *names) if names else found[0]
            link = Sparsh(mode="on", path=self.sparsh, data=data, program=found[1],
                          only=tuple(names))
            provider = agent.provider
            link.shots, link.shots_why = shots(
                getattr(provider, "name", ""),
                getattr(getattr(provider, "settings", None), "base_url", ""), str(agent.model))
            await asyncio.to_thread(link.connect, manager, agent, grants)
        except (MCPError, SparshLinkError) as exc:
            self._note(f"dvara: {who.id}'s phone is off for this turn -- sparsh: {exc}")

    async def _run_turn(self, agent, *, key: str, run: Run,
                        resuming: Hold | None, answers, door: str | None,
                        decisions: Decisions, wait, ceiling, provider_name: str,
                        who: Actor, watch: Safely | None = None,
                        kept: Sequence[attached.Kept] = (),
                        carrying: bool = False) -> Reply:
        self._rehydrate(agent, key)
        # the turn's steps are noted under its run id (runsteps.py)
        agent.turn_tag = run.id
        # EVERY STEP IS SAVED, not only the turn's end: a restart in the
        # middle of a job leaves it here as far as it got (carrying.py).
        agent.on_step = lambda a: self.sessions.save(
            a, provider_name=provider_name, session_id=key)
        if resuming is not None:
            events = self._carry_on(agent, resuming, answers or {}, run,
                                    decisions, door)
        elif carrying:
            if agent.unfinished is None:
                raise Refused(NOTHING_STOPPED)
            events = agent.carry_on()
        else:
            if agent.held is not None:
                # A NEW MESSAGE SETS A HELD TURN ASIDE -- Yantra answers the
                # waiting calls "set aside, never ran" as this turn begins
                # (its note 88), and the queue follows the conversation
                # rather than offering an answer nothing can take.
                self.holds.drop_key(key)
            message, images = run.message, None
            if any(k.picture for k in kept):
                base_url = getattr(getattr(agent.provider, "settings", None), "base_url", "")
                if await attached.sees(provider_name, base_url or "", str(agent.model)):
                    images = attached.pictures(list(kept))
                else:
                    message = f"{message}\n\n{attached.NOT_SEEN}"
            events = agent.run_streaming(message, images=images)
        before_total = _copy(agent.total_usage)
        before_models = {m: _copy(u) for m, u in agent.usage_by_model.items()}

        end: TurnEnd | None = None
        tell = watch or Safely(None)

        def streamed(event) -> None:
            # Words and a chosen tool come through Yantra's callback, while
            # the loop below drains the model's stream (its _atee).
            seen = shown(event, agent)
            if seen is not None:
                tell(seen)

        agent.on_stream_event = streamed
        try:
            async for event in events:
                if isinstance(event, ToolExecuted):
                    streamed(event)
                if isinstance(event, TurnEnd):
                    end = event
                    if end.reason == "held" and agent.held is not None:
                        # Named on the hold before the checkpoint below is
                        # written, so the Run that answers it can say which
                        # one it continues even after a restart.
                        agent.held.recorded = run.id
                elif isinstance(event, ToolExecuted):
                    # A REFUSED CALL IS STILL ONE OF THESE, which is
                    # Yantra's own decision and the reason this is one
                    # branch rather than two: the loop turns a denial into
                    # an error result rather than an exception, so a
                    # refusal, a crash and a success all arrive here and
                    # ``refusal`` is what tells them apart.
                    run.tools.append(ToolStep(
                        event.call.name, event.refusal,
                        decisions.of(event.call.id)))
        finally:
            # Save even when the turn died. Yantra guarantees history is
            # resumable at this point -- outstanding tool calls have
            # synthesized results -- so what is written is always loadable.
            self.sessions.save(agent, provider_name=provider_name,
                               session_id=key)
            if not is_unattended():
                # Kept to read again (past.py) -- a person's conversation,
                # never a schedule's run, and never at the turn's cost.
                try:
                    self.past.kept(who.id, run.agent, key, run.thread,
                                   snapshot(agent, provider_name))
                except Exception as exc:
                    self._note(f"dvara: conversation not kept: {exc}")
            # AND ACCOUNT FOR IT. A turn that raised on its fourth model
            # call still paid for the first three, and this is the only
            # place that knows it: the handler upstairs has a Run and no
            # agent. Leave it out and a crash erases its own cost --
            # which the daily allowance then never sees, so a person with
            # a $2 day can spend all afternoon in failing turns. Zero
            # tokens is also a real answer, and cheap to write down.
            run.usage = _delta(before_total, agent.total_usage)
            run.cost_usd = _cost(before_models, agent.usage_by_model,
                                 provider_name=provider_name)
            run.answered_from = list(decisions.channels)
            run.waited_seconds = round(wait.waited, 3)
            run.ended_at = datetime.now(UTC)

        run.stop_reason = end.reason if end else "error"
        run.detail = end.detail if end else None
        run.reply = (end.response.message.text().strip()
                     if end and end.response is not None else "")
        held = None
        if run.stop_reason == "held" and agent.held is not None:
            held = self._keep(agent, key, run, decisions)
            run.reply = waiting_text(held)
        if not run.reply:
            run.reply = _explain(run.stop_reason, run.detail, ceiling)
        noticed = self._noticed(agent, run)
        if noticed:
            run.reply = f"{run.reply}\n\n{noticed}"
        self.runs.record(run)
        # Behind the answer: learned skills counted, and a look for one to
        # keep (learning.py) -- started now, run after this returns.
        self.learning.after_turn(agent, end, run=run, key=key, who=who,
                                 provider_name=provider_name)
        return Reply(text=run.reply, run_id=run.id, agent=run.agent,
                     actor=run.actor, stop_reason=run.stop_reason,
                     detail=run.detail, cost_usd=run.cost_usd,
                     usage=run.usage,
                     receipt=self._receipt(who, run, provider_name),
                     held=held,
                     refused=_refused(wait.lapsed, run.tools))

    def _keep(self, agent, key: str, run: Run,
              decisions: Decisions) -> Hold:
        """File a turn that stopped, and put its waiting calls on the Run.

        A HELD CALL IS A STEP, marked ``held``. The loop reports no
        ``ToolExecuted`` for it -- it has no result -- so without this the
        ledger would show a turn that stopped for no visible reason.
        """
        waiting = agent.held.waiting
        for request in waiting:
            run.tools.append(ToolStep(request.tool_name, HELD,
                                      decisions.of(request.call_id)))
        return self.holds.keep(
            key=key, actor=run.actor, agent=run.agent, thread=run.thread,
            run_id=run.id,
            held_at=datetime.fromtimestamp(agent.held.at, UTC),
            calls=[Waiting(r.call_id, r.tool_name, r.summary)
                   for r in waiting])

    def _carry_on(self, agent, hold: Hold, answers: Mapping[str, bool | str],
                  run: Run, decisions: Decisions, door: str | None):
        """Check a hold against the conversation, use it up, and resume.

        EVERYTHING THAT CAN BE WRONG IS FOUND BEFORE THE ROW GOES. The
        checkpoint may no longer hold this turn (a newer message set it
        aside, somebody cleared the conversation), or the answers may not
        match what is waiting; either is a refusal that costs nothing and
        leaves the person free to try again. Only then is the row dropped
        -- before a single call runs, so a crash cannot run one twice
        (holds.py).
        """
        if agent.held is None or agent.held.ids != [c.call_id
                                                    for c in hold.calls]:
            self.holds.drop(hold.id)
            raise NoSuchHold(
                "that turn is no longer waiting: the conversation moved on "
                "since it was held, so there is nothing to carry on")
        try:
            check_answers(agent.held, answers, agent.history)
        except ValueError as exc:
            raise Refused(str(exc)) from None
        run.message = held_task(agent.history) or run.message
        run.resumes = agent.held.recorded or hold.run_id
        self.holds.drop(hold.id)
        for call_id in answers:
            # The person settled every one of these, from wherever they
            # answered -- the same record a question answered in time
            # leaves (gate.py).
            decisions.by_person(call_id, door)
        return agent.resume(dict(answers))

    # ---- the pieces --------------------------------------------------------

    def _ceiling(self, *, spec: AgentSpec, who: Actor) -> money.Ceiling:
        """Package ∧ actor ∧ what is left of today. See money.py."""
        spent = (0.0 if who.max_usd_per_day is None
                 else self.runs.spent_since(who.id, money.day_start()))
        return money.compose(
            package=spec.max_usd_per_turn,
            actor_turn=who.max_usd_per_turn,
            remaining_today=money.remaining_today(who.max_usd_per_day, spent),
        )

    def _receipt(self, who: Actor, run: Run, provider_name: str) -> str | None:
        """The line under the answer, asked for AFTER the run is recorded.

        Order matters and is the whole of this method's difficulty. The
        allowance figure a person wants is what is left NOW, which is to
        say after the turn they just paid for -- and reading it back out
        of the ledger, rather than subtracting in memory from the number
        ``_ceiling`` started with, is what makes it the same figure the
        next turn will be gated on. An unpriced turn contributes nothing
        to either, so the two cannot drift.
        """
        if who.receipt is None:
            return None
        remaining = None
        waiting = None
        if who.receipt == "remaining":
            remaining = money.remaining_today(
                who.max_usd_per_day,
                self.runs.spent_since(who.id, money.day_start()))
            # The other allowance, read back the same way and for the same
            # reason (notes/15). A free provider silences the money half
            # and not this one: waiting on a person costs the same on
            # every road.
            waiting = patience.receipt(
                patience.remaining_today(
                    who.max_wait_per_day,
                    self.runs.waited_since(who.id, money.day_start())),
                run.waited_seconds)
        spent = money.receipt(who.receipt, cost_usd=run.cost_usd,
                              free=bills_nothing(provider_name),
                              remaining=remaining)
        return " · ".join(part for part in (spent, waiting) if part) or None

    def _provider(self, name: str) -> Provider:
        """One connection pool per provider, for the life of the service."""
        if name not in self._providers:
            self._providers[name] = self._provider_factory(name)
        return self._providers[name]

    def tidy(self, now: datetime | None = None) -> int:
        """Let go of conversations a program started and nobody will
        continue; how many went.

        Samay starts a fresh thread for every scheduled run, so a run's
        history never drags the last four hundred answers into its
        prompt. Nothing ever writes to that thread again, and without
        this its checkpoints stay for good: one more per run, for as long
        as the schedule runs.

        ONLY A THREAD NOBODY STARTED. The ledger's first run on a thread
        decides (``RunStore.finished_unattended``); a person's own
        conversation is never touched, even if a program later wrote into
        it. KEPT A WHILE FIRST: ``keep_unattended`` after its last turn,
        so the owner can still read what a run was told and said. NEVER
        WHILE IT COULD GO ON: a thread with a question still waiting for
        its person (a hold), or a turn running on it now, is skipped and
        looked at again next time.

        THE RECORD STAYS, AND SO DO THE FILES. Every run stays in the
        ledger -- ``dvara runs``, ``dvara case`` and the day's spending
        read it -- and the files it wrote are in the person's folder with
        this agent (``_workspace``), where their chat can find them. Only
        the conversation (sessions.sqlite3) goes.
        """
        now = now or datetime.now(UTC)
        before = now - timedelta(seconds=self.keep_unattended)
        waiting = {hold.key for hold in self.holds.pending(now=now)}
        gone = 0
        for actor, agent, thread in self.runs.finished_unattended(before):
            key = session_key(actor, agent, thread)
            if key in waiting or key in self._locks:
                continue
            self.sessions.forget(key)
            self.runs.mark_tidied(actor, agent, thread)
            gone += 1
        return gone

    async def _start_over(self, key: str, *, spec: AgentSpec, who: Actor, thread: str,
                          text: str, came_by: str | None, started: datetime) -> str:
        """``/new`` (fresh.py): this conversation forgotten, and anything
        it was holding for the person with it -- never while a turn is
        still working on it. A package that remembers looks back over it,
        but behind the answer: the copy goes to ``_look_back_behind``, and
        what it noticed comes as a message of its own (notes/51)."""
        if key in self._locks:
            return fresh.STILL_ANSWERING
        async with self._locks.hold(key):
            noticed = ""
            ending = self.sessions.load_latest(key)
            if (self.runs.last_stop(who.id, workspace_parts(key)[1], thread)
                    == "looked_back"):
                # looked back over already, when it went quiet: nothing new
                waiting = self.offered.get(who.id)
                noticed = remembering.looked_back(waiting) if waiting else ""
            elif ending is not None:
                self._look_back_behind(spec, who, key, ending, thread=thread,
                                       text=text, came_by=came_by, started=started)
            self.holds.drop_key(key)
            # Already kept, turn by turn (past.py): the next one is new.
            self.past.ended(key)
            gone = self.sessions.forget(key)
        said = fresh.STARTED_OVER if gone else fresh.NOTHING_YET
        if self.learning.drop_lesson(who.id, workspace_parts(key)[1]):
            # Its opening went with the conversation: the agent would no
            # longer know it was being taught (learning.py).
            from yantra.skills.lesson import DROPPED
            said = f"{said} {DROPPED}"
        return f"{said}\n\n{noticed}" if noticed else said

    def _look_back_behind(self, spec: AgentSpec, who: Actor, key: str, ending: dict,
                          **run: Any) -> None:
        """The look back over the conversation ``/new`` just ended, run
        after the answer has gone: the person starts over at once, and what
        it noticed comes as a notice, numbered for ``/remember``, as the
        quiet look's does. Nothing noticed, nothing sent. Many people share
        one model here, so it simply takes its turn in the model's queue."""
        async def look() -> None:
            said = await self._look_back(spec, who, key, payload=ending,
                                         ended=True, **run)
            if not said:
                return
            text = f"{workspace_parts(key)[1]}: {said}"
            if self.told_behind is not None:
                await self.told_behind(who.id, text)
                return
            try:
                await self.notify(text=text, actor=who.id)
            except Refused:
                pass
        task = asyncio.get_running_loop().create_task(look())
        self._behind.add(task)
        task.add_done_callback(self._behind.discard)

    async def settle(self) -> None:
        """Wait for every look back still running behind a ``/new``: what
        a test, or a service stopping, waits on before it reads the result."""
        while self._behind:
            await asyncio.gather(*list(self._behind), return_exceptions=True)

    async def _past_words(self, key: str, *, who: Actor, agent: str, thread: str,
                          text: str) -> str | tuple[str, list[dict]]:
        """``/chats`` lists, ``/chats WORDS`` finds, ``/chats N`` goes back
        into one, ``/chats delete N [sure]`` deletes one (past.py)."""
        pick = past.picked(text)
        open_id = self.past.current(key) if self.sessions.load_latest(key) else None
        verb, _, rest = pick.partition(" ")
        if verb.lower() == "delete" and rest.split()[:1] and rest.split()[0].isdigit():
            n, sure = rest.split()[0], rest.split()[1:2] == ["sure"]
            return self._past_delete(who, agent, int(n), sure, open_id)
        rows = self.past.listed(who.id, agent)
        if verb.lower() == "open" and rest.strip():
            # ``/chats open N``, as Yantra's terminal says it, or ``/chats
            # open ID``: what a page sends for the row it drew.
            pick = rest.strip()
            if not pick.isdigit():
                place = next((n for n, r in enumerate(rows, 1) if r.id == pick), None)
                if place is None:
                    return "That conversation is gone. Send /chats to see what's kept."
                pick = str(place)
        if not pick.isdigit():
            # Found ones keep their number in the whole list, so the N
            # sent next means the row that was on screen.
            return past.listing(agent, self.past.listed(who.id, agent, pick)
                                if pick else rows, pick, open_id=open_id,
                                numbers={r.id: n for n, r in enumerate(rows, 1)})
        if not 1 <= int(pick) <= len(rows):
            return (f"There's no conversation {pick} to go back to. Send /chats to "
                    f"see them." if rows else past.listing(agent, rows))
        chosen = rows[int(pick) - 1]
        if chosen.id == open_id:
            return "That's the conversation we're in now."
        elsewhere = [k for k in self.past.open_on(who.id, chosen.id) if k != key]
        if elsewhere:
            return (f"That conversation is still going on {past.came_of_key(elsewhere[0])}. "
                    f"Carry it on there, or send /new there first.")
        if key in self._locks:
            return fresh.STILL_ANSWERING.replace("/new", f"/chats {pick}")
        async with self._locks.hold(key):
            payload = self.past.payload(who.id, chosen.id)
            if payload is None:
                return "That conversation just went. Send /chats to see what's kept."
            self.holds.drop_key(key)
            self.sessions.forget(key)
            self.sessions.save_payload(payload, session_id=key)
            self.past.opened(key, chosen.id)
        said = past.reopened(payload, agent)
        if self.learning.drop_lesson(who.id, agent):
            from yantra.skills.lesson import DROPPED
            said = f"{said}\n\n{DROPPED}"
        return said, past.transcript(payload)

    def _past_test(self, key: str, who: Actor, agent: str, spec: AgentSpec,
                   text: str) -> str:
        """``/keep test`` (this one) or ``/chats test N`` (from the list),
        kept in the person's own tests of this agent (past.py)."""
        from yantra.kept_tests import keep_from_log, people_root
        chosen = past.test_pick(text)
        if chosen is None:
            if not self.sessions.load_latest(key):
                return "There's nothing to keep yet: ask me something first."
            conversation, words = self.past.current(key), past.keep_test_words(text) or ""
            turn = None
        else:
            n, words = chosen
            rows = self.past.listed(who.id, agent)
            turn, words = past.turn_of(words)
            if not 1 <= n <= len(rows):
                return f"There's no conversation {n}. Send /chats to see them."
            conversation = rows[n - 1].id
        wanted = [w.strip() for w in words.split(",") if w.strip()]
        try:
            case_id, _, recording = keep_from_log(
                self.past.log(who.id), conversation, agent, words=wanted,
                root=people_root(who.id), package=spec.root, person=who.id,
                turn=turn)
        except ConfigError as exc:
            return f"I couldn't keep that as a test: {exc}."
        title = next((r.title for r in self.past.listed(who.id, agent)
                      if r.id == conversation), recording.question[:80])
        return past.tested(case_id, title, recording.used, wanted)

    def _past_tests(self, who: Actor, agent: str, text: str) -> str:
        """``/tests`` lists the person's kept tests of this agent;
        ``/tests delete N`` takes one back (its case and recording; the
        conversation stays in /chats)."""
        from yantra.kept_tests import forget, kept_in, people_root, suite_dir
        suite = suite_dir(agent, people_root(who.id))
        kept = kept_in(suite)
        verb, _, rest = past.picked(text).partition(" ")
        if verb.lower() == "delete" and rest.strip().isdigit():
            n = int(rest.strip())
            if not 1 <= n <= len(kept):
                return f"There's no kept test {n}. Send /tests to see them."
            forget(suite, kept[n - 1].id)
            return (f"Taken back: “{kept[n - 1].question[:80]}” is no longer a test. "
                    f"The conversation is still in /chats.")
        if verb:
            return "Send /tests to see your kept tests, /tests delete N to take one back."
        return past.tests_listing(agent, kept)

    def _past_export(self, key: str, who: Actor, agent: str,
                     n: int) -> tuple[str, Path | None]:
        """``/chats export N``: the conversation as a Markdown file in their
        folder with this agent (``shared/``), sent with the answer. Words,
        answers and the tools' names -- never a tool's output (Yantra's
        history.export_markdown)."""
        rows = self.past.listed(who.id, agent)
        if not 1 <= n <= len(rows):
            return f"There's no conversation {n}. Send /chats to see them.", None
        kept = self.past.read(who.id, rows[n - 1].id)
        if kept is None:
            return "That conversation just went. Send /chats to see what's kept.", None
        made = past.export_to(self._workspace(key) / past.SHARED, kept, agent)
        return (f"Here is “{kept['title']}”, to share: your words, my answers and the "
                f"names of the tools I used (never what they returned). It's kept in "
                f"your files too, as {past.SHARED}/{made.name}."), made

    def _past_delete(self, who: Actor, agent: str, n: int, sure: bool,
                     open_id: str | None) -> str:
        """Asked once: a chat has no dialog, so the word ``sure`` is it."""
        rows = self.past.listed(who.id, agent)
        if not 1 <= n <= len(rows):
            return f"There's no conversation {n}. Send /chats to see them."
        chosen = rows[n - 1]
        if chosen.id == open_id:
            return ("That's the conversation we're in now. Send /new first, then "
                    "delete it.")
        if not sure:
            return (f"Delete “{chosen.title}” for good? It can't be brought back. "
                    f"Send /chats delete {n} sure to delete it.")
        self.past.delete(who.id, chosen.id)
        return f"Deleted “{chosen.title}” for good."

    async def _look_back(self, spec: AgentSpec, who: Actor, key: str, *, thread: str,
                         text: str, came_by: str | None, started: datetime,
                         quiet: bool = False, ended: bool = False,
                         payload: dict | None = None) -> str:
        """Yantra's look back over the conversation ``/new`` ends: one call
        to the agent's own model, on the person's allowance and recorded
        as a Run like any turn. Never costs the start-over: a look back
        that fails is a line for the owner, and the conversation still goes."""
        from yantra.memory.reflect import areflect

        ceiling = self._ceiling(spec=spec, who=who)
        if ceiling.amount is not None and ceiling.amount <= 0:
            return ""                       # no allowance left to look back with
        run = Run(actor=who.id, agent=workspace_parts(key)[1], thread=thread,
                  message=text, started_at=started, cost_usd=0.0, came_by=came_by)
        async with self._remembered(spec, who, key, history=True,
                                    payload=payload) as agent:
            if agent is None:
                return ""
            run.model = agent.model
            before_total = _copy(agent.total_usage)
            before_models = {m: _copy(u) for m, u in agent.usage_by_model.items()}
            found = []
            try:
                found = await areflect(agent)
                run.stop_reason = "looked_back"
            except Exception as exc:  # noqa: BLE001 -- the start-over still happens
                run.stop_reason, run.detail = "error", f"{type(exc).__name__}: {exc}"
                when = "after a quiet while" if quiet else "at /new"
                self._note(f"dvara: {who.id}: the look back {when} failed -- {run.detail}")
            finally:
                run.usage = _delta(before_total, agent.total_usage)
                run.cost_usd = _cost(before_models, agent.usage_by_model,
                                     provider_name=agent.provider_name)
                run.ended_at = datetime.now(UTC)
        if found:
            # the whole conversation, read once: it replaces its parts
            self.offered.add(who.id, run.agent,
                             [remembering.Offer(c.statement, c.kind) for c in found],
                             replace=True)
        waiting = self.offered.get(who.id)
        said = (remembering.looked_back(waiting, quiet=quiet, ended=ended)
                if waiting else "")
        if (quiet or ended) and not found:
            said = ""        # unasked: only news is worth a message
        run.reply = said or ("Looked back; nothing new to remember."
                             if run.stop_reason == "looked_back" else "")
        self.runs.record(run)
        return said

    def _noticed(self, agent, run: Run) -> str:
        """What Yantra noticed about the person during this turn
        (``memory.pending``: before shortening the conversation, or in a
        learned task's write-up), listed for them to keep; a run nobody
        is at lets it go, since nobody is there to say which."""
        memory = getattr(agent, "memory", None)
        pending = list(getattr(memory, "pending", None) or [])
        if not pending:
            return ""
        memory.pending.clear()
        if run.unattended:
            return ""
        new = self.offered.add(run.actor, run.agent,
                               [remembering.Offer(c.statement, c.kind) for c in pending])
        return remembering.noticed(new) if new else ""

    @asynccontextmanager
    async def _remembered(self, spec: AgentSpec, who: Actor, key: str, *,
                          history: bool = False,
                          payload: dict | None = None) -> AsyncIterator[object | None]:
        """An agent built for this person as a turn would be, with their
        memory open (their name, their own key) and no message sent; None
        when this package keeps none for them. ``history``: this
        conversation loaded too, for a look back over it -- or ``payload``,
        a conversation ``/new`` has already let go of."""
        provider_name = self.provider_name or spec.provider or guess_provider()
        model = self.model or spec.model or default_model(provider_name)
        spec, remembers = self._memory_for(spec, who)
        if spec.memory in (None, "off"):
            yield None
            return
        try:
            agent = spec.build_async(cwd=self._workspace(key),
                                     provider=self._provider(provider_name),
                                     provider_name=provider_name, model=model,
                                     memory_user=remembers.user, own_skills_only=True)
        except ConfigError as exc:
            self._note(f"dvara: {who.id}: memory could not be opened -- {exc}")
            yield None
            return
        agent.provider_name = provider_name
        manager = None
        if self.memory is not None and getattr(agent, "memory", None) is not None:
            from yantra.mcp import MCPManager

            manager = MCPManager(agent.registry, agent=agent,
                                 memory_path=self._workspace(key) / ".yantra" / "mcp.json")
            await self._remembering(agent, manager, who=who, remembers=remembers)
        try:
            if history and payload is not None:
                apply_payload(agent, payload, history_only=True)
            elif history:
                self._rehydrate(agent, key)
            yield agent if getattr(agent, "memory", None) is not None else None
        finally:
            if manager is not None:
                await asyncio.to_thread(manager.shutdown)

    async def _household_words(self, who: Actor, text: str) -> str:
        """``/remember for everyone …`` and ``/household …`` (household.py)."""
        owner = self.owner is not None and who.id == self.owner
        fact = household.for_everyone(text)
        try:
            if fact is not None and owner:
                kept = self.household.add(fact, who.id)
                return f"Kept for everyone's agents: {kept.text}"
            if fact is not None:
                if self.owner is None:
                    return ("Nobody here keeps what everyone knows, so there's nobody "
                            "to offer it to.")
                offered = self.household.offer(fact, who.id)
                number = len(self.household.offered())
                try:
                    boss = self.actors.get(self.owner)
                    await self.notices.send(boss.id, self._told_at(boss),
                                            household.offer_notice(offered, number))
                except Refused:
                    pass
                return f"Offered to {self.owner} to keep for everyone: {offered.text}"
            words = text.split()[1:]
            verb, rest = (words[0].lower(), " ".join(words[1:])) if words else ("", "")
            if not verb:
                return household.listing(self.household, owner=owner)
            if not owner:
                return f"Only {self.owner or 'the owner'} changes what everyone knows."
            if verb in ("forget", "remove", "delete"):
                gone = self.household.forget(rest)
                return f"Forgotten for everyone: {gone.text}"
            if verb in ("yes", "keep", "no", "not"):
                taken = self.household.take(rest, keep=verb in ("yes", "keep"))
                return (f"Kept for everyone's agents: {taken.text}"
                        if verb in ("yes", "keep") else f"Not kept: {taken.text}")
            return ("Send /household to see it, /household forget N, "
                    "/household yes N or /household no N.")
        except HouseholdProblem as exc:
            return str(exc)[:1].upper() + str(exc)[1:] + "."

    async def _memory_words(self, spec: AgentSpec, who: Actor, key: str, text: str) -> str:
        """``/memory``, ``/memory forget ID``, ``/remember …`` (remembering.py)."""
        from yantra.memory import MemoryStoreError, short_id
        from yantra.memory.reflect import Candidate, keep

        name = workspace_parts(key)[1]
        if spec.memory in (None, "off"):
            return remembering.NOTHING_HERE.format(agent=name)
        word, rest = remembering.word_of(text), remembering.rest_of(text)
        offers = self.offered.get(who.id)
        picked: list[int] = []
        if word == "/remember":
            if not rest and offers:
                return remembering.listing(offers, head="I noticed this about you:")
            decline, rest = remembering.declining(rest)
            pick = remembering.chosen(rest, len(offers))
            if isinstance(pick, str):
                return pick
            if decline:          # no store and no model: only the list changes
                gone = self.offered.take(who.id, pick, decline=True)
                return remembering.declined_words([o.statement for o in gone])
            picked = pick
        forget = None
        if word == "/memory" and rest:
            verb, _, target = rest.partition(" ")
            if verb.lower() not in ("forget", "remove", "delete") or not target.strip():
                return "Send /memory to see what I remember, or /memory forget ID."
            forget = target.strip()
        async with self._remembered(spec, who, key) as agent:
            if agent is None:
                return remembering.NO_STORE
            memory = agent.memory
            try:
                if picked:
                    chosen = [offers[n - 1] for n in picked]
                    await asyncio.to_thread(
                        keep, memory, [Candidate(o.statement, o.kind) for o in chosen])
                    self.offered.take(who.id, picked)
                    return remembering.kept_words([o.statement for o in chosen])
                if forget is not None:
                    if "forget" in memory.cannot():
                        return "Where your memories are kept, I can't remove one from here."
                    gone = await asyncio.to_thread(memory.forget, forget)
                    return (f"Forgot #{forget.lstrip('#')}." if gone else
                            f"There's no memory #{forget.lstrip('#')}. Send /memory to see them.")
                if "list" in memory.cannot():
                    return "Where your memories are kept, I can't list them from here."
                items = await asyncio.to_thread(memory.list, 100)
                return remembering.memory_list(items, short_id)
            except MemoryStoreError as exc:
                return f"That didn't work: {exc}"
            except Exception as exc:  # noqa: BLE001 -- a store down is a sentence
                self._note(f"dvara: {who.id}: {word} failed -- {type(exc).__name__}: {exc}")
                return "I couldn't reach where your memories are kept just now. Try again soon."

    # ---- chores: what happens with nobody writing ----------------------------

    async def chores(self, *, tick: float = 60.0) -> None:
        """Runs beside the channels for as long as the service is up: a
        look back over each conversation gone quiet (``look_back_quiet``)
        every ``tick``, and every sign-in checked once a day
        (``check_sign_ins``). A chore that fails is a line for the owner;
        the loop goes on."""
        loop = asyncio.get_running_loop()
        # the first check a few minutes in, not at every restart's first second
        checked = loop.time() - max(0.0, self.check_every - FIRST_CHECK_AFTER)
        # once, as it starts: the jobs the last restart stopped part way
        await self._chore(self.tell_stopped)
        while True:
            await self._chore(self.look_back_quiet)
            if self.check_every and loop.time() - checked >= self.check_every:
                checked = loop.time()
                await self._chore(self.check_sign_ins)
            await asyncio.sleep(tick)

    async def _chore(self, job: Callable[[], Awaitable[int]]) -> None:
        try:
            await job()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 -- the next tick tries again
            self._note(f"dvara: {job.__name__} failed -- {type(exc).__name__}: {exc}")

    async def look_back_quiet(self, now: datetime | None = None) -> int:
        """A look back over every conversation nobody has written in for
        ``quiet_for`` (30 minutes by default), as ``/new`` does but keeping
        the conversation: a chat on Telegram is never ended by anybody, so
        waiting for ``/new`` kept nothing. What it noticed is sent to the
        person as a notice, numbered for ``/remember``. Conversations
        quiet for more than a day are left alone (a service started for
        the first time does not look back over its past). Returns how
        many were looked back over."""
        if not self.quiet_for:
            return 0
        now = now or datetime.now(UTC)
        quiet = self.runs.gone_quiet(now - timedelta(seconds=self.quiet_for),
                                     now - timedelta(days=1))
        done = 0
        for actor, agent, thread, ended in quiet:
            key = session_key(actor, agent, thread)
            if self._looked.get(key) == ended or key in self._locks:
                continue
            self._looked[key] = ended
            try:
                who = self.actors.get(actor)
                spec = self.roster.spec(agent)
            except (Refused, ConfigProblem, KeyError):
                continue
            if self.sessions.load_latest(key) is None:
                continue                     # /new already let it go
            async with self._locks.hold(key):
                said = await self._look_back(spec, who, key, thread=thread,
                                             text="(quiet for a while: looked back)",
                                             came_by="dvara", started=now, quiet=True)
            done += 1
            if said:
                try:
                    await self.notify(text=f"{agent}: {said}", actor=actor)
                except Refused:
                    pass
        return done

    async def check_sign_ins(self) -> int:
        """Every Setu folder this service reads, checked now (signins.py);
        each refusal not told before told to whoever can fix it. Returns
        how many were told."""
        program = self.accounts._program()
        if program is None:
            return 0
        folders: dict[Path, list[Actor]] = {}
        for actor_id in self.actors.ids():
            who = self.actors.get(actor_id)
            if who.setu is None:
                continue
            home = (self.state / "setu" / who.id if who.setu == OWN_SETU
                    else Path(who.setu).expanduser())
            if home.is_dir():
                folders.setdefault(home.resolve(), []).append(who)
        told = 0
        for home, people in folders.items():
            try:
                found = await signins.check(program, home)
            except RuntimeError as exc:
                self._note(f"dvara: could not check the sign-ins in {home} -- {exc}")
                continue
            for gone in self.signins_told.news(home, found):
                fixers = [p for p in people if p.manages_setu]
                if not fixers:
                    self._note(f"dvara: {signins.message(gone, from_chat=False)} "
                               f"(folder {home}, used by {', '.join(p.id for p in people)})")
                for who in fixers:
                    try:
                        await self.notify(text=signins.message(gone, from_chat=True),
                                          actor=who.id)
                        told += 1
                    except Refused:
                        pass
        return told

    def _tidy_quietly(self) -> None:
        """``tidy`` after an unattended turn, which is when there is more
        to tidy. A failure is the owner's to read, never the turn's."""
        try:
            self.tidy()
        except Exception as exc:  # noqa: BLE001 -- the reply still goes out
            self._note(f"dvara: could not tidy finished scheduled runs: "
                       f"{type(exc).__name__}: {exc}")

    def _workspace(self, key: str) -> Path:
        """Where this person's agent may write: one folder per person per
        agent, whichever conversation the turn is in.

        NOT the package directory. An agent that edits the folder you
        review and commit is an agent whose package stops being
        reviewable, which is the one property the whole format exists to
        have. The key's components are already percent-escaped, so a
        name somebody else chose cannot climb out of here.

        THE PERSON'S, NOT THE CONVERSATION'S. Conversations keep separate
        histories and share files, as sessions do on a desktop. A person
        on their phone sees a file only by asking the agent, in their
        chat; a scheduled run starts a conversation of its own every
        time. So the log a schedule keeps has to be in the folder the chat
        works in, or nobody but the owner could ever read it.
        """
        actor, agent, _ = workspace_parts(key)
        work = self.state / "work" / actor / agent
        work.mkdir(parents=True, exist_ok=True)
        return work

    def _steps_words(self, key: str, text: str) -> str:
        from yantra import steps
        payload = self.sessions.load_latest(key)
        if payload is None:
            return "Nothing here yet: ask me something first."
        asked = text.split()[1:2]
        try:
            view = steps.timeline(payload, int(asked[0]) if asked and asked[0].isdigit()
                                  else None)
        except LookupError as exc:
            return str(exc)
        return steps.text(view)

    def run_steps(self, run_id: str) -> dict:
        """One run, step by step, whole (runsteps.py): for the door's own
        callers. NoSteps when there is no such run or nothing left of it."""
        from dvara import runsteps
        return runsteps.timeline(self.sessions, self.runs.get(run_id))

    def _stopped(self, key: str) -> dict | None:
        """The job a restart stopped part way in this conversation, if
        its newest checkpoint is one (Yantra's carry.py)."""
        payload = self.sessions.load_latest(key)
        return (payload or {}).get("unfinished") or None

    async def tell_stopped(self) -> int:
        """As the service starts: each person with a job a restart stopped
        part way is told what and how far, once, and that ``/carry``
        carries it on (carrying.py). A schedule's or a watch's run is
        Samay's or Prahari's to carry on. Returns how many were told."""
        told = carrying.Told(self.state / "carry-told.json")
        sent = 0
        for key, info in self.sessions.unfinished():
            try:
                actor, agent, thread = parse_key(key)
            except ValueError:
                continue
            if not carrying.is_peoples(thread) or told.already(key, info):
                continue
            try:
                await self.notify(actor=actor, text=carrying.stopped_words(agent, info))
            except Refused:
                continue          # no longer on the roster
            told.mark(key, info)
            sent += 1
        return sent

    def _rehydrate(self, agent, key: str) -> None:
        """Restore the conversation; keep the identity we just built.

        ``history_only`` is the framework's word for this distinction, and
        it did not exist when this service was first written: the code
        here captured the three identity fields, let ``apply_payload``
        overwrite them, and put them back. That worked, and it meant
        dvara had to know WHICH fields a checkpoint carries -- so the day
        a fourth one was added, this would have silently started
        restoring it. Naming the half you want is the version that
        survives the format growing.
        """
        payload = self.sessions.load_latest(key)
        if payload is not None:
            apply_payload(agent, payload, history_only=True)


# ---- small pure helpers ----------------------------------------------------


def phone_for(who: Actor, asked: bool | str) -> tuple[str, ...]:
    """Which of ``who``'s phones a scheduled run works: the one it names,
    or their only one; () when they have every phone (``phone = true``)
    and it names none. Refused, in a sentence for its logbook, when it
    names a phone that isn't theirs -- or names none and they have
    several: a run that guessed would tap on the wrong one's apps."""
    if isinstance(asked, str) and asked:
        if who.phones and asked not in who.phones:
            raise Refused(f"the phone {asked!r} isn't one of {who.id}'s "
                          f"({', '.join(who.phones)})")
        return (asked,)
    if len(who.phones) == 1:
        return who.phones
    if who.phones:
        raise Refused(f"this schedule doesn't say which phone, and {who.id} has "
                      f"{len(who.phones)} ({', '.join(who.phones)}): make it again "
                      f"naming one")
    return ()


def works_phone(spec: AgentSpec) -> bool:
    """Whether this package lets Sparsh's tools in. A package's allow list
    is complete (Yantra's admit_only): one that leaves out
    ``mcp__sparsh__*`` hides every phone tool however the service was
    started. Its turns then get no phone -- not a server and a prompt
    about tools the model can't call, which on a real schedule had the
    agent call one, read "no such tool", and tell its person the phone
    wasn't connected, after they had unlocked it to let the run in."""
    from yantra.tools.base import ToolRegistry

    tools = ToolRegistry()
    tools.admit_only(spec.tool_allow, spec.tool_deny)
    return tools.admits("mcp__sparsh__look")


def reads_phone(spec: AgentSpec) -> bool:
    """Whether this package lets in ``phone_status`` -- the battery and the
    missed calls, read without the screen. One that admits that and not
    the screen's tools (a morning brief) gets the phone on every run, a
    schedule's too: nothing it can call waits for the phone to be free or
    asks for it to be unlocked, which is what a phone job is for."""
    from yantra.tools.base import ToolRegistry

    tools = ToolRegistry()
    tools.admit_only(spec.tool_allow, spec.tool_deny)
    return tools.admits("mcp__sparsh__phone_status")


def _copy(usage: Usage) -> Usage:
    return Usage(usage.input_tokens, usage.output_tokens,
                 usage.cache_read_tokens, usage.cache_write_tokens)


def _delta(before: Usage, after: Usage) -> Usage:
    """This TURN's tokens, not the session's.

    ``agent.total_usage`` is cumulative and a rehydrated agent starts a
    turn already carrying last week's numbers. Billing the difference is
    what keeps a Run row about the turn it describes.
    """
    return Usage(
        input_tokens=after.input_tokens - before.input_tokens,
        output_tokens=after.output_tokens - before.output_tokens,
        cache_read_tokens=after.cache_read_tokens - before.cache_read_tokens,
        cache_write_tokens=after.cache_write_tokens - before.cache_write_tokens,
    )


def _cost(before: dict[str, Usage], after: dict[str, Usage], *,
          provider_name: str) -> float | None:
    """Dollars for this turn, or None when any of it cannot be priced.

    Per MODEL, because one turn can span two of them (a sub-agent on a
    cheaper slug is the obvious case) and a single rate would be a guess.
    ``session_cost`` reports whether it managed to price everything; when
    it did not, this returns None rather than a total that quietly
    understates -- the same refusal to guess that ``price_for`` makes.

    A MISSING PRICE MEANS TWO OPPOSITE THINGS, which is why the provider
    is an argument here. On a local server there is nothing to pay and
    $0.00 is the true answer; on a hosted one the same silence means
    nobody knows, and writing zero into a row an owner will later sum is
    how a bill becomes a surprise.
    """
    buckets = {}
    for model, usage in after.items():
        buckets[model] = _delta(before.get(model, Usage()), usage)
    live = {m: u for m, u in buckets.items()
            if u.input_tokens or u.output_tokens
            or u.cache_read_tokens or u.cache_write_tokens}
    if not live:
        return 0.0
    dollars, fully_priced = session_cost(live)
    if fully_priced:
        return dollars
    return 0.0 if bills_nothing(provider_name) else None


def _explain(reason: str, detail: str | None, ceiling: money.Ceiling) -> str:
    """A sentence for a turn that produced no words of its own.

    "over_budget" is not an answer to a person; it is a log line. Whose
    ceiling stopped them, and when it comes back, is.
    """
    if reason == "over_budget":
        whose = {
            "today": (f"your daily allowance ran out mid-answer; it comes "
                      f"back at {money.next_reset():%H:%M UTC on %-d %b}"),
            "actor": "you reached the spending limit set for you",
            "package": "this agent reached the cost ceiling its author set",
        }.get(ceiling.whose or "", "the cost ceiling was reached")
        return f"{whose}. {detail}" if detail else whose
    if reason == "max_iterations":
        return "I worked as long as I am allowed to and did not finish that one"
    if reason == "cancelled":
        return "that was interrupted"
    return detail or "I have no answer for that"


def _refused(lapsed: Sequence[str], steps) -> tuple[str, ...]:
    """What a scheduled run's report says was refused: each question that
    lapsed, in its own words (``tool: what it would have done``), then the
    tools refused outright -- a tool named in a lapse is not named again."""
    named = {line.split(": ", 1)[0] for line in lapsed}
    return tuple(dict.fromkeys([*lapsed, *(
        step.name for step in steps
        if step.refusal not in (None, HELD) and step.name not in named)]))

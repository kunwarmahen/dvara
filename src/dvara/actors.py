"""Actors: who is allowed to talk to what, and what they may spend.

Yantra's entire world is "the operator" -- the person at the keyboard,
present, trusted and singular. None of those three survive a service, and
this module is where the missing noun gets defined.

AN ACTOR IS ASSIGNED, NEVER ASSERTED. Nothing that arrives from outside
gets to say who it is. A channel adapter maps its own native identity (a
Telegram user id, say) onto an actor id from a file the owner wrote, and
an id that is not in that file is not served. The whole security model of
a personal service rests on that sentence, so the file is deliberately
boring: TOML, reviewable, diffable, and it holds no secrets.

    [actor.mahen]
    agents           = ["researcher"]   # omit => every agent in the roster
    max_usd_per_turn = 0.25
    max_usd_per_day  = 2.00
    max_wait_per_day = 300              # seconds kept waiting on them, a day
    permissions      = "ask"            # this person may be asked to approve

``agents`` follows ``AgentSpec.tool_allow``'s convention exactly: absent
means everything, a list is a COMPLETE whitelist, and an empty list is an
error rather than a silent "this person may reach nothing" -- because an
empty allowlist is far likelier to be a bug than an intention.

``permissions`` is a rung on the ladder in ``gate.py``, and it can only
ever TIGHTEN: the mode a turn runs under is the minimum of the package's,
the owner's and this one, so writing ``"yolo"`` beside a guest's name
grants them nothing. What it is actually for is the other direction --
``"read_only"`` beside somebody the owner serves but would not want woken
up to approve a shell command, on a service where the owner themselves is
asked. Absent means the tightest rung, which is what a person who was
never considered should get.

## One person, several channels

    [[actor.mahen.channel]]
    kind = "telegram"
    id   = 8675309

A PERSON IS ONE ACTOR, ON HOWEVER MANY CHANNELS. Before this table
existed the mapping from a channel's native identity onto an actor lived
in the adapter, and the honest consequence was that the same person
reachable two ways was two actors -- which is three separate things, not
one: two queues of pending questions, two agent whitelists to keep in
step, and TWO DAILY ALLOWANCES out of one number the owner wrote once.
The last of those is the argument. A ceiling that doubles when somebody
installs a bot is not a ceiling.

So the mapping moves here, where the rest of the assignment already is.
The file the owner reviews is now the whole answer to "who does this
service serve, and where can I reach them", rather than half of it with
the other half in a bot's environment.

**dvara learns that channels exist; it never learns which ones.** ``kind``
is an opaque token this module checks the SHAPE of and nothing else -- no
list of known channels, no branch anywhere on the string "telegram". A
second channel is an adapter and three lines of TOML, not a patch to this
file. ``id`` is likewise opaque: whatever that channel calls the person,
in whatever way makes the adapter's own lookup work. (It is written as a
number above because Telegram writes user ids as numbers everywhere it
documents them, and an owner copying one in should not have to know that
this file wanted a string. Integers are accepted and stored as text; the
comparison is always textual.)

A ``(kind, id)`` pair BELONGS TO AT MOST ONE ACTOR, checked at load
across the whole file. Two actors claiming one Telegram id has no correct
resolution -- first-wins would hand one person another person's history
because of the order two tables happen to appear in -- so it is an error
naming both, the same shape of failure ``keys.py`` escapes its components
to prevent.

The table reads in both directions, which is why it is one table and not
two. Inbound, an adapter turns its native id into an actor and asserts
nothing. Outbound, a question put to that actor is delivered to every
channel they are reachable on -- see ``AskDesk.route``.

## What follows the answer

    receipt = "cost"        # $0.0031
    receipt = "remaining"   # $0.08 left today

TWO READERS WANT TWO DIFFERENT NUMBERS, WHICH IS WHY THIS IS NOT A FLAG.
The owner is watching a bill and wants what the turn COST. A person on an
allowance is deciding whether to ask the follow-up now, and the figure
they act on is what is LEFT -- "$0.43 spent" is a number they would then
have to do arithmetic on, which is Yantra's note 43 arriving here through
a different door. A single boolean can offer one of those two and never
the other, and the one it would offer is the one a guest cannot use.

Absent is the default and means silence. Most people in a chat did not
ask to be shown a meter, and a footer under every answer is a line
everybody reads forever.

``"remaining"`` on somebody with no ``max_usd_per_day`` is a contradiction
rather than a quiet no-op: there is no allowance to have anything left
of, and the owner who wrote it meant something they have not said.

## Read again when it changes

A book remembers the file it came from and that file's stamp, so a
service can notice an edit without being restarted. It was a papercut
while the only way in was a terminal; it became a real one the day a
guest could be handed a bot's @handle at a party and the answer was
"hold on, I have to restart the service".

WHAT IS HERE IS THE PARSE, AND NOTHING ELSE. ``reread`` returns a new
book or raises, and does not decide what to do about a file that has
stopped parsing -- that is policy, it belongs to the host, and
``service.py`` answers it by keeping the last good roster and saying so.
A parser that swallowed the error would be a parser that silently decided
a thing nobody asked it to decide.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dvara.errors import ConfigProblem, Refused
from dvara.gate import LADDER

#: Keys an actor table may carry. UNKNOWN KEYS ARE ERRORS: a misspelled
#: ``max_usd_per_day`` that quietly means "no ceiling" is the exact
#: failure a ceiling exists to prevent (the same rule Yantra's package
#: loader applies to ``agent.toml``).
ACTOR_KEYS = frozenset({"agents", "max_usd_per_turn", "max_usd_per_day",
                        "max_wait_per_day", "permissions", "channel",
                        "receipt"})

#: What may follow an answer, under it, for this person. Absent is the
#: third option and the default, because most people in a chat did not
#: ask to be shown a meter.
RECEIPTS = ("cost", "remaining")

#: Keys one ``[[actor.NAME.channel]]`` entry may carry. Both required:
#: a channel with no kind cannot be routed and one with no id names
#: nobody, and either mistake is silent at the moment it matters.
CHANNEL_KEYS = frozenset({"kind", "id"})

#: What a channel kind may look like. The same token rule Yantra applies
#: to refusal codes, for the same reason: this string ends up a dict key,
#: a log field and a column, and one with a space or a slash in it is
#: quoted forever afterwards by everybody who touches it.
_KIND = re.compile(r"[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True)
class Channel:
    """Where one person is reachable, in one channel's own terms.

    Two jobs in one pair, which is the reason it is one record rather
    than an inbound map and an outbound map that can disagree. INBOUND,
    an adapter hands ``(kind, id)`` over and gets back the actor the
    owner assigned -- so the adapter asserts nothing and a native id
    absent from the file is simply not served. OUTBOUND, ``id`` is the
    address a question is delivered to on that channel.

    Both directions want the same string in every channel worth having,
    because a channel that cannot send you a message at the identity it
    received one from is not a channel a person can be asked on. (In
    Telegram's private chats the user id and the chat id are the same
    number, which is the case this was drawn from.)
    """

    kind: str
    id: str


@dataclass(frozen=True)
class Actor:
    """One person the owner has decided to serve."""

    id: str
    #: None means every agent in the roster; a tuple is a complete whitelist.
    agents: tuple[str, ...] | None = None
    max_usd_per_turn: float | None = None
    max_usd_per_day: float | None = None
    #: Seconds a day this person may be kept waiting on questions
    #: (patience.py). None means no limit.
    max_wait_per_day: float | None = None
    #: A rung on gate.py's ladder, or None for the tightest one. Composes
    #: by minimum with the package's mode and the owner's policy, so it
    #: can only ever make a turn stricter.
    permissions: str | None = None
    #: Every channel this person is reachable on. Empty is ordinary: an
    #: actor named straight off the roster by the CLI or a trusted HTTP
    #: caller needs no channel identity at all.
    channels: tuple[Channel, ...] = ()
    #: What follows this person's answers: "cost", "remaining", or None
    #: for nothing at all. See the module docstring on why it is not a
    #: boolean.
    receipt: str | None = None

    def may_use(self, agent: str) -> bool:
        return self.agents is None or agent in self.agents

    def reach(self) -> tuple[tuple[str, str], ...]:
        """``(kind, address)`` pairs, for a desk deciding where to ask.

        Plain tuples rather than ``Channel`` objects because the desk
        must not import this module -- ``actors`` imports ``gate``
        imports ``asks``, and a desk that knew what an actor was would
        close that ring. What it needs is an address and a word for which
        notifier can deliver to it, and that is two strings.
        """
        return tuple((c.kind, c.id) for c in self.channels)


class ActorBook:
    """The owner's roster of people, loaded from one TOML file."""

    def __init__(self, actors: dict[str, Actor],
                 *, where: Path | str = "<memory>",
                 source: Path | None = None) -> None:
        self._actors = dict(actors)
        #: The file this came from, when it came from one, and that file's
        #: stamp at the moment it was read. Both None for a book built in
        #: memory -- which is the CLI's tests and an embedder, and neither
        #: of those has a file to notice a change in.
        self.source = source
        self.stamp = _stamp(source)
        # The table read backwards, built once. A channel adapter asks
        # this question on every inbound message, and a scan over every
        # actor's channels per message is a linear search nobody needs.
        self._by_channel: dict[tuple[str, str], str] = {}
        for actor in self._actors.values():
            for channel in actor.channels:
                claimed = self._by_channel.setdefault(
                    (channel.kind, channel.id), actor.id)
                if claimed != actor.id:
                    raise ConfigProblem(
                        f"{where}: {channel.kind} id {channel.id!r} is "
                        f"claimed by "
                        f"both [actor.{claimed}] and [actor.{actor.id}]; "
                        f"one channel identity is one person, and there "
                        f"is no right way to guess which")

    def __len__(self) -> int:
        return len(self._actors)

    def ids(self) -> list[str]:
        return sorted(self._actors)

    def get(self, actor_id: str) -> Actor:
        """The actor, or a refusal.

        The refusal says nothing about who else exists. A stranger probing
        a bot learns only that they are not on the list.
        """
        try:
            return self._actors[actor_id]
        except KeyError:
            raise Refused("you are not on this service's list of people") from None

    def resolve(self, kind: str, native_id: str | int) -> Actor:
        """The actor an adapter's own identity belongs to, or a refusal.

        THE ADAPTER BRINGS A NATIVE ID AND GETS BACK A NAME; IT NEVER
        BRINGS A NAME. That is the whole of "assigned, never asserted"
        expressed as a function signature -- there is no argument here
        through which a message could nominate who it is.

        The refusal is the same sentence a stranger gets for an unknown
        actor id, and deliberately so: a person probing a bot with
        somebody else's user id learns nothing about who is on the list.
        """
        try:
            return self._actors[self._by_channel[(kind, str(native_id))]]
        except KeyError:
            raise Refused(
                "you are not on this service's list of people") from None

    def may(self, actor_id: str, agent: str) -> Actor:
        """The actor, having checked they may reach ``agent``."""
        actor = self.get(actor_id)
        if not actor.may_use(agent):
            raise Refused(f"you do not have access to the agent {agent!r}")
        return actor

    @classmethod
    def from_toml(cls, path: Path) -> ActorBook:
        """Parse the owner's file, complaining loudly about every mistake."""
        path = Path(path).expanduser()
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ConfigProblem(f"no actors file at {path}") from None
        except tomllib.TOMLDecodeError as exc:
            raise ConfigProblem(f"{path}: {exc}") from None
        return cls.from_dict(raw, where=path, source=path)

    @classmethod
    def from_dict(cls, raw: dict, *, where: Path | str = "<memory>",
                  source: Path | None = None) -> ActorBook:
        table = raw.get("actor")
        if not isinstance(table, dict) or not table:
            raise ConfigProblem(
                f"{where}: no [actor.NAME] tables -- a service with no "
                f"actors can serve nobody"
            )
        actors = {}
        for name, body in table.items():
            if not isinstance(body, dict):
                raise ConfigProblem(f"{where}: [actor.{name}] must be a table")
            unknown = sorted(set(body) - ACTOR_KEYS)
            if unknown:
                raise ConfigProblem(
                    f"{where}: [actor.{name}] has unknown key(s) "
                    f"{', '.join(unknown)}; known: "
                    f"{', '.join(sorted(ACTOR_KEYS))}"
                )
            actors[name] = Actor(
                id=name,
                agents=_agents(body.get("agents"), name, where),
                max_usd_per_turn=_money(body, "max_usd_per_turn", name, where),
                max_usd_per_day=_money(body, "max_usd_per_day", name, where),
                max_wait_per_day=_seconds(body, "max_wait_per_day", name,
                                          where),
                permissions=_mode(body.get("permissions"), name, where),
                channels=_channels(body.get("channel"), name, where),
                receipt=_receipt(body, name, where),
            )
        # Checked in __init__ rather than here, because the reverse index
        # is what makes the claim, and an ActorBook built any other way
        # has to be as trustworthy as one parsed from a file.
        return cls(actors, where=where, source=source)

    # ---- reading it again --------------------------------------------------

    def changed(self) -> bool:
        """Whether the file this was read from has been touched since.

        Mtime AND size, because a file edited twice inside one filesystem
        timestamp tick is a real thing on a coarse clock and an owner
        adding a guest at a party will not forgive it. Neither is a
        content hash, which is the honest version of this and costs a read
        of the whole file on every turn to catch a case -- an edit that
        changes nothing -- where the reload is a no-op anyway.
        """
        return self.source is not None and _stamp(self.source) != self.stamp

    def reread(self) -> ActorBook:
        """The file as it is now, or a ``ConfigProblem`` saying why not.

        Deliberately just the parse. Whether a service that cannot read
        its new roster should stop or should carry on with the last good
        one is a POLICY question, and policy belongs to whoever owns the
        conversation rather than to the parser (service.py decides, and
        decides to carry on).
        """
        if self.source is None:
            return self
        return ActorBook.from_toml(self.source)


def _stamp(path: Path | None) -> tuple | None:
    """A file's (mtime, size), or None when there is nothing to stamp.

    A file that has been DELETED stamps as None, which is different from
    the tuple it had a moment ago -- so it reads as a change, the reread
    raises, and the host says so and keeps the roster it has. That is the
    wanted behaviour and not an accident: some editors save by truncating
    and rewriting, so a file that is briefly empty or briefly gone is a
    thing an owner does by accident, and the one response that is correct
    for both the accident and the deliberate deletion is to carry on with
    what is already loaded and tell somebody.
    """
    if path is None:
        return None
    try:
        info = path.expanduser().stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def _agents(value, name: str, where) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigProblem(f"{where}: [actor.{name}] agents must be a list of names")
    if not value:
        raise ConfigProblem(
            f"{where}: [actor.{name}] agents is present but empty, which "
            f"would leave this person no agents at all; omit the key to "
            f"allow every agent in the roster"
        )
    return tuple(value)


def _receipt(body: dict, name: str, where) -> str | None:
    """What follows this person's answers, or a loud complaint.

    The cross-check is the point of doing this here rather than in a
    one-line coercion: ``"remaining"`` names a fraction of an allowance,
    and an actor with neither ``max_usd_per_day`` nor
    ``max_wait_per_day`` (notes/15) has no allowance for anything to
    remain of. Rendering nothing would be a key that silently
    does not work; rendering the turn's cost instead would be answering a
    question nobody asked.
    """
    value = body.get("receipt")
    if value is None:
        return None
    if not isinstance(value, str) or value not in RECEIPTS:
        raise ConfigProblem(
            f"{where}: [actor.{name}] receipt must be one of "
            f"{', '.join(RECEIPTS)} (got {value!r}); omit the key for "
            f"nothing under the answer, which is the default")
    if (value == "remaining" and body.get("max_usd_per_day") is None
            and body.get("max_wait_per_day") is None):
        raise ConfigProblem(
            f"{where}: [actor.{name}] asks for what is left of a daily "
            f"allowance and has no max_usd_per_day or max_wait_per_day to "
            f"have anything left of; set one, or use receipt = \"cost\"")
    return value


def _channels(value, name: str, where) -> tuple[Channel, ...]:
    """The person's addresses, or a loud complaint about one of them.

    Strict about SHAPE and silent about MEANING. Every check here would
    hold for a channel invented next year, because none of them knows
    what any channel is called -- the moment this function grows a list
    of known kinds is the moment adding a channel means editing dvara.
    """
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ConfigProblem(
            f"{where}: [actor.{name}] channel must be written as "
            f"[[actor.{name}.channel]] tables, one per place this person "
            f"can be reached")
    channels = []
    for entry in value:
        unknown = sorted(set(entry) - CHANNEL_KEYS)
        if unknown:
            raise ConfigProblem(
                f"{where}: [[actor.{name}.channel]] has unknown key(s) "
                f"{', '.join(unknown)}; known: "
                f"{', '.join(sorted(CHANNEL_KEYS))}")
        kind = entry.get("kind")
        if not isinstance(kind, str) or not _KIND.match(kind):
            raise ConfigProblem(
                f"{where}: [[actor.{name}.channel]] kind must be a short "
                f"lower-case token naming the channel -- letters, digits "
                f"and underscores (got {kind!r})")
        native = entry.get("id")
        # An integer is the expected mistake rather than a mistake at
        # all: Telegram prints user ids as bare numbers in everything it
        # publishes, and an owner pasting one in should not have to know
        # this file wanted quotes. Stored as text, compared as text, so
        # 8675309 and "8675309" are the same person either way.
        if isinstance(native, bool) or not isinstance(native, str | int):
            raise ConfigProblem(
                f"{where}: [[actor.{name}.channel]] id must be the string "
                f"or number {kind} knows this person by (got {native!r})")
        native = str(native).strip()
        if not native:
            raise ConfigProblem(
                f"{where}: [[actor.{name}.channel]] id is empty; a channel "
                f"entry with no id reaches nobody and matches nobody")
        channels.append(Channel(kind=kind, id=native))
    for i, channel in enumerate(channels):
        if channel in channels[:i]:
            raise ConfigProblem(
                f"{where}: [actor.{name}] lists {channel.kind} id "
                f"{channel.id!r} twice; a question would be delivered to "
                f"them once per line")
    return tuple(channels)


def _mode(value, name: str, where) -> str | None:
    """A rung, or a loud complaint.

    Unknown modes read as the tightest at RUNTIME, which is the right
    failure for a package somebody else wrote. In the owner's own file it
    is the wrong one: a typo that silently means "this person may approve
    nothing" is a support question, not a safety property, and the owner
    is standing right here to be told.
    """
    if value is None:
        return None
    if not isinstance(value, str) or value not in LADDER:
        raise ConfigProblem(
            f"{where}: [actor.{name}] permissions must be one of "
            f"{', '.join(LADDER)} (got {value!r})")
    return value


def _seconds(body: dict, key: str, name: str, where) -> float | None:
    """A positive number of seconds, or None. Zero is refused for money's
    reason: an allowance of nothing is "never ask this person", which is
    said with ``permissions = "read_only"``, where it is legible."""
    value = body.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigProblem(
            f"{where}: [actor.{name}] {key} must be a number of seconds")
    if value <= 0:
        raise ConfigProblem(
            f"{where}: [actor.{name}] {key} must be greater than zero "
            f"(got {value}); to never ask this person, give them "
            f'permissions = "read_only"')
    return float(value)


def _money(body: dict, key: str, name: str, where) -> float | None:
    value = body.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigProblem(f"{where}: [actor.{name}] {key} must be a number")
    if value <= 0:
        raise ConfigProblem(
            f"{where}: [actor.{name}] {key} must be greater than zero "
            f"(got {value}); a ceiling of nothing is a refusal to serve "
            f"this person, which is done by leaving them out of the file"
        )
    return float(value)

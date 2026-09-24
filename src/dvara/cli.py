"""The operator's side of the door.

Yantra's CLI is flags all the way down, and for one interactive session
that is right: there is one thing to do and the flags describe how. A
service genuinely has modes -- serve it, talk to it, ask what it holds --
so this one has subcommands, and the two CLIs are different shapes
because they answer different questions.

``dvara say`` exists for a reason worth stating: it drives the service
DIRECTLY, in process, with no HTTP and no channel. It is how you rehearse
a package against a local model before any bot token exists, and it is
how the receipts in the notes were produced.

    dvara agents --root ~/agents
    dvara say --actor mahen --agent researcher "what changed today?"
    dvara runs --actor mahen
    dvara serve --host 127.0.0.1 --port 8765
    dvara telegram --agent researcher

``--ask`` is where a front end becomes a channel. The escalating gate
needs somewhere to put a question and somewhere an answer can land, and
which of those two a front end supplies is the only thing that differs
between them: at a keyboard the question is printed and the answer is a
keystroke, so ``say`` supplies both halves; ``telegram`` sends the
question with two buttons on it and the press comes back through the poll
it never stopped running; a served process supplies neither, because the
answer is going to arrive over HTTP from an adapter that is talking to
somebody elsewhere.

``telegram`` and ``serve`` are the two ways a person who is not at this
keyboard gets in, and they are not alternatives. The bot runs the service
IN THIS PROCESS and reaches the desk directly; the HTTP surface is for an
adapter that is somewhere else.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from yantra import render_case

from dvara import patience
from dvara.actors import ActorBook, Channel
from dvara.asks import DEFAULT_TIMEOUT, Ask, AskDesk
from dvara.cases import append, case_from_run, unasserted
from dvara.claim import Claim
from dvara.errors import ConfigProblem, Refused
from dvara.gate import Policy
from dvara.roster import Roster
from dvara.rules import RuleBook
from dvara.service import Service
from dvara.telegram import POLL_SECONDS, TelegramBot

DEFAULT_ROOT = "~/dvara/agents"
DEFAULT_ACTORS = "~/dvara/actors.toml"
DEFAULT_POLICY = "~/dvara/policy.toml"
DEFAULT_STATE = "~/dvara/state"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dvara",
        description="the door your agents live behind",
    )
    parser.add_argument("--root", default=os.environ.get("DVARA_ROOT", DEFAULT_ROOT),
                        help="the OWNER-CONTROLLED directory of agent packages. "
                             "Agents are named, never pathed: nothing a caller "
                             "sends can reach outside this directory")
    parser.add_argument("--actors", default=os.environ.get("DVARA_ACTORS",
                                                           DEFAULT_ACTORS),
                        help="TOML file of the people this service serves")
    parser.add_argument("--policy", default=os.environ.get("DVARA_POLICY", ""),
                        help=f"TOML file of standing allow/deny/ask rules, "
                             f"matched per tool call. Optional: with none, "
                             f"every call that could change something is "
                             f"decided by the rung alone (default "
                             f"{DEFAULT_POLICY} if it exists)")
    parser.add_argument("--state", default=os.environ.get("DVARA_STATE",
                                                          DEFAULT_STATE),
                        help="where sessions, run history and per-conversation "
                             "workspaces live")
    parser.add_argument("--provider", default=None,
                        help="override every package's provider (anthropic | "
                             "openai | responses | ollama)")
    parser.add_argument("--model", default=None,
                        help="override every package's model slug")
    parser.add_argument("--yolo", action="store_true",
                        help="let agents run every tool without asking. The "
                             "owner's half of the permission decision -- a "
                             "package that asks for yolo does not get it "
                             "unless this is set too")
    parser.add_argument("--ask", action="store_true",
                        help="escalate to a person instead of refusing. With "
                             "`say` the question is printed here and you "
                             "answer it; with `telegram` it arrives in their "
                             "chat with two buttons on it; with `serve` it "
                             "waits at GET /asks for whoever is talking to "
                             "that person")
    parser.add_argument("--ask-timeout", type=float, default=DEFAULT_TIMEOUT,
                        metavar="SECONDS",
                        help=f"how long a question waits before it is refused "
                             f"for silence (default {DEFAULT_TIMEOUT:g})")

    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("agents", help="list the agents this service can offer")

    say = subs.add_parser("say", help="run one turn, in process, no HTTP")
    say.add_argument("text", help="what to say to the agent")
    # An actor id, OR a channel identity the actors file maps onto one.
    # The second exists so an owner can prove a mapping works before
    # wiring a bot to it: a bot that answers nothing tells you nothing
    # about WHICH of the two halves is wrong.
    who = say.add_mutually_exclusive_group(required=True)
    who.add_argument("--actor")
    who.add_argument("--as", dest="as_channel", metavar="KIND:ID",
                     help="speak as a channel identity from actors.toml, "
                          "e.g. --as telegram:8675309")
    say.add_argument("--agent", required=True)
    say.add_argument("--thread", default="cli")

    runs = subs.add_parser("runs", help="what this service has been doing")
    runs.add_argument("--actor", default=None)
    runs.add_argument("--agent", default=None)
    runs.add_argument("--limit", type=int, default=20)

    case = subs.add_parser(
        "case", help="turn a recorded run into an eval case for its package")
    case.add_argument("run", help="a run id, or enough of one to be unique")
    case.add_argument("--because", default=None,
                      help="what was wrong with it. Required for a turn that "
                           "ended normally -- a wrong answer looks exactly "
                           "like a right one from out here")
    case.add_argument("--write", action="store_true",
                      help="append it to the package's evals/cases.toml "
                           "instead of printing it. You are editing a folder "
                           "you commit, so read it first")

    rules = subs.add_parser(
        "rules", help="your standing answers, and what each one has done")
    rules.add_argument("--days", type=int, default=30, metavar="N",
                       help="count over the last N days (default 30); 0 "
                            "counts everything ever recorded")

    telegram = subs.add_parser(
        "telegram", help="answer messages as a Telegram bot")
    telegram.add_argument(
        "--agent", required=True,
        help="the ONE agent this bot is. A bot token is an identity with a "
             "name and an @handle; a second agent is a second token and a "
             "second process, not a prefix on every message")
    telegram.add_argument(
        "--catch-up", action="store_true",
        help="answer the messages that arrived while this was down. Off by "
             "default: a day-old question answered now is a wrong answer, "
             "and a backlog of ten spends ten turns of somebody's allowance "
             "in one breath")
    telegram.add_argument(
        "--poll-seconds", type=int, default=POLL_SECONDS, metavar="SECONDS",
        help=f"how long each long poll holds the connection open "
             f"(default {POLL_SECONDS})")

    serve = subs.add_parser("serve", help="listen for channel adapters")
    serve.add_argument("--host", default="127.0.0.1",
                       help="localhost by default, deliberately: reaching the "
                            "network is a decision, not a default")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--telegram", metavar="AGENT", default=None,
        help="also run a Telegram bot for AGENT, in THIS process. Two "
             "dvaras cannot share a --state directory, so this is how you "
             "have a bot and an HTTP surface at once -- one ask desk, one "
             "set of conversation locks, one ledger")
    serve.add_argument("--catch-up", action="store_true",
                       help="with --telegram: answer the messages that "
                            "arrived while this was down")
    return parser


#: Commands that RUN A TURN, and therefore claim the state directory.
#: The read-only ones are absent on purpose -- see claim.py: looking at
#: your own ledger while the bot answers somebody is the most ordinary
#: thing an owner does.
CLAIMS = ("say", "serve", "telegram")


def _service(args) -> Service:
    desk = None
    if args.ask:
        try:
            desk = AskDesk(timeout=args.ask_timeout)
        except ValueError as exc:
            raise ConfigProblem(str(exc)) from None
    # NAMED IS REQUIRED, DEFAULT IS OPTIONAL. An owner who typed a path
    # and got silence would have a policy file that does nothing and no
    # way to tell; an owner who has never written one is not missing
    # anything.
    named = bool(args.policy)
    rules = RuleBook.from_toml(Path(args.policy or DEFAULT_POLICY),
                               required=named)
    return Service(
        roster=Roster(Path(args.root)),
        actors=ActorBook.from_toml(Path(args.actors)),
        state=Path(args.state),
        policy=Policy(mode="yolo" if args.yolo else "ask", rules=rules),
        asks=desk,
        provider_name=args.provider,
        model=args.model,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # THE COMMAND CLAIMS, NOT THE SERVICE. A `Service` an embedder built
    # inside their own process is not a second dvara (claim.py), and the
    # local below is what HOLDS the claim: it has to stay referenced for
    # as long as the command runs, because closing the file releases the
    # lock and CPython closes it the moment nothing points at it.
    claim = None
    try:
        if args.command in CLAIMS:
            claim = Claim(Path(args.state))
            claim.take(f"dvara {args.command}")
        if args.command == "serve":
            return _serve(args)
        service = _service(args)
    except ConfigProblem as exc:
        # The owner's own files are wrong. Loud, and never answered into
        # a channel -- this is the one human who can fix it.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if args.command == "serve" and claim is not None:
            claim.release()

    try:
        if args.command == "agents":
            return _agents(service)
        if args.command == "say":
            return _say(service, args)
        if args.command == "runs":
            return _runs(service, args)
        if args.command == "case":
            return _case(service, args)
        if args.command == "rules":
            return _rules(service, args)
        if args.command == "telegram":
            return _telegram(service, args)
    finally:
        service.close()
        if claim is not None:
            claim.release()
    return 2


def _agents(service: Service) -> int:
    names = service.roster.names()
    if not names:
        print(f"no agent packages in {service.roster.root}")
        return 1
    for name in names:
        spec = service.roster.spec(name)
        label = f"{name} {spec.version}" if spec.version else name
        print(f"{label:<28} {spec.description or ''}".rstrip())
    return 0


def _as_channel(spec: str | None) -> Channel | None:
    """``kind:id`` off the command line, or nothing.

    Split on the FIRST colon only: a channel kind is a token and cannot
    contain one, while plenty of channels name people with strings that
    can.
    """
    if spec is None:
        return None
    kind, sep, native = spec.partition(":")
    if not sep or not kind.strip() or not native.strip():
        raise ConfigProblem(
            f"--as wants KIND:ID, naming a channel identity from your "
            f"actors file (got {spec!r})")
    return Channel(kind=kind.strip(), id=native.strip())


async def _typed_line() -> str:
    """One line from stdin, ABANDONABLE when the question times out.

    ``asyncio.to_thread(input, ...)`` was the old answer and it had a cost
    recorded since note 02: a question that times out leaves a thread
    parked inside ``input()``, the default executor's threads are not
    daemons, and the interpreter joins them on the way out -- so the
    process sits there wanting a keypress nobody now has any reason to
    give it. The fix is not a bigger hammer on the thread; it is not
    using one.

    ``add_reader`` hands the descriptor to the event loop, which is what
    an event loop is for. Cancellation removes the reader and returns,
    leaving nothing behind at all. The tty is still in canonical mode, so
    it does the line editing and this gets a whole line on Enter, exactly
    as ``input`` did.

    Falls back to the thread wherever stdin cannot be watched -- a closed
    descriptor, a platform without ``add_reader`` -- because a front end
    that is the ONLY place a question could go must not stop asking.
    """
    loop = asyncio.get_running_loop()
    try:
        fileno = sys.stdin.fileno()
    except (OSError, ValueError):
        return await asyncio.to_thread(_blocking_line)
    answered: asyncio.Future[str] = loop.create_future()

    def readable() -> None:
        loop.remove_reader(fileno)
        if not answered.done():
            answered.set_result(_blocking_line())

    try:
        loop.add_reader(fileno, readable)
    except (NotImplementedError, OSError, ValueError):
        return await asyncio.to_thread(_blocking_line)
    try:
        return await answered
    finally:
        with contextlib.suppress(Exception):
            loop.remove_reader(fileno)


def _blocking_line() -> str:
    """One line, or "" at end of input. A closed pipe is not consent."""
    try:
        return sys.stdin.readline()
    except (EOFError, OSError, ValueError):
        return ""


def _ask_at_the_keyboard(desk: AskDesk):
    """Print the question, read the answer, hand it back to the desk.

    Never a blocking read on this loop: the turn that asked is suspended
    on it, and stopping it here would be exactly the failure the awaitable
    gate exists to avoid, reintroduced one layer up. And never a read that
    outlives the question -- see ``_typed_line``.

    ANYTHING THAT IS NOT YES IS NO. A stray newline, a closed pipe, a
    person who typed "maybe" -- none of those are consent, and the
    deadline is still running underneath in case nobody types at all.
    """
    async def notify(ask: Ask) -> None:
        print(f"\n{ask.agent} wants to run {ask.tool}:", file=sys.stderr)
        print(f"  {ask.summary}", file=sys.stderr)
        print("approve? [y/N] ", end="", file=sys.stderr, flush=True)
        typed = await _typed_line()
        # "terminal" is not a channel kind and never appears in
        # actors.toml -- it is where the answer came from, which is the
        # question the Run is recording. A person who approved something
        # at the keyboard was at the keyboard.
        desk.answer(ask.id, actor=ask.actor, via="terminal",
                    approve=typed.strip().lower() in ("y", "yes"))

    return notify


def _say(service: Service, args) -> int:
    if service.asks is not None:
        # The terminal is the channel. Attached here rather than in
        # `_service` because `serve` builds the same desk and must NOT
        # get this: there is nobody at that process's keyboard, and a
        # question printed to a log is a question nobody answers.
        service.asks.notify = _ask_at_the_keyboard(service.asks)

    try:
        via = _as_channel(args.as_channel)
    except ConfigProblem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    async def go():
        try:
            return await service.deliver(actor=args.actor, via=via,
                                         agent=args.agent,
                                         thread=args.thread, text=args.text)
        finally:
            await service.aclose()

    reply = asyncio.run(go())
    print(reply.text)
    if reply.receipt:
        # Where a chat would put it, so `say` shows an owner what their
        # guest will actually see -- the same reason --as exists. The
        # banner below is the operator's view of the same turn and says
        # more; this is the person's.
        print(reply.receipt)
    if reply.detail and not reply.ok:
        # The owner is standing right here. A channel gets the polite
        # sentence; the person who can FIX it gets the reason, because a
        # misconfigured base URL that reports only "that went wrong at my
        # end" is a afternoon spent guessing.
        print(f"  {reply.detail}", file=sys.stderr)
    line = f"[{reply.stop_reason}"
    if reply.cost_usd is not None:
        line += f" · ${reply.cost_usd:.4f}"
    if reply.usage is not None:
        line += (f" · {reply.usage.input_tokens}in/"
                 f"{reply.usage.output_tokens}out")
    if reply.run_id:
        line += f" · run {reply.run_id}"
    print(f"{line}]", file=sys.stderr)
    return 0 if reply.ok else 1


def _runs(service: Service, args) -> int:
    rows = service.runs.recent(actor=args.actor, agent=args.agent,
                               limit=args.limit)
    if not rows:
        print("no runs recorded yet")
        return 0
    # Newest first, so the run AFTER each one has already been printed:
    # a version that differs there is a package edited between the two,
    # under a conversation that was already going. The note therefore
    # hangs on the EARLIER of the pair and says "after this turn", which
    # is the direction a reader scanning down the page is travelling.
    previous = {}
    for run in rows:
        cost = f"${run.cost_usd:.4f}" if run.cost_usd is not None else "unpriced"
        stamp = run.started_at.strftime("%Y-%m-%d %H:%M")
        print(f"{stamp}  {run.actor}/{run.agent}  {run.stop_reason:<14} "
              f"{cost:>9}  {run.message[:48]!r}")
        key = (run.actor, run.agent, run.thread)
        was = previous.get(key)
        if was is not None and was != run.agent_version:
            # A PACKAGE EDITED ON DISK TAKES EFFECT ON THE NEXT TURN --
            # desirable when you are fixing a prompt, alarming when a
            # conversation changes personality mid-sentence, and invisible
            # until somebody writes it down (notes/10).
            print(f"{'':<18}{run.agent} changed after this turn: "
                  f"{run.agent_version or '?'} -> {was or '?'}")
        previous[key] = run.agent_version
        if run.tools:
            # The shape of the turn, on one line, with the refused calls
            # marked. This is the line an owner scans for "what has it
            # been TRYING to do", which the verdict above never said.
            path = " -> ".join(
                _step(step) for step in run.tools)
            where = (f"  [answered from {', '.join(run.answered_from)}]"
                     if run.answered_from else "")
            # How long a person was kept on the hook (notes/15) -- only
            # when somebody was, which is the turn the owner wants to see.
            waited = (f"  [waited {patience.duration(run.waited_seconds)}]"
                      if run.waited_seconds and run.waited_seconds >= 0.5
                      else "")
            print(f"{'':<18}{path}{where}{waited}")
        if run.detail and not run.ok:
            # Why it went wrong, where the owner is already looking. The
            # store has carried this since the first commit; not printing
            # it made the ledger a list of shrugs.
            print(f"{'':<18}{run.detail}")
    return 0


def _rules(service: Service, args) -> int:
    """Each standing answer, and how many calls it has settled.

    THE ONES THAT HAVE NEVER FIRED ARE THE POINT. A rule that is doing
    work shows up as a question you stopped being asked, which is a thing
    you notice; a rule that has never matched anything shows up as
    nothing at all, and lives in the file forever looking like policy.

    A rule is counted by an id hashed from what it SAYS, so editing one
    starts its count over. That is correct -- you changed the standing
    answer, and the old one's history is not this one's -- and it is said
    out loud below, because a zero beside a rule you have had for a year
    is otherwise alarming.
    """
    book = service.policy.rules
    if not len(book):
        where = book.source or "no policy file"
        print(f"no standing rules ({where}). Every call that could change "
              f"something is decided by the rung alone.")
        return 0
    since = None
    if args.days > 0:
        since = datetime.now(UTC) - timedelta(days=args.days)
    counts = service.runs.rule_counts(since)

    window = f"the last {args.days} days" if since else "all recorded runs"
    print(f"{book.source}  ·  {len(book)} rule(s)  ·  calls settled over "
          f"{window}")
    for rule in book:
        target = ", ".join(f"{name}={'|'.join(alts)}"
                           for name, alts in sorted(rule.args.items()))
        wrote = f"{rule.tool} {target}".strip()
        count = counts.get(rule.id, 0)
        settled = f"{count:>5}" if count else "    ·"
        print(f"  {settled}  {rule.verdict:<6} {wrote}")
    if any(counts.get(rule.id, 0) == 0 for rule in book):
        print()
        print("  ·  = never matched a call in this window. A rule you "
              "edited starts over: the count follows what a rule SAYS, "
              "not where it sits in the file.")
    return 0


def _step(step) -> str:
    """One tool call, and what settled it, in as few characters as it takes.

    The decision is shown only when there WAS one. Most calls are allowed
    by the rung, and writing "(rung)" beside nine of every ten would bury
    the one that says a person was woken up at two in the morning.
    """
    name = step.name if step.ran else f"{step.name}(refused)"
    if step.decided_by is None:
        return name
    return f"{name}[{step.decided_by}]"


def _case(service: Service, args) -> int:
    """A recorded run -> a case its package's gate will run from now on.

    Printed by default. ``--write`` is a flag somebody has to type,
    because the alternative is a service that edits the folder its owner
    reviews and commits, which is the one thing note 01 would not let a
    running agent do (cases.py).
    """
    run = service.runs.get(args.run)
    if run is None:
        print(f"error: no run matching {args.run!r} (a prefix works, if it "
              f"picks out exactly one)", file=sys.stderr)
        return 1
    try:
        case = case_from_run(run, because=args.because)
        if not args.write:
            print(render_case(case), end="")
            # To stderr, so the block above stays pasteable.
            print(f"\n# from run {run.id} against {run.agent}. Read it "
                  f"before you commit it: the message is somebody's own "
                  f"words.", file=sys.stderr)
            advisory = unasserted(run)
            if advisory:
                print(f"# {advisory}", file=sys.stderr)
            return 0
        path = append(service.roster.path(run.agent), case)
    except Refused as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{path}: added {case.id}")
    print(f"  run it with: yantra --agent {service.roster.path(run.agent)} "
          f"--eval --case '{case.id}'")
    return 0


def _bot(service: Service, args) -> TelegramBot:
    """One bot, from the environment and the flags, for either command.

    THE TOKEN IS NOT A FLAG. A bot token is a credential, and a
    credential on a command line is in the shell history and in every
    `ps` on the box. Missing is a ``ConfigProblem`` rather than a printed
    line, so `serve --telegram` and `telegram` refuse it identically.
    """
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        raise ConfigProblem(
            "$TELEGRAM_TOKEN is not set. BotFather gives you one per bot; "
            "it belongs in the environment, never on a command line")
    return TelegramBot(service, token=token,
                       agent=getattr(args, "telegram", None) or args.agent,
                       catch_up=args.catch_up,
                       poll_seconds=getattr(args, "poll_seconds",
                                            POLL_SECONDS))


def _telegram(service: Service, args) -> int:
    """Long-poll Telegram, in this process, as a client of this service.

    IN PROCESS, NOT OVER HTTP, and that is the whole reason this is a
    subcommand rather than a script in a README. A bot that talked to
    ``dvara serve`` would have to find a pending question by polling
    ``GET /asks``, so a "may I run this?" would sit for up to one poll
    interval while its own deadline ran down. Here it registers a route
    on the desk and the question is pushed the instant it is raised. The
    HTTP surface remains exactly what it was: the way in for an adapter
    that is NOT in this process.

    THE TOKEN IS NOT A FLAG. A bot token is a credential, and a
    credential on a command line is in the shell history and in every
    `ps` on the box.
    """
    try:
        bot = _bot(service, args)
    except (ConfigProblem, Refused) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    async def go():
        try:
            await bot.run()
        finally:
            await service.aclose()

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        # Ctrl-C is how a bot is stopped, so it is an exit and not a
        # traceback. `run` has already cancelled the turns in flight and
        # each of them recorded itself on the way out.
        return 0
    except ConfigProblem as exc:
        # A bad token, or a second poller on the same one. Loud, and
        # never answered into a chat: this is the owner's to fix.
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def _serve(args) -> int:
    """The HTTP surface, and optionally a bot on the same event loop.

    ONE PROCESS, BOTH JOBS. `dvara serve` and `dvara telegram` may not
    share a state directory -- the lock that serializes two messages in
    one conversation and the queue of questions waiting for a person both
    live in memory (claim.py) -- so `--telegram` is not a shortcut, it is
    the only way to have a bot and an HTTP surface at once.
    """
    token = os.environ.get("DVARA_TOKEN", "")
    try:
        service = _service(args)
        bot = _bot(service, args) if args.telegram else None
        from dvara.http import create_app
        app = create_app(service, token=token,
                         alongside=bot.run if bot is not None else None)
    except (ConfigProblem, Refused) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ImportError:
        print("error: the HTTP surface needs the http extra "
              "(uv sync --extra http)", file=sys.stderr)
        return 2

    import uvicorn

    also = f" · telegram → {args.telegram}" if bot is not None else ""
    print(f"dvara · {len(service.roster.names())} agent(s) · "
          f"{len(service.actors)} actor(s) · "
          f"http://{args.host}:{args.port}{also}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0

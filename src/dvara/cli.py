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
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dvara.actors import ActorBook
from dvara.errors import ConfigProblem
from dvara.gate import Policy
from dvara.roster import Roster
from dvara.service import Service

DEFAULT_ROOT = "~/dvara/agents"
DEFAULT_ACTORS = "~/dvara/actors.toml"
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

    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("agents", help="list the agents this service can offer")

    say = subs.add_parser("say", help="run one turn, in process, no HTTP")
    say.add_argument("text", help="what to say to the agent")
    say.add_argument("--actor", required=True)
    say.add_argument("--agent", required=True)
    say.add_argument("--thread", default="cli")

    runs = subs.add_parser("runs", help="what this service has been doing")
    runs.add_argument("--actor", default=None)
    runs.add_argument("--agent", default=None)
    runs.add_argument("--limit", type=int, default=20)

    serve = subs.add_parser("serve", help="listen for channel adapters")
    serve.add_argument("--host", default="127.0.0.1",
                       help="localhost by default, deliberately: reaching the "
                            "network is a decision, not a default")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def _service(args) -> Service:
    return Service(
        roster=Roster(Path(args.root)),
        actors=ActorBook.from_toml(Path(args.actors)),
        state=Path(args.state),
        policy=Policy(mode="yolo" if args.yolo else "ask"),
        provider_name=args.provider,
        model=args.model,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "serve":
            return _serve(args)
        service = _service(args)
    except ConfigProblem as exc:
        # The owner's own files are wrong. Loud, and never answered into
        # a channel -- this is the one human who can fix it.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "agents":
            return _agents(service)
        if args.command == "say":
            return _say(service, args)
        if args.command == "runs":
            return _runs(service, args)
    finally:
        service.close()
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


def _say(service: Service, args) -> int:
    async def go():
        try:
            return await service.deliver(actor=args.actor, agent=args.agent,
                                         thread=args.thread, text=args.text)
        finally:
            await service.aclose()

    reply = asyncio.run(go())
    print(reply.text)
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
    for run in rows:
        cost = f"${run.cost_usd:.4f}" if run.cost_usd is not None else "unpriced"
        stamp = run.started_at.strftime("%Y-%m-%d %H:%M")
        print(f"{stamp}  {run.actor}/{run.agent}  {run.stop_reason:<14} "
              f"{cost:>9}  {run.message[:48]!r}")
        if run.detail and not run.ok:
            # Why it went wrong, where the owner is already looking. The
            # store has carried this since the first commit; not printing
            # it made the ledger a list of shrugs.
            print(f"{'':<18}{run.detail}")
    return 0


def _serve(args) -> int:
    token = os.environ.get("DVARA_TOKEN", "")
    try:
        service = _service(args)
        from dvara.http import create_app
        app = create_app(service, token=token)
    except ConfigProblem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ImportError:
        print("error: the HTTP surface needs the http extra "
              "(uv sync --extra http)", file=sys.stderr)
        return 2

    import uvicorn

    print(f"dvara · {len(service.roster.names())} agent(s) · "
          f"{len(service.actors)} actor(s) · http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0

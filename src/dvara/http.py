"""The HTTP surface -- a transport, and honest about being only that.

Ten endpoints for any caller, five more for a page's chat (web.py),
no session state, no cleverness. Everything that decides
anything lives in ``service.py``; this module moves JSON.

THREE WAYS IN, AND THEY ARE NOT THE SAME WAY. ``/message`` starts a turn;
``/asks`` and ``/asks/{id}`` release one that is already standing there
waiting for a person to approve a tool call. They have to be separate
paths, because a turn holds its conversation's lock while it waits -- an
approval arriving as a MESSAGE would queue up behind the very turn it was
meant to release, and sit there until the deadline passed. ``/holds`` and
``/holds/{id}`` carry on a turn that stopped because nobody answered in
time (notes/16): nothing is standing there any more, so an answer there
STARTS the rest of the turn and replies with what it came to.

A FOURTH WAY IN, FOR A TURN THAT IS NOT DVARA'S. ``/ask`` puts one
question to a person and replies with their answer -- for a run started
somewhere else (Samay's direct road) that met a call nobody allowed
ahead of time. The question is the same question a turn here would put,
on the same desk, through the same owner's rules; only the turn lives
elsewhere.

THE TOKEN AUTHENTICATES THE CALLER, NOT THE PERSON. That distinction is
the whole security posture of this layer. A caller here is a channel
adapter -- a Telegram bridge, a script, the owner's own terminal --
running inside the owner's trust boundary. So the body's ``actor`` field
is an ASSERTION BY A TRUSTED CALLER, which is exactly why the bearer
token guarding it is mandatory rather than optional: without it, anyone
who can reach the port can claim to be anyone in the actors file.

TWO WAYS TO SAY WHO, AND AN ADAPTER SHOULD PREFER THE SECOND. ``actor``
is that assertion. ``channel`` -- ``{"kind": "telegram", "id": "8675309"}``
-- hands over the identity the adapter actually has and lets the roster
map it, which is the same trust boundary with one fewer place to be
wrong: a bridge that carries no table of its own cannot carry a stale
one, and an owner who removes somebody from ``actors.toml`` has removed
them, rather than having removed them from one of two files. Both forms
are accepted on every endpoint that names a person; exactly one per
request.

Consequences, accepted on purpose:

* Bind to localhost by default. A service reachable from the network is a
  decision an owner makes explicitly, with a reverse proxy and TLS in
  front of it, not something that happens because a default was 0.0.0.0.
* No token, no app. ``create_app`` refuses to build rather than start
  something that would serve a stranger, because "I will add auth later"
  is how it never gets added.
* Comparison is constant-time. A token compared with ``==`` leaks its
  length and its prefix to anyone patient.

ONE PROCESS MAY DO BOTH JOBS. ``create_app(..., alongside=...)`` starts a
coroutine on the server's own event loop and cancels it on shutdown --
which is how ``dvara serve --telegram`` runs a bot and an HTTP surface
together. It is not a convenience: two processes over one state directory
is refused (``claim.py``), because the per-session lock and the queue of
pending questions live in memory, so this is the only way to have both.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

from yantra import parse_grant

from dvara.actors import Channel
from dvara.asks import NotYours
from dvara.errors import ConfigProblem, Refused
from dvara.holds import NoSuchHold, NotYourHold
from dvara.service import Service


def _whom(body: dict) -> tuple[str | None, Channel | None]:
    """Read who a request is about, in whichever of the two forms it used.

    Rejected here rather than in the service for the ones that are a
    MALFORMED REQUEST rather than a refused one: a ``channel`` that is
    not an object with two strings in it is a caller with a bug, and 400
    says so where a polite sentence in a reply body would be read by a
    bridge as the agent having answered something.
    """
    actor, channel = body.get("actor"), body.get("channel")
    if actor is not None and channel is not None:
        raise HTTPException(
            status_code=400,
            detail="name a person with actor or with channel, not both")
    if channel is not None:
        if not isinstance(channel, dict):
            raise HTTPException(
                status_code=400,
                detail='channel must be {"kind": ..., "id": ...}')
        kind, native = channel.get("kind"), channel.get("id")
        if not isinstance(kind, str) or not kind.strip():
            raise HTTPException(status_code=400,
                                detail="missing or empty: channel.kind")
        # Numbers allowed for the same reason actors.toml allows them:
        # a Telegram id is a number everywhere Telegram writes one down,
        # and JSON is one more place an adapter would have to remember to
        # quote it.
        if isinstance(native, bool) or not isinstance(native, str | int):
            raise HTTPException(status_code=400,
                                detail="missing or empty: channel.id")
        if not str(native).strip():
            raise HTTPException(status_code=400,
                                detail="missing or empty: channel.id")
        return None, Channel(kind=kind, id=str(native))
    if not isinstance(actor, str) or not actor.strip():
        raise HTTPException(
            status_code=400,
            detail="missing or empty: actor (or a channel naming one)")
    return actor, None


def _resolve(service: Service, kind: str | None, native: str | None) -> str:
    """A channel identity, as an actor id, for the two ask endpoints.

    404 for an unmapped identity, not 403: the caller is inside the
    owner's trust boundary and what it has is a name for nobody. The
    sentence stays the roster's own, which says nothing about who else
    exists.
    """
    if not kind or not native:
        raise HTTPException(
            status_code=400,
            detail="channel and channel_id go together; neither is enough "
                   "on its own")
    try:
        return service.actors.resolve(kind, native).id
    except Refused as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


def create_app(service: Service, *, token: str,
               alongside: Callable[[], Awaitable[None]] | None = None) -> Any:
    """A FastAPI app in front of one ``Service``.

    FastAPI is imported at MODULE level rather than in here, which looks
    like a stylistic choice and is not: this file carries ``from
    __future__ import annotations``, so FastAPI resolves every parameter
    annotation against the module's globals. A ``Request`` imported
    inside the function is invisible there, and FastAPI silently decides
    the parameter must be a body field -- every request then 422s before
    a line of this code runs. The optional dependency stays optional
    because nothing imports ``dvara.http`` until somebody serves.
    """
    if not token or len(token) < 16:
        raise ConfigProblem(
            "dvara needs a bearer token of at least 16 characters "
            "($DVARA_TOKEN); a service without one serves whoever "
            "reaches the port"
        )

    @asynccontextmanager
    async def lifespan(_app):
        # ``alongside`` is how a channel adapter runs IN THIS PROCESS
        # rather than beside it -- a Telegram long poll, today. It goes on
        # the server's own loop on purpose: one process means one ask
        # desk and one set of per-session locks, which is the whole of
        # why two of these may not share a state directory (claim.py).
        job = (asyncio.ensure_future(alongside())
               if alongside is not None else None)
        try:
            yield
        finally:
            # Sockets back on the way out. A lifespan rather than the
            # on_event decorator: the older hook is deprecated, and a
            # DeprecationWarning in a service is a warning nobody sees.
            if job is not None:
                job.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await job
            await service.aclose()

    app = FastAPI(title="dvara", docs_url=None, redoc_url=None,
                  lifespan=lifespan)

    def check(authorization: str | None) -> None:
        offered = ""
        if authorization and authorization.lower().startswith("bearer "):
            offered = authorization[7:]
        if not secrets.compare_digest(offered, token):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    async def health(authorization: str | None = Header(default=None)) -> dict:
        check(authorization)
        return {"ok": True, "agents": len(service.roster.names()),
                "actors": len(service.actors)}

    @app.get("/agents")
    async def agents(authorization: str | None = Header(default=None)) -> dict:
        """What this service can offer. A listing loads no package's code."""
        check(authorization)
        return {"agents": service.roster.names()}

    @app.post("/message")
    async def message(request: Request,
                      authorization: str | None = Header(default=None)) -> dict:
        check(authorization)
        body = await request.json()
        missing = [f for f in ("agent", "thread", "text")
                   if not isinstance(body.get(f), str) or not body[f].strip()]
        if missing:
            raise HTTPException(status_code=400,
                                detail=f"missing or empty: {', '.join(missing)}")
        actor, via = _whom(body)
        unattended = body.get("unattended", False)
        allow_tools = body.get("allow_tools") or []
        if not isinstance(unattended, bool):
            raise HTTPException(status_code=400,
                                detail="unattended is true or false")
        if not isinstance(allow_tools, list) or not all(
                isinstance(g, str) for g in allow_tools):
            raise HTTPException(status_code=400,
                                detail="allow_tools is a list of tool-name globs")
        for text in allow_tools:
            try:
                parse_grant(text)
            except ValueError as exc:
                raise HTTPException(status_code=400,
                                    detail=f"allow_tools: {exc}") from None
        if allow_tools and not unattended:
            # An answer given ahead of time is for a turn nobody is at.
            # A person who IS there answers the question when it comes.
            raise HTTPException(status_code=400,
                                detail="allow_tools goes with unattended: true")
        # A schedule's own: the phone, the steps its person let it do on it
        # unasked, and how long its questions may wait (service.deliver).
        phone = body.get("phone", False)
        phone_steps = body.get("phone_steps") or []
        wait = body.get("wait")
        if not isinstance(phone, bool):
            raise HTTPException(status_code=400, detail="phone is true or false")
        if not isinstance(phone_steps, list) or not all(
                isinstance(s, str) for s in phone_steps):
            raise HTTPException(status_code=400,
                                detail="phone_steps is a list of sentences")
        if wait is not None and (isinstance(wait, bool)
                                 or not isinstance(wait, (int, float)) or wait <= 0):
            raise HTTPException(status_code=400, detail="wait is seconds, more than 0")
        if (phone or phone_steps or wait is not None) and not unattended:
            raise HTTPException(status_code=400,
                                detail="phone, phone_steps and wait go with unattended: true")
        if phone_steps and not phone:
            raise HTTPException(status_code=400, detail="phone_steps go with phone: true")
        # Which way the turn came in, for the page (runs.py): the caller's
        # own word (Samay says "samay"), else its channel's kind, else http.
        came_by = body.get("came_by")
        if came_by is not None and (not isinstance(came_by, str)
                                    or not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", came_by)):
            raise HTTPException(status_code=400,
                                detail="came_by is one short lowercase word, like samay")
        came_by = came_by or (via.kind if via is not None else "http")
        reply = await service.deliver(actor=actor, via=via,
                                      agent=body["agent"],
                                      thread=body["thread"], text=body["text"],
                                      unattended=unattended,
                                      allow_tools=allow_tools,
                                      phone=phone, phone_steps=phone_steps,
                                      wait=float(wait) if wait is not None else None,
                                      came_by=came_by)
        return {
            "text": reply.text,
            "ok": reply.ok,
            "run_id": reply.run_id,
            "agent": reply.agent,
            # Who the turn actually ran as. A caller that arrived with a
            # channel identity has never seen an actor id, and needs one
            # to answer a question this turn may have raised.
            "actor": reply.actor,
            "stop_reason": reply.stop_reason,
            "detail": reply.detail,
            "cost_usd": reply.cost_usd,
            # A rendered line, beside the raw number rather than instead
            # of it. A channel can only print prose; anything that draws
            # a meter wants the float. Yantra's note 43 settled that
            # shape -- parsing the sentence back into the number is how
            # the two drift apart.
            "receipt": reply.receipt,
            # The turn stopped for approval nobody gave in time. The id is
            # what POST /holds/{id} answers; the calls are what to show.
            "held": reply.held.as_dict() if reply.held else None,
            # What only a person can fix, what was busy, what was refused
            # (Yantra's unattended.py) -- for the program that asked.
            "needs_person": list(reply.needs),
            "busy": list(reply.busy),
            "refused": list(reply.refused),
            # ``/file NAME`` answered: where the file is on this machine.
            # Named, not sent -- a bridge that wants the bytes is here and
            # can read it (files.py).
            "files": [str(f) for f in reply.files],
        }

    @app.post("/ask")
    async def ask(request: Request,
                  authorization: str | None = Header(default=None)) -> dict:
        """Put ONE question to a person and wait for their answer.

        For a run Dvara is not running -- Samay's direct road, Yantra
        started with nobody at it -- that met a call nobody allowed ahead
        of time. The question goes where every other question here goes,
        the person's chat with two buttons, through the same owner's
        rules (service.ask); the reply is the decision, after at most
        ``timeout`` seconds. 200 either way: "they said no" and "nobody
        answered" are answers, not errors.
        """
        check(authorization)
        body = await request.json()
        missing = [f for f in ("actor", "tool", "summary")
                   if not isinstance(body.get(f), str) or not body[f].strip()]
        if missing:
            raise HTTPException(status_code=400,
                                detail=f"missing or empty: {', '.join(missing)}")
        arguments = body.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise HTTPException(status_code=400, detail="arguments is an object")
        timeout = body.get("timeout")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
                or timeout <= 0:
            raise HTTPException(status_code=400, detail="timeout is seconds, more than 0")
        try:
            answer = await service.ask(
                actor=body["actor"], tool=body["tool"], summary=body["summary"],
                arguments=arguments, timeout=float(timeout),
                agent=str(body.get("agent") or ""), thread=str(body.get("thread") or ""))
        except Refused as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"approved": answer.approved, "reason": answer.reason or "",
                "code": "" if answer.approved else answer.code or "",
                "via": answer.via or ""}

    @app.post("/notify")
    async def notify(request: Request,
                     authorization: str | None = Header(default=None)) -> dict:
        """Tell a person something, on their own channels (notices.py).

        200 says where it went: ``sent`` now, ``kept`` for an adapter to
        collect, or neither -- a person with no channel, said as
        ``nowhere: true`` rather than as an error, because the caller
        asked a fair question and that is its answer.
        """
        check(authorization)
        body = await request.json()
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(status_code=400, detail="missing or empty: text")
        actor, via = _whom(body)
        try:
            who, sent = await service.notify(text=text, actor=actor, via=via)
        except Refused as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"actor": who, "sent": sent.sent, "kept": sent.kept,
                "failed": sent.failed, "nowhere": sent.nowhere}

    @app.get("/notices")
    async def notices(channel: str,
                      authorization: str | None = Header(default=None)) -> dict:
        """Notices waiting for a channel adapter in another process --
        each handed over once, oldest first."""
        check(authorization)
        return {"notices": [n.as_dict() for n in service.notices.take(channel)]}

    # ---- the web channel (web.py): a page's chat, as a trusted caller -----

    def web_for(actor: object) -> Any:
        """The web channel and a person on it, or the reason not."""
        if service.web is None:
            raise HTTPException(status_code=404,
                                detail="this service has no web channel; "
                                       "start it with --web")
        if not isinstance(actor, str) or not actor.strip():
            raise HTTPException(status_code=400, detail="missing or empty: actor")
        try:
            service.actors.get(actor)
        except Refused as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return service.web

    @app.get("/web")
    async def web_look(actor: str = "", after: int = 0,
                       authorization: str | None = Header(default=None)) -> dict:
        """A person's lines after ``after``, the agents they may talk to,
        what is running, and the questions and held turns waiting for
        them -- everything a page draws, in one look."""
        check(authorization)
        service.refresh()
        return web_for(actor).look(actor, max(0, after))

    @app.post("/web/message")
    async def web_say(request: Request,
                      authorization: str | None = Header(default=None)) -> dict:
        """Say something on the page. Answers at once with the line
        written; the agent's answer is a later line (web.py)."""
        check(authorization)
        body = await request.json()
        web = web_for(body.get("actor"))
        missing = [f for f in ("agent", "text")
                   if not isinstance(body.get(f), str) or not body[f].strip()]
        if missing:
            raise HTTPException(status_code=400,
                                detail=f"missing or empty: {', '.join(missing)}")
        service.refresh()
        try:
            line = web.say(body["actor"], body["agent"], body["text"])
        except Refused as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"line": line.as_dict()}

    @app.post("/web/asks/{ask_id}")
    async def web_answer(ask_id: str, request: Request,
                         authorization: str | None = Header(default=None)) -> dict:
        """A question answered from the page -- the same desk, the same
        first-answer-wins, as Telegram's buttons."""
        check(authorization)
        body = await request.json()
        web_for(body.get("actor"))
        if not isinstance(body.get("approve"), bool):
            raise HTTPException(status_code=400,
                                detail="approve must be true or false")
        if service.asks is None:
            raise HTTPException(status_code=404,
                                detail="this service does not escalate")
        try:
            landed = service.asks.answer(ask_id, actor=body["actor"],
                                         approve=body["approve"], via="web")
        except NotYours:
            raise HTTPException(status_code=403,
                                detail="that question was put to somebody else") from None
        if not landed:
            raise HTTPException(status_code=404,
                                detail="that question is not waiting any more")
        return {"answered": True, "approved": body["approve"]}

    @app.post("/web/holds/{hold_id}")
    async def web_carry_on(hold_id: str, request: Request,
                           authorization: str | None = Header(default=None)) -> dict:
        """A held turn answered from the page; what it comes to is a line."""
        check(authorization)
        body = await request.json()
        web = web_for(body.get("actor"))
        answers = body.get("answers")
        if not isinstance(answers, dict) or not answers:
            raise HTTPException(
                status_code=400,
                detail="answers must map each waiting call's id to true, "
                       "false, or a reason")
        try:
            web.carry_on(hold_id, body["actor"], answers)
        except NotYourHold:
            raise HTTPException(status_code=403,
                                detail="that held turn ran as somebody else") from None
        except NoSuchHold as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return {"started": True}

    @app.get("/web/file")
    async def web_file(actor: str = "", line: int = 0, n: int = 0,
                       authorization: str | None = Header(default=None)) -> Any:
        """A file a line carried, by line and number."""
        check(authorization)
        path = web_for(actor).file(actor, line, n)
        if path is None:
            raise HTTPException(status_code=404, detail="no such file any more")
        return FileResponse(path, filename=path.name)

    @app.get("/asks")
    async def asks(actor: str | None = None, channel: str | None = None,
                   channel_id: str | None = None,
                   authorization: str | None = Header(default=None)) -> dict:
        """Questions standing right now, oldest first.

        Unfiltered by default, because one adapter may serve several
        people. ``?actor=`` narrows to one of them; ``?channel=&channel_id=``
        narrows to the same person named the way the adapter knows them.

        ONE PERSON IS ONE QUEUE. A question raised by a turn that came in
        over HTTP is listed here for the same actor as one raised in a
        chat, because the person is the same person -- which is the whole
        of what the channel table in ``actors.toml`` bought.
        """
        check(authorization)
        if service.asks is None:
            return {"asks": []}
        if channel is not None or channel_id is not None:
            if actor is not None:
                raise HTTPException(
                    status_code=400,
                    detail="name a person with actor or with "
                           "channel+channel_id, not both")
            actor = _resolve(service, channel, channel_id)
        return {"asks": [ask.as_dict() for ask in service.asks.pending(actor)]}

    @app.post("/asks/{ask_id}")
    async def answer(ask_id: str, request: Request,
                     authorization: str | None = Header(default=None)) -> dict:
        """Release a waiting turn, one way or the other.

        ``approve`` MUST BE A JSON BOOLEAN. Accepting anything truthy
        would make the string "no" an approval, which is the exact shape
        of the bug that ends with a shell command nobody agreed to: a
        channel adapter forwarding a person's literal words into a field
        that was expecting a decision.
        """
        check(authorization)
        body = await request.json()
        actor, via = _whom(body)
        # Where the answer came from, for the Run. A caller that named a
        # channel is standing in that channel's doorway and says so; one
        # that asserted an actor id is a bridge whose own name this
        # service does not know, and "http" is the honest answer rather
        # than a guess at which app the person was holding.
        door = via.kind if via is not None else "http"
        if via is not None:
            actor = _resolve(service, via.kind, via.id)
        if not isinstance(body.get("approve"), bool):
            raise HTTPException(status_code=400,
                                detail="approve must be true or false")
        if service.asks is None:
            raise HTTPException(status_code=404,
                                detail="this service does not escalate")
        try:
            landed = service.asks.answer(ask_id, actor=actor,
                                         approve=body["approve"], via=door)
        except NotYours:
            # Distinguished from 404 deliberately. Both sides of this line
            # are inside the owner's trust boundary, and a routing bug in
            # an adapter that looked like an expired question would be an
            # afternoon lost; the id was already known to whoever sent it.
            raise HTTPException(
                status_code=403,
                detail="that question was put to somebody else") from None
        if not landed:
            raise HTTPException(
                status_code=404,
                detail="no question with that id is waiting -- it was "
                       "answered, it timed out, or the turn behind it went "
                       "away")
        return {"answered": True, "approved": body["approve"]}

    @app.get("/holds")
    async def holds(actor: str | None = None, channel: str | None = None,
                    channel_id: str | None = None,
                    authorization: str | None = Header(default=None)) -> dict:
        """Held turns that can still be answered, oldest first.

        Filtered exactly as ``/asks`` is, and for the same reason: one
        adapter may serve several people, and one person is one queue.
        """
        check(authorization)
        if channel is not None or channel_id is not None:
            if actor is not None:
                raise HTTPException(
                    status_code=400,
                    detail="name a person with actor or with "
                           "channel+channel_id, not both")
            actor = _resolve(service, channel, channel_id)
        return {"holds": [hold.as_dict()
                          for hold in service.holds.pending(actor)]}

    @app.post("/holds/{hold_id}")
    async def carry_on(hold_id: str, request: Request,
                       authorization: str | None = Header(default=None)
                       ) -> dict:
        """Answer a held turn, and reply with what it came to.

        ``answers`` maps each waiting call's id to true, false, or the
        person's reason for refusing it as a string. ONLY A JSON BOOLEAN
        APPROVES, for the reason ``/asks/{id}`` insists on one: the
        string "yes" is a refusal whose reason is "yes", never a yes.
        """
        check(authorization)
        body = await request.json()
        actor, via = _whom(body)
        door = via.kind if via is not None else "http"
        if via is not None:
            # Resolved here, as /asks/{id} does, so an identity the roster
            # has never heard of is the same 404 on both answer paths.
            actor = _resolve(service, via.kind, via.id)
        answers = body.get("answers")
        if not isinstance(answers, dict) or not answers:
            raise HTTPException(
                status_code=400,
                detail="answers must map each waiting call's id to true, "
                       "false, or a reason")
        try:
            reply = await service.resume(hold_id, answers=answers,
                                         actor=actor, door=door)
        except NotYourHold:
            raise HTTPException(
                status_code=403,
                detail="that held turn ran as somebody else") from None
        except NoSuchHold as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        except Refused as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"text": reply.text, "ok": reply.ok, "run_id": reply.run_id,
                "agent": reply.agent, "actor": reply.actor,
                "stop_reason": reply.stop_reason, "detail": reply.detail,
                "cost_usd": reply.cost_usd, "receipt": reply.receipt,
                "held": reply.held.as_dict() if reply.held else None}

    return app

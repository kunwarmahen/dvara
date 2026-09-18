"""The HTTP surface -- a transport, and honest about being only that.

Five endpoints, no session state, no cleverness. Everything that decides
anything lives in ``service.py``; this module moves JSON.

TWO WAYS IN, AND THEY ARE NOT THE SAME WAY. ``/message`` starts a turn;
``/asks`` and ``/asks/{id}`` release one that is already standing there
waiting for a person to approve a tool call. They have to be separate
paths, because a turn holds its conversation's lock while it waits -- an
approval arriving as a MESSAGE would queue up behind the very turn it was
meant to release, and sit there until the deadline passed.

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
are accepted on all three endpoints that name a person; exactly one per
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
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from dvara.actors import Channel
from dvara.asks import NotYours
from dvara.errors import ConfigProblem, Refused
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


def create_app(service: Service, *, token: str) -> Any:
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
        # Sockets back on the way out. A lifespan rather than the
        # on_event decorator: the older hook is deprecated, and a
        # DeprecationWarning in a service is a warning nobody sees.
        yield
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
        reply = await service.deliver(actor=actor, via=via,
                                      agent=body["agent"],
                                      thread=body["thread"], text=body["text"])
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
        }

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

    return app

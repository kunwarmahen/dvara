"""The HTTP surface -- a transport, and honest about being only that.

Three endpoints, no session state, no cleverness. Everything that decides
anything lives in ``service.py``; this module moves JSON.

THE TOKEN AUTHENTICATES THE CALLER, NOT THE PERSON. That distinction is
the whole security posture of this layer. A caller here is a channel
adapter -- a Telegram bridge, a script, the owner's own terminal --
running inside the owner's trust boundary, and it is the adapter's job to
map its channel's native identity onto an actor id. So the body's
``actor`` field is an ASSERTION BY A TRUSTED CALLER, which is exactly why
the bearer token guarding it is mandatory rather than optional: without
it, anyone who can reach the port can claim to be anyone in the actors
file.

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

from dvara.errors import ConfigProblem
from dvara.service import Service


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
        missing = [f for f in ("actor", "agent", "thread", "text")
                   if not isinstance(body.get(f), str) or not body[f].strip()]
        if missing:
            raise HTTPException(status_code=400,
                                detail=f"missing or empty: {', '.join(missing)}")
        reply = await service.deliver(actor=body["actor"], agent=body["agent"],
                                      thread=body["thread"], text=body["text"])
        return {
            "text": reply.text,
            "ok": reply.ok,
            "run_id": reply.run_id,
            "agent": reply.agent,
            "stop_reason": reply.stop_reason,
            "detail": reply.detail,
            "cost_usd": reply.cost_usd,
        }

    return app

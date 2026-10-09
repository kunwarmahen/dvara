"""The owner's page -- served by ``dvara page``, beside the door, not in it.

An owner running a door for a household wants to see it without a
terminal: who is on it, which agents they may use, what those agents
have been doing, and what it is costing. ``dvara runs`` answers one of
those at a time, in a terminal. This page shows them together:

    GET /api/status          serving or not, the version, problems
    GET /api/people          everyone in the actors file, with today's spend
    GET /api/agents          the agents in the root
    GET /api/runs?actor=&agent=&limit=N   newest first
    GET /api/files           each person's folder per agent: names, sizes, dates
    GET /api/file?agent=A&path=P          one of the owner's own files, as text
    GET /api/schedules       each person's schedules, as Samay says them
    GET  /api/waiting        the owner's questions and held turns, from the door
    POST /api/asks/ID        {approve: true|false}
    POST /api/holds/ID       {answers: {call id: true|false|"reason"}}

A SEPARATE PROCESS, AND IT ONLY READS. ``dvara page`` reads what ``dvara
serve`` writes -- the actors file, the runs ledger -- and claims nothing
(claim.py): looking at your own ledger while the bot answers somebody is
the most ordinary thing an owner does. Nothing on the page changes who
is served or what they may spend; that stays the actors file, which the
door re-reads without a restart.

ITS ONE KIND OF ANSWER GOES THROUGH THE DOOR. A question waiting for the
owner lives in the serving process's memory (asks.py), and a held turn
is carried on by running a turn (holds.py), so neither can be answered
from here. The page asks the running door instead, over the HTTP surface
every adapter uses (``GET /asks``, ``POST /asks/ID``, ``GET /holds``,
``POST /holds/ID``), with ``DVARA_TOKEN`` held in this process and never
sent to a browser. The door still checks the answer is from the person
asked; this page only ever names the owner (``--as``), and never takes a
name from the browser. So it shows, and answers, THE OWNER'S OWN
QUESTIONS ONLY -- somebody else's never reach the page at all. With no
door running there is nothing to answer: the page says so, and held
turns stay on disk for when it is back. The page does not open the
holds file itself, because listing it drops the expired ones, and that
is the door's to do.

THE OWNER'S WORDS ON THE OWNER'S PAGE, NOBODY ELSE'S. Every run is
listed -- who, which agent, when, what it cost, which tools it called
and which were refused -- because that is what an owner watching a bill
or an agent needs. But what a person typed and what the agent said back
is theirs: a run's ``message`` and ``reply`` are on the page only for the
owner's own runs (``--as``). The ledger holds everyone's words; this
page does not put them on a screen. The same for how to reach someone:
channels are listed by kind (``telegram``), never by their id.

FILES BY NAME FOR EVERYONE, OPENED ONLY FOR THE OWNER. Each person has a
folder per agent (``state/work/<person>/<agent>``). The page lists every
folder's files -- name, size, when it changed -- because an owner with a
full disk needs to know whose it is. It opens only the owner's own, with
the same walls as ``/file`` in the chat (files.py): a name that leaves
the folder, or starts with a dot, is not found.

SCHEDULES IN SAMAY'S WORDS. Each person's schedules come from ``samay
list --json`` (the ``samay`` program: ``--samay``, ``$DVARA_SAMAY``, or
on PATH), shown as Samay's own sentence with the next time and how the
last run ended. What a schedule asks the agent to do is the person's
words, so like a run's message it is on the page for the owner's own
schedules only. Changing a schedule is Samay's page, linked from here.

UNPRICED IS COUNTED, NOT ROUNDED. A turn on a local model has no price,
and spending says how many such turns there were rather than adding
them as $0.00 (runs.py, money.py).

A TOKEN, ALWAYS, and it is not ``DVARA_TOKEN``. A write also has to say
it comes from the page itself (``Origin``), on top of the token. Every ``/api`` call
carries the page's own token: ``$DVARA_PAGE_TOKEN``, or one made once
and kept in the state folder (readable by you alone), printed after a
``#`` in the address -- the part a browser never sends to a server. The
door's token can speak as anyone in the actors file, so it never goes to
a browser.

NOTHING RUNS INLINE. Three static files, a policy that allows scripts
only from the page's own address, every value drawn as text, and
``frame-ancestors 'self'``: no other site can frame it.

LOCALHOST BY DEFAULT; ``--host`` is a decision, as it is for ``serve``.

Standard library only, as Samay's and Setu's pages are: the FastAPI in
``http.py`` is an optional extra for the door, and a page that only
reads should not need it.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import httpx

from dvara import files as person_files
from dvara import money
from dvara.actors import OWN_SETU, Actor, ActorBook
from dvara.errors import ConfigProblem
from dvara.roster import Roster
from dvara.runs import Run, RunStore
from dvara.status import report

DEFAULT_PORT = 8785
ENV_TOKEN = "DVARA_PAGE_TOKEN"
TOKEN_FILE = "page.token"
MAX_RUNS = 500
MAX_BODY = 64 * 1024
ENV_DOOR = "DVARA_URL"
#: A held turn answered runs the rest of the turn: minutes, on a slow model.
RESUME_TIMEOUT = 600.0
#: The most files listed for one folder; the rest are counted.
FILES_AT_MOST = 200
#: The most of one file the page shows.
SHOW_AT_MOST = 256 * 1024
ENV_SAMAY = "DVARA_SAMAY"

STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/page.js": ("page.js", "text/javascript; charset=utf-8"),
          "/page.css": ("page.css", "text/css; charset=utf-8"),
          "/favicon.svg": ("favicon.svg", "image/svg+xml")}

POLICY = ("default-src 'none'; script-src 'self'; style-src 'self'; "
          "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
          "form-action 'none'; frame-ancestors 'self'")


def page_token(state: Path) -> str:
    """``$DVARA_PAGE_TOKEN``, or the one kept in the state folder (made once)."""
    configured = os.environ.get(ENV_TOKEN, "").strip()
    if configured:
        if len(configured) < 16:
            raise ConfigProblem(f"{ENV_TOKEN} must be at least 16 characters")
        return configured
    path = state / TOKEN_FILE
    try:
        kept = path.read_text().strip()
        if len(kept) >= 16:
            return kept
    except OSError:
        pass
    token = secrets.token_urlsafe(24)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(token + "\n")
    return token


class ApiError(Exception):
    def __init__(self, code: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class Door:
    """The running ``dvara serve``, asked as the owner and as nobody else.

    ``url`` is where it answers (``--door``, ``$DVARA_URL``, or what
    ``dvara status`` says it is serving at); ``token`` is ``DVARA_TOKEN``.
    Either missing is a reason, said on the page, not an error.
    """

    def __init__(self, owner: str, url: str | None, token: str | None,
                 *, transport: httpx.BaseTransport | None = None) -> None:
        self.owner = owner
        self.url = url.rstrip("/") if url else None
        self.token = token or None
        self._transport = transport

    def why_not(self) -> str | None:
        if self.url is None:
            return "the door isn't running, so nothing is waiting on an answer now"
        if self.token is None:
            return "to answer from here, start dvara page with DVARA_TOKEN set (the door's token)"
        return None

    def _call(self, method: str, path: str, *, body: dict | None = None,
              timeout: float = 10.0) -> tuple[int, dict]:
        with httpx.Client(transport=self._transport, timeout=timeout) as http:
            res = http.request(method, f"{self.url}{path}", json=body,
                               headers={"Authorization": f"Bearer {self.token}"})
        try:
            data = res.json()
        except ValueError:
            data = {"detail": res.text[:200]}
        return res.status_code, data if isinstance(data, dict) else {}

    def waiting(self) -> dict[str, Any]:
        why = self.why_not()
        if why is not None:
            return {"door": {"reachable": False, "why": why}, "asks": [], "holds": []}
        try:
            who = quote(self.owner, safe="")
            code_a, asks = self._call("GET", f"/asks?actor={who}")
            code_h, holds = self._call("GET", f"/holds?actor={who}")
        except httpx.HTTPError as exc:
            return {"door": {"reachable": False,
                             "why": f"the door at {self.url} didn't answer ({type(exc).__name__})"},
                    "asks": [], "holds": []}
        if code_a == 401 or code_h == 401:
            return {"door": {"reachable": False,
                             "why": "the door refused DVARA_TOKEN: it isn't the door's token"},
                    "asks": [], "holds": []}
        # the door was asked for the owner; it is checked again here, since
        # somebody else's question must never reach this page
        return {"door": {"reachable": True, "why": None},
                "asks": [a for a in asks.get("asks", []) if a.get("actor") == self.owner],
                "holds": [h for h in holds.get("holds", []) if h.get("actor") == self.owner]}

    def answer(self, ask_id: str, approve: bool) -> tuple[int, dict]:
        return self._call("POST", f"/asks/{quote(ask_id, safe='')}",
                          body={"actor": self.owner, "approve": approve})

    def carry_on(self, hold_id: str, answers: dict[str, bool | str]) -> tuple[int, dict]:
        return self._call("POST", f"/holds/{quote(hold_id, safe='')}",
                          body={"actor": self.owner, "answers": answers},
                          timeout=RESUME_TIMEOUT)


class Api:
    """What each endpoint does, apart from HTTP -- so tests can call it
    straight, and the handler below stays a thin skin."""

    def __init__(self, *, root: Path, actors: Path, state: Path, owner: str,
                 now=None, door: Door | None = None, samay: str | None = None) -> None:
        self.root, self.actors, self.state = root, actors, state
        self.owner = owner
        #: The samay program to read schedules with (None: found on PATH).
        self.samay = samay
        self._door = door
        self._now = now or (lambda: datetime.now(UTC))
        self._runs: RunStore | None = None
        # an owner who is not in the file is a typo, said at start
        if owner not in self._book().ids():
            raise ConfigProblem(f"--as {owner!r} is not in {actors}: the page shows "
                                "the owner's own runs, so it needs to know who that is")

    def _book(self) -> ActorBook:
        # read on every request: the door re-reads it without a restart,
        # and the page should not show yesterday's household
        return ActorBook.from_toml(self.actors)

    @property
    def runs(self) -> RunStore:
        if self._runs is None:
            self._runs = RunStore(self.state / "runs.sqlite3")
        return self._runs

    def close(self) -> None:
        if self._runs is not None:
            self._runs.close()

    @property
    def door(self) -> Door:
        """The door to answer through: the one given, or the one serving
        now (asked each time: it may have started since the page did)."""
        if self._door is not None:
            return self._door
        url = os.environ.get(ENV_DOOR, "").strip() or None
        if url is None:
            url = report(root=self.root, actors=self.actors, state=self.state)["url"]
        return Door(self.owner, url, os.environ.get("DVARA_TOKEN", "").strip())

    def handle(self, method: str, path: str, query: dict[str, list[str]],
               body: dict | None = None) -> tuple[int, dict[str, Any]]:
        parts = [p for p in path.split("/") if p][1:]      # after "api"
        if method == "POST" and len(parts) == 2 and parts[0] in ("asks", "holds"):
            return self._answer(parts[0], parts[1], body or {})
        if method != "GET":
            raise ApiError(405, "the page changes nothing but your own answers")
        if parts == ["waiting"]:
            return 200, self.door.waiting()
        if parts == ["status"]:
            return 200, self.status()
        if parts == ["people"]:
            return 200, {"people": self.people()}
        if parts == ["agents"]:
            return 200, {"agents": self.agents()}
        if parts == ["runs"]:
            actor = (query.get("actor") or [None])[0] or None
            agent = (query.get("agent") or [None])[0] or None
            limit = _int((query.get("limit") or ["50"])[0], "limit")
            return 200, {"runs": self.recent(actor, agent, max(1, min(limit, MAX_RUNS)))}
        if parts == ["files"]:
            return 200, {"folders": self.folders()}
        if parts == ["file"]:
            return 200, self.open_file((query.get("agent") or [""])[0],
                                       (query.get("path") or [""])[0])
        if parts == ["schedules"]:
            return 200, self.schedules()
        raise ApiError(404, f"no such endpoint: GET /api/{'/'.join(parts)}")

    def _answer(self, kind: str, item: str, body: dict) -> tuple[int, dict[str, Any]]:
        if not item.replace("-", "").replace("_", "").isalnum():
            raise ApiError(400, "that is not an id")
        door = self.door
        if (why := door.why_not()) is not None:
            raise ApiError(409, why)
        approve, answers = body.get("approve"), body.get("answers")
        # ONLY A JSON BOOLEAN APPROVES (http.py): "no" is not a yes
        if kind == "asks" and not isinstance(approve, bool):
            raise ApiError(400, "approve must be true or false")
        if kind == "holds" and (not isinstance(answers, dict) or not answers or not all(
                isinstance(v, bool | str) for v in answers.values())):
            raise ApiError(400, "answers maps each waiting call's id to true, false, "
                                "or a reason")
        try:
            code, data = (door.answer(item, approve) if kind == "asks"
                          else door.carry_on(item, answers))
        except httpx.HTTPError as exc:
            raise ApiError(502, f"the door didn't answer ({type(exc).__name__})") from None
        if code >= 400:
            raise ApiError(code, str(data.get("detail") or "the door refused it"))
        return 200, data

    def status(self) -> dict[str, Any]:
        data = report(root=self.root, actors=self.actors, state=self.state)
        return {"format": "dvara.page.status.v1", "version": data["version"],
                "owner": self.owner, "serving": data["serving"], "url": data["url"],
                "since": (data["running"] or {}).get("since"),
                "state": data["state"], "agents": len(data["agents"]),
                "people": data["people"], "problems": data["problems"]}

    def people(self) -> list[dict[str, Any]]:
        book = self._book()
        today = money.day_start(self._now())
        week = today - timedelta(days=6)
        return [self._person(book.get(i), today, week) for i in book.ids()]

    def _person(self, actor: Actor, today: datetime, week: datetime) -> dict[str, Any]:
        spent = self.runs.spent_since(actor.id, today)
        turns, unpriced = self.runs.turns_since(actor.id, today)
        week_turns, week_unpriced = self.runs.turns_since(actor.id, week)
        return {
            "id": actor.id,
            "owner": actor.id == self.owner,
            "agents": list(actor.agents) if actor.agents is not None else None,
            "permissions": actor.permissions,
            # kinds only: an id is how to reach somebody, not the owner's to show
            "channels": sorted({c.kind for c in actor.channels}),
            "accounts": ("own folder" if actor.setu == OWN_SETU
                         else "shared folder" if actor.setu else None),
            "allowance": {"per_day": actor.max_usd_per_day,
                          "per_turn": actor.max_usd_per_turn,
                          "wait_per_day": actor.max_wait_per_day},
            "today": {"spent": spent, "turns": turns, "unpriced": unpriced,
                      "left": money.remaining_today(actor.max_usd_per_day, spent),
                      "resets": money.next_reset(self._now()).isoformat()},
            "week": {"spent": self.runs.spent_since(actor.id, week),
                     "turns": week_turns, "unpriced": week_unpriced},
        }

    # ---- files and schedules -------------------------------------------------------

    def folders(self) -> list[dict[str, Any]]:
        """Each person's folder per agent: the files in it, newest first."""
        work = self.state / "work"
        out = []
        for person in self._book().ids():
            base = work / person
            agents = sorted(p for p in base.iterdir() if p.is_dir()) \
                if base.is_dir() else []
            for folder in agents:
                if folder.name.startswith("."):
                    continue
                found = person_files._theirs(folder)
                rows = []
                for path in found[:FILES_AT_MOST]:
                    st = path.stat()
                    rows.append({"path": str(path.relative_to(folder)), "size": st.st_size,
                                 "modified": datetime.fromtimestamp(st.st_mtime, UTC)
                                 .isoformat(timespec="seconds")})
                out.append({"person": person, "agent": folder.name,
                            "owner": person == self.owner, "files": rows,
                            "count": len(found),
                            "bytes": sum(p.stat().st_size for p in found)})
        return out

    def open_file(self, agent: str, path: str) -> dict[str, Any]:
        """One of the owner's own files, as text -- nobody else's."""
        if not agent or "/" in agent or agent.startswith("."):
            raise ApiError(404, "no such file")
        found = person_files.pick(self.state / "work" / self.owner / agent, path)
        if found is None:
            raise ApiError(404, "no such file")
        size = found.stat().st_size
        with found.open("rb") as handle:
            data = handle.read(SHOW_AT_MOST)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        return {"agent": agent, "path": path, "size": size,
                "text": text, "binary": text is None, "truncated": size > SHOW_AT_MOST}

    def schedules(self) -> dict[str, Any]:
        """Each person's schedules, as Samay says them."""
        import shutil
        import subprocess

        program = self.samay or os.environ.get(ENV_SAMAY) or shutil.which("samay")
        if not program:
            return {"samay": {"found": False, "why": "Samay isn't on this computer "
                              "(start dvara page with --samay PATH to name it)",
                              "page": None}, "schedules": []}
        try:
            listed = subprocess.run([program, "list", "--json"], capture_output=True,
                                    text=True, timeout=30)
            cards = json.loads(listed.stdout) if listed.returncode == 0 else None
            status = subprocess.run([program, "status", "--json"], capture_output=True,
                                    text=True, timeout=30)
            page = (json.loads(status.stdout) or {}).get("url") \
                if status.returncode == 0 else None
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {"samay": {"found": False, "page": None,
                              "why": f"Samay didn't answer ({type(exc).__name__})"},
                    "schedules": []}
        if not isinstance(cards, list):
            why = (listed.stderr or "").strip().splitlines()[-1:] or ["no answer"]
            return {"samay": {"found": False, "page": None,
                              "why": f"Samay didn't list its schedules: {why[0]}"},
                    "schedules": []}
        people = set(self._book().ids())
        rows = []
        for card in cards:
            person = card.get("owner") if isinstance(card, dict) else None
            if person not in people:
                continue           # somebody this door does not serve
            last = card.get("last_run") or {}
            rows.append({
                # a direct-road schedule names its package by path: the name is enough
                "id": card.get("id"), "person": person,
                "agent": Path(str(card.get("agent") or "")).name,
                "sentence": card.get("sentence") or "", "state": card.get("state") or "",
                "paused_because": card.get("paused_because") or "",
                "next_at": card.get("next_at"),
                "last": ({"outcome": last.get("outcome"),
                          "at": last.get("ended_at") or last.get("due_at")}
                         if last else None),
                # what it asks the agent to do is the person's own words
                "prompt": card.get("prompt") if person == self.owner else None,
            })
        rows.sort(key=lambda r: (r["person"] != self.owner, r["person"],
                                 r["next_at"] or "~"))
        return {"samay": {"found": True, "why": None, "page": page}, "schedules": rows}

    def agents(self) -> list[dict[str, Any]]:
        try:
            roster = Roster(self.root)
            names = roster.names()
        except ConfigProblem:
            return []
        book = self._book()
        return [{"name": name,
                 "people": [i for i in book.ids() if book.get(i).may_use(name)]}
                for name in names]

    def recent(self, actor: str | None, agent: str | None, limit: int
               ) -> list[dict[str, Any]]:
        return [self._run(r) for r in self.runs.recent(actor=actor, agent=agent,
                                                       limit=limit)]

    def _run(self, run: Run) -> dict[str, Any]:
        mine = run.actor == self.owner
        return {
            "id": run.id, "actor": run.actor, "agent": run.agent,
            "started_at": run.started_at.isoformat(),
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "stop_reason": run.stop_reason, "ok": run.ok, "model": run.model,
            "cost_usd": run.cost_usd, "unattended": run.unattended,
            "waited_seconds": run.waited_seconds, "resumes": run.resumes,
            "tools": [{"name": s.name, "refusal": s.refusal} for s in run.tools],
            # the owner's own words, and nobody else's
            "message": run.message if mine else None,
            "reply": run.reply if mine else None,
            "detail": run.detail if mine else None,
        }


def _int(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"{name} must be a whole number") from None


class PageServer:
    """The API and the page, until stopped."""

    def __init__(self, api: Api, token: str, *, host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT) -> None:
        self.api = api
        self.token = token
        self.httpd = ThreadingHTTPServer((host, port), _handler(self))
        self.httpd.daemon_threads = True
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{port}/"

    @property
    def page_url(self) -> str:
        return f"{self.url}#token={self.token}"

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        name="dvara-page", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread is not None:
            self._thread.join()
        self.api.close()


def _handler(server: PageServer):
    # no lock here: the ledger holds its own, and a held turn carried on can
    # take minutes -- the rest of the page must not wait behind it

    class Handler(BaseHTTPRequestHandler):
        server_version = "dvara-page"

        def log_message(self, *_a: Any) -> None:
            pass

        def _send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", POLICY)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data: dict[str, Any]) -> None:
            self._send(code, json.dumps(data).encode(), "application/json")

        def _dispatch(self, method: str) -> None:
            url = urlparse(self.path)
            if method == "GET" and url.path in STATIC:
                name, kind = STATIC[url.path]
                return self._send(200, files("dvara").joinpath("static", name).read_bytes(),
                                  kind)
            if not url.path.startswith("/api/"):
                return self._json(404, {"detail": "not found"})
            offered = self.headers.get("Authorization", "")
            if not hmac.compare_digest(offered.encode(), f"Bearer {server.token}".encode()):
                return self._json(401, {"detail": "missing or wrong token"})
            body: dict = {}
            if method == "POST":
                origin = self.headers.get("Origin")
                if origin is not None and urlparse(origin).netloc != self.headers.get("Host"):
                    return self._json(403, {"detail": "an answer comes from this page only"})
                size = int(self.headers.get("Content-Length") or 0)
                if size > MAX_BODY:
                    return self._json(413, {"detail": "request too large"})
                try:
                    body = json.loads(self.rfile.read(size) or b"{}")
                except json.JSONDecodeError:
                    return self._json(400, {"detail": "the body is not JSON"})
                if not isinstance(body, dict):
                    return self._json(400, {"detail": "the body is a JSON object"})
            try:
                code, data = server.api.handle(method, url.path, parse_qs(url.query), body)
            except ApiError as exc:
                return self._json(exc.code, {"detail": exc.detail})
            except (ConfigProblem, ValueError) as exc:     # a broken actors file, said
                return self._json(500, {"detail": str(exc)})
            except Exception as exc:     # a bug is a 500 that says what, not a hang
                return self._json(500, {"detail": f"{type(exc).__name__}: {exc}"})
            self._json(code, data)

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

    return Handler

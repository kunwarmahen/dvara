"""What happens with nobody writing (Service.chores): a look back over a
conversation gone quiet, a daily check of every sign-in, and a person's
schedules moved when their time zone changes.

The bias these tests encode: AN UNASKED MESSAGE THAT IS NOT NEWS. Both
chores write to a person nobody asked to hear from, so a look back that
found nothing must say nothing -- unless the model kept something itself
while they talked, which the look back then names once instead of
falling silent on it -- a conversation looked back over must not
be looked back over again until they write, a refused sign-in is
told once, to whoever can fix it -- never to somebody who can't, never
twice, and a first look at someone's zone is not a move. The other bias
is a look back that ENDS the conversation: unlike /new, the quiet one
keeps it.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from dvara import signins
from dvara.actors import ActorBook
from dvara.gate import Policy
from dvara.keys import session_key
from tests.conftest import calls, says

REMEMBERING = ('[agent]\nname = "greeter"\nprompt = "prompt.md"\n'
               '[memory]\nvia = "local"\n')
LOOKED = "fact: Lives in Pune (Asia/Kolkata time)"


@pytest.fixture(autouse=True)
def own_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("YANTRA_USER", "the-machine")


def people(**extra):
    owner = {"channel": [{"kind": "telegram", "id": "42"}], **extra}
    return ActorBook.from_dict({"actor": {"owner": owner}})


def listening(service):
    got: list[str] = []

    async def sender(address, text):
        got.append(text)
    service.notices.route("telegram", sender)
    return got


def later(minutes):
    return datetime.now(UTC) + timedelta(minutes=minutes)


class TestAQuietConversation:

    def test_it_is_looked_back_over_once_and_the_person_told(self, make_service,
                                                             agents_root):
        (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
        service = make_service([says("Pune is lovely."), says(LOOKED)], actors=people())
        got = listening(service)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                    text="I live in Pune"))
        assert asyncio.run(service.look_back_quiet(later(10))) == 0     # not quiet yet
        assert asyncio.run(service.look_back_quiet(later(31))) == 1
        assert len(got) == 1 and "1. Lives in Pune" in got[0] and "/remember" in got[0]
        assert "Looking back over our conversation" in got[0] and "started over" not in got[0]
        assert asyncio.run(service.look_back_quiet(later(45))) == 0     # once
        # the conversation is still there to carry on
        assert service.sessions.load_latest(session_key("owner", "greeter", "chat"))

    def test_a_look_back_that_found_nothing_sends_nothing(self, make_service, agents_root):
        (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
        service = make_service([says("hi"), says("nothing worth keeping")],
                               actors=people())
        got = listening(service)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                    text="hello"))
        assert asyncio.run(service.look_back_quiet(later(31))) == 1
        assert got == []
        assert service.runs.recent()[0].stop_reason == "looked_back"

    def test_a_package_that_keeps_no_memories_asks_no_model(self, make_service):
        service = make_service([says("hi")], actors=people())
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                    text="hello"))
        asyncio.run(service.look_back_quiet(later(31)))
        assert len(service.scripted.requests) == 1

    def test_zero_turns_it_off(self, make_service, agents_root):
        (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
        service = make_service([says("hi")], actors=people(), quiet_for=0)
        asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                    text="hello"))
        assert asyncio.run(service.look_back_quiet(later(600))) == 0


def stand_in_setu(tmp_path, rows):
    program = tmp_path / "setu"
    program.write_text("#!/bin/sh\ncat <<'EOF'\n" + json.dumps({"checked": rows})
                       + "\nEOF\n")
    program.chmod(0o755)
    return str(program)


GONE = {"ref": "gmail:work", "connector": "gmail", "account": "work",
        "email": "me@work.test", "state": "expired",
        "since": "2026-10-11T08:00:00+00:00", "why": "invalid_grant"}


class TestARefusedSignIn:

    def test_it_is_told_once_with_the_words_that_fix_it(self, make_service, tmp_path):
        service = make_service(actors=people(setu=True))
        (service.state / "setu" / "owner").mkdir(parents=True, exist_ok=True)
        service.accounts.setu = stand_in_setu(tmp_path, [GONE])
        got = listening(service)
        assert asyncio.run(service.check_sign_ins()) == 1
        assert got == ["Your gmail sign-in (me@work.test) stopped working on 2026-10-11: "
                       "the site refused it. Send /connect gmail as work to sign in again."]
        assert asyncio.run(service.check_sign_ins()) == 0               # not twice

    def test_back_and_refused_again_is_news(self, tmp_path):
        told = signins.Told(tmp_path)
        gone = signins.Expired("gmail:work", "gmail", "work", "", "2026-10-11", "x")
        assert told.news(tmp_path / "f", [gone]) == [gone]
        assert told.news(tmp_path / "f", []) == []                      # signed in again
        assert told.news(tmp_path / "f", [gone]) == [gone]

    def test_a_shared_folder_nobody_manages_is_a_line_for_the_owner(
            self, make_service, tmp_path, capsys):
        shared = tmp_path / "owners-setu"
        shared.mkdir()
        service = make_service(actors=people(setu=str(shared)))
        service.accounts.setu = stand_in_setu(tmp_path, [GONE])
        got = listening(service)
        assert asyncio.run(service.check_sign_ins()) == 0
        assert got == []
        assert "setu connect gmail --as work" in capsys.readouterr().err

    def test_nothing_refused_tells_nobody(self, make_service, tmp_path):
        service = make_service(actors=people(setu=True))
        (service.state / "setu" / "owner").mkdir(parents=True, exist_ok=True)
        service.accounts.setu = stand_in_setu(tmp_path, [{**GONE, "state": "ok"}])
        got = listening(service)
        assert asyncio.run(service.check_sign_ins()) == 0 and got == []


def test_new_after_a_quiet_look_back_lists_without_asking_again(make_service, agents_root):
    (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
    service = make_service([says("ok"), says(LOOKED)], actors=people())
    listening(service)
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                text="I live in Pune"))
    asyncio.run(service.look_back_quiet(later(31)))
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                        text="/new"))
    assert "1. Lives in Pune" in reply.text
    assert len(service.scripted.requests) == 2          # the turn and one look back


def test_what_the_model_kept_unasked_is_said_under_the_answer_and_at_the_look_back(
        make_service, agents_root):
    (agents_root / "greeter" / "agent.toml").write_text(
        REMEMBERING + '[permissions]\nmode = "yolo"\n')
    service = make_service([calls("remember", {"statement": "Lives in Cary, NC"}),
                            says("Saved."), says("Nothing new here.")],
                           actors=people(permissions="yolo"),
                           policy=Policy(mode="yolo"))
    got = listening(service)
    reply = asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                        text="I live in Cary"))
    assert "(Kept about you: Lives in Cary, NC -- /memory forget " in reply.text
    assert "I noticed" not in reply.text
    assert service.runs.kept_since_look_back("owner", "greeter", "chat") == [
        "Lives in Cary, NC"]
    assert asyncio.run(service.look_back_quiet(later(31))) == 1
    assert len(got) == 1 and "Already kept while we talked:\n- Lives in Cary, NC" in got[0]
    # told once: the look back is the line the next quiet spell starts after
    assert service.runs.kept_since_look_back("owner", "greeter", "chat") == []


def test_a_look_back_with_nothing_new_and_nothing_kept_still_says_nothing(
        make_service, agents_root):
    (agents_root / "greeter" / "agent.toml").write_text(REMEMBERING)
    service = make_service([says("ok"), says("Nothing new here.")], actors=people())
    got = listening(service)
    asyncio.run(service.deliver(actor="owner", agent="greeter", thread="chat",
                                text="hello"))
    assert asyncio.run(service.look_back_quiet(later(31))) == 1
    assert got == []


class TestANoticeOnAPhone:
    """ntfy (push.py). The bias: A TOPIC SOMEBODY ELSE COULD READ -- each
    person's is their own, unguessable without the owner's key, and the
    same every time so their phone stays subscribed."""

    def test_each_person_has_their_own_steady_unguessable_topic(self, tmp_path):
        from dvara import push
        mine = push.topic(tmp_path, "priya")
        assert mine == push.topic(tmp_path, "priya") != push.topic(tmp_path, "ravi")
        assert mine.startswith("dvara-priya-") and len(mine.rsplit("-", 1)[1]) == 16
        assert push.topic(tmp_path / "other", "priya") != mine          # another key
        assert oct((tmp_path / push.KEY_FILE).stat().st_mode)[-3:] == "600"

    def test_a_notice_is_posted_to_their_topic_on_the_houses_server(self, make_service):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        heard = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode()
                heard.append((self.path, body, self.headers.get("Click")))
                self.send_response(200)
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            service = make_service(actors=people(), ntfy=f"http://127.0.0.1:"
                                   f"{server.server_address[1]}", ntfy_click="http://home/")
            _, sent = asyncio.run(service.notify(actor="owner", text="2 new mails"))
            assert "ntfy" in sent.sent
            assert heard == [(f"/{service.push.topic('owner')}", "2 new mails",
                              "http://home/")]
        finally:
            server.shutdown()
            server.server_close()

    def test_a_skill_offered_has_keep_and_not_now_that_carry_no_key(self, make_service):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        heard = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_POST(self):
                heard.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            service = make_service(actors=people(), ntfy=f"http://127.0.0.1:"
                                   f"{server.server_address[1]}",
                                   ntfy_click="http://house:8760/#chat")
            offer = {"offer": {"id": "4638", "agent": "minder", "name": "folio", "test": "-"}}
            asyncio.run(service.notify(actor="owner", text="Keep it?", extra=offer))
            [(path, raw)] = heard
            posted = json.loads(raw)
            assert path == "/" and posted["topic"] == service.push.topic("owner")
            keep, drop = posted["actions"]
            assert (keep["label"], drop["label"]) == ("Keep", "Not now")
            assert keep["url"] == "http://house:8760/api/push/answer"
            said = json.loads(keep["body"])
            assert said["word"] == "keep" and said["offer"] == "4638"
            assert "token" not in raw.decode().lower()
        finally:
            server.shutdown()
            server.server_close()

    def test_a_press_is_taken_only_with_the_mark_made_for_exactly_it(self, make_service):
        from fastapi.testclient import TestClient

        from dvara import push
        from dvara.http import create_app

        service = make_service(actors=people(), web=True, ntfy="http://127.0.0.1:9",
                               ntfy_click="http://house:8760/")
        token = "a-token-long-enough-to-be-real"
        auth = {"Authorization": f"Bearer {token}"}
        good = push.mark(service.state, "owner", "greeter", "4638", "keep")
        press = {"actor": "owner", "agent": "greeter", "offer": "4638", "word": "keep"}
        with TestClient(create_app(service, token=token)) as client:
            for wrong in ({**press, "mark": "0" * 32},
                          {**press, "offer": "9999", "mark": good},     # another offer
                          {**press, "word": "drop", "mark": good},      # another word
                          {**press, "actor": "ravi", "mark": good}):    # another person
                assert client.post("/push/answer", headers=auth, json=wrong).status_code == 403
            assert client.post("/push/answer", json={**press, "mark": good}).status_code == 401
            ok = client.post("/push/answer", headers=auth, json={**press, "mark": good})
            assert ok.status_code == 200
            lines = client.get("/web?actor=owner", headers=auth).json()["lines"]
            assert lines[0]["text"] == "/skills keep 4638"


SAMAY = """#!/bin/sh
echo "$@" >> "$(dirname "$0")/asked"
[ -f "$(dirname "$0")/down" ] && { echo "error: the clock is busy" >&2; exit 2; }
echo '{"moved": [{"prompt": "the weather",' \\
     '"sentence": "every day at 08:00 -- next: ... (Europe/London)"}]}'
"""


class TestMoving:
    """Their zone changes in the actors file while the service runs."""

    @staticmethod
    def zoned(tmp_path, zone):
        path = tmp_path / "actors.toml"
        line = f'zone = "{zone}"\n' if zone else ""
        path.write_text('[actor.owner]\n' + line +
                        '[[actor.owner.channel]]\nkind = "telegram"\nid = "42"\n')
        return path

    @pytest.fixture
    def samay(self, tmp_path):
        program = tmp_path / "bin" / "samay"
        program.parent.mkdir()
        program.write_text(SAMAY)
        program.chmod(0o755)
        return program

    def test_a_move_takes_their_schedules_and_tells_them_once(self, make_service, tmp_path,
                                                              samay):
        path = self.zoned(tmp_path, "America/New_York")
        service = make_service(actors=ActorBook.from_toml(path), samay=str(samay))
        got = listening(service)
        assert asyncio.run(service.follow_zones()) == 0             # first look: written down
        assert not (samay.parent / "asked").exists() and got == []
        self.zoned(tmp_path, "Europe/London")
        assert asyncio.run(service.follow_zones()) == 1
        assert (samay.parent / "asked").read_text().split() == [
            "zone", "owner", "--from", "America/New_York", "--to", "Europe/London", "--json"]
        assert got == ["Your time zone is now Europe/London, so your schedules moved with "
                       "you:\n• the weather: every day at 08:00 -- next: ... (Europe/London)\n"
                       "Any schedule you set in another time zone on purpose stays where it is."]
        assert asyncio.run(service.follow_zones()) == 0             # not twice

    def test_no_zone_is_this_machines_and_a_failed_move_is_tried_again(
            self, make_service, tmp_path, samay, capsys):
        path = self.zoned(tmp_path, "")
        service = make_service(actors=ActorBook.from_toml(path), samay=str(samay))
        asyncio.run(service.follow_zones())
        (samay.parent / "down").write_text("")
        self.zoned(tmp_path, "Asia/Tokyo")
        assert asyncio.run(service.follow_zones()) == 0
        assert "didn't move -- error: the clock is busy" in capsys.readouterr().err
        (samay.parent / "down").unlink()
        assert asyncio.run(service.follow_zones()) == 1             # the next tick
        asked = (samay.parent / "asked").read_text().splitlines()
        assert asked[-1].split() == ["zone", "owner", "--from", "--to", "Asia/Tokyo", "--json"]

    def test_with_schedules_off_nothing_is_asked(self, make_service, tmp_path):
        service = make_service(actors=people(zone="Asia/Tokyo"))
        assert asyncio.run(service.follow_zones()) == 0
        assert not (service.state / "zones.json").exists()

"""`dvara status`: is the door open, asked of the lock and nothing else.

The bias here is a status that answers from something that can go stale.
A lock file outlives the process that wrote it -- SIGKILL, a crash, a
container stopped -- and its pid may by then be somebody else's. So the
tests hold the claim for real, let it go, and check the answer follows
the LOCK while the file stays exactly where it was.

And asking must not start anything: no state directory made, no ledger
opened, no claim taken that would refuse the next `dvara serve`.
"""

from __future__ import annotations

import json

from dvara.claim import Claim, holder
from dvara.cli import CLAIMS, main
from dvara.status import FORMAT, report


def _actors(tmp_path):
    path = tmp_path / "actors.toml"
    path.write_text("[actor.owner]\n[actor.guest]\n", encoding="utf-8")
    return path


def test_a_lock_file_nobody_holds_is_not_a_running_service(tmp_path):
    state = tmp_path / "state"
    claim = Claim(state)
    claim.take("dvara serve", at="http://127.0.0.1:8765")
    assert holder(state)["at"] == "http://127.0.0.1:8765"
    claim.release()
    assert (state / "dvara.lock").read_text().startswith("pid ")
    assert holder(state) is None


def test_a_served_door_says_where_it_listens(tmp_path, agents_root):
    state = tmp_path / "state"
    claim = Claim(state)
    claim.take("dvara serve", at="http://0.0.0.0:8765")
    try:
        data = report(root=agents_root, actors=_actors(tmp_path), state=state)
    finally:
        claim.release()
    assert data["format"] == FORMAT
    assert data["serving"] is True
    assert data["url"] == "http://0.0.0.0:8765"
    assert data["running"]["command"] == "dvara serve"
    assert data["people"] == 2
    assert data["agents"]


def test_a_turn_at_the_keyboard_is_busy_but_not_serving(tmp_path, agents_root):
    """`dvara say` holds the claim too; nobody else can reach it."""
    state = tmp_path / "state"
    claim = Claim(state)
    claim.take("dvara say")
    try:
        data = report(root=agents_root, actors=_actors(tmp_path), state=state)
    finally:
        claim.release()
    assert data["running"]["command"] == "dvara say"
    assert data["serving"] is False and data["url"] is None


def test_a_broken_file_is_a_problem_in_words_not_a_failed_status(tmp_path):
    bad = tmp_path / "actors.toml"
    bad.write_text("[actor.owner\n", encoding="utf-8")
    data = report(root=tmp_path / "nowhere", actors=bad, state=tmp_path / "s")
    assert data["serving"] is False
    assert len(data["problems"]) == 2


def test_asking_makes_nothing_and_claims_nothing(tmp_path, agents_root, capsys):
    assert "status" not in CLAIMS
    state = tmp_path / "state"
    code = main(["--root", str(agents_root), "--actors", str(_actors(tmp_path)),
                 "--state", str(state), "status", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["running"] is None
    assert not state.exists()


def test_status_answers_while_the_service_holds_the_directory(tmp_path,
                                                              agents_root,
                                                              capsys):
    state = tmp_path / "state"
    claim = Claim(state)
    claim.take("dvara telegram")
    try:
        code = main(["--root", str(agents_root), "--actors",
                     str(_actors(tmp_path)), "--state", str(state), "status"])
    finally:
        claim.release()
    assert code == 0
    assert "serving (dvara telegram" in capsys.readouterr().out

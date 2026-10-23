"""`dvara keeps`: where the house's agents, people and talks are, for a backup.

The bias: A BACKUP OF A DOOR NOBODY RUNS. Sarathi asks with the folders
sarathi.toml names, so the places must be the ones given (--root,
--actors, --state), never the defaults; the rules file must be found
where the service finds it; and asking must not take the folder's claim
from a running dvara (it is answered before anything is opened).
"""

from __future__ import annotations

import json

from dvara.cli import main


def _ask(tmp_path, capsys, *more):
    assert main(["--root", str(tmp_path / "agents"), "--actors",
                 str(tmp_path / "actors.toml"), "--state", str(tmp_path / "state"),
                 *more, "keeps", "--json"]) == 0
    said = json.loads(capsys.readouterr().out)
    assert said["format"] == "dvara.keeps.v1"
    return {p["id"]: p for p in said["keeps"]}


def test_the_places_are_the_folders_it_was_given(tmp_path, capsys):
    (tmp_path / "actors.toml").write_text("")
    places = _ask(tmp_path, capsys)
    assert places["agents"]["path"] == str(tmp_path / "agents")
    assert places["actors"] == {**places["actors"], "path": str(tmp_path / "actors.toml"),
                                "exists": True}
    assert places["state"]["exists"] is False
    assert "policy" not in places               # there is none to keep


def test_the_rules_beside_the_actors_file_are_kept(tmp_path, capsys):
    (tmp_path / "policy.toml").write_text("[rules]\n")
    assert _ask(tmp_path, capsys)["policy"]["path"] == str(tmp_path / "policy.toml")


def test_rules_named_elsewhere_are_the_ones_kept(tmp_path, capsys):
    (tmp_path / "mine.toml").write_text("")
    places = _ask(tmp_path, capsys, "--policy", str(tmp_path / "mine.toml"))
    assert places["policy"]["path"] == str(tmp_path / "mine.toml")


def test_peoples_browser_caches_and_the_doors_lock_are_left_out(tmp_path, capsys):
    leave_out = set(_ask(tmp_path, capsys)["state"]["leave_out"])
    assert {"Cache", "Singleton*", "dvara.lock"} <= leave_out
    assert not {"setu", "past", "sessions.sqlite3", "household.json"} & leave_out


def test_asking_makes_no_folder(tmp_path, capsys):
    _ask(tmp_path, capsys)
    assert not (tmp_path / "state").exists()

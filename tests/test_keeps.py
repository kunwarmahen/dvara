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


# -- a new home ---------------------------------------------------------------------
# The bias: A RESTORED HOUSE THAT POINTS AT THE OLD COMPUTER. Each person's
# `setu =` and the sign-in marks name whole paths; on a new home every one is a
# folder that isn't there, and each person's Setu folder is Setu's to fix.


def _old_house(tmp_path):
    actors = tmp_path / "actors.toml"
    actors.write_text('# the house\n[actor.mahen]\nsetu = "/home/old/.local/state/setu"\n'
                      "[actor.asha]\nsetu = '/home/old/dvara/state/setu/asha'\n"
                      'note = "/home/older/x"\n')
    state = tmp_path / "state"
    (state / "setu" / "asha").mkdir(parents=True)
    (state / "setu" / "asha" / "vault.json").write_text("{}")
    (state / "signins.json").write_text(json.dumps(
        {"/home/old/.local/state/setu": {"google-personal": "2026-11-01"}}))
    setu = tmp_path / "setu"
    setu.write_text("#!/bin/sh\necho \"$SETU_HOME $*\" >> \"$0.log\"\n"
                    "echo '{\"rehomed\": [{\"file\": \"'$SETU_HOME'/vault.json\", "
                    "\"paths\": 3}]}'\n")
    setu.chmod(0o755)
    return actors, state, setu


def test_a_new_home_moves_dvaras_paths_and_asks_setu_for_each_persons(tmp_path, capsys):
    actors, state, setu = _old_house(tmp_path)
    assert main(["--root", str(tmp_path / "agents"), "--actors", str(actors), "--state",
                 str(state), "keeps", "--rehome", "/home/old", "/home/new",
                 "--setu", str(setu), "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rehomed"]
    assert [(r["file"].rsplit("/", 1)[1], r["paths"]) for r in rows] == [
        ("actors.toml", 2), ("signins.json", 1), ("vault.json", 3)]
    text = actors.read_text()
    assert text.startswith("# the house\n")                       # their comments kept
    assert 'setu = "/home/new/.local/state/setu"' in text
    assert "setu = '/home/new/dvara/state/setu/asha'" in text
    assert '"/home/older/x"' in text                             # not under /home/old
    assert list(json.loads((state / "signins.json").read_text())) == [
        "/home/new/.local/state/setu"]
    log = (tmp_path / "setu.log").read_text()
    assert log == f"{state}/setu/asha keeps --rehome /home/old /home/new --json\n"


def test_keeps_says_it_can_rehome_and_without_setu_it_says_why(tmp_path, capsys):
    from dvara.keeps import rehome, report
    assert report(tmp_path, tmp_path / "a.toml", tmp_path / "s", tmp_path / "p")["rehome"]
    actors, state, _ = _old_house(tmp_path)
    rows = rehome("/home/old", "/home/new", actors=actors, state=state,
                  policy=tmp_path / "policy.toml", setu=None)
    assert rows[-1]["problem"].startswith("setu isn't on this computer")

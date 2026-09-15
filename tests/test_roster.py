"""Bias: a package path that comes from a stranger is remote code execution.

Loading a package runs its Python at import time, as the invoking user,
before any permission gate exists. So the tests here are mostly about
names that are NOT names -- traversal, absolute paths, symlinks out of
the root -- plus the one property the whole design rests on: listing and
inspecting a package must not import anything.
"""

from __future__ import annotations

import pytest

from dvara.errors import ConfigProblem, Refused
from dvara.roster import Roster
from tests.conftest import write_package


def test_the_roster_lists_every_package_under_its_root(agents_root):
    write_package(agents_root, "researcher")
    assert Roster(agents_root).names() == ["greeter", "researcher"]


def test_a_directory_without_a_manifest_is_not_an_agent(agents_root):
    (agents_root / "notes").mkdir()
    assert "notes" not in Roster(agents_root).names()


def test_a_missing_root_is_the_owners_problem_not_a_refusal(tmp_path):
    # ConfigProblem, not Refused: nobody asked for this, and it must
    # never be answered into a channel as if a person caused it.
    with pytest.raises(ConfigProblem):
        Roster(tmp_path / "nowhere")


@pytest.mark.parametrize("name", [
    "../../etc", "..", "/etc/passwd", "greeter/../../x", "~", ".hidden", "",
    "green\nter", "a" * 200,
])
def test_a_name_that_is_really_a_path_is_refused(agents_root, name):
    with pytest.raises(Refused):
        Roster(agents_root).path(name)


def test_a_symlink_out_of_the_root_is_refused(tmp_path, agents_root):
    outside = tmp_path / "outside"
    write_package(outside, "secret")
    (agents_root / "secret").symlink_to(outside / "secret")
    # The name is perfectly well-formed; it is the RESOLVED path that is
    # not inside the root, which is the check a name pattern cannot make.
    with pytest.raises(Refused):
        Roster(agents_root).path("secret")


def test_an_unparseable_manifest_refuses_without_quoting_the_error(agents_root):
    write_package(agents_root, "broken", body="[agent]\nname = \n")
    with pytest.raises(Refused) as caught:
        Roster(agents_root).spec("broken")
    assert "unavailable" in str(caught.value)


def test_listing_and_inspecting_never_import_a_packages_code(agents_root):
    # The property dvara's whole security story depends on: a service can
    # survey a root full of strangers' packages without running any of
    # them. This one detonates at import time if it is ever imported.
    where = write_package(agents_root, "landmine", body=(
        '[agent]\nname = "landmine"\nprompt = "prompt.md"\n'
        '[tools]\ndirs = ["tools"]\n'
    ))
    (where / "tools").mkdir()
    (where / "tools" / "boom.py").write_text(
        "raise SystemExit('a package listing executed somebody else's code')\n"
    )
    roster = Roster(agents_root)
    assert "landmine" in roster.names()
    spec = roster.spec("landmine")          # parses the manifest...
    assert spec.tool_dirs                   # ...and merely NAMES the dir

"""Several phones, each one person's.

The bias these tests encode: A PERSON'S AGENT REACHES THEIR PHONES AND
NO OTHERS. With several phones named, a person's ``phones`` are all
their turns get -- Sparsh is started with only those -- and a phone
named under two people is a config error, not a guess. A schedule
works the phone it names, or their only one; one that names none for
a person with several is refused rather than run on whichever answers,
because a guess taps the wrong phone's apps. ``phone = true`` still
means every phone, and so leaves none for anyone else.

Sparsh here is test_phone's fake program, naming two phones.
"""

from __future__ import annotations

import asyncio
import json
import sys
import textwrap

import pytest

from dvara.actors import ActorBook
from dvara.errors import ConfigProblem, Refused
from dvara.phoneview import asked
from dvara.service import phone_for
from tests.conftest import says
from tests.test_phone import FAKE, logged, phone_tools

NAMED = FAKE.replace(
    '''"phones": [{{"serial": "emulator-5554", "state": "device",
                                     "model": "sdk_gphone64"}}],''',
    '''"phones": [{{"serial": "84B7N16128001616", "state": "device",
                                     "model": "Nexus_6P", "name": "nexus"}},
                                    {{"serial": "emulator-5554", "state": "device",
                                     "model": "sdk_gphone64", "name": "pixel"}}],
            "named": [{{"name": "nexus", "where": "84B7N16128001616", "kind": "Android"}},
                      {{"name": "pixel", "where": "emulator-5554", "kind": "Android"}}],''',
).replace('if args == ["state", "--json"]:', 'if args[:2] == ["state", "--json"]:',
          ).replace('if args == ["wake"]:', 'if args[:1] == ["wake"]:')
assert NAMED != FAKE

PEOPLE = ActorBook.from_dict({"actor": {
    "asha": {"phones": ["nexus"]},
    "ravi": {"phones": ["pixel"], "agents": ["greeter"]},
    "both": {"phones": ["nexus-2", "pixel-2"]},
}})


@pytest.fixture
def named_sparsh(tmp_path):
    log = tmp_path / "sparsh.log"
    program = tmp_path / "sparsh"
    program.write_text(f"#!{sys.executable}\n"
                       + textwrap.dedent(NAMED).format(log=str(log), python=sys.executable))
    program.chmod(0o755)
    return program, log


class TestWhoseIsWhich:
    def test_a_phone_under_two_people_is_an_error_naming_both(self):
        with pytest.raises(ConfigProblem, match=r"'nexus' is in phones for both "
                                                r"\[actor.a\] and \[actor.b\]"):
            ActorBook.from_dict({"actor": {"a": {"phones": ["nexus"]},
                                           "b": {"phones": ["nexus"]}}})

    def test_every_phone_leaves_none_for_anyone_else(self):
        with pytest.raises(ConfigProblem, match="phone = true, which is every phone"):
            ActorBook.from_dict({"actor": {"a": {"phone": True},
                                           "b": {"phones": ["pixel"]}}})

    def test_every_and_some_for_one_person_is_one_too_many(self):
        with pytest.raises(ConfigProblem, match="keep one"):
            ActorBook.from_dict({"actor": {"a": {"phone": True, "phones": ["pixel"]}}})

    @pytest.mark.parametrize("bad", [["Nexus"], "nexus", [1], ["a", "a"]])
    def test_phones_are_names(self, bad):
        with pytest.raises(ConfigProblem, match="phones"):
            ActorBook.from_dict({"actor": {"a": {"phones": bad}}})

    def test_a_person_with_phones_has_a_phone(self):
        asha = PEOPLE.get("asha")
        assert asha.has_phone and not asha.phone and asha.phones == ("nexus",)


class TestTheirPhonesOnly:
    def test_each_persons_turn_starts_sparsh_with_only_theirs(
            self, make_service, named_sparsh):
        service = make_service([says("ok"), says("ok")], sparsh=str(named_sparsh[0]),
                               actors=PEOPLE)
        asyncio.run(service.deliver(actor="asha", agent="greeter", thread="a", text="hi"))
        asyncio.run(service.deliver(actor="ravi", agent="greeter", thread="r", text="hi"))
        starts = [a for a in logged(named_sparsh[1]) if a[:1] == ["mcp"]]
        assert starts[0][-2:] == ["--phone", "nexus"]
        assert starts[1][-2:] == ["--phone", "pixel"]
        assert "mcp__sparsh__look" in phone_tools(service)

    def test_a_phone_sparsh_doesnt_name_costs_the_phone_not_the_turn(
            self, make_service, named_sparsh):
        service = make_service([says("ok")], sparsh=str(named_sparsh[0]), actors=PEOPLE)
        reply = asyncio.run(service.deliver(actor="both", agent="greeter", thread="b",
                                            text="hi"))
        assert reply.ok and phone_tools(service) == set()
        assert not [a for a in logged(named_sparsh[1]) if a[:1] == ["mcp"]]


class TestAScheduleNamesItsPhone:
    def test_their_only_phone_is_the_one(self):
        assert phone_for(PEOPLE.get("asha"), True) == ("nexus",)
        assert phone_for(PEOPLE.get("asha"), "nexus") == ("nexus",)

    def test_one_that_isnt_theirs_is_refused(self):
        with pytest.raises(Refused, match="'pixel' isn't one of asha's"):
            phone_for(PEOPLE.get("asha"), "pixel")

    def test_none_named_among_several_is_refused_not_guessed(self):
        with pytest.raises(Refused, match="doesn't say which phone, and both has 2 "
                                          r"\(nexus-2, pixel-2\)"):
            phone_for(PEOPLE.get("both"), True)

    def test_every_phone_and_none_named_is_unnamed(self):
        every = ActorBook.from_dict({"actor": {"o": {"phone": True}}}).get("o")
        assert phone_for(every, True) == () and phone_for(every, "pixel") == ("pixel",)

    def test_its_phone_is_checked_free_and_is_the_only_one_it_gets(
            self, make_service, named_sparsh, monkeypatch):
        monkeypatch.setenv("FAKE_PHONE", "asleep")
        service = make_service([says("ok")], sparsh=str(named_sparsh[0]), actors=PEOPLE)
        reply = asyncio.run(service.deliver(actor="ravi", agent="greeter", thread="s",
                                            text="go", unattended=True, phone="pixel"))
        assert reply.ok
        seen = logged(named_sparsh[1])
        assert ["state", "--json", "--phone", "pixel"] in seen
        assert ["wake", "--phone", "pixel"] in seen
        assert [a for a in seen if a[:1] == ["mcp"]][0][-2:] == ["--phone", "pixel"]

    def test_a_refused_one_is_a_reply_with_its_sentence(self, make_service, named_sparsh):
        service = make_service([says("ok")], sparsh=str(named_sparsh[0]), actors=PEOPLE)
        reply = asyncio.run(service.deliver(actor="ravi", agent="greeter", thread="s",
                                            text="go", unattended=True, phone="nexus"))
        assert reply.stop_reason == "refused" and "isn't one of ravi's" in reply.text
        assert logged(named_sparsh[1]) == []

    def test_the_check_for_another_road_names_it_too(self, make_service, named_sparsh,
                                                       monkeypatch):
        monkeypatch.setenv("FAKE_PHONE", "asleep")
        service = make_service([], sparsh=str(named_sparsh[0]), actors=PEOPLE)
        said = asyncio.run(service.phone_ready(actor="both", wait=60, about="x"))
        assert said.startswith("skipped: this schedule doesn't say which phone")
        go = asyncio.run(service.phone_ready(actor="both", wait=60, about="x",
                                             phone="pixel-2"))
        assert go is None
        assert ["state", "--json", "--phone", "pixel-2"] in logged(named_sparsh[1])


class TestSlashPhone:
    def test_the_name_after_the_word(self):
        assert asked("/phone nexus") == "nexus" and asked("/phone") == ""

    def test_their_first_phone_and_the_others_by_name(self, make_service, named_sparsh):
        book = ActorBook.from_dict({"actor": {"o": {"phones": ["pixel", "nexus"]}}})
        service = make_service([], sparsh=str(named_sparsh[0]), actors=book)
        reply = asyncio.run(service.deliver(actor="o", agent="greeter", thread="t",
                                            text="/phone"))
        assert reply.text.startswith("Your phone (nexus) now shows com.android.settings")
        assert "Your other phones: /phone pixel" in reply.text
        reply = asyncio.run(service.deliver(actor="o", agent="greeter", thread="t",
                                            text="/phone pixel"))
        assert reply.text.startswith("Your phone (pixel)")
        peeks = [a for a in logged(named_sparsh[1]) if a[:2] == ["look", "--peek"]]
        assert peeks[-1][peeks[-1].index("--serial") + 1] == "emulator-5554"

    def test_someone_elses_phone_by_name_is_a_sentence(self, make_service, named_sparsh):
        service = make_service([], sparsh=str(named_sparsh[0]), actors=PEOPLE)
        reply = asyncio.run(service.deliver(actor="asha", agent="greeter", thread="t",
                                            text="/phone pixel"))
        assert reply.text == "pixel isn't one of your phones (nexus)."
        assert not [a for a in logged(named_sparsh[1]) if a[:2] == ["look", "--peek"]]


def test_settings_show_a_persons_phones():
    from dvara.settings import person

    assert person(PEOPLE.get("asha"))["phones"] == ["nexus"]
    assert json.dumps(person(PEOPLE.get("asha")))

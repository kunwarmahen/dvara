"""A role: a child's or a guest's safe settings, in one word.

The bias these tests encode: AN OWNER WHO WROTE ONE WORD GETS A SAFE
PERSON, AND WHAT THEY WROTE BY HAND IS NEVER UNDONE BY IT. The ways that
goes wrong: a role that overrides an earlier bedtime the owner chose; a
child whose questions still go to the child because nobody named an
approver; a guest who can change things because the rung was left out;
a misspelled role read as "no limits"; and the page, saving its form,
writing the role's defaults into the file as if the owner had typed
them, so changing the role later changes nothing.
"""

from __future__ import annotations

import asyncio
import tomllib

import pytest

from dvara import settings
from dvara.actors import ActorBook
from dvara.asks import AskDesk
from dvara.errors import ConfigProblem

from tests.conftest import calls, says
from tests.test_what_decided_it import scribe


def book(**people) -> ActorBook:
    return ActorBook.from_dict({"actor": {"owner": {}, **people}})


class TestTheRoleFillsIn:
    def test_a_child_gets_hours_messages_dollars_and_asking(self):
        kid = book(anya={"role": "child"}).get("anya")
        assert str(kid.hours) == "07:00-21:00" and kid.max_turns_per_day == 60
        assert kid.max_usd_per_day == 1.0 and kid.permissions == "ask"
        assert set(kid.from_role) == {"hours", "max_turns_per_day", "max_usd_per_day",
                                      "permissions"}

    def test_a_guest_only_looks(self):
        guest = book(sam={"role": "guest"}).get("sam")
        assert guest.permissions == "read_only" and guest.max_usd_per_day == 0.25
        assert guest.setu is None and not guest.has_phone

    def test_what_the_owner_wrote_wins(self):
        kid = book(anya={"role": "child", "hours": "06:30-20:00"}).get("anya")
        assert str(kid.hours) == "06:30-20:00" and "hours" not in kid.from_role
        assert kid.max_turns_per_day == 60

    def test_an_adult_fills_nothing_and_no_role_is_as_before(self):
        assert book(mo={"role": "adult"}).get("mo").from_role == ()
        plain = book(mo={}).get("mo")
        assert plain.role is None and plain.hours is None

    @pytest.mark.parametrize("bad", ["kid", "Child", 1, True])
    def test_a_role_that_isnt_one_is_an_error_not_no_limits(self, bad):
        with pytest.raises(ConfigProblem, match="role must be one of adult, child, guest"):
            book(anya={"role": bad})


class TestAChildsBedtime:
    def test_after_hours_a_childs_turn_is_refused_before_any_model(self, make_service):
        from datetime import datetime, timedelta
        later = datetime.now().astimezone() + timedelta(hours=2)
        window = f"{later:%H:%M}-{later + timedelta(hours=1):%H:%M}"
        service = make_service([], actors=book(anya={"role": "child", "hours": window}))
        reply = asyncio.run(service.deliver(actor="anya", agent="greeter", thread="t",
                                            text="hi"))
        assert reply.stop_reason == "refused" and window in reply.text


class TestAChildsQuestionGoesToTheOwner:
    def test_with_no_approver_named(self, make_service, agents_root, priced_model):
        scribe(agents_root)
        desk = AskDesk(timeout=5, on_timeout="hold")
        service = make_service([calls("write_file", {"path": "a.txt", "content": "x"}),
                                says("written.")],
                               # all day: the role's own 07:00-21:00 would refuse a
                               # run of these tests after nine at night
                               actors=book(anya={"role": "child", "hours": "00:00-23:59"}),
                               asks=desk, owner="owner")

        async def go():
            turn = asyncio.create_task(service.deliver(actor="anya", agent="scribe",
                                                       thread="t", text="write it"))
            for _ in range(10_000):
                if desk.pending() or turn.done():
                    break
                await asyncio.sleep(0)
            assert desk.pending(), (await turn).text if turn.done() else "no question"
            ask = desk.pending()[0]
            assert ask.actor == "owner" and ask.summary.startswith("For anya:")
            desk.answer(ask.id, actor="owner", approve=True)
            return await turn
        assert asyncio.run(go()).ok

    def test_an_approver_the_owner_named_wins(self, make_service):
        service = make_service([], actors=book(mum={}, anya={"role": "child",
                                                           "approver": "mum"}),
                               asks=AskDesk(timeout=5), owner="owner")
        assert service._desk_for(service.actors.get("anya")).approver == "mum"

    def test_a_guests_questions_are_not_sent_to_the_owner(self, make_service):
        desk = AskDesk(timeout=5)
        service = make_service([], actors=book(sam={"role": "guest"}), asks=desk,
                               owner="owner")
        assert service._desk_for(service.actors.get("sam")) is desk


class TestThePageKeepsTheRoleTheRoles:
    def test_the_page_shows_the_roles_values_beside_blank_boxes(self):
        shown = settings.person(book(anya={"role": "child", "hours": "06:30-20:00"})
                                .get("anya"))
        assert shown["role"] == "child" and shown["hours"] == "06:30-20:00"
        assert shown["max_turns_per_day"] is None
        assert shown["role_fills"]["max_turns_per_day"] == 60
        assert "hours" not in shown["role_fills"]

    def test_saving_the_form_writes_the_role_not_its_defaults(self, tmp_path):
        actors = tmp_path / "actors.toml"
        actors.write_text('[actor.owner]\n')
        settings.set_person(actors, "anya", {"role": "child", "hours": None,
                                             "max_turns_per_day": None})
        written = tomllib.loads(actors.read_text())["actor"]["anya"]
        assert written == {"role": "child"}
        settings.set_person(actors, "anya", {"role": "guest"})
        assert ActorBook.from_toml(actors).get("anya").permissions == "read_only"

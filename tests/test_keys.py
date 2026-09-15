"""Bias: a session key that is not injective is a cross-actor history leak.

Every test here is aimed at one failure -- two different (actor, agent,
thread) triples that produce the same string, so one person's
conversation opens inside another's. The escaping is the whole defence,
and these are the inputs that would defeat a naive join.
"""

from __future__ import annotations

import pytest

from dvara.errors import Refused
from dvara.keys import parse_key, session_key, workspace_parts


def test_a_key_carries_all_three_nouns():
    assert session_key("mahen", "researcher", "chat-42") == \
        "mahen/researcher/chat-42"


def test_a_separator_inside_a_component_cannot_forge_another_component():
    # The naive join gives BOTH of these "a/b/c/d": one person reading
    # another's thread because of how they were named.
    forged = session_key("a/b", "c", "d")
    honest = session_key("a", "b", "c/d")
    assert forged != honest


def test_every_key_round_trips_to_the_triple_it_came_from():
    for triple in [("mahen", "researcher", "chat-42"),
                   ("a/b", "c d", "%2F"),
                   ("emoji 🚪", "agent.v2", "thread#1")]:
        assert parse_key(session_key(*triple)) == triple


@pytest.mark.parametrize("thread", ["../../etc", "..", ".", "a/../..", "/"])
def test_a_thread_id_cannot_climb_out_of_the_workspace(thread):
    # Escaping kills the separator; it does NOT kill a lone "..", which
    # is legal in a URL path and lethal in a filesystem one.
    parts = workspace_parts(session_key("mahen", "greeter", thread))
    assert parts[2] not in {"", ".", ".."}
    assert "/" not in parts[2]


def test_an_empty_component_is_refused_rather_than_silently_shared():
    # "" would otherwise be a perfectly good key that everyone with a
    # missing field shares.
    with pytest.raises(Refused):
        session_key("mahen", "greeter", "")
    with pytest.raises(Refused):
        session_key("  ", "greeter", "chat")

"""A chat turn with many tools sends only those its words point at.

The bias: A PERSON'S TOOLS GROW WITHOUT A WORD TO THE PACKAGE. Every
account they connect (Robinhood, Notion, a server of their own) adds its
tools to every turn, and a package that needs ``"*:read"`` admits them
all. Sent whole, 227 of them overflowed a local model's window, which
cut the top of the prompt to fit -- the system prompt and most of the
tool list -- and the model answered a question it could no longer see.
So past twenty tools a turn gets Yantra's selection, the same rule its
terminal uses: the tools that match the conversation, the few pinned,
and ``list_available_tools`` for the rest. A tool not sent can still be
called by name. ``[tools] per_turn`` in the package still decides,
``0`` sending every tool.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import calls, says, write_package


@pytest.fixture(autouse=True)
def selection_as_shipped(monkeypatch):
    monkeypatch.delenv("YANTRA_TOOLS_PER_TURN", raising=False)


def ask(service, text, agent="greeter"):
    return asyncio.run(service.deliver(actor="owner", agent=agent, thread="t", text=text))


def sent(service, i=0) -> set[str]:
    return {t.name for t in service.scripted.requests[i]["tools"]}


def test_past_twenty_tools_a_turn_sends_a_few_and_the_way_to_the_rest(make_service):
    service = make_service([says("hello")])
    assert ask(service, "fetch https://example.com for me").ok
    names = sent(service)
    assert len(names) <= 14, names              # of the 50-odd built in
    assert "list_available_tools" in names and "web_fetch" in names


def test_a_tool_not_sent_is_still_called_by_name(make_service):
    service = make_service([calls("list_dir", {"path": "."}), says("done")])
    assert ask(service, "hello there").ok
    assert "list_dir" not in sent(service)
    result = service.scripted.requests[1]["messages"][-1].content[0]
    assert type(result).__name__ == "ToolResult" and not result.is_error, result


def test_the_package_can_send_every_tool(make_service, agents_root):
    write_package(agents_root, "wide", body='[agent]\nname = "wide"\nprompt = "prompt.md"\n'
                  '[tools]\nper_turn = 0\n')
    service = make_service([says("hello")])
    assert ask(service, "hello", agent="wide").ok
    assert len(sent(service)) > 20 and "list_available_tools" not in sent(service)

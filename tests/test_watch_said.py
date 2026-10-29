"""A step's line on the page: never a card that asks its server.

Prahari's create_watch card previews the watch, and on Dvara's road that
preview is a look that comes back to this service -- whose loop is the
one writing the step line. Said inline, it froze the service for the
whole look limit, every time a watch was made."""

from __future__ import annotations

from types import SimpleNamespace

from dvara.watch import said


class _Tool:
    def __init__(self, explain=None) -> None:
        self.explain = explain
        self.asked = 0

    def summary(self, args, ctx):
        self.asked += 1
        return "New watch: GOOGL below 316.50"


def _agent(tool):
    return SimpleNamespace(_get_visible_tool=lambda name: tool, ctx=None)


def test_a_tool_with_a_card_is_said_by_its_call_not_its_card():
    tool = _Tool(explain=lambda args: "a card that would ask the server")
    call = SimpleNamespace(name="mcp__prahari__create_watch",
                           arguments={"name": "GOOGL below 316.50"})
    line = said(_agent(tool), call)
    assert tool.asked == 0
    assert line == 'mcp__prahari__create_watch({"name": "GOOGL below 316.50"})'


def test_a_plain_tool_is_said_by_its_summary():
    tool = _Tool()
    call = SimpleNamespace(name="web_fetch", arguments={"url": "https://x"})
    assert said(_agent(tool), call) == "web_fetch: New watch: GOOGL below 316.50"
    assert tool.asked == 1

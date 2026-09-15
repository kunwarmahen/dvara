"""Shared test helpers.

The seam every test here leans on is ``Service(provider_factory=...)``:
no test may touch the network, and none may depend on which API keys
happen to live in the shell that ran pytest. A scripted provider answers
with exactly the responses a test wrote, and raises the moment the loop
makes a call nobody scripted -- which is how an "it passed" that silently
took a different path gets caught.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from yantra.providers.base import Provider, ProviderSettings
from yantra.types import (
    EndEvent,
    Message,
    ModelResponse,
    StartEvent,
    StreamEvent,
    TextBlock,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolCallStart,
    Usage,
)

from dvara.actors import ActorBook
from dvara.roster import Roster
from dvara.service import Service

#: Everything a provider or a knob reads straight off the environment.
#: Sealed for the same reason Yantra seals it: a suite that turns green
#: or red depending on whose laptop it ran on is not a suite.
AMBIENT = tuple(
    f"{prefix}_{suffix}"
    for prefix in ("ANTHROPIC", "OPENAI", "RESPONSES", "OLLAMA", "DVARA")
    for suffix in ("API_KEY", "AUTH_TOKEN", "BASE_URL", "MODEL", "TOKEN",
                   "ROOT", "ACTORS", "STATE")
)


@pytest.fixture(autouse=True)
def seal_ambient_env(monkeypatch):
    for name in AMBIENT:
        monkeypatch.delenv(name, raising=False)
    for name in list(os.environ):
        if name.startswith(("YANTRA_", "DVARA_")):
            monkeypatch.delenv(name, raising=False)


class ScriptedProvider(Provider):
    """Answers from a list; raises when the loop asks for one more."""

    name = "scripted"

    def __init__(self, script: list[ModelResponse]) -> None:
        super().__init__(ProviderSettings(api_key="script",
                                          base_url="http://script.local"))
        self.script = list(script)
        self.requests: list[dict] = []

    def _next(self, **kwargs) -> ModelResponse:
        self.requests.append(kwargs)
        if not self.script:
            raise AssertionError(
                "script exhausted -- the loop made an unscripted model call"
            )
        return self.script.pop(0)

    def complete(self, *, messages, system, tools, model,
                 max_tokens=16384, temperature=None) -> ModelResponse:
        return self._next(messages=list(messages), system=system, tools=tools,
                          model=model, max_tokens=max_tokens)

    def stream(self, *, messages, system, tools, model,
               max_tokens=16384, temperature=None):
        response = self._next(messages=list(messages), system=system,
                              tools=tools, model=model, max_tokens=max_tokens)
        yield from _events_for(response)

    async def acomplete(self, *, messages, system, tools, model,
                        max_tokens=16384, temperature=None) -> ModelResponse:
        return self.complete(messages=messages, system=system, tools=tools,
                             model=model, max_tokens=max_tokens)

    async def astream(self, *, messages, system, tools, model,
                      max_tokens=16384, temperature=None):
        for event in self.stream(messages=messages, system=system, tools=tools,
                                 model=model, max_tokens=max_tokens):
            yield event


def _events_for(response: ModelResponse) -> Iterator[StreamEvent]:
    """Re-express one ModelResponse as the events a real provider emits."""
    yield StartEvent(model=response.model)
    index = 0
    for block in response.message.content:
        match block:
            case TextBlock(text=text):
                mid = len(text) // 2  # split to prove fragments rejoin
                yield TextDelta(text[:mid])
                yield TextDelta(text[mid:])
            case ToolCall(id=cid, name=name, arguments=args):
                yield ToolCallStart(index=index, id=cid, name=name)
                raw = json.dumps(args)
                if raw != "{}":
                    yield ToolCallDelta(index=index, partial_json=raw)
                index += 1
    yield EndEvent(stop_reason=response.stop_reason, usage=response.usage)


def says(text: str, *, usage: Usage | None = None,
         model: str = "test-model") -> ModelResponse:
    """Script helper: a plain end_turn answer."""
    return ModelResponse(
        message=Message("assistant", [TextBlock(text)]),
        stop_reason="end_turn",
        usage=usage or Usage(),
        model=model,
    )


def calls(tool: str, arguments: dict, *, call_id: str = "c1",
          usage: Usage | None = None,
          model: str = "test-model") -> ModelResponse:
    """Script helper: a turn that wants a tool run, so the loop continues."""
    return ModelResponse(
        message=Message("assistant", [ToolCall(call_id, tool, arguments)]),
        stop_reason="tool_use",
        usage=usage or Usage(),
        model=model,
    )


@pytest.fixture
def priced_model(tmp_path, monkeypatch):
    """Give "test-model" a list price, absurdly high so one call blows any
    ceiling. $YANTRA_PRICES is Yantra's own seam for exactly this -- it is
    how a ceiling gets rehearsed without an account with a card behind it.
    """
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"test-model": {"input": 1000.0,
                                                 "output": 1000.0}}))
    monkeypatch.setenv("YANTRA_PRICES", str(prices))
    return "test-model"


# ---- packages on disk ------------------------------------------------------

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def write_package(root: Path, name: str, *, body: str | None = None,
                  prompt: str = "You are a test agent.") -> Path:
    """One agent package, the smallest thing ``load_package`` accepts."""
    where = root / name
    where.mkdir(parents=True)
    (where / "agent.toml").write_text(
        body if body is not None else
        f'[agent]\nname = "{name}"\nprompt = "prompt.md"\n',
        encoding="utf-8",
    )
    (where / "prompt.md").write_text(prompt, encoding="utf-8")
    return where


@pytest.fixture
def agents_root(tmp_path: Path) -> Path:
    root = tmp_path / "agents"
    root.mkdir()
    write_package(root, "greeter")
    return root


@pytest.fixture
def actors() -> ActorBook:
    return ActorBook.from_dict({
        "actor": {
            "owner": {},
            "guest": {"agents": ["greeter"], "max_usd_per_turn": 0.02,
                      "max_usd_per_day": 0.10},
        }
    })


@pytest.fixture
def make_service(tmp_path: Path, agents_root: Path, actors: ActorBook):
    """A service wired to a scripted provider. Closed for you afterwards."""
    built: list[Service] = []

    def build(script: list[ModelResponse] | None = None, **kwargs) -> Service:
        provider = ScriptedProvider(script if script is not None
                                    else [says("hello")])
        kwargs.setdefault("provider_name", "anthropic")
        kwargs.setdefault("model", "test-model")
        service = Service(
            roster=Roster(kwargs.pop("root", agents_root)),
            actors=kwargs.pop("actors", actors),
            state=tmp_path / "state",
            provider_factory=lambda name: provider,
            **kwargs,
        )
        service.scripted = provider  # the test's handle on what was asked
        built.append(service)
        return service

    yield build
    for service in built:
        service.close()

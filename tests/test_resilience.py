"""
Tests for items 2, 3, 5, 9:
  2. Fallback provider
  3. Error classification
  5. check_fn on tools
  9. Status buffering on retries
"""
from __future__ import annotations

from typing import AsyncIterator

import pytest
from pydantic import BaseModel

from enterprise_ai.engine.loop import QueryLoop
from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.executor import HookExecutor
from enterprise_ai.hooks.registry import HookRegistry
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.providers.errors import ErrorClass, classify_error
from enterprise_ai.providers.retry import RetryConfig
from enterprise_ai.schema import StreamEvent, ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry

# ── Helpers ──────────────────────────────────────────────────────────────────

class FakeProvider(Provider):
    """Provider whose complete() returns a canned response or raises on demand."""

    def __init__(self, responses: list) -> None:
        # Each entry is either an LLMResponse or an Exception to raise
        self._responses = list(responses)
        self._call_count = 0

    @property
    def model(self) -> str:
        return "fake/model"

    async def complete(self, messages, tools=None, max_tokens=8096, **kwargs) -> LLMResponse:
        if not self._responses:
            return LLMResponse(content="done", tool_calls=[])
        entry = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        if isinstance(entry, Exception):
            raise entry
        return entry

    async def stream(self, messages, tools=None, max_tokens=8096, **kwargs) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
        yield  # make it a generator


def ok_response(text: str = "done") -> LLMResponse:
    return LLMResponse(content=text, tool_calls=[])


def _transient_error(status: int = 429) -> Exception:
    exc = Exception(f"HTTP {status}")
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


def _fatal_error(status: int = 404) -> Exception:
    exc = Exception(f"HTTP {status}")
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


def _fallback_error(status: int = 401) -> Exception:
    exc = Exception(f"HTTP {status}")
    exc.status_code = status  # type: ignore[attr-defined]
    return exc


def _make_loop(
    provider: Provider,
    fallback_provider: Provider | None = None,
    retry_config: RetryConfig | None = None,
    hooks: HookExecutor | None = None,
) -> QueryLoop:
    registry = ToolRegistry()
    permissions = PermissionEngine(mode=PermissionMode.auto)
    orchestrator = Orchestrator(registry=registry, permissions=permissions)
    memory = SessionMemory()
    return QueryLoop(
        provider=provider,
        registry=registry,
        orchestrator=orchestrator,
        memory=memory,
        max_turns=3,
        retry_config=retry_config,
        fallback_provider=fallback_provider,
        hooks=hooks,
    )


def _make_ctx() -> ToolContext:
    return ToolContext(
        session_id="test-session",
        agent_id="test-agent",
        working_dir=".",
        permission_mode="auto",
    )


# ── Item 3: Error classification ─────────────────────────────────────────────

def test_classify_429_is_transient():
    assert classify_error(_transient_error(429)) == ErrorClass.TRANSIENT


def test_classify_500_is_transient():
    assert classify_error(_transient_error(500)) == ErrorClass.TRANSIENT


def test_classify_503_is_transient():
    assert classify_error(_transient_error(503)) == ErrorClass.TRANSIENT


def test_classify_401_is_fallback():
    assert classify_error(_fallback_error(401)) == ErrorClass.FALLBACK


def test_classify_403_is_fallback():
    assert classify_error(_fallback_error(403)) == ErrorClass.FALLBACK


def test_classify_400_is_fallback():
    assert classify_error(_fallback_error(400)) == ErrorClass.FALLBACK


def test_classify_404_is_fatal():
    assert classify_error(_fatal_error(404)) == ErrorClass.FATAL


def test_classify_410_is_fatal():
    assert classify_error(_fatal_error(410)) == ErrorClass.FATAL


def test_classify_unknown_exception_is_transient():
    assert classify_error(ValueError("boom")) == ErrorClass.TRANSIENT


def test_classify_httpx_network_error_is_transient():
    try:
        import httpx
        exc = httpx.NetworkError("connection refused")
        assert classify_error(exc) == ErrorClass.TRANSIENT
    except ImportError:
        pytest.skip("httpx not installed")


# ── Item 2: Fallback provider ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_used_on_auth_error():
    """401 from primary → fallback provider is called and succeeds."""
    primary = FakeProvider([_fallback_error(401)])
    fallback = FakeProvider([ok_response("fallback result")])
    loop = _make_loop(primary, fallback_provider=fallback, retry_config=RetryConfig(max_attempts=1))

    result = await loop.run("hello", _make_ctx())

    assert result.output == "fallback result"
    assert primary._call_count == 1
    assert fallback._call_count == 1


@pytest.mark.asyncio
async def test_fallback_used_after_transient_retries_exhausted():
    """429 × max_attempts → fallback provider is called."""
    primary = FakeProvider([_transient_error(429), _transient_error(429)])
    fallback = FakeProvider([ok_response("fallback ok")])
    loop = _make_loop(
        primary,
        fallback_provider=fallback,
        retry_config=RetryConfig(max_attempts=2, base_delay_ms=0),
    )

    result = await loop.run("hello", _make_ctx())

    assert result.output == "fallback ok"
    assert fallback._call_count == 1


@pytest.mark.asyncio
async def test_fatal_error_does_not_trigger_fallback():
    """404 is FATAL — fallback is NOT attempted."""
    primary = FakeProvider([_fatal_error(404)])
    fallback = FakeProvider([ok_response("should not be called")])
    loop = _make_loop(primary, fallback_provider=fallback, retry_config=RetryConfig(max_attempts=1))

    result = await loop.run("hello", _make_ctx())

    assert result.state.value == "error"
    assert fallback._call_count == 0


@pytest.mark.asyncio
async def test_no_fallback_configured_raises_after_retries():
    """Without fallback_provider, the primary error propagates as session error."""
    primary = FakeProvider([_fallback_error(401)])
    loop = _make_loop(primary, retry_config=RetryConfig(max_attempts=1))

    result = await loop.run("hello", _make_ctx())

    assert result.state.value == "error"


@pytest.mark.asyncio
async def test_fallback_failure_returns_error():
    """Both primary and fallback fail → session error."""
    primary = FakeProvider([_fallback_error(401)])
    fallback = FakeProvider([_fatal_error(500)])
    loop = _make_loop(primary, fallback_provider=fallback, retry_config=RetryConfig(max_attempts=1))

    result = await loop.run("hello", _make_ctx())

    assert result.state.value == "error"


@pytest.mark.asyncio
async def test_primary_success_fallback_not_called():
    """Primary succeeds on first attempt → fallback never touched."""
    primary = FakeProvider([ok_response("primary ok")])
    fallback = FakeProvider([ok_response("should not see this")])
    loop = _make_loop(primary, fallback_provider=fallback)

    result = await loop.run("hello", _make_ctx())

    assert result.output == "primary ok"
    assert fallback._call_count == 0


# ── Item 5: check_fn on tools ────────────────────────────────────────────────


class _DummyInput(BaseModel):
    x: str = ""


class AlwaysTool(BaseTool):
    name = "always_tool"
    description = "always available"
    input_schema = _DummyInput

    async def call(self, input, ctx):
        return ToolResult.ok("", name=self.name, content="ok")


class GatedTool(BaseTool):
    name = "gated_tool"
    description = "gated by check_fn"
    input_schema = _DummyInput

    def __init__(self, available: bool) -> None:
        self.check_fn = lambda: available

    async def call(self, input, ctx):
        return ToolResult.ok("", name=self.name, content="gated")


def test_check_fn_none_means_always_available():
    t = AlwaysTool()
    assert t.is_available() is True


def test_check_fn_true_tool_appears_in_registry():
    reg = ToolRegistry()
    reg.register(GatedTool(available=True))
    assert len(reg.all()) == 1
    assert len(reg.schemas()) == 1


def test_check_fn_false_tool_hidden_from_registry():
    reg = ToolRegistry()
    reg.register(GatedTool(available=False))
    assert reg.all() == []
    assert reg.schemas() == []


def test_check_fn_false_does_not_affect_other_tools():
    reg = ToolRegistry()
    reg.register(AlwaysTool())
    reg.register(GatedTool(available=False))
    assert len(reg.all()) == 1
    assert reg.all()[0].name == "always_tool"


def test_check_fn_evaluated_at_query_time():
    """check_fn is called each time all()/schemas() is called."""
    available = [True]
    reg = ToolRegistry()

    class DynamicTool(BaseTool):
        name = "dynamic"
        description = "dynamic"
        input_schema = _DummyInput
        check_fn = staticmethod(lambda: available[0])

        async def call(self, input, ctx):
            return ToolResult.ok("", name=self.name, content="ok")

    reg.register(DynamicTool())
    assert len(reg.all()) == 1

    available[0] = False
    assert reg.all() == []

    available[0] = True
    assert len(reg.all()) == 1


# ── Item 9: Status buffering ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_events_not_fired_on_success():
    """Primary fails once (TRANSIENT), succeeds on second attempt — no notification fired."""
    primary = FakeProvider([_transient_error(429), ok_response("ok")])
    fired: list[dict] = []

    async def capture(payload):
        fired.append(payload.data)

    hook_reg = HookRegistry()
    hook_reg.on(HookEvent.notification, capture)
    hooks = HookExecutor(hook_reg)

    loop = _make_loop(
        primary,
        retry_config=RetryConfig(max_attempts=2, base_delay_ms=0),
        hooks=hooks,
    )
    result = await loop.run("hello", _make_ctx())

    assert result.output == "ok"
    # No notification events should have been fired
    assert fired == []


@pytest.mark.asyncio
async def test_retry_events_fired_on_total_failure():
    """Primary fails all attempts — notification events emitted once at the end."""
    primary = FakeProvider([_transient_error(429), _transient_error(429)])
    fired: list[dict] = []

    async def capture(payload):
        fired.append(payload.data)

    hook_reg = HookRegistry()
    hook_reg.on(HookEvent.notification, capture)
    hooks = HookExecutor(hook_reg)

    loop = _make_loop(
        primary,
        retry_config=RetryConfig(max_attempts=2, base_delay_ms=0),
        hooks=hooks,
    )
    result = await loop.run("hello", _make_ctx())

    assert result.state.value == "error"
    # One retry event should have been buffered and emitted
    retry_events = [e for e in fired if e.get("type") == "retry"]
    assert len(retry_events) == 1
    assert retry_events[0]["attempt"] == 1
    assert retry_events[0]["max_attempts"] == 2


@pytest.mark.asyncio
async def test_fallback_event_emitted_on_total_failure():
    """Primary fails with FALLBACK error, fallback also fails — both events emitted."""
    primary = FakeProvider([_fallback_error(401)])
    fallback = FakeProvider([_fatal_error(500)])
    fired: list[dict] = []

    async def capture(payload):
        fired.append(payload.data)

    hook_reg = HookRegistry()
    hook_reg.on(HookEvent.notification, capture)
    hooks = HookExecutor(hook_reg)

    loop = _make_loop(
        primary,
        fallback_provider=fallback,
        retry_config=RetryConfig(max_attempts=1),
        hooks=hooks,
    )
    await loop.run("hello", _make_ctx())

    types = [e.get("type") for e in fired]
    assert "fallback" in types
    assert "fallback_failed" in types


@pytest.mark.asyncio
async def test_retry_buffer_cleared_after_successful_run():
    """After a successful run, the internal buffer is empty."""
    primary = FakeProvider([ok_response("ok")])
    loop = _make_loop(primary, retry_config=RetryConfig(max_attempts=3, base_delay_ms=0))
    await loop.run("hello", _make_ctx())
    assert loop._retry_buffer == []

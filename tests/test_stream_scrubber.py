"""Tests for item 7: streaming scrubbers."""
from __future__ import annotations

import pytest

from enterprise_ai.stream.scrubber import TagScrubber

# ── Basic single-chunk behaviour ──────────────────────────────────────────────

def test_no_tags_passes_through():
    s = TagScrubber("<think>", "</think>")
    assert s.process("hello world") == "hello world"


def test_full_tag_in_one_chunk_stripped():
    s = TagScrubber("<think>", "</think>")
    assert s.process("before<think>hidden</think>after") == "beforeafter"


def test_only_tag_content_stripped():
    s = TagScrubber("<think>", "</think>")
    assert s.process("<think>hidden</think>") == ""


def test_text_before_tag_preserved():
    s = TagScrubber("<think>", "</think>")
    assert s.process("Hello <think>hidden</think>") == "Hello "


def test_text_after_tag_preserved():
    s = TagScrubber("<think>", "</think>")
    assert s.process("<think>hidden</think> world") == " world"


def test_multiple_tags_in_one_chunk():
    s = TagScrubber("<x>", "</x>")
    assert s.process("a<x>1</x>b<x>2</x>c") == "abc"


# ── Cross-chunk boundary behaviour ───────────────────────────────────────────

def test_open_tag_split_across_chunks():
    s = TagScrubber("<think>", "</think>")
    r1 = s.process("Hello <thi")   # partial open tag buffered
    r2 = s.process("nk>hidden")    # open tag completes
    r3 = s.process("</think> done")
    assert r1 == "Hello "
    assert r2 == ""
    assert r3 == " done"


def test_close_tag_split_across_chunks():
    s = TagScrubber("<think>", "</think>")
    s.process("<think>hidden")     # enter block
    r1 = s.process("still hidden</thi")  # partial close buffered
    r2 = s.process("nk> visible")
    assert r1 == ""
    assert r2 == " visible"


def test_open_tag_at_exact_chunk_boundary():
    s = TagScrubber("<tag>", "</tag>")
    r1 = s.process("before<tag>")
    r2 = s.process("hidden</tag>after")
    assert r1 == "before"
    assert r2 == "after"


def test_partial_open_tag_at_end_then_mismatch():
    """Partial match at chunk end that turns out not to be the tag."""
    s = TagScrubber("<think>", "</think>")
    r1 = s.process("Hello <thi")   # partial match
    r2 = s.process("s is not a tag>")  # partial resolves — not the open tag
    combined = r1 + r2
    assert "Hello" in combined
    assert "not a tag" in combined


# ── State management ──────────────────────────────────────────────────────────

def test_in_block_property():
    s = TagScrubber("<think>", "</think>")
    assert not s.in_block
    s.process("<think>")
    assert s.in_block
    s.process("</think>")
    assert not s.in_block


def test_reset_clears_state():
    s = TagScrubber("<think>", "</think>")
    s.process("<think>not closed yet")
    assert s.in_block
    s.reset()
    assert not s.in_block
    # After reset, normal text passes through
    assert s.process("visible") == "visible"


def test_reset_clears_partial_buffer():
    s = TagScrubber("<think>", "</think>")
    s.process("partial <thi")  # partial buffered
    s.reset()
    # After reset the buffered partial is gone — next chunk stands alone
    assert s.process("nk>still visible") == "nk>still visible"


# ── Different tags ────────────────────────────────────────────────────────────

def test_memory_context_tag():
    s = TagScrubber("<memory-context>", "</memory-context>")
    result = s.process("Answer: <memory-context>private notes</memory-context> here.")
    assert result == "Answer:  here."


def test_custom_tags():
    s = TagScrubber("[[HIDDEN]]", "[[/HIDDEN]]")
    result = s.process("public [[HIDDEN]]secret[[/HIDDEN]] text")
    assert result == "public  text"


# ── Integration with Agent.stream() ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_applies_scrubber_to_text_deltas():
    """Agent.stream() applies scrubbers to text_delta events."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.schema.event import EventType

    async def fake_stream(*args, **kwargs):
        yield StreamEvent.text("Hello ")
        yield StreamEvent.text("<think>hidden</think>")
        yield StreamEvent.text("world")
        yield StreamEvent(type=EventType.session_end, data={"output": "Hello world"})

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        from enterprise_ai.agent.agent import Agent
        from enterprise_ai.providers.anthropic import AnthropicProvider

        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            stream_scrubbers=[TagScrubber("<think>", "</think>")],
        )
        agent._loop._provider.stream = fake_stream  # type: ignore[method-assign]

        events = []
        async for event in agent.stream("test"):
            events.append(event)

    text_events = [e for e in events if e.type == EventType.text_delta]
    combined = "".join(e.data["delta"] for e in text_events)
    assert "hidden" not in combined
    assert "Hello " in combined
    assert "world" in combined

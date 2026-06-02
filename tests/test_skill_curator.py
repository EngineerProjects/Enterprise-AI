"""Tests for item 12: SkillCurator — post-session skill auto-generation."""
from __future__ import annotations

import json

import pytest

from enterprise_ai.schema import Message
from enterprise_ai.skills.curator import SkillCurator, SkillProposal

# ── SkillProposal dataclass ───────────────────────────────────────────────────

def test_proposal_to_skill():
    proposal = SkillProposal(
        name="code-review",
        description="Review code for correctness.",
        when_to_use="When reviewing a pull request.",
        body="## Steps\n\n1. Read the diff.\n2. Check logic.",
        confidence=0.9,
    )
    skill = proposal.to_skill()
    assert skill.name == "code-review"
    assert skill.description == "Review code for correctness."
    assert skill.when_to_use == "When reviewing a pull request."
    assert "Steps" in skill.body


def test_proposal_to_markdown_has_frontmatter():
    proposal = SkillProposal(
        name="debug-session",
        description="Systematic debugging.",
        when_to_use="When a test fails.",
        body="Follow these steps.",
        confidence=0.8,
    )
    md = proposal.to_markdown()
    assert md.startswith("---")
    assert "name: debug-session" in md
    assert 'description: "Systematic debugging."' in md
    assert 'when_to_use: "When a test fails."' in md
    assert "Follow these steps." in md


def test_proposal_to_markdown_empty_optional_fields():
    proposal = SkillProposal(name="minimal", description="", when_to_use="", body="Do stuff.")
    md = proposal.to_markdown()
    assert "description:" not in md
    assert "when_to_use:" not in md
    assert "Do stuff." in md


def test_proposal_save_writes_file(tmp_path):
    proposal = SkillProposal(
        name="test-skill",
        description="A test skill.",
        when_to_use="For testing.",
        body="Test body.",
        confidence=0.85,
    )
    path = proposal.save(tmp_path)
    assert path.exists()
    assert path.name == "test-skill.md"
    content = path.read_text()
    assert "name: test-skill" in content
    assert "Test body." in content


def test_proposal_save_returns_path(tmp_path):
    proposal = SkillProposal(name="my-skill", description="", when_to_use="", body="x")
    path = proposal.save(tmp_path)
    assert str(path).endswith("my-skill.md")


# ── SkillCurator._parse_response ─────────────────────────────────────────────

def test_parse_response_valid():
    raw = json.dumps({
        "is_reusable": True,
        "confidence": 0.85,
        "name": "code-review",
        "description": "Review code.",
        "when_to_use": "When reviewing PRs.",
        "body": "Follow these steps.",
    })
    proposal = SkillCurator._parse_response(raw)
    assert proposal is not None
    assert proposal.name == "code-review"
    assert proposal.confidence == 0.85


def test_parse_response_strips_markdown_fences():
    raw = '```json\n{"is_reusable": true, "confidence": 0.9, "name": "my-skill", "description": "", "when_to_use": "", "body": "do it"}\n```'
    proposal = SkillCurator._parse_response(raw)
    assert proposal is not None
    assert proposal.name == "my-skill"


def test_parse_response_not_reusable_returns_none():
    raw = json.dumps({
        "is_reusable": False,
        "confidence": 0.0,
        "name": "",
        "description": "",
        "when_to_use": "",
        "body": "",
    })
    assert SkillCurator._parse_response(raw) is None


def test_parse_response_invalid_json_returns_none():
    assert SkillCurator._parse_response("not json at all") is None


def test_parse_response_missing_fields_defaults():
    raw = json.dumps({"is_reusable": True, "confidence": 0.8})
    proposal = SkillCurator._parse_response(raw)
    assert proposal is not None
    assert proposal.name == ""
    assert proposal.body == ""


# ── SkillCurator._format_conversation ────────────────────────────────────────

def test_format_conversation_includes_roles():
    messages = [Message.user("hello"), Message.assistant("world")]
    result = SkillCurator._format_conversation(messages)
    assert "[USER]:" in result
    assert "[ASSISTANT]:" in result
    assert "hello" in result
    assert "world" in result


def test_format_conversation_truncates_long_messages():
    long_text = "x" * 1000
    messages = [Message.user(long_text)]
    result = SkillCurator._format_conversation(messages)
    assert len(result) < len(long_text) + 20


# ── SkillCurator.analyze ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_returns_none_for_empty_messages():
    from unittest.mock import MagicMock
    curator = SkillCurator(provider=MagicMock())
    result = await curator.analyze([])
    assert result is None


@pytest.mark.asyncio
async def test_analyze_returns_proposal_above_threshold():
    from typing import AsyncIterator

    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    response_json = json.dumps({
        "is_reusable": True,
        "confidence": 0.9,
        "name": "systematic-debug",
        "description": "Step-by-step debugging approach.",
        "when_to_use": "When a test fails unexpectedly.",
        "body": "## Debugging\n\n1. Reproduce.\n2. Isolate.\n3. Fix.",
    })

    class FakeProvider(Provider):
        @property
        def model(self): return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content=response_json, tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    curator = SkillCurator(provider=FakeProvider(), confidence_threshold=0.7)
    messages = [Message.user("Fix the bug"), Message.assistant("I'll debug it step by step.")]
    proposal = await curator.analyze(messages)

    assert proposal is not None
    assert proposal.name == "systematic-debug"
    assert proposal.confidence == 0.9


@pytest.mark.asyncio
async def test_analyze_returns_none_below_threshold():
    from typing import AsyncIterator

    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    response_json = json.dumps({
        "is_reusable": True,
        "confidence": 0.5,   # below 0.7 threshold
        "name": "weak-skill",
        "description": "Maybe useful.",
        "when_to_use": "Sometimes.",
        "body": "Do stuff.",
    })

    class FakeProvider(Provider):
        @property
        def model(self): return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content=response_json, tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    curator = SkillCurator(provider=FakeProvider(), confidence_threshold=0.7)
    proposal = await curator.analyze([Message.user("hello")])
    assert proposal is None


@pytest.mark.asyncio
async def test_analyze_propagates_session_id():
    from typing import AsyncIterator

    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.schema.session import SessionResult

    response_json = json.dumps({
        "is_reusable": True,
        "confidence": 0.95,
        "name": "tracked-skill",
        "description": "x",
        "when_to_use": "y",
        "body": "z",
    })

    class FakeProvider(Provider):
        @property
        def model(self): return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content=response_json, tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    curator = SkillCurator(provider=FakeProvider())
    result = SessionResult(session_id="sess-42", output="done")
    proposal = await curator.analyze([Message.user("do something")], result=result)

    assert proposal is not None
    assert proposal.source_session_id == "sess-42"


@pytest.mark.asyncio
async def test_analyze_samples_last_n_messages():
    """Curator only sends the last max_messages_to_sample messages."""
    from typing import AsyncIterator

    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    captured: list[list[Message]] = []

    class CapturingProvider(Provider):
        @property
        def model(self): return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            captured.append(messages)
            return LLMResponse(content='{"is_reusable": false, "confidence": 0}', tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    curator = SkillCurator(provider=CapturingProvider(), max_messages_to_sample=3)
    many = [Message.user(f"msg-{i}") for i in range(10)]
    await curator.analyze(many)

    # The user message passed to the provider should only contain the last 3 messages
    assert captured
    user_msg = next(m for m in captured[0] if m.role.value == "user")
    assert "msg-9" in user_msg.text()
    assert "msg-0" not in user_msg.text()

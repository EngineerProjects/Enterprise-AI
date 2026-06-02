"""Tests for the prompt/ module: PromptBuilder, cache helpers, templates."""
from __future__ import annotations

from enterprise_ai.prompt.builder import PromptBuilder
from enterprise_ai.prompt.cache import apply_cache_to_system, apply_cache_to_tools
from enterprise_ai.prompt.templates import BUDGET_NUDGE_MESSAGE, COMPACTION_PROMPT

# ── PromptBuilder.add ─────────────────────────────────────────────────────────

def test_add_single_block():
    p = PromptBuilder().add("You are helpful.")
    assert p.build() == "You are helpful."


def test_add_multiple_blocks_joined_with_separator():
    p = PromptBuilder().add("Block A").add("Block B")
    result = p.build()
    assert "Block A" in result
    assert "Block B" in result
    assert "---" in result


def test_add_empty_string_ignored():
    p = PromptBuilder().add("").add("   ").add("Real content")
    assert p.build() == "Real content"
    assert len(p) == 1


def test_add_strips_whitespace():
    p = PromptBuilder().add("  hello  ")
    assert p.build() == "hello"


def test_chainable():
    result = PromptBuilder().add("A").add("B").add("C").build()
    assert result.count("---") == 2


# ── PromptBuilder.add_project_instructions ────────────────────────────────────

def test_add_project_instructions_no_file(tmp_path):
    """Empty directory → no block added."""
    p = PromptBuilder().add_project_instructions(tmp_path)
    assert p.build() == ""
    assert len(p) == 0


def test_add_project_instructions_reads_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Rules\nDon't break prod.")
    p = PromptBuilder().add_project_instructions(tmp_path)
    assert "Rules" in p.build()
    assert "Project Instructions" in p.build()


# ── PromptBuilder.mark_cached ─────────────────────────────────────────────────

def test_no_cache_markers_by_default():
    p = PromptBuilder().add("hello")
    assert not p.has_cache_markers()


def test_mark_cached_sets_flag_on_last_part():
    p = PromptBuilder().add("A").add("B").mark_cached()
    assert p.has_cache_markers()


def test_mark_cached_on_empty_builder_does_nothing():
    p = PromptBuilder().mark_cached()
    assert not p.has_cache_markers()
    assert len(p) == 0


# ── PromptBuilder.build_anthropic ────────────────────────────────────────────

def test_build_anthropic_no_cache_returns_string():
    p = PromptBuilder().add("System prompt.")
    result = p.build_anthropic()
    assert isinstance(result, str)
    assert result == "System prompt."


def test_build_anthropic_with_cache_returns_list():
    p = PromptBuilder().add("System prompt.").mark_cached()
    result = p.build_anthropic()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["type"] == "text"
    assert result[0]["text"] == "System prompt."
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_build_anthropic_only_last_marked_block_has_cache():
    p = (
        PromptBuilder()
        .add("Block 1")
        .add("Block 2")
        .mark_cached()
    )
    result = p.build_anthropic()
    assert isinstance(result, list)
    assert len(result) == 2
    assert "cache_control" not in result[0]
    assert result[1]["cache_control"] == {"type": "ephemeral"}


def test_build_anthropic_multiple_cached_blocks():
    p = (
        PromptBuilder()
        .add("Static A").mark_cached()
        .add("Static B").mark_cached()
    )
    result = p.build_anthropic()
    assert isinstance(result, list)
    assert result[0]["cache_control"] == {"type": "ephemeral"}
    assert result[1]["cache_control"] == {"type": "ephemeral"}


# ── cache helpers ─────────────────────────────────────────────────────────────

def test_apply_cache_to_system_string():
    result = apply_cache_to_system("You are helpful.")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["text"] == "You are helpful."
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_apply_cache_to_system_existing_blocks():
    blocks = [
        {"type": "text", "text": "Block 1"},
        {"type": "text", "text": "Block 2"},
    ]
    result = apply_cache_to_system(blocks)
    assert len(result) == 2
    assert "cache_control" not in result[0]
    assert result[1]["cache_control"] == {"type": "ephemeral"}


def test_apply_cache_to_system_empty_list():
    result = apply_cache_to_system([])
    assert result == []


def test_apply_cache_to_tools_last_tool_marked():
    tools = [
        {"name": "bash", "description": "run"},
        {"name": "read", "description": "read file"},
    ]
    result = apply_cache_to_tools(tools)
    assert len(result) == 2
    assert "cache_control" not in result[0]
    assert result[0]["name"] == "bash"
    assert result[1]["cache_control"] == {"type": "ephemeral"}


def test_apply_cache_to_tools_single_tool():
    tools = [{"name": "bash", "description": "run"}]
    result = apply_cache_to_tools(tools)
    assert result[0]["cache_control"] == {"type": "ephemeral"}


def test_apply_cache_to_tools_empty():
    assert apply_cache_to_tools([]) == []


def test_cache_helpers_do_not_mutate_originals():
    original = [{"name": "bash"}]
    apply_cache_to_tools(original)
    assert "cache_control" not in original[0]


# ── templates ─────────────────────────────────────────────────────────────────

def test_compaction_prompt_has_placeholder():
    assert "{messages_text}" in COMPACTION_PROMPT


def test_compaction_prompt_formattable():
    result = COMPACTION_PROMPT.format(messages_text="[USER]: hello\n[ASSISTANT]: hi")
    assert "[USER]: hello" in result


def test_budget_nudge_message_is_string():
    assert isinstance(BUDGET_NUDGE_MESSAGE, str)
    assert len(BUDGET_NUDGE_MESSAGE) > 0


def test_templates_are_overridable():
    import enterprise_ai.prompt.templates as tpl

    original = tpl.BUDGET_NUDGE_MESSAGE
    try:
        tpl.BUDGET_NUDGE_MESSAGE = "Poursuis la tâche."
        # The token budget tracker reads from the module at call time
        from enterprise_ai.engine.token_budget import TokenBudgetConfig, TokenBudgetTracker
        cfg = TokenBudgetConfig(turn_token_budget=1_000_000)
        tracker = TokenBudgetTracker(cfg)
        tracker.record_tokens(1_000, 500)
        decision = tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
        assert decision.nudge_message == "Poursuis la tâche."
    finally:
        tpl.BUDGET_NUDGE_MESSAGE = original


# ── Integration: Agent._build_system_prompt uses PromptBuilder ───────────────

def test_agent_build_system_prompt_uses_builder():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        system_prompt="You are a senior engineer.",
    )
    assert "You are a senior engineer." in agent._loop._system_prompt


def test_agent_system_prompt_with_project_instructions(tmp_path):
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    (tmp_path / "AGENTS.md").write_text("Always write tests.")
    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        system_prompt="Base prompt.",
        working_dir=str(tmp_path),
    )
    assert "Always write tests." in agent._loop._system_prompt
    assert "Base prompt." in agent._loop._system_prompt

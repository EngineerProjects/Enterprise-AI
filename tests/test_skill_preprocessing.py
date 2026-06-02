"""Tests for item 11: skill preprocessing."""
from __future__ import annotations

from enterprise_ai.skills.preprocessing import preprocess
from enterprise_ai.skills.skill import Skill

# ── Variable substitution ─────────────────────────────────────────────────────

def test_no_placeholders_passthrough():
    assert preprocess("hello world") == "hello world"


def test_date_default_var():
    from datetime import date
    result = preprocess("Today is ${date}.")
    assert date.today().isoformat() in result


def test_pwd_default_var():
    import os
    result = preprocess("Working in ${pwd}.")
    assert os.getcwd() in result


def test_custom_var_substitution():
    result = preprocess("Session: ${session_id}", vars={"session_id": "abc-123"})
    assert "abc-123" in result


def test_custom_var_overrides_default():
    result = preprocess("Date: ${date}", vars={"date": "2099-01-01"})
    assert "2099-01-01" in result


def test_unknown_placeholder_left_as_is():
    result = preprocess("Value: ${unknown_var}")
    assert "${unknown_var}" in result


def test_multiple_vars_substituted():
    result = preprocess(
        "Agent ${agent_id} on ${host}",
        vars={"agent_id": "worker-1", "host": "server-42"},
    )
    assert "worker-1" in result
    assert "server-42" in result


def test_same_var_multiple_times():
    result = preprocess("${name} is ${name}", vars={"name": "Claude"})
    assert result == "Claude is Claude"


# ── Shell block execution ─────────────────────────────────────────────────────

def test_shell_disabled_by_default():
    body = "Result:\n```bash\necho hello\n```"
    result = preprocess(body)
    assert "echo hello" in result   # block not executed
    assert "hello" in result        # but still present as literal


def test_shell_enabled_executes_block():
    body = "```bash\necho hello_from_shell\n```"
    result = preprocess(body, enable_shell=True)
    assert "hello_from_shell" in result
    assert "```" not in result      # fence replaced by output


def test_shell_error_leaves_block_unchanged():
    body = "```bash\nthis_command_does_not_exist_xyz\n```"
    result = preprocess(body, enable_shell=True)
    assert "this_command_does_not_exist_xyz" in result


def test_shell_empty_output_leaves_block_unchanged():
    body = "```bash\n: # no-op\n```"
    result = preprocess(body, enable_shell=True)
    # no-op prints nothing; block is left in place
    assert ": # no-op" in result


def test_sh_tag_also_executed():
    body = "```sh\necho sh_executed\n```"
    result = preprocess(body, enable_shell=True)
    assert "sh_executed" in result


def test_vars_substituted_before_shell():
    """Variables in shell blocks are substituted before execution."""
    body = "```bash\necho ${greeting}\n```"
    result = preprocess(body, vars={"greeting": "hi_from_var"}, enable_shell=True)
    assert "hi_from_var" in result


# ── Skill.system_prompt_block() integration ───────────────────────────────────

def test_skill_block_applies_vars():
    skill = Skill(
        name="my_skill",
        body="Agent is ${agent_id}.",
    )
    block = skill.system_prompt_block(vars={"agent_id": "worker-7"})
    assert "worker-7" in block


def test_skill_block_default_vars_applied():
    from datetime import date
    skill = Skill(name="date_skill", body="Date: ${date}")
    block = skill.system_prompt_block()
    assert date.today().isoformat() in block


def test_skill_block_shell_disabled_by_default():
    skill = Skill(name="shell_skill", body="```bash\necho secret\n```")
    block = skill.system_prompt_block()
    assert "echo secret" in block  # not executed


def test_skill_block_shell_enabled():
    skill = Skill(name="shell_skill", body="```bash\necho from_shell\n```")
    block = skill.system_prompt_block(enable_shell=True)
    assert "from_shell" in block


def test_skill_block_when_to_use_preserved():
    skill = Skill(
        name="my_skill",
        when_to_use="When reviewing code",
        body="Instructions: ${lang}",
    )
    block = skill.system_prompt_block(vars={"lang": "Python"})
    assert "When reviewing code" in block
    assert "Python" in block


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_skill_vars_passed_to_skills():
    """skill_vars passed to Agent propagate into skill blocks."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    skill = Skill(
        name="test_skill",
        body="Project root: ${project_root}",
    )
    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            skills=[skill],
            skill_vars={"project_root": "/srv/myproject"},
        )
    assert "/srv/myproject" in agent._loop._system_prompt

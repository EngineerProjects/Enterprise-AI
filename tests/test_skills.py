"""
Unit tests for the skill system: loader, registry, and Agent integration.
No LLM calls — we test parsing, resolution, and prompt injection.
"""
import textwrap
from pathlib import Path

from enterprise_ai.skills.loader import _parse_simple_yaml, load_skill_file
from enterprise_ai.skills.registry import SkillRegistry
from enterprise_ai.skills.skill import Skill

# ---------------------------------------------------------------------------
# YAML parser
# ---------------------------------------------------------------------------

def test_parse_simple_yaml_string_values():
    text = textwrap.dedent("""\
        name: code-review
        description: "Review code carefully"
        context: inline
        version: 1.0.0
    """)
    result = _parse_simple_yaml(text)
    assert result["name"] == "code-review"
    assert result["description"] == "Review code carefully"
    assert result["context"] == "inline"


def test_parse_simple_yaml_list():
    text = textwrap.dedent("""\
        allowed-tools:
          - bash
          - file_editor
          - code_search
    """)
    result = _parse_simple_yaml(text)
    assert result["allowed-tools"] == ["bash", "file_editor", "code_search"]


def test_parse_simple_yaml_bool():
    text = "user-invocable: false\n"
    result = _parse_simple_yaml(text)
    assert result["user-invocable"] is False


def test_parse_simple_yaml_null():
    text = "model: null\n"
    result = _parse_simple_yaml(text)
    assert result["model"] is None


# ---------------------------------------------------------------------------
# Skill file loader
# ---------------------------------------------------------------------------

def test_load_skill_file_with_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(textwrap.dedent("""\
        ---
        name: my-skill
        description: "Does something useful"
        when_to_use: "Use when needed"
        allowed-tools:
          - bash
          - file_editor
        context: fork
        version: 2.0.0
        ---

        # My Skill

        Do the thing properly.
    """))

    skill = load_skill_file(skill_file)
    assert skill.name == "my-skill"
    assert skill.description == "Does something useful"
    assert skill.when_to_use == "Use when needed"
    assert skill.allowed_tools == ["bash", "file_editor"]
    assert skill.context == "fork"
    assert skill.version == "2.0.0"
    assert "Do the thing properly" in skill.body


def test_load_skill_file_no_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "plain-skill.md"
    skill_file.write_text("# Plain Skill\n\nJust markdown content.")

    skill = load_skill_file(skill_file)
    assert skill.name == "plain-skill"  # falls back to filename stem
    assert "Just markdown content" in skill.body
    assert skill.allowed_tools == []
    assert skill.context == "inline"


def test_load_skill_file_partial_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "partial.md"
    skill_file.write_text(textwrap.dedent("""\
        ---
        name: partial
        ---
        Body content.
    """))
    skill = load_skill_file(skill_file)
    assert skill.name == "partial"
    assert "Body content" in skill.body
    assert skill.allowed_tools == []


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------

def test_registry_finds_skills_in_directory(tmp_path: Path):
    (tmp_path / "skill-a.md").write_text("---\nname: skill-a\n---\nDo A.")
    (tmp_path / "skill-b.md").write_text("---\nname: skill-b\n---\nDo B.")

    registry = SkillRegistry(extra_dirs=[tmp_path])
    assert registry.get("skill-a") is not None
    assert registry.get("skill-b") is not None
    assert registry.get("nonexistent") is None


def test_registry_resolve_returns_known_skills(tmp_path: Path):
    (tmp_path / "skill-a.md").write_text("---\nname: skill-a\n---\nDo A.")
    registry = SkillRegistry(extra_dirs=[tmp_path])

    resolved = registry.resolve(["skill-a", "unknown-skill"])
    assert len(resolved) == 1
    assert resolved[0].name == "skill-a"


def test_registry_extra_dirs_take_priority(tmp_path: Path):
    builtin_dir = tmp_path / "builtin"
    builtin_dir.mkdir()
    (builtin_dir / "my-skill.md").write_text("---\nname: my-skill\n---\nBuiltin version.")

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "my-skill.md").write_text("---\nname: my-skill\n---\nProject version.")

    # extra_dirs listed first → project takes priority
    registry = SkillRegistry(extra_dirs=[project_dir, builtin_dir])
    skill = registry.get("my-skill")
    assert skill is not None
    assert "Project version" in skill.body


def test_registry_register_programmatic():
    registry = SkillRegistry()
    skill = Skill(name="custom", description="A custom skill", body="Do custom things.")
    registry.register(skill)
    assert registry.get("custom") is not None


def test_registry_reload_clears_cache(tmp_path: Path):
    (tmp_path / "skill-a.md").write_text("---\nname: skill-a\n---\nV1.")
    registry = SkillRegistry(extra_dirs=[tmp_path])
    assert registry.get("skill-a") is not None

    registry.reload()
    # After reload it re-scans from disk — skill-a still exists
    assert registry.get("skill-a") is not None


# ---------------------------------------------------------------------------
# Built-in skills
# ---------------------------------------------------------------------------

def test_builtin_skills_loadable():
    """The registry should be able to load the built-in skills we shipped."""
    registry = SkillRegistry()
    skills = registry.all()
    names = [s.name for s in skills]
    assert "code-review" in names
    assert "systematic-debugging" in names
    assert "web-research" in names
    assert "test-driven-development" in names


def test_builtin_code_review_has_allowed_tools():
    registry = SkillRegistry()
    skill = registry.get("code-review")
    assert skill is not None
    assert skill.restricts_tools()
    assert "file_editor" in skill.allowed_tools


# ---------------------------------------------------------------------------
# Skill → system prompt injection
# ---------------------------------------------------------------------------

def test_skill_system_prompt_block_with_when_to_use():
    skill = Skill(
        name="debug",
        when_to_use="When facing a bug",
        body="Follow the systematic debugging process.",
    )
    block = skill.system_prompt_block()
    assert "When facing a bug" in block
    assert "systematic debugging" in block


def test_skill_system_prompt_block_without_when_to_use():
    skill = Skill(name="plain", body="Just do the task.")
    block = skill.system_prompt_block()
    assert "Just do the task" in block


# ---------------------------------------------------------------------------
# Agent skill integration (no LLM calls)
# ---------------------------------------------------------------------------

def test_agent_accepts_skill_names(tmp_path: Path):
    """Agent resolves skill names and injects them into the system prompt."""
    (tmp_path / "my-skill.md").write_text(textwrap.dedent("""\
        ---
        name: my-skill
        ---
        Always end your response with 'Done!'.
    """))

    from enterprise_ai.skills.registry import SkillRegistry
    registry = SkillRegistry(extra_dirs=[tmp_path])
    skill = registry.get("my-skill")
    assert skill is not None

    # Test _build_system_prompt directly without creating a full Agent
    from enterprise_ai.agent.agent import Agent
    prompt = Agent._build_system_prompt("Base prompt.", [skill])
    assert "Base prompt" in prompt
    assert "Done!" in prompt


def test_agent_merged_allowed_tools_no_restriction():
    from enterprise_ai.agent.agent import Agent
    skills = [Skill(name="a", body="x"), Skill(name="b", body="y")]
    result = Agent._merged_allowed_tools(skills)
    assert result is None  # no restrictions → all tools allowed


def test_agent_merged_allowed_tools_with_restriction():
    from enterprise_ai.agent.agent import Agent
    skills = [
        Skill(name="a", body="x", allowed_tools=["bash", "file_editor"]),
        Skill(name="b", body="y", allowed_tools=["web_search"]),
    ]
    result = Agent._merged_allowed_tools(skills)
    assert result == {"bash", "file_editor", "web_search"}

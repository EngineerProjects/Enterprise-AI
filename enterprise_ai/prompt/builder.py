"""
PromptBuilder — fluent system-prompt assembly with optional Anthropic caching.

Usage:
    from enterprise_ai.prompt import PromptBuilder

    system = (
        PromptBuilder()
        .add("You are a senior software engineer.")
        .add_project_instructions(".")
        .add_skill("code-review")
        .mark_cached()          # everything above will be cached by Anthropic
        .build()
    )
    agent = Agent(provider=..., system_prompt=system, cache_system_prompt=True)

    # Or build the Anthropic-native format directly (list[dict] with cache_control):
    anthropic_system = PromptBuilder().add("...").mark_cached().build_anthropic()
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enterprise_ai.skills.skill import Skill

_SEPARATOR = "\n\n---\n\n"


@dataclass
class _Part:
    content: str
    cached: bool = False


class PromptBuilder:
    """Fluent builder for system prompts."""

    def __init__(self) -> None:
        self._parts: list[_Part] = []

    # ── Content methods ────────────────────────────────────────────────────

    def add(self, text: str) -> "PromptBuilder":
        """Add a free-form text block."""
        stripped = text.strip()
        if stripped:
            self._parts.append(_Part(content=stripped))
        return self

    def add_project_instructions(self, workdir: str | Path = ".") -> "PromptBuilder":
        """Read AGENTS.md / ENTERPRISE_AI.md from workdir and add if found."""
        from enterprise_ai.engine.instructions import read_project_instructions

        instructions = read_project_instructions(workdir)
        if instructions:
            self._parts.append(_Part(content=f"## Project Instructions\n\n{instructions}"))
        return self

    def add_skill(self, skill: str | Skill) -> "PromptBuilder":
        """Resolve a skill by name (or pass a Skill object) and append its block."""
        from enterprise_ai.skills.registry import resolve_skills

        if isinstance(skill, str):
            resolved = resolve_skills([skill])
        else:
            resolved = [skill]

        for s in resolved:
            block = s.system_prompt_block()
            if block:
                self._parts.append(_Part(content=block))
        return self

    # ── Cache control ──────────────────────────────────────────────────────

    def mark_cached(self) -> "PromptBuilder":
        """Mark the most-recently added part for Anthropic cache_control.

        In the Anthropic API, cache_control on the last block caches all
        preceding content. Call this after adding your expensive static context
        (e.g. after add_project_instructions or add_skill).
        """
        if self._parts:
            last = self._parts[-1]
            self._parts[-1] = _Part(content=last.content, cached=True)
        return self

    # ── Build methods ──────────────────────────────────────────────────────

    def build(self) -> str:
        """Return the assembled prompt as a plain string.

        Compatible with Agent(system_prompt=...) for any provider.
        """
        return _SEPARATOR.join(p.content for p in self._parts if p.content)

    def build_anthropic(self) -> str | list[dict]:
        """Return the system prompt in Anthropic API format.

        Returns a plain string if no parts are marked for caching.
        Returns a list of content blocks with cache_control where marked.
        """
        if not any(p.cached for p in self._parts):
            return self.build()

        blocks: list[dict] = []
        for part in self._parts:
            if not part.content:
                continue
            block: dict = {"type": "text", "text": part.content}
            if part.cached:
                block["cache_control"] = {"type": "ephemeral"}
            blocks.append(block)
        return blocks or ""

    # ── Introspection ──────────────────────────────────────────────────────

    def has_cache_markers(self) -> bool:
        return any(p.cached for p in self._parts)

    def __len__(self) -> int:
        return len(self._parts)

    def __bool__(self) -> bool:
        return bool(self._parts)

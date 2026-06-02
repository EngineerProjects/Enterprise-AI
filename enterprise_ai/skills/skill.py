from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """
    A parsed skill file.

    A skill is a Markdown file with YAML frontmatter that injects reusable
    procedural instructions into an agent's context. Skills define HOW to do
    a specific task (code-review, brainstorming, systematic-debugging) — they
    are NOT role definitions.

    File format:
        ---
        name: code-review
        description: "Review code for correctness, security and style."
        when_to_use: "When asked to review code or before merging."
        allowed-tools:
          - file_editor
          - code_search
        model: claude-haiku-4-5-20251001   # optional model override
        context: inline                     # inline | fork
        ---

        # Code Review

        Review the code systematically...
    """

    name: str
    description: str = ""
    when_to_use: str = ""
    body: str = ""                          # Markdown body injected into system prompt
    allowed_tools: list[str] = field(default_factory=list)   # empty = all tools allowed
    model: str | None = None               # None = use agent default
    context: str = "inline"               # inline | fork
    user_invocable: bool = True
    version: str = ""
    source_path: Path | None = None

    def system_prompt_block(self) -> str:
        """Returns the text block to inject into the agent's system prompt."""
        lines = []
        if self.when_to_use:
            lines.append(f"<!-- Skill: {self.name} | {self.when_to_use} -->")
        lines.append(self.body.strip())
        return "\n".join(lines)

    def restricts_tools(self) -> bool:
        return bool(self.allowed_tools)

    def __str__(self) -> str:
        return f"Skill({self.name!r}, context={self.context})"

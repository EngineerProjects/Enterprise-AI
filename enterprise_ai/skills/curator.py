"""
SkillCurator — post-session analysis that proposes reusable skills.

After a successful agent run, feed the conversation to the curator.
If the session follows a clear, generalisable procedure the curator
emits a SkillProposal you can persist, review, and re-inject later.

Usage::

    curator = SkillCurator(provider=provider, confidence_threshold=0.75)
    proposal = await curator.analyze(agent.snapshot(), result)
    if proposal:
        path = proposal.save("~/.enterprise_ai/skills/")
        agent.add_skill(proposal.to_skill())
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from enterprise_ai.schema import Message

if TYPE_CHECKING:
    from enterprise_ai.providers.base import Provider
    from enterprise_ai.schema.session import SessionResult
    from enterprise_ai.skills.skill import Skill


_CURATOR_SYSTEM = """\
You are a skill-extraction assistant.

Given a conversation between a user and an AI agent, decide whether the agent
followed a clear, reusable procedure that would benefit other sessions.

A good reusable skill:
- Applies to a broad class of tasks (not tied to one specific repo, file, or user name)
- Has distinct, repeatable steps
- Can be described as a general procedure

Respond ONLY with a single JSON object (no markdown fences, no extra text):
{
  "is_reusable": true | false,
  "confidence": 0.0-1.0,
  "name": "kebab-case-skill-name",
  "description": "One sentence describing what the skill does.",
  "when_to_use": "One sentence: when to apply this skill.",
  "body": "Markdown body with the procedural instructions extracted from the conversation."
}

If is_reusable is false, set confidence to 0 and leave the other fields as empty strings.
"""


@dataclass
class SkillProposal:
    """A proposed skill extracted from a completed agent session."""

    name: str
    description: str
    when_to_use: str
    body: str
    confidence: float = 0.0
    source_session_id: str = ""

    def to_skill(self) -> "Skill":
        """Convert to a live :class:`~enterprise_ai.skills.Skill` object."""
        from enterprise_ai.skills.skill import Skill

        return Skill(
            name=self.name,
            description=self.description,
            when_to_use=self.when_to_use,
            body=self.body,
        )

    def to_markdown(self) -> str:
        """Serialise to the standard skill .md frontmatter format."""
        lines = ["---", f"name: {self.name}"]
        if self.description:
            lines.append(f'description: "{self.description}"')
        if self.when_to_use:
            lines.append(f'when_to_use: "{self.when_to_use}"')
        lines += ["---", "", self.body.strip(), ""]
        return "\n".join(lines)

    def save(self, directory: str | Path) -> Path:
        """Write the proposal as a .md file into *directory*. Returns the path."""
        path = Path(directory) / f"{self.name}.md"
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


class SkillCurator:
    """
    Analyses a completed agent session and proposes a reusable skill.

    The curator asks the provider to inspect the conversation and return a
    structured JSON proposal.  Proposals below *confidence_threshold* are
    discarded so callers only receive high-confidence suggestions.
    """

    def __init__(
        self,
        provider: "Provider",
        confidence_threshold: float = 0.7,
        max_messages_to_sample: int = 20,
    ) -> None:
        self._provider = provider
        self._threshold = confidence_threshold
        self._max_sample = max_messages_to_sample

    async def analyze(
        self,
        messages: list[Message],
        result: "SessionResult | None" = None,
    ) -> SkillProposal | None:
        """
        Analyse *messages* from a completed session.

        Returns a :class:`SkillProposal` whose confidence >=
        ``confidence_threshold``, or ``None`` if no reusable skill was found.
        """
        if not messages:
            return None

        sampled = messages[-self._max_sample :]
        conversation = self._format_conversation(sampled)

        query = [
            Message.system(_CURATOR_SYSTEM),
            Message.user(f"Conversation to analyse:\n\n{conversation}"),
        ]
        resp = await self._provider.complete(query, max_tokens=2048)

        proposal = self._parse_response(resp.content)
        if proposal is None:
            return None
        if result is not None:
            proposal.source_session_id = result.session_id
        if proposal.confidence < self._threshold or not proposal.name:
            return None
        return proposal

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _format_conversation(messages: list[Message]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            text = msg.text()[:500]
            lines.append(f"[{role.upper()}]: {text}")
        return "\n\n".join(lines)

    @staticmethod
    def _parse_response(text: str) -> SkillProposal | None:
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if not data.get("is_reusable"):
            return None
        return SkillProposal(
            name=data.get("name", ""),
            description=data.get("description", ""),
            when_to_use=data.get("when_to_use", ""),
            body=data.get("body", ""),
            confidence=float(data.get("confidence", 0.0)),
        )

"""
ContextEngine — pluggable interface for conversation context management.

Implement this interface to replace or extend the built-in LLM-based
compaction with custom strategies: sliding window, RAG-based retrieval,
hierarchical summarisation, etc.

Usage:
    from enterprise_ai.memory.context_engine import ContextEngine
    from enterprise_ai.schema import Message

    class MyEngine(ContextEngine):
        def should_compact(self, messages):
            return len(messages) > 50

        async def compact(self, messages, system_prompt=""):
            # keep the last 20 messages
            return messages[-20:]

    agent = Agent(provider=..., context_engine=MyEngine())

The built-in CompactionEngine subclasses ContextEngine and is used when
Agent is constructed with a compaction_config= argument.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from enterprise_ai.schema import Message


class ContextEngine(ABC):
    """
    Abstract base for context management strategies.

    The two required methods (should_compact / compact) match the existing
    CompactionEngine interface so all call sites remain compatible.

    The four lifecycle hooks have default no-op implementations — override
    them when your engine needs to track session boundaries.
    """

    @abstractmethod
    def should_compact(self, messages: list[Message]) -> bool:
        """Return True when compaction should be triggered."""

    @abstractmethod
    async def compact(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> list[Message]:
        """
        Reduce the message list.
        Must return a non-empty list — the caller replaces the current
        history with the returned list.
        """

    # ── Optional lifecycle hooks ──────────────────────────────────────────────

    def on_session_start(self, session_id: str) -> None:
        """Called when a session begins (before the first LLM call)."""

    def on_session_end(self, session_id: str, messages: list[Message]) -> None:
        """Called when a session finishes (after the last LLM call)."""

    def on_session_reset(self) -> None:
        """Called when the in-memory history is cleared."""

    def carry_over_new_session_context(
        self,
        old_session_id: str,
        new_session_id: str,
    ) -> None:
        """
        Called when a branch session starts from an existing session.
        Override to migrate engine-internal state (e.g. vector indexes)
        from the old session to the new one.
        """

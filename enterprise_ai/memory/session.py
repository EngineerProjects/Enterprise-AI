from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from enterprise_ai.schema import Message

if TYPE_CHECKING:
    from enterprise_ai.memory.compaction import CompactionEngine


class SessionMemory:
    """In-memory sliding window conversation history."""

    def __init__(
        self,
        max_messages: int = 200,
        compaction_engine: CompactionEngine | None = None,
    ) -> None:
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self._compaction_engine: Any = compaction_engine

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def get(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    async def maybe_compact(self, system_prompt: str = "") -> bool:
        """Compact old messages via LLM summarization if configured and threshold reached."""
        if self._compaction_engine is None:
            return False
        messages = list(self._messages)
        if not self._compaction_engine.should_compact(messages):
            return False
        compacted = await self._compaction_engine.compact(messages, system_prompt)
        self._messages.clear()
        for msg in compacted:
            self._messages.append(msg)
        return True

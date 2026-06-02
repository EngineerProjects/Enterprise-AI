from __future__ import annotations

from collections import deque

from enterprise_ai.schema import Message


class SessionMemory:
    """In-memory sliding window conversation history."""

    def __init__(self, max_messages: int = 200) -> None:
        self._messages: deque[Message] = deque(maxlen=max_messages)

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def get(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

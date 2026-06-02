from __future__ import annotations

from dataclasses import dataclass

import enterprise_ai.prompt.templates as _tpl
from enterprise_ai.memory.context_engine import ContextEngine
from enterprise_ai.providers.base import Provider
from enterprise_ai.schema import Message

_DEFAULT_CONTEXT_WINDOW = 200_000


@dataclass
class CompactionConfig:
    auto_compact_threshold: float = 0.85
    compact_target_percentage: float = 0.50
    max_summary_tokens: int = 2_000
    auto_compact_buffer_tokens: int = 13_000
    max_consecutive_failures: int = 3
    keep_recent_messages: int = 10


class CompactionEngine(ContextEngine):
    def __init__(self, provider: Provider, config: CompactionConfig | None = None) -> None:
        self._provider = provider
        self._config = config or CompactionConfig()
        self._consecutive_failures: int = 0

    def _estimate_tokens(self, messages: list[Message]) -> int:
        return sum(len(m.text()) for m in messages) // 4

    def should_compact(self, messages: list[Message]) -> bool:
        if self._consecutive_failures >= self._config.max_consecutive_failures:
            return False
        estimated = self._estimate_tokens(messages)
        threshold = int(_DEFAULT_CONTEXT_WINDOW * self._config.auto_compact_threshold)
        return estimated >= threshold

    def _split(self, messages: list[Message]) -> tuple[list[Message], list[Message]]:
        keep = self._config.keep_recent_messages
        if len(messages) <= keep:
            return [], list(messages)
        return list(messages[:-keep]), list(messages[-keep:])

    async def compact(self, messages: list[Message], system_prompt: str = "") -> list[Message]:
        to_summarise, to_keep = self._split(messages)
        if not to_summarise:
            return messages

        messages_text = "\n".join(
            f"[{m.role.value.upper()}]: {m.text()[:400]}" for m in to_summarise
        )
        prompt = _tpl.COMPACTION_PROMPT.format(messages_text=messages_text)

        try:
            resp = await self._provider.complete(
                [Message.user(prompt)],
                max_tokens=self._config.max_summary_tokens,
            )
            summary = resp.content.strip()
            self._consecutive_failures = 0
        except Exception:
            self._consecutive_failures += 1
            return messages

        summary_msg = Message.user(
            f"[Conversation summary — earlier context compacted]\n\n{summary}"
        )
        result: list[Message] = []
        if system_prompt:
            result.append(Message.system(system_prompt))
        result.append(summary_msg)
        result.extend(to_keep)
        return result

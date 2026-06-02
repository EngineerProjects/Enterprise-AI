"""
Anthropic cache_control helpers.

Applying cache_control marks a "checkpoint" in the Anthropic API:
everything up to and including the marked block is cached server-side
for 5 minutes (90 % cost reduction on cache hits).

Recommended pattern:
  - Mark the last system-prompt block
  - Mark the last tool schema
"""
from __future__ import annotations


def apply_cache_to_system(system: str | list[dict]) -> list[dict]:
    """Wrap a system prompt string (or existing block list) with cache_control.

    The last block gets cache_control = {"type": "ephemeral"}, which causes
    Anthropic to cache all preceding context up to that point.
    """
    if isinstance(system, str):
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    if not system:
        return system

    blocks = list(system)
    last = dict(blocks[-1])
    last["cache_control"] = {"type": "ephemeral"}
    return [*blocks[:-1], last]


def apply_cache_to_tools(tools: list[dict]) -> list[dict]:
    """Add cache_control to the last tool schema in the list.

    This caches all tool definitions up to and including the last one.
    """
    if not tools:
        return tools

    result = list(tools)
    last = dict(result[-1])
    last["cache_control"] = {"type": "ephemeral"}
    return [*result[:-1], last]

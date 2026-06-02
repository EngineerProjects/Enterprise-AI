from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrimStrategy(str, Enum):
    truncate = "truncate"  # keep head, cut tail
    snip = "snip"          # keep head + tail, cut middle
    preview = "preview"    # keep first N lines + summary note


@dataclass
class TrimConfig:
    max_chars: int = 40_000
    strategy: TrimStrategy = TrimStrategy.snip
    # snip ratios: head gets 60%, tail gets 30%, 10% margin
    snip_head_ratio: float = 0.60
    snip_tail_ratio: float = 0.30
    # preview: number of lines to keep
    preview_lines: int = 20


_DEFAULT_CONFIG = TrimConfig()


def trim_tool_result(content: str, config: TrimConfig | None = None) -> str:
    """
    Trim oversized tool output using the configured strategy.
    Returns the original string unchanged if within the limit.
    """
    cfg = config or _DEFAULT_CONFIG
    if len(content) <= cfg.max_chars:
        return content

    if cfg.strategy == TrimStrategy.truncate:
        return (
            content[: cfg.max_chars]
            + f"\n\n[... output truncated at {cfg.max_chars:,} chars]"
        )

    if cfg.strategy == TrimStrategy.snip:
        head_size = int(cfg.max_chars * cfg.snip_head_ratio)
        tail_size = int(cfg.max_chars * cfg.snip_tail_ratio)
        removed = len(content) - head_size - tail_size
        head = content[:head_size]
        tail = content[-tail_size:]
        return f"{head}\n\n[... {removed:,} chars snipped ...]\n\n{tail}"

    if cfg.strategy == TrimStrategy.preview:
        lines = content.splitlines()
        kept = lines[: cfg.preview_lines]
        remaining_lines = len(lines) - cfg.preview_lines
        result = "\n".join(kept)
        if remaining_lines > 0:
            result += (
                f"\n\n[... {remaining_lines:,} more lines,"
                f" {len(content):,} total chars]"
            )
        return result

    # fallback
    return content[: cfg.max_chars] + "\n\n[... output truncated]"

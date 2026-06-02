"""Tests for smart tool result trimming (micro-compaction)."""

from enterprise_ai.execution.compaction import TrimConfig, TrimStrategy, trim_tool_result


def _make_content(n_chars: int) -> str:
    """Create a content string of exactly n_chars."""
    line = "abcdefghij\n"  # 11 chars
    times = (n_chars // len(line)) + 1
    return (line * times)[:n_chars]


# ── No trimming needed ──────────────────────────────────────────────────────

def test_no_trim_under_limit():
    content = _make_content(1_000)
    result = trim_tool_result(content)
    assert result == content


def test_no_trim_at_exact_limit():
    content = _make_content(40_000)
    result = trim_tool_result(content)
    assert result == content


# ── Truncate strategy ───────────────────────────────────────────────────────

def test_truncate_cuts_at_limit():
    content = _make_content(60_000)
    cfg = TrimConfig(max_chars=40_000, strategy=TrimStrategy.truncate)
    result = trim_tool_result(content, cfg)
    assert len(result) > 40_000  # includes the note
    assert result.startswith(content[:40_000])
    assert "truncated" in result


def test_truncate_note_contains_limit():
    content = _make_content(50_000)
    cfg = TrimConfig(max_chars=30_000, strategy=TrimStrategy.truncate)
    result = trim_tool_result(content, cfg)
    assert "30,000" in result or "30000" in result


# ── Snip strategy (default) ─────────────────────────────────────────────────

def test_snip_preserves_head_and_tail():
    content = "HEAD" + "x" * 50_000 + "TAIL"
    cfg = TrimConfig(max_chars=40_000, strategy=TrimStrategy.snip)
    result = trim_tool_result(content, cfg)
    assert "HEAD" in result
    assert "TAIL" in result


def test_snip_marker_present():
    content = _make_content(60_000)
    cfg = TrimConfig(max_chars=40_000, strategy=TrimStrategy.snip)
    result = trim_tool_result(content, cfg)
    assert "snipped" in result


def test_snip_marker_contains_removed_count():
    content = _make_content(60_000)
    cfg = TrimConfig(max_chars=40_000, strategy=TrimStrategy.snip)
    result = trim_tool_result(content, cfg)
    # Removed chars = 60_000 - head(24_000) - tail(12_000) = 24_000
    assert "24,000" in result or "24000" in result


def test_snip_result_shorter_than_input():
    content = _make_content(80_000)
    result = trim_tool_result(content)
    assert len(result) < len(content)


# ── Preview strategy ────────────────────────────────────────────────────────

def test_preview_keeps_first_n_lines():
    lines = [f"line {i}" for i in range(100)]
    content = "\n".join(lines)
    cfg = TrimConfig(max_chars=50, strategy=TrimStrategy.preview, preview_lines=5)
    result = trim_tool_result(content, cfg)
    for i in range(5):
        assert f"line {i}" in result


def test_preview_note_shows_remaining_lines():
    lines = [f"line {i}" for i in range(100)]
    content = "\n".join(lines)
    cfg = TrimConfig(max_chars=50, strategy=TrimStrategy.preview, preview_lines=5)
    result = trim_tool_result(content, cfg)
    assert "95" in result  # 100 - 5 = 95 more lines


# ── Default config ───────────────────────────────────────────────────────────

def test_default_config_uses_snip():
    content = _make_content(60_000)
    result = trim_tool_result(content)
    assert "snipped" in result


def test_custom_max_chars():
    content = _make_content(10_000)
    cfg = TrimConfig(max_chars=5_000, strategy=TrimStrategy.truncate)
    result = trim_tool_result(content, cfg)
    assert result.startswith(content[:5_000])

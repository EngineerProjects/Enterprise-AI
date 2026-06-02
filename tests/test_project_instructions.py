"""Tests for project instructions loader."""
import pytest

from enterprise_ai.engine.project_instructions import _MAX_BYTES, read_project_instructions


def test_reads_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("You are a helpful assistant.")
    result = read_project_instructions(tmp_path)
    assert result == "You are a helpful assistant."


def test_reads_enterprise_ai_md(tmp_path):
    (tmp_path / "ENTERPRISE_AI.md").write_text("Enterprise AI instructions.")
    result = read_project_instructions(tmp_path)
    assert result == "Enterprise AI instructions."


def test_reads_dot_dir_instructions(tmp_path):
    dot_dir = tmp_path / ".enterprise_ai"
    dot_dir.mkdir()
    (dot_dir / "instructions.md").write_text("Dot dir instructions.")
    result = read_project_instructions(tmp_path)
    assert result == "Dot dir instructions."


def test_priority_agents_md_wins(tmp_path):
    (tmp_path / "AGENTS.md").write_text("From AGENTS.md")
    (tmp_path / "ENTERPRISE_AI.md").write_text("From ENTERPRISE_AI.md")
    result = read_project_instructions(tmp_path)
    assert result == "From AGENTS.md"


def test_priority_enterprise_ai_over_dot_dir(tmp_path):
    (tmp_path / "ENTERPRISE_AI.md").write_text("From ENTERPRISE_AI.md")
    dot_dir = tmp_path / ".enterprise_ai"
    dot_dir.mkdir()
    (dot_dir / "instructions.md").write_text("From dot dir")
    result = read_project_instructions(tmp_path)
    assert result == "From ENTERPRISE_AI.md"


def test_returns_empty_if_no_file(tmp_path):
    result = read_project_instructions(tmp_path)
    assert result == ""


def test_empty_file_skipped(tmp_path):
    (tmp_path / "AGENTS.md").write_text("   \n  ")
    (tmp_path / "ENTERPRISE_AI.md").write_text("Fallback content.")
    result = read_project_instructions(tmp_path)
    assert result == "Fallback content."


def test_truncates_at_32kb(tmp_path):
    # Lines of exactly 100 "x" + newline — any partial line means a mid-line cut
    line = "x" * 100 + "\n"
    content = line * 340  # ~34 KB, over the 32 KB limit
    (tmp_path / "AGENTS.md").write_bytes(content.encode())
    result = read_project_instructions(tmp_path)
    # Must be within the byte limit
    assert len(result.encode()) <= _MAX_BYTES
    # Input is larger than the limit, so some truncation happened
    assert len(result) < len(content.strip())
    # All preserved lines must be complete (length 100), not partial cuts
    for text_line in result.splitlines():
        assert len(text_line) == 100, f"Partial line detected: {len(text_line)} chars"


def test_accepts_path_object(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Path object works.")
    result = read_project_instructions(tmp_path)
    assert result == "Path object works."


def test_accepts_string_path(tmp_path):
    (tmp_path / "AGENTS.md").write_text("String path works.")
    result = read_project_instructions(str(tmp_path))
    assert result == "String path works."


def test_nonexistent_dir_returns_empty():
    result = read_project_instructions("/nonexistent/path/xyz123")
    assert result == ""

from __future__ import annotations

from pathlib import Path

_CANDIDATE_FILES = [
    "AGENTS.md",
    "ENTERPRISE_AI.md",
    ".enterprise_ai/instructions.md",
]

_MAX_BYTES = 32 * 1024  # 32 KB cap


def read_project_instructions(workdir: str | Path) -> str:
    """
    Read project-level instructions from the working directory.

    Checks AGENTS.md, ENTERPRISE_AI.md, and .enterprise_ai/instructions.md
    in order and returns the first non-empty content found.
    Caps at 32 KB, truncating at the last newline within the limit.
    Returns "" if no file is found or all are empty.
    """
    workdir = Path(workdir)
    for name in _CANDIDATE_FILES:
        path = workdir / name
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if not data.strip():
            continue
        if len(data) > _MAX_BYTES:
            truncated = data[:_MAX_BYTES]
            last_nl = truncated.rfind(b"\n")
            if last_nl > 0:
                truncated = truncated[:last_nl]
            data = truncated
        content = data.decode("utf-8", errors="replace").strip()
        if content:
            return content
    return ""

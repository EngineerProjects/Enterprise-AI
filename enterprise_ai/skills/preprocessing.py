"""
Skill preprocessing — applied to a skill's body before system-prompt injection.

Two transformations:

  1. Template variable substitution  (always on)
     Replace ${var} placeholders with values from a vars dict.
     Built-in defaults: ${date}, ${pwd}.
     Caller-provided vars override the defaults.

  2. Inline shell execution  (opt-in, disabled by default)
     Fenced code blocks tagged "bash" or "sh" are executed.
     The fence is replaced with the command's stdout.
     Execution errors leave the original block unchanged.

Usage:
    from enterprise_ai.skills.preprocessing import preprocess

    body = preprocess(
        skill.body,
        vars={"session_id": "abc-123", "agent_id": "worker-1"},
        enable_shell=False,
    )
"""
from __future__ import annotations

import re
import subprocess
from datetime import date as _date

_SHELL_BLOCK_RE = re.compile(
    r"```(?:bash|sh)\s*\n(.*?)```",
    re.DOTALL,
)


def _default_vars() -> dict[str, str]:
    import os
    return {
        "date": _date.today().isoformat(),
        "pwd": os.getcwd(),
    }


def _substitute_vars(text: str, vars: dict[str, str]) -> str:
    """Replace ${key} with vars[key]. Unknown placeholders are left as-is."""
    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return vars.get(key, m.group(0))

    return re.sub(r"\$\{([^}]+)\}", _replace, text)


def _run_shell_blocks(text: str) -> str:
    """Execute ```bash / ```sh blocks and replace with their stdout."""
    def _exec(m: re.Match) -> str:
        cmd = m.group(1).strip()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = proc.stdout.strip()
            return output if output else m.group(0)
        except Exception:
            return str(m.group(0))  # leave original block on error

    return _SHELL_BLOCK_RE.sub(_exec, text)


def preprocess(
    body: str,
    vars: dict[str, str] | None = None,
    enable_shell: bool = False,
) -> str:
    """
    Apply skill preprocessing to a body string.

    Args:
        body:         The raw skill body (Markdown).
        vars:         Template variables that override defaults.
                      Defaults always include ${date} and ${pwd}.
        enable_shell: If True, execute ```bash / ```sh fenced blocks.
                      Off by default — only enable for trusted skills.

    Returns:
        The preprocessed body string.
    """
    effective = {**_default_vars(), **(vars or {})}
    result = _substitute_vars(body, effective)
    if enable_shell:
        result = _run_shell_blocks(result)
    return result

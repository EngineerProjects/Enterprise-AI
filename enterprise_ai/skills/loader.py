from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from enterprise_ai.skills.skill import Skill

# Simple YAML frontmatter parser — avoids adding PyYAML as a hard dep
# (it's already optional in many setups). Falls back to empty dict on parse error.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^(\w[\w-]*):\s*(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s+-\s+(.+)$")


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """
    Parse a limited subset of YAML — enough for skill frontmatter.
    Handles: string scalars, null, bool, lists of scalars.
    """
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        list_m = _LIST_ITEM_RE.match(line)
        if list_m and current_key and current_list is not None:
            current_list.append(list_m.group(1).strip().strip('"').strip("'"))
            continue

        kv_m = _KV_RE.match(line)
        if kv_m:
            if current_key and current_list is not None:
                result[current_key] = current_list

            key = kv_m.group(1)
            val = kv_m.group(2).strip()

            if val == "" or val == "|" or val == ">":
                current_key = key
                current_list = []
                continue

            current_key = None
            current_list = None

            # Unquote
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]

            # Coerce
            if val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
            elif val.lower() in ("null", "~", ""):
                result[key] = None
            else:
                result[key] = val

    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def load_skill_file(path: Path) -> Skill:
    """
    Parse a Markdown skill file with optional YAML frontmatter.
    A plain Markdown file (no frontmatter) is treated as a nameless skill
    using the filename as the skill name.
    """
    text = path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    body = text

    m = _FRONTMATTER_RE.match(text)
    if m:
        try:
            fm = _parse_simple_yaml(m.group(1))
        except Exception:
            fm = {}
        body = text[m.end():]

    # Resolve name — prefer frontmatter, fall back to filename stem
    names = fm.get("name", path.stem)
    if isinstance(names, list):
        name = names[0]
    else:
        name = str(names)

    allowed_tools = fm.get("allowed-tools", fm.get("allowed_tools", []))
    if isinstance(allowed_tools, str):
        allowed_tools = [allowed_tools]

    return Skill(
        name=name,
        description=str(fm.get("description", "")),
        when_to_use=str(fm.get("when_to_use", fm.get("when-to-use", ""))),
        body=body.strip(),
        allowed_tools=list(allowed_tools),
        model=fm.get("model") or None,
        context=str(fm.get("context", "inline")),
        user_invocable=bool(fm.get("user-invocable", fm.get("user_invocable", True))),
        version=str(fm.get("version", "")),
        source_path=path,
    )

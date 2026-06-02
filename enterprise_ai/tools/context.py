from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass
class ToolContext:
    session_id: str = ""
    agent_id: str = ""
    working_dir: str = "."
    permission_mode: str = "onRequest"
    sandbox: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

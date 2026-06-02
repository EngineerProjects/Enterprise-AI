from __future__ import annotations

from enum import Enum
from typing import Awaitable, Callable

from enterprise_ai.schema import ToolCall


class PermissionMode(str, Enum):
    on_request = "onRequest"
    auto = "auto"
    bypass = "bypass"


class PermissionDecision(str, Enum):
    allow = "allow"
    deny = "deny"
    ask = "ask"


class PermissionResult:
    def __init__(self, decision: PermissionDecision, reason: str = "") -> None:
        self.decision = decision
        self.reason = reason

    @property
    def allowed(self) -> bool:
        return self.decision == PermissionDecision.allow


AskCallback = Callable[[ToolCall], Awaitable[bool]]

ALWAYS_ALLOW_TOOLS = {"terminate", "code_search"}
ALWAYS_DENY_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    ":(){ :|:& };:",  # fork bomb
    "mkfs",
    "/dev/sda",
]


class PermissionEngine:
    def __init__(
        self,
        mode: PermissionMode = PermissionMode.on_request,
        deny_tools: set[str] | None = None,
        allow_tools: set[str] | None = None,
        ask_callback: AskCallback | None = None,
    ) -> None:
        self.mode = mode
        self._deny_tools: set[str] = deny_tools or set()
        self._allow_tools: set[str] = allow_tools or set()
        self._ask_callback = ask_callback
        self._denial_count: dict[str, int] = {}

    async def check(self, tool_call: ToolCall) -> PermissionResult:
        name = tool_call.name

        # Step 1: deny rules (immediate, cannot be bypassed by mode)
        if name in self._deny_tools:
            return PermissionResult(PermissionDecision.deny, f"Tool '{name}' is in the deny list")

        # Step 2: bypass-immune safety check
        safety = self._safety_check(tool_call)
        if safety:
            return PermissionResult(PermissionDecision.deny, safety)

        # Step 3: bypass mode — skip remaining checks
        if self.mode == PermissionMode.bypass:
            return PermissionResult(PermissionDecision.allow)

        # Step 4: always-allow tools
        if name in ALWAYS_ALLOW_TOOLS or name in self._allow_tools:
            return PermissionResult(PermissionDecision.allow)

        # Step 5: auto mode — allow unless denied above
        if self.mode == PermissionMode.auto:
            return PermissionResult(PermissionDecision.allow)

        # Step 6: onRequest mode — ask the user
        if self._ask_callback is not None:
            approved = await self._ask_callback(tool_call)
            if approved:
                return PermissionResult(PermissionDecision.allow)
            self._denial_count[name] = self._denial_count.get(name, 0) + 1
            return PermissionResult(PermissionDecision.deny, "User denied")

        # Default: allow (no callback configured in onRequest mode)
        return PermissionResult(PermissionDecision.allow)

    def _safety_check(self, tool_call: ToolCall) -> str:
        """Bypass-immune check — returns an error message if dangerous, empty string if safe."""
        input_str = str(tool_call.input).lower()
        for pattern in ALWAYS_DENY_PATTERNS:
            if pattern.lower() in input_str:
                return f"Blocked: input contains dangerous pattern '{pattern}'"
        return ""

    def denial_count(self, tool_name: str) -> int:
        return self._denial_count.get(tool_name, 0)

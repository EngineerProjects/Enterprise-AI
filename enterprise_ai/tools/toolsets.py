"""
Toolset system — named, composable groups of built-in tools.

Usage:
    # Use a built-in toolset
    agent = Agent(toolset="development")

    # Compose toolsets
    agent = Agent(toolset="team_worker")          # development + task/mail tools
    agent = Agent(toolset="research")             # web + code search

    # Add extra tools on top of a toolset
    agent = Agent(toolset="development", tools=[MyCustomTool()])

    # Register a custom toolset
    from enterprise_ai.tools.toolsets import register_toolset, register_tool_factory
    register_tool_factory("my_api", lambda: MyApiTool())
    register_toolset("my_company", {
        "description": "Company tools",
        "tools": ["bash", "my_api"],
        "includes": ["development"],
    })
    agent = Agent(toolset="my_company")

    # Inspect available toolsets
    from enterprise_ai.tools.toolsets import list_toolsets
    print(list_toolsets())
"""
from __future__ import annotations

from typing import Callable

from enterprise_ai.tools.contract import BaseTool

# ── Built-in toolset definitions ──────────────────────────────────────────────
#
# Each entry has:
#   tools    — list of tool factory names (resolved via _TOOL_FACTORIES)
#   includes — other toolset names to merge in first (recursive, dedup'd)

TOOLSETS: dict[str, dict] = {
    "minimal": {
        "description": "Bash + file editor + terminate",
        "tools": ["bash", "file_editor", "terminate"],
        "includes": [],
    },
    "development": {
        "description": "Full development toolkit: bash, file editor, code search, terminate",
        "tools": ["bash", "file_editor", "code_search", "terminate"],
        "includes": [],
    },
    "research": {
        "description": "Web research and code search",
        "tools": ["web_search", "code_search", "terminate"],
        "includes": [],
    },
    "full": {
        "description": "All standalone built-in tools (no team coordination)",
        "tools": ["bash", "file_editor", "code_search", "web_search", "terminate"],
        "includes": [],
    },
    "team_worker": {
        "description": "Development + team task board and mailbox",
        "tools": [
            "spawn_agent",
            "send_mail", "read_mail",
            "post_task", "claim_task", "complete_task", "fail_task", "list_tasks",
        ],
        "includes": ["development"],
    },
}

# ── User-registered tool factories ────────────────────────────────────────────

_EXTRA_FACTORIES: dict[str, Callable[[], BaseTool]] = {}


def register_tool_factory(name: str, factory: Callable[[], BaseTool]) -> None:
    """Register a custom tool factory so it can be referenced in toolset definitions."""
    _EXTRA_FACTORIES[name] = factory


def register_toolset(name: str, spec: dict) -> None:
    """
    Register a custom toolset.

        register_toolset("my_company", {
            "description": "Company stack",
            "tools": ["bash", "my_api"],
            "includes": ["development"],
        })
    """
    TOOLSETS[name] = spec


def list_toolsets() -> dict[str, str]:
    """Return {name: description} for all registered toolsets."""
    return {name: spec.get("description", "") for name, spec in TOOLSETS.items()}


# ── Resolution ─────────────────────────────────────────────────────────────────

def _builtin_factories() -> dict[str, Callable[[], BaseTool]]:
    """Lazy import of built-in tools to avoid circular imports at module load."""
    from enterprise_ai.tools.builtin import (
        BashTool,
        ClaimTaskTool,
        CodeSearchTool,
        CompleteTaskTool,
        FailTaskTool,
        FileEditorTool,
        ListTasksTool,
        MailboxStatusTool,
        PostTaskTool,
        ReadMailTool,
        SendMailTool,
        SpawnTool,
        TerminateTool,
        WebSearchTool,
    )

    return {
        "bash": BashTool,
        "file_editor": FileEditorTool,
        "web_search": WebSearchTool,
        "code_search": CodeSearchTool,
        "terminate": TerminateTool,
        "spawn_agent": SpawnTool,
        "send_mail": SendMailTool,
        "read_mail": ReadMailTool,
        "mailbox_status": MailboxStatusTool,
        "post_task": PostTaskTool,
        "claim_task": ClaimTaskTool,
        "complete_task": CompleteTaskTool,
        "fail_task": FailTaskTool,
        "list_tasks": ListTasksTool,
    }


def _collect_names(name: str, seen: set[str]) -> list[str]:
    """Recursively collect unique tool names from a toolset + its includes."""
    if name in seen:
        return []
    seen.add(name)
    spec = TOOLSETS.get(name)
    if spec is None:
        raise ValueError(
            f"Unknown toolset: '{name}'. "
            f"Available: {sorted(TOOLSETS)}"
        )
    names: list[str] = []
    for include in spec.get("includes", []):
        for n in _collect_names(include, seen):
            if n not in names:
                names.append(n)
    for tool_name in spec.get("tools", []):
        if tool_name not in names:
            names.append(tool_name)
    return names


def resolve_toolset(name: str) -> list[BaseTool]:
    """
    Resolve a toolset name to a list of instantiated tool objects.

    Custom tool factories registered via register_tool_factory() take
    precedence over built-in factories with the same name.
    """
    factories = {**_builtin_factories(), **_EXTRA_FACTORIES}
    tool_names = _collect_names(name, set())
    tools: list[BaseTool] = []
    for n in tool_names:
        factory = factories.get(n)
        if factory is not None:
            tools.append(factory())
    return tools

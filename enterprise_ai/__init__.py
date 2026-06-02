"""
enterprise-ai — Python SDK for autonomous multi-agent workflows.

Quick start:
    from enterprise_ai import Agent
    from enterprise_ai.tools import BashTool, FileEditorTool
    from enterprise_ai.providers import AnthropicProvider

    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        tools=[BashTool(), FileEditorTool()],
    )
    result = await agent.run("Fix the failing test in tests/auth_test.py")
"""

from enterprise_ai.agent import Agent
from enterprise_ai.schema import Message, Role, SessionResult, StreamEvent, ToolCall, ToolResult

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "Message", "Role", "ToolCall", "ToolResult", "StreamEvent", "SessionResult",
    "__version__",
]

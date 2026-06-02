from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class StdioServerConfig:
    """
    MCP server running as a local subprocess (most common).
    The server process communicates via stdin/stdout.

    Example — GitHub MCP server:
        StdioServerConfig(command="npx", args=["-y", "@modelcontextprotocol/server-github"])

    Example — local Python MCP server:
        StdioServerConfig(command="python", args=["my_mcp_server.py"])
    """

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: Literal["stdio"] = "stdio"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.command} {' '.join(self.args)}".strip()


@dataclass
class SSEServerConfig:
    """
    MCP server accessible via HTTP + Server-Sent Events (remote servers).

    Example:
        SSEServerConfig(url="http://localhost:3000/sse", name="my-remote-mcp")
    """

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    transport: Literal["sse"] = "sse"
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.url


MCPServerConfig = StdioServerConfig | SSEServerConfig

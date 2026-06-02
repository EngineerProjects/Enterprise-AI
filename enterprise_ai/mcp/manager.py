from __future__ import annotations

import asyncio

from enterprise_ai.mcp.client import MCPClient
from enterprise_ai.mcp.config import MCPServerConfig
from enterprise_ai.mcp.tool import MCPTool


class MCPManager:
    """
    Manages connections to multiple MCP servers.

    On start(), connects to all configured servers in parallel and
    aggregates their tools. All tools are then available to inject
    into an Agent's ToolRegistry.

    Usage:
        manager = MCPManager([
            StdioServerConfig(command="npx", args=["-y", "@mcp/server-github"]),
            SSEServerConfig(url="http://localhost:3000/sse", name="custom"),
        ])
        async with manager:
            agent = Agent(tools=[...] + manager.tools)
    """

    def __init__(self, configs: list[MCPServerConfig]) -> None:
        self._configs = configs
        self._clients: list[MCPClient] = []

    async def start(self) -> None:
        self._clients = [MCPClient(cfg) for cfg in self._configs]
        results = await asyncio.gather(
            *[c.start() for c in self._clients],
            return_exceptions=True,
        )
        failed = []
        for client, result in zip(self._clients, results):
            if isinstance(result, Exception):
                failed.append(f"{client.name}: {result}")
        if failed:
            # Log failures but don't abort — partial connectivity is fine
            import warnings
            warnings.warn(f"MCP servers failed to connect: {'; '.join(failed)}", stacklevel=2)
        # Keep only connected clients
        self._clients = [c for c in self._clients if c.is_connected]

    async def stop(self) -> None:
        await asyncio.gather(
            *[c.stop() for c in self._clients],
            return_exceptions=True,
        )
        self._clients.clear()

    @property
    def tools(self) -> list[MCPTool]:
        """All tools from all connected MCP servers."""
        result: list[MCPTool] = []
        for client in self._clients:
            result.extend(client.tools)
        return result

    @property
    def clients(self) -> list[MCPClient]:
        return list(self._clients)

    def get_client(self, name: str) -> MCPClient | None:
        return next((c for c in self._clients if c.name == name), None)

    def tool_count(self) -> int:
        return sum(len(c.tools) for c in self._clients)

    async def __aenter__(self) -> MCPManager:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

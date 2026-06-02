from __future__ import annotations

from typing import Any

from enterprise_ai.mcp.config import MCPServerConfig, SSEServerConfig, StdioServerConfig
from enterprise_ai.mcp.tool import MCPTool


class MCPClient:
    """
    Persistent connection to one MCP server.

    Manages the full lifecycle:
    - start(): launches the subprocess or opens the HTTP connection
    - discover(): fetches available tools from the server
    - call_tool(): executes a tool and returns the text result
    - stop(): closes the connection and cleans up

    Usage as an async context manager:
        async with MCPClient(StdioServerConfig(command="npx", args=["-y", "@mcp/server-github"])) as client:
            tools = client.tools  # list[MCPTool]
            result = await client.call_tool("search_repositories", {"query": "python agents"})
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._session: Any = None
        self._ctx_stack: Any = None
        self._tools: list[MCPTool] = []
        self._started = False

    async def start(self) -> None:
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise ImportError("mcp package required: pip install 'enterprise-ai[mcp]'")

        if isinstance(self.config, StdioServerConfig):
            from mcp import StdioServerParameters
            params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env or None,
            )
            self._ctx_stack = stdio_client(params)
        else:
            assert isinstance(self.config, SSEServerConfig)
            self._ctx_stack = sse_client(
                url=self.config.url,
                headers=self.config.headers or None,
            )

        read, write = await self._ctx_stack.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        await self._discover_tools()
        self._started = True

    async def stop(self) -> None:
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        if self._ctx_stack is not None:
            try:
                await self._ctx_stack.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None
        self._ctx_stack = None
        self._started = False

    async def _discover_tools(self) -> None:
        if self._session is None:
            return
        response = await self._session.list_tools()
        self._tools = [
            MCPTool(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if isinstance(tool.inputSchema, dict) else {},
                client=self,
                server_name=self.config.name,
            )
            for tool in response.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if self._session is None:
            raise RuntimeError("MCPClient not started — call start() first")

        result = await self._session.call_tool(tool_name, arguments)

        # Extract text from result content blocks
        parts: list[str] = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif hasattr(block, "data"):
                parts.append(f"[binary data: {len(block.data)} bytes]")
            else:
                parts.append(str(block))

        if result.isError:
            raise RuntimeError("\n".join(parts) or "MCP tool returned an error")

        return "\n".join(parts) or "(no output)"

    async def refresh_tools(self) -> None:
        """Re-discover tools from the server (useful if tools change at runtime)."""
        await self._discover_tools()

    @property
    def tools(self) -> list[MCPTool]:
        return list(self._tools)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_connected(self) -> bool:
        return self._started

    async def __aenter__(self) -> MCPClient:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

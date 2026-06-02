"""
Unit tests for the MCP client layer.
Tests config parsing, MCPTool wrapping, and MCPManager aggregation.
Real MCP server connections are skipped (require external processes).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from enterprise_ai.mcp.config import SSEServerConfig, StdioServerConfig
from enterprise_ai.mcp.manager import MCPManager
from enterprise_ai.mcp.tool import MCPTool, _AnyInput
from enterprise_ai.tools.context import ToolContext

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_stdio_config_name_defaults_to_command():
    cfg = StdioServerConfig(command="npx", args=["-y", "@mcp/server-github"])
    assert "npx" in cfg.name
    assert "@mcp/server-github" in cfg.name


def test_stdio_config_explicit_name():
    cfg = StdioServerConfig(command="python", args=["server.py"], name="my-server")
    assert cfg.name == "my-server"


def test_sse_config_name_defaults_to_url():
    cfg = SSEServerConfig(url="http://localhost:3000/sse")
    assert cfg.name == "http://localhost:3000/sse"


def test_sse_config_explicit_name():
    cfg = SSEServerConfig(url="http://localhost:3000/sse", name="remote")
    assert cfg.name == "remote"


# ---------------------------------------------------------------------------
# MCPTool
# ---------------------------------------------------------------------------

def _make_mock_client(call_result: str = "tool output") -> MagicMock:
    client = MagicMock()
    client.call_tool = AsyncMock(return_value=call_result)
    client.name = "test-server"
    return client


def test_mcp_tool_name_and_description():
    client = _make_mock_client()
    tool = MCPTool(
        name="search_repos",
        description="Search GitHub repositories",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        client=client,
    )
    assert tool.name == "search_repos"
    assert tool.description == "Search GitHub repositories"


def test_mcp_tool_to_schema_preserves_mcp_schema():
    client = _make_mock_client()
    schema = {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}
    tool = MCPTool(name="search", description="desc", input_schema=schema, client=client)

    ts = tool.to_schema()
    assert ts.name == "search"
    assert ts.input_schema == schema


def test_mcp_tool_parse_input_accepts_any_dict():
    client = _make_mock_client()
    tool = MCPTool(name="t", description="d", input_schema={}, client=client)
    parsed = tool.parse_input({"key": "value", "number": 42})
    assert isinstance(parsed, _AnyInput)


@pytest.mark.asyncio
async def test_mcp_tool_call_forwards_to_client():
    client = _make_mock_client("repos: [repo1, repo2]")
    tool = MCPTool(name="list_repos", description="d", input_schema={}, client=client)

    inp = tool.parse_input({"owner": "myorg"})
    ctx = ToolContext(agent_id="test")
    result = await tool.call(inp, ctx)

    assert not result.is_error
    assert "repos" in result.content
    client.call_tool.assert_called_once_with("list_repos", {"owner": "myorg"})


@pytest.mark.asyncio
async def test_mcp_tool_call_error_returns_error_result():
    client = _make_mock_client()
    client.call_tool = AsyncMock(side_effect=RuntimeError("tool failed"))
    tool = MCPTool(name="failing_tool", description="d", input_schema={}, client=client)

    inp = tool.parse_input({})
    ctx = ToolContext(agent_id="test")
    result = await tool.call(inp, ctx)

    assert result.is_error
    assert "tool failed" in result.content


# ---------------------------------------------------------------------------
# MCPManager
# ---------------------------------------------------------------------------

def _make_mock_mcp_client(name: str, tools: list[MCPTool]) -> MagicMock:
    client = MagicMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.is_connected = True
    client.name = name
    client.tools = tools
    return client


@pytest.mark.asyncio
async def test_manager_aggregates_tools_from_all_clients():
    """MCPManager.tools returns tools from all connected clients."""
    mock_raw_client = _make_mock_client()
    tool_a = MCPTool("tool_a", "desc a", {}, mock_raw_client)
    tool_b = MCPTool("tool_b", "desc b", {}, mock_raw_client)
    tool_c = MCPTool("tool_c", "desc c", {}, mock_raw_client)

    cfg_a = StdioServerConfig(command="server-a", name="server-a")
    cfg_b = StdioServerConfig(command="server-b", name="server-b")

    manager = MCPManager([cfg_a, cfg_b])

    # Patch MCPClient to return our mock clients
    mock_client_a = _make_mock_mcp_client("server-a", [tool_a, tool_b])
    mock_client_b = _make_mock_mcp_client("server-b", [tool_c])

    with patch("enterprise_ai.mcp.manager.MCPClient", side_effect=[mock_client_a, mock_client_b]):
        await manager.start()

    assert manager.tool_count() == 3
    names = [t.name for t in manager.tools]
    assert "tool_a" in names
    assert "tool_b" in names
    assert "tool_c" in names


@pytest.mark.asyncio
async def test_manager_continues_when_one_server_fails():
    """Failed server connections don't abort the whole manager."""
    mock_raw_client = _make_mock_client()
    tool_ok = MCPTool("ok_tool", "works", {}, mock_raw_client)

    cfg_a = StdioServerConfig(command="good-server", name="good")
    cfg_b = StdioServerConfig(command="bad-server", name="bad")

    manager = MCPManager([cfg_a, cfg_b])

    good_client = _make_mock_mcp_client("good", [tool_ok])
    bad_client = MagicMock()
    bad_client.start = AsyncMock(side_effect=ConnectionError("server not found"))
    bad_client.is_connected = False
    bad_client.name = "bad"

    with patch("enterprise_ai.mcp.manager.MCPClient", side_effect=[good_client, bad_client]):
        import warnings
        with warnings.catch_warnings(record=True):
            await manager.start()

    # Only good client remains
    assert len(manager.clients) == 1
    assert manager.clients[0].name == "good"


@pytest.mark.asyncio
async def test_manager_stop_disconnects_all():
    cfg = StdioServerConfig(command="server", name="s1")
    manager = MCPManager([cfg])

    mock_client = _make_mock_mcp_client("s1", [])
    with patch("enterprise_ai.mcp.manager.MCPClient", return_value=mock_client):
        await manager.start()
        await manager.stop()

    mock_client.stop.assert_called_once()
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_manager_as_context_manager():
    cfg = StdioServerConfig(command="server", name="s1")
    manager = MCPManager([cfg])

    mock_client = _make_mock_mcp_client("s1", [])
    with patch("enterprise_ai.mcp.manager.MCPClient", return_value=mock_client):
        async with manager:
            assert len(manager.clients) == 1

    mock_client.stop.assert_called_once()


@pytest.mark.asyncio
async def test_manager_get_client_by_name():
    cfg_a = StdioServerConfig(command="a", name="alpha")
    cfg_b = StdioServerConfig(command="b", name="beta")
    manager = MCPManager([cfg_a, cfg_b])

    mock_a = _make_mock_mcp_client("alpha", [])
    mock_b = _make_mock_mcp_client("beta", [])
    with patch("enterprise_ai.mcp.manager.MCPClient", side_effect=[mock_a, mock_b]):
        await manager.start()

    assert manager.get_client("alpha") is mock_a
    assert manager.get_client("beta") is mock_b
    assert manager.get_client("nonexistent") is None
    await manager.stop()

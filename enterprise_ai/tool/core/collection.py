"""Collection classes for managing multiple tools."""

from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolFailure, ToolResult


class ToolCollection:
    """A collection of defined tools.

    This class allows for the management and execution of multiple tools.
    It provides methods to execute tools by name, execute all tools, and add new tools to the collection.
    """

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        """Convert all tools to function call format."""
        return [tool.to_param() for tool in self.tools]

    async def execute(
        self, *, name: str, tool_input: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a specific tool by name with provided input."""
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            result = await tool(**(tool_input or {}))
            return cast(ToolResult, result)
        except ToolError as e:
            return ToolFailure(error=e.message)
        except EnterpriseAIError as e:
            return ToolFailure(error=str(e))
        except Exception as e:
            return ToolFailure(error=f"Unexpected error: {str(e)}")

    async def execute_all(self) -> List[ToolResult]:
        """Execute all tools in the collection sequentially."""
        results = []
        for tool in self.tools:
            try:
                result = await tool()
                results.append(result)
            except ToolError as e:
                results.append(ToolFailure(error=e.message))
            except Exception as e:
                results.append(ToolFailure(error=f"Error: {str(e)}"))
        return results

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool) -> "ToolCollection":
        """Add a single tool to the collection."""
        self.tools = (*self.tools, tool)
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool) -> "ToolCollection":
        """Add multiple tools to the collection."""
        for tool in tools:
            self.add_tool(tool)
        return self

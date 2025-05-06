"""Collection classes for managing multiple tools."""

from typing import Any, Dict, Iterator, List, Optional, Tuple, Union, cast
import asyncio

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolState
from enterprise_ai.tool.core.result import ToolFailure, ToolResult, ToolResultMetadata
from enterprise_ai.logger import get_logger

logger = get_logger("tool.collection")


class ToolCollection:
    """A collection of defined tools.

    This class allows for the management and execution of multiple tools.
    It provides methods to execute tools by name, execute all tools, and add new tools to the collection.
    """

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool):
        """Initialize a tool collection with optional initial tools."""
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self._locks = {}  # Tool-specific locks for concurrent execution

        # Create locks for each tool
        for tool in tools:
            self._locks[tool.name] = asyncio.Lock()

    def __iter__(self) -> Iterator[BaseTool]:
        """Allow iteration over tools in the collection."""
        return iter(self.tools)

    def __len__(self) -> int:
        """Get the number of tools in the collection."""
        return len(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        """Convert all tools to function call format."""
        return [tool.to_param() for tool in self.tools]

    def get_tool_names(self) -> List[str]:
        """Get a list of all tool names in the collection."""
        return list(self.tool_map.keys())

    def get_tool_by_capability(self, capability: str) -> Optional[BaseTool]:
        """Find a tool with the specified capability.

        Args:
            capability: Capability to search for

        Returns:
            First tool with matching capability or None
        """
        for tool in self.tools:
            if hasattr(tool, "capabilities") and capability in tool.capabilities:
                return tool
        return None

    def filter_by_capabilities(
        self, capabilities: List[str], match_all: bool = False
    ) -> List[BaseTool]:
        """Filter tools by capabilities.

        Args:
            capabilities: List of capabilities to filter by
            match_all: If True, tools must have all capabilities;
                     If False, tools must have at least one capability

        Returns:
            List of tools matching the capability criteria
        """
        result = []

        for tool in self.tools:
            if not hasattr(tool, "capabilities"):
                continue

            tool_capabilities = tool.capabilities

            # Convert to string values if needed
            tool_cap_values = {
                cap.value if hasattr(cap, "value") else str(cap) for cap in tool_capabilities
            }

            if match_all:
                # Tool must have all capabilities
                if all(cap in tool_cap_values for cap in capabilities):
                    result.append(tool)
            else:
                # Tool must have at least one capability
                if any(cap in tool_cap_values for cap in capabilities):
                    result.append(tool)

        return result

    async def execute(
        self, *, name: str, tool_input: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a specific tool by name with provided input."""
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(
                error=f"Tool {name} is invalid", metadata=ToolResultMetadata(tool_name=name)
            )

        # Get or create a lock for this tool
        lock = self._locks.get(name)
        if not lock:
            lock = asyncio.Lock()
            self._locks[name] = lock

        # Start tracking execution
        metadata = ToolResultMetadata(tool_name=name)

        try:
            # Execute with the tool-specific lock
            async with lock:
                # Update tool state if possible
                if hasattr(tool, "_update_state"):
                    try:
                        tool._update_state(ToolState.RUNNING)
                    except Exception as e:
                        logger.warning(f"Error updating tool state: {e}")

                # Execute tool with timeout if specified
                try:
                    result = await tool(**(tool_input or {}))
                except Exception as e:
                    logger.error(f"Error executing tool {name}: {e}")
                    return ToolFailure(error=f"Error executing tool: {str(e)}", metadata=metadata)

                # Ensure result has metadata with tool info
                if isinstance(result, ToolResult):
                    if result.metadata is None:
                        result.metadata = metadata
                    elif result.metadata.tool_name is None:
                        result.metadata.tool_name = name

                    # Safely handle result completion
                    try:
                        if hasattr(result, "complete"):
                            return result.complete()
                        return result
                    except Exception as e:
                        logger.warning(f"Error completing result: {e}")
                        return result
                else:
                    # Convert non-ToolResult to ToolResult
                    try:
                        new_result = ToolResult(output=result, metadata=metadata)
                        if hasattr(new_result, "complete"):
                            return new_result.complete()
                        return new_result
                    except Exception as e:
                        logger.warning(f"Error creating result object: {e}")
                        return ToolResult(output=str(result), metadata=metadata)

        except ToolError as e:
            # Update tool state
            if hasattr(tool, "_update_state"):
                try:
                    tool._update_state(ToolState.ERROR)
                except Exception:
                    pass

            return ToolFailure(error=e.message, metadata=metadata)
        except EnterpriseAIError as e:
            # Update tool state
            if hasattr(tool, "_update_state"):
                try:
                    tool._update_state(ToolState.ERROR)
                except Exception:
                    pass

            return ToolFailure(error=str(e), metadata=metadata)
        except Exception as e:
            # Update tool state
            if hasattr(tool, "_update_state"):
                try:
                    tool._update_state(ToolState.ERROR)
                except Exception:
                    pass

            logger.error(f"Unexpected error in tool {name}: {str(e)}")
            return ToolFailure(error=f"Unexpected error: {str(e)}", metadata=metadata)
        finally:
            # Reset tool state if needed
            if hasattr(tool, "_update_state"):
                try:
                    tool._update_state(ToolState.IDLE)
                except Exception:
                    pass

    async def execute_all(self) -> List[ToolResult]:
        """Execute all tools in the collection sequentially."""
        results = []
        for tool in self.tools:
            metadata = ToolResultMetadata(tool_name=tool.name)
            try:
                # Update tool state
                if hasattr(tool, "_update_state"):
                    tool._update_state(ToolState.RUNNING)

                result = await tool()

                # Ensure result has metadata
                if isinstance(result, ToolResult):
                    if result.metadata is None:
                        result.metadata = metadata
                    elif result.metadata.tool_name is None:
                        result.metadata.tool_name = tool.name

                    # Complete the metadata
                    result.complete()

                    results.append(result)
                else:
                    # Convert non-ToolResult to ToolResult
                    results.append(ToolResult(output=result, metadata=metadata).complete())

            except ToolError as e:
                # Update tool state
                if hasattr(tool, "_update_state"):
                    tool._update_state(ToolState.ERROR)

                results.append(ToolFailure(error=e.message, metadata=metadata.complete()))
            except Exception as e:
                # Update tool state
                if hasattr(tool, "_update_state"):
                    tool._update_state(ToolState.ERROR)

                results.append(ToolFailure(error=f"Error: {str(e)}", metadata=metadata.complete()))
            finally:
                # Reset tool state
                if hasattr(tool, "_update_state"):
                    tool._update_state(ToolState.IDLE)

        return results

    async def execute_parallel(
        self, executions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, ToolResult]:
        """Execute multiple tools in parallel.

        Args:
            executions: Dictionary mapping tool names to their input parameters

        Returns:
            Dictionary mapping tool names to their results
        """
        tasks = {}

        # Create a task for each execution
        for tool_name, params in executions.items():
            if tool_name not in self.tool_map:
                tasks[tool_name] = ToolFailure(
                    error=f"Tool {tool_name} is invalid",
                    metadata=ToolResultMetadata(tool_name=tool_name).complete(),
                )
                continue

            # Create a task for this execution
            tasks[tool_name] = asyncio.create_task(self.execute(name=tool_name, tool_input=params))

        # Wait for all tasks to complete
        results = {}
        for tool_name, task in tasks.items():
            if isinstance(task, ToolResult):
                # Already completed task (error case)
                results[tool_name] = task
            else:
                try:
                    results[tool_name] = await task
                except Exception as e:
                    results[tool_name] = ToolFailure(
                        error=f"Execution error: {str(e)}",
                        metadata=ToolResultMetadata(tool_name=tool_name).complete(),
                    )

        return results

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool) -> "ToolCollection":
        """Add a single tool to the collection."""
        if tool.name in self.tool_map:
            # Replace existing tool
            self.tools = tuple(t for t in self.tools if t.name != tool.name) + (tool,)
        else:
            # Add new tool
            self.tools = (*self.tools, tool)

        # Update tool map
        self.tool_map[tool.name] = tool

        # Create a lock for this tool
        self._locks[tool.name] = asyncio.Lock()

        return self

    def add_tools(self, *tools: BaseTool) -> "ToolCollection":
        """Add multiple tools to the collection."""
        for tool in tools:
            self.add_tool(tool)
        return self

    def remove_tool(self, name: str) -> bool:
        """Remove a tool from the collection.

        Args:
            name: Name of the tool to remove

        Returns:
            True if the tool was removed, False if not found
        """
        if name not in self.tool_map:
            return False

        # Remove from tools tuple
        self.tools = tuple(tool for tool in self.tools if tool.name != name)

        # Remove from tool map
        del self.tool_map[name]

        # Remove lock
        if name in self._locks:
            del self._locks[name]

        return True

    async def cleanup(self) -> None:
        """Clean up all tools in the collection."""
        for tool in self.tools:
            if hasattr(tool, "cleanup") and callable(getattr(tool, "cleanup")):
                try:
                    await tool.cleanup()
                except Exception as e:
                    logger.warning(f"Error during cleanup of tool {tool.name}: {e}")

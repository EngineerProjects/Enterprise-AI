"""
Optimized LLM Tool Adapter for Enterprise AI.

This module provides efficient integration between the class-based tool system 
and the function-based LLM tool execution system.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints
from functools import wraps

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolDefinition, ToolCall, ToolResult
from enterprise_ai.schema.tool_utils import ToolConverter
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.registry import get_registry

logger = get_logger("tool.llm_adapter")


class LLMToolAdapter:
    """
    Optimized adapter that converts class-based tools to function-based tools for LLM integration.
    
    Enhanced with better error handling, caching, and tool lifecycle management.
    """
    
    def __init__(self):
        self._tool_instances: Dict[str, BaseTool] = {}
        self._function_tools: Dict[str, Callable] = {}
        self._tool_definitions_cache: Optional[List[ToolDefinition]] = None
        self._converter = ToolConverter()
        
    async def register_tool_class(
        self, 
        tool_class: type[BaseTool], 
        initialize: bool = True,
        **init_kwargs: Any
    ) -> str:
        """
        Register a tool class and create an optimized function wrapper for LLM use.
        
        Args:
            tool_class: The BaseTool class to register
            initialize: Whether to initialize the tool
            **init_kwargs: Initialization arguments for the tool
            
        Returns:
            Tool name that was registered
        """
        # Create tool instance
        tool_instance = tool_class(**init_kwargs)
        
        if initialize and tool_instance.requires_initialization:
            success = await tool_instance.initialize()
            if not success:
                raise RuntimeError(f"Failed to initialize tool: {tool_instance.name}")
        
        # Store the instance
        self._tool_instances[tool_instance.name] = tool_instance
        
        # Create optimized function wrapper with proper metadata
        function_wrapper = self._create_function_wrapper(tool_instance)
        
        # Store the function
        self._function_tools[tool_instance.name] = function_wrapper
        
        # Clear cache since we added a new tool
        self._tool_definitions_cache = None
        
        logger.info("Registered tool class %s as function %s", tool_class.__name__, tool_instance.name)
        return tool_instance.name
    
    def _create_function_wrapper(self, tool_instance: BaseTool) -> Callable:
        """Create an optimized synchronous function wrapper for a tool instance."""
        
        def tool_function(**kwargs: Any) -> Union[str, Dict[str, Any]]:
            """Synchronous function wrapper for the tool."""
            try:
                # Import config dynamically to get current timeout setting
                from enterprise_ai.config import get_config
                execution_timeout = get_config("execution.timeout", 120.0)
                
                # Simple and reliable execution approach
                if asyncio.iscoroutinefunction(tool_instance.execute):
                    # Handle async execute method
                    try:
                        # Try to get current event loop
                        loop = asyncio.get_running_loop()
                        # If we're in an event loop, we need to handle this carefully
                        
                        # Use asyncio.run in a way that works in different contexts
                        import threading
                        import queue
                        
                        result_queue = queue.Queue()
                        exception_queue = queue.Queue()
                        
                        def run_async_tool():
                            """Run the async tool in a separate event loop."""
                            try:
                                # Create new event loop for this thread
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    result = new_loop.run_until_complete(tool_instance.execute(**kwargs))
                                    result_queue.put(result)
                                finally:
                                    new_loop.close()
                            except Exception as e:
                                exception_queue.put(e)
                        
                        # Run in separate thread to avoid event loop conflicts
                        thread = threading.Thread(target=run_async_tool, daemon=True)
                        thread.start()
                        thread.join(timeout=execution_timeout)  # USE CONFIG TIMEOUT
                        
                        if thread.is_alive():
                            raise TimeoutError(f"Tool execution timed out after {execution_timeout} seconds")
                        
                        if not exception_queue.empty():
                            raise exception_queue.get()
                        
                        if not result_queue.empty():
                            result = result_queue.get()
                        else:
                            raise RuntimeError("Tool execution failed to return result")
                            
                    except RuntimeError as e:
                        # Check if it's the "no running event loop" error
                        if "no running event loop" in str(e).lower() or "cannot be called from a running event loop" in str(e).lower():
                            # No running event loop, safe to use asyncio.run()
                            result = asyncio.run(tool_instance.execute(**kwargs))
                        else:
                            # Some other RuntimeError, re-raise it
                            raise
                else:
                    # Call sync execute directly
                    result = tool_instance.execute(**kwargs)
                
                # Handle different result types efficiently
                if hasattr(result, 'result') and result.result is not None:
                    return result.result
                elif hasattr(result, 'output') and result.output is not None:
                    return result.output
                elif hasattr(result, 'error') and result.error is not None:
                    return {"error": result.error}
                else:
                    return str(result)
                    
            except Exception as e:
                logger.error("Error executing tool %s: %s", tool_instance.name, e)
                return {"error": str(e)}
        
        # Set function metadata for LLM discovery
        tool_function.__name__ = tool_instance.name
        tool_function.__doc__ = tool_instance.description
        
        # Add parameter annotations if available
        if tool_instance.parameters:
            try:
                # Extract parameter info from JSON schema for better type hints
                properties = tool_instance.parameters.get("properties", {})
                required = tool_instance.parameters.get("required", [])
                
                # Create annotations (basic mapping)
                annotations = {}
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    if param_type == "string":
                        annotations[param_name] = str
                    elif param_type == "integer":
                        annotations[param_name] = int
                    elif param_type == "number":
                        annotations[param_name] = float
                    elif param_type == "boolean":
                        annotations[param_name] = bool
                    else:
                        annotations[param_name] = Any
                
                tool_function.__annotations__ = annotations
            except Exception as e:
                logger.debug("Could not create annotations for %s: %s", tool_instance.name, e)
        
        return tool_function
    
    def get_tool_functions(self) -> Dict[str, Callable]:
        """Get all registered tool functions for LLM use."""
        return self._function_tools.copy()
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get cached tool definitions in the format expected by LLM providers."""
        if self._tool_definitions_cache is None:
            self._tool_definitions_cache = []
            
            for name, tool_instance in self._tool_instances.items():
                try:
                    # Use the schema converter for consistency
                    if tool_instance.parameters:
                        # Tool already has parameters defined
                        definition = ToolDefinition.create_function_tool(
                            name=name,
                            description=tool_instance.description,
                            parameters=tool_instance.parameters
                        )
                    else:
                        # Generate from function signature
                        tool_function = self._function_tools.get(name)
                        if tool_function:
                            definition = self._converter.function_to_tool_definition(tool_function)
                        else:
                            # Fallback
                            definition = ToolDefinition.create_function_tool(
                                name=name,
                                description=tool_instance.description,
                                parameters={"type": "object", "properties": {}, "required": []}
                            )
                    
                    self._tool_definitions_cache.append(definition)
                    
                except Exception as e:
                    logger.warning("Failed to create definition for tool %s: %s", name, e)
                    # Create minimal definition
                    fallback_definition = ToolDefinition.create_function_tool(
                        name=name,
                        description=tool_instance.description or f"Tool: {name}",
                        parameters={"type": "object", "properties": {}, "required": []}
                    )
                    self._tool_definitions_cache.append(fallback_definition)
        
        return self._tool_definitions_cache.copy()
    
    async def register_all_tools(self, categories: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Register all tools from the registry with optimized batch processing.
        
        Args:
            categories: Optional list of categories to include
            
        Returns:
            Dictionary mapping tool class names to registered function names
        """
        registry = get_registry()
        registered = {}
        
        # Get tools to register
        tools_to_register = []
        
        if categories:
            # Register tools from specific categories
            for category in categories:
                tools = registry.get_tools_by_category(category)
                tools_to_register.extend(tools)
        else:
            # Register all tools
            all_tools = registry.get_all_tool_classes()
            tools_to_register.extend(all_tools.values())
        
        # Register tools with error handling
        for tool_class in tools_to_register:
            try:
                name = await self.register_tool_class(tool_class)
                registered[tool_class.__name__] = name
            except Exception as e:
                logger.warning("Failed to register tool %s: %s", tool_class.__name__, e)
        
        logger.info("Registered %s tools for LLM use", len(registered))
        return registered
    
    def get_tool_instance(self, name: str) -> Optional[BaseTool]:
        """Get a tool instance by name."""
        return self._tool_instances.get(name)
    
    def get_registered_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        return list(self._tool_instances.keys())
    
    async def cleanup(self) -> None:
        """Clean up all registered tool instances."""
        cleanup_tasks = []
        
        for name, tool_instance in self._tool_instances.items():
            if hasattr(tool_instance, 'cleanup'):
                cleanup_tasks.append(self._safe_cleanup(name, tool_instance))
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self._tool_instances.clear()
        self._function_tools.clear()
        self._tool_definitions_cache = None
    
    async def _safe_cleanup(self, name: str, tool_instance: BaseTool) -> None:
        """Safely cleanup a tool instance."""
        try:
            await tool_instance.cleanup()
        except Exception as e:
            logger.warning("Error cleaning up tool %s: %s", name, e)


# Global adapter instance
_global_adapter = LLMToolAdapter()


async def get_llm_tools(categories: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Callable]:
    """
    Get tool functions for LLM use, automatically registering from the tool registry.
    
    Args:
        categories: Optional list of categories to include
        force_refresh: Whether to force refresh the tool registration
        
    Returns:
        Dictionary of tool functions ready for LLM use
    """
    if not _global_adapter._function_tools or force_refresh:
        await _global_adapter.register_all_tools(categories)
    
    return _global_adapter.get_tool_functions()


async def get_llm_tool_definitions(categories: Optional[List[str]] = None, force_refresh: bool = False) -> List[ToolDefinition]:
    """
    Get tool definitions for LLM providers.
    
    Args:
        categories: Optional list of categories to include
        force_refresh: Whether to force refresh the tool registration
        
    Returns:
        List of ToolDefinition objects
    """
    if not _global_adapter._tool_instances or force_refresh:
        await _global_adapter.register_all_tools(categories)
    
    return _global_adapter.get_tool_definitions()


def get_adapter() -> LLMToolAdapter:
    """Get the global tool adapter instance."""
    return _global_adapter


async def cleanup_adapter() -> None:
    """Clean up the global adapter."""
    await _global_adapter.cleanup()
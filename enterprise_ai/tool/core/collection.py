"""
Enhanced tool collection management for Enterprise AI.

This module provides optimized collection and management of multiple tools
with better integration with the LLM system.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Union, Type

from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool, ToolCapability, ToolConfig
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.tool.core.llm_adapter import LLMToolAdapter

logger = get_logger("tool.core.collection")


class ToolCollection:
    """
    Enhanced collection of tools with optimized LLM integration.
    
    Provides efficient management of multiple tools and seamless
    integration with the LLM system.
    """
    
    def __init__(self, name: str = "default"):
        """
        Initialize a new tool collection.
        
        Args:
            name: Name of the collection
        """
        self.name = name
        self._tools: Dict[str, BaseTool] = {}
        self._llm_adapter: Optional[LLMToolAdapter] = None
        self._initialized = False
    
    async def add_tool(
        self, 
        tool: Union[BaseTool, Type[BaseTool]], 
        initialize: bool = True,
        **init_kwargs: Any
    ) -> str:
        """
        Add a tool to the collection.
        
        Args:
            tool: Tool instance or tool class
            initialize: Whether to initialize the tool
            **init_kwargs: Initialization arguments for tool classes
            
        Returns:
            Name of the added tool
        """
        if isinstance(tool, type) and issubclass(tool, BaseTool):
            # It's a tool class, instantiate it
            tool_instance = tool(**init_kwargs)
        else:
            # It's already an instance
            tool_instance = tool
        
        # Initialize if required
        if initialize and tool_instance.requires_initialization:
            success = await tool_instance.initialize()
            if not success:
                raise RuntimeError(f"Failed to initialize tool: {tool_instance.name}")
        
        # Add to collection
        self._tools[tool_instance.name] = tool_instance
        
        # Update LLM adapter if it exists
        if self._llm_adapter:
            await self._llm_adapter.register_tool_class(type(tool_instance), initialize=False)
        
        logger.info(f"Added tool '{tool_instance.name}' to collection '{self.name}'")
        return tool_instance.name
    
    async def add_tools_by_category(
        self, 
        categories: List[str],
        initialize: bool = True
    ) -> List[str]:
        """
        Add all tools from specified categories.
        
        Args:
            categories: List of category names
            initialize: Whether to initialize the tools
            
        Returns:
            List of tool names that were added
        """
        registry = get_registry()
        added_tools = []
        
        for category in categories:
            tool_classes = registry.get_tools_by_category(category)
            for tool_class in tool_classes:
                try:
                    tool_name = await self.add_tool(tool_class, initialize=initialize)
                    added_tools.append(tool_name)
                except Exception as e:
                    logger.warning(f"Failed to add tool {tool_class.__name__}: {e}")
        
        return added_tools
    
    async def add_tools_by_capability(
        self,
        capabilities: List[Union[str, ToolCapability]],
        match_all: bool = False,
        initialize: bool = True
    ) -> List[str]:
        """
        Add tools that have specified capabilities.
        
        Args:
            capabilities: List of required capabilities
            match_all: If True, tools must have all capabilities
            initialize: Whether to initialize the tools
            
        Returns:
            List of tool names that were added
        """
        registry = get_registry()
        added_tools = []
        
        # Convert capabilities to strings
        cap_strings = [
            cap.value if isinstance(cap, ToolCapability) else cap 
            for cap in capabilities
        ]
        
        if match_all:
            # Find tools that have all capabilities
            tool_sets = [
                set(registry.get_tools_by_capability(cap)) 
                for cap in cap_strings
            ]
            if tool_sets:
                tool_classes = set.intersection(*tool_sets)
            else:
                tool_classes = set()
        else:
            # Find tools that have at least one capability
            tool_classes = set()
            for cap in cap_strings:
                tool_classes.update(registry.get_tools_by_capability(cap))
        
        for tool_class in tool_classes:
            try:
                tool_name = await self.add_tool(tool_class, initialize=initialize)
                added_tools.append(tool_name)
            except Exception as e:
                logger.warning(f"Failed to add tool {tool_class.__name__}: {e}")
        
        return added_tools
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all tools in the collection."""
        return self._tools.copy()
    
    def get_tool_names(self) -> List[str]:
        """Get names of all tools in the collection."""
        return list(self._tools.keys())
    
    def has_tool(self, name: str) -> bool:
        """Check if collection has a tool with the given name."""
        return name in self._tools
    
    def remove_tool(self, name: str) -> bool:
        """
        Remove a tool from the collection.
        
        Args:
            name: Name of the tool to remove
            
        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Removed tool '{name}' from collection '{self.name}'")
            return True
        return False
    
    async def get_llm_integration(self) -> LLMToolAdapter:
        """
        Get LLM adapter for this collection.
        
        Returns:
            LLM tool adapter configured with collection tools
        """
        if self._llm_adapter is None:
            self._llm_adapter = LLMToolAdapter()
            
            # Register all tools in the collection
            for tool_instance in self._tools.values():
                await self._llm_adapter.register_tool_class(
                    type(tool_instance), 
                    initialize=False  # Already initialized
                )
        
        return self._llm_adapter
    
    async def get_llm_tools(self) -> Dict[str, Any]:
        """Get tool functions for LLM use."""
        adapter = await self.get_llm_integration()
        return adapter.get_tool_functions()
    
    async def get_llm_tool_definitions(self) -> List[Any]:
        """Get tool definitions for LLM providers."""
        adapter = await self.get_llm_integration()
        return adapter.get_tool_definitions()
    
    async def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """
        Execute a tool by name.
        
        Args:
            name: Name of the tool to execute
            **kwargs: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in collection '{self.name}'")
        
        return await tool(**kwargs)
    
    def get_tools_by_capability(
        self, 
        capability: Union[str, ToolCapability]
    ) -> List[BaseTool]:
        """Get tools in this collection that have a specific capability."""
        if isinstance(capability, ToolCapability):
            capability = capability.value
        
        return [
            tool for tool in self._tools.values()
            if tool.has_capability(capability)
        ]
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        capabilities_count = {}
        total_executions = 0
        
        for tool in self._tools.values():
            # Count capabilities
            for cap in tool.capabilities:
                cap_str = cap.value if isinstance(cap, ToolCapability) else cap
                capabilities_count[cap_str] = capabilities_count.get(cap_str, 0) + 1
            
            # Sum executions
            total_executions += getattr(tool, '_execution_count', 0)
        
        return {
            "name": self.name,
            "tool_count": len(self._tools),
            "tool_names": list(self._tools.keys()),
            "capabilities": capabilities_count,
            "total_executions": total_executions,
            "has_llm_integration": self._llm_adapter is not None
        }
    
    async def cleanup(self) -> None:
        """Clean up all tools in the collection."""
        cleanup_tasks = []
        
        for tool in self._tools.values():
            if hasattr(tool, 'cleanup'):
                cleanup_tasks.append(self._safe_cleanup_tool(tool))
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        if self._llm_adapter:
            await self._llm_adapter.cleanup()
        
        self._tools.clear()
        self._llm_adapter = None
        
        logger.info(f"Cleaned up tool collection '{self.name}'")
    
    async def _safe_cleanup_tool(self, tool: BaseTool) -> None:
        """Safely cleanup a single tool."""
        try:
            await tool.cleanup()
        except Exception as e:
            logger.warning(f"Error cleaning up tool {tool.name}: {e}")
    
    def __len__(self) -> int:
        """Return number of tools in collection."""
        return len(self._tools)
    
    def __contains__(self, item: Union[str, BaseTool]) -> bool:
        """Check if collection contains a tool."""
        if isinstance(item, str):
            return item in self._tools
        elif isinstance(item, BaseTool):
            return item.name in self._tools
        return False
    
    def __iter__(self):
        """Iterate over tools in collection."""
        return iter(self._tools.values())
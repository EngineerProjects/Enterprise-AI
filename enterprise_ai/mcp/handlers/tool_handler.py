"""
Tool execution handler for MCP requests.

This module handles tool execution requests, routing them through
the existing Enterprise AI tool framework.
"""

from typing import Any, Dict, List, Optional

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tool.core.registry import ToolRegistry

from enterprise_ai.mcp.executor import ToolExecutor
from enterprise_ai.mcp.session_manager import SessionManager

logger = get_logger("mcp.handlers.tool")


class ToolHandler:
    """Handles tool execution requests for the MCP server."""
    
    def __init__(
        self,
        executor: ToolExecutor,
        session_manager: SessionManager,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """Initialize the tool handler."""
        self.executor = executor
        self.session_manager = session_manager
        self.tool_registry = tool_registry or ToolRegistry()
        
        # Auto-register tools from registry
        self._register_tools_from_registry()
    
    def _register_tools_from_registry(self) -> None:
        """Register all tools from the tool registry."""
        try:
            tools = self.tool_registry.get_all_tool_classes()
            tool_functions = {}
            
            for tool_name, tool_class in tools.items():
                # Create a wrapper function that properly instantiates and initializes the tool
                async def tool_wrapper(tool_cls=tool_class, tool_name=tool_name, **kwargs):
                    try:
                        # Check if required parameters are provided
                        model_fields = getattr(tool_cls, 'model_fields', {})
                        if 'parameters' in model_fields:
                            expected_params = model_fields['parameters'].default or {}
                            if isinstance(expected_params, dict) and 'required' in expected_params:
                                required_params = expected_params.get('required', [])
                                for param in required_params:
                                    if param not in kwargs:
                                        raise ValueError(f"Parameter '{param}' is required")
                        
                        # Instantiate the tool
                        tool_instance = tool_cls()
                        
                        # Initialize the tool if required
                        if getattr(tool_instance, 'requires_initialization', False):
                            init_success = await tool_instance.initialize(**kwargs)
                            if not init_success:
                                raise Exception(f"Failed to initialize tool {tool_name}")
                        
                        # Call the tool's execute method
                        result = await tool_instance.execute(**kwargs)
                        
                        # Clean up if needed
                        if hasattr(tool_instance, 'cleanup'):
                            try:
                                await tool_instance.cleanup()
                            except Exception as cleanup_error:
                                logger.warning("Tool %s cleanup failed: %s", tool_name, cleanup_error)
                        
                        return result
                        
                    except Exception as e:
                        logger.error("Error executing tool %s: %s", tool_name, e)
                        raise
                
                tool_functions[tool_name] = tool_wrapper
            
            self.executor.register_tools(tool_functions)
            logger.info("Registered %d tools from registry", len(tool_functions))
            
        except Exception as e:
            logger.error("Failed to register tools from registry: %s", e)
    
    async def handle_tool_execution(
        self,
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Handle tool execution requests.
        
        Args:
            tool_calls: List of tool calls to execute
            session_id: Optional session ID
            context: Optional execution context
            
        Returns:
            List of tool execution results
        """
        try:
            # Create session if not provided
            if session_id is None:
                session_id = self.session_manager.create_session()
            
            # Execute tools
            results = await self.executor.execute_tool_calls(
                tool_calls=tool_calls,
                session_id=session_id,
                context=context
            )
            
            return results
            
        except Exception as e:
            logger.error("Tool execution failed: %s", e)
            # Return error results for all tool calls
            error_results = []
            for tool_call in tool_calls:
                error_result = ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    result="",
                    success=False,
                    error=f"Execution failed: {str(e)}",
                    metadata={}
                )
                error_results.append(error_result)
            
            return error_results
    
    async def handle_tool_list_request(self) -> List[Dict[str, Any]]:
        """Handle request to list available tools."""
        try:
            tools = self.tool_registry.get_all_tool_classes()
            tool_definitions = []
            
            for tool_name, tool_class in tools.items():
                # Access Pydantic model fields properly
                model_fields = getattr(tool_class, 'model_fields', {})
                
                # Get description from model fields or fallback methods
                description = ""
                if 'description' in model_fields:
                    description = model_fields['description'].default or ""
                
                # If no description in model fields, try class attribute or docstring
                if not description:
                    description = getattr(tool_class, "description", "")
                if not description and tool_class.__doc__:
                    # Use first line of docstring as fallback
                    doc_lines = tool_class.__doc__.strip().split('\n')
                    if doc_lines:
                        description = doc_lines[0].strip()
                
                # Final fallback
                if not description:
                    description = f"{tool_name} - Tool description not available"
                
                # Get parameters from model fields
                parameters = {}
                if 'parameters' in model_fields:
                    parameters = model_fields['parameters'].default or {}
                if not parameters:
                    parameters = getattr(tool_class, "parameters", {})
                
                # Get capabilities from model fields
                capabilities = set()
                if 'capabilities' in model_fields:
                    capabilities = model_fields['capabilities'].default or set()
                if not capabilities:
                    capabilities = getattr(tool_class, "capabilities", set())
                
                # Convert capabilities to list of strings
                capabilities_list = []
                for cap in capabilities:
                    if hasattr(cap, 'value'):  # ToolCapability enum
                        capabilities_list.append(cap.value)
                    else:
                        capabilities_list.append(str(cap))
                
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": description,
                        "parameters": parameters
                    },
                    # additional MCP metadata
                    "metadata": {
                        "capabilities": capabilities_list,
                        "tool_metadata": getattr(tool_class, "metadata", {})
                    }
                }
                tool_definitions.append(tool_def)
            
            return tool_definitions
            
        except Exception as e:
            logger.error("Failed to list tools: %s", e)
            return []
    
    async def handle_tool_info_request(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Handle request for specific tool information."""
        try:
            tool_class = self.tool_registry.get_tool_class(tool_name)
            if not tool_class:
                return None
            
            # Access Pydantic model fields properly
            model_fields = getattr(tool_class, 'model_fields', {})
            
            # Get description from model fields or fallback methods
            description = ""
            if 'description' in model_fields:
                description = model_fields['description'].default or ""
            
            # If no description in model fields, try class attribute or docstring
            if not description:
                description = getattr(tool_class, "description", "")
            if not description and tool_class.__doc__:
                # Use first line of docstring as fallback
                doc_lines = tool_class.__doc__.strip().split('\n')
                if doc_lines:
                    description = doc_lines[0].strip()
            
            # Final fallback
            if not description:
                description = f"{tool_name} - Tool description not available"
            
            # Get parameters from model fields
            parameters = {}
            if 'parameters' in model_fields:
                parameters = model_fields['parameters'].default or {}
            if not parameters:
                parameters = getattr(tool_class, "parameters", {})
            
            # Get capabilities from model fields
            capabilities = set()
            if 'capabilities' in model_fields:
                capabilities = model_fields['capabilities'].default or set()
            if not capabilities:
                capabilities = getattr(tool_class, "capabilities", set())
            
            # Convert capabilities to list of strings
            capabilities_list = []
            for cap in capabilities:
                if hasattr(cap, 'value'):  # ToolCapability enum
                    capabilities_list.append(cap.value)
                else:
                    capabilities_list.append(str(cap))
            
            # Get config from model fields
            config = {}
            if 'config' in model_fields:
                try:
                    default_config = model_fields['config'].default
                    if default_config and hasattr(default_config, 'dict'):
                        config = default_config.dict()
                    elif default_config and hasattr(default_config, '__dict__'):
                        config = default_config.__dict__
                    elif default_config and not str(type(default_config)).startswith('<class \'pydantic_core.'):
                        # Avoid PydanticUndefinedType objects
                        config = default_config if isinstance(default_config, dict) else {}
                except (AttributeError, TypeError):
                    # Handle any Pydantic-related errors gracefully
                    config = {}
            
            return {
                "name": tool_name,
                "description": description,
                "parameters": parameters,
                "capabilities": capabilities_list,
                "config": config,
                "metadata": getattr(tool_class, "metadata", {}),
                "execution_stats": self.executor.get_execution_stats()
            }
            
        except Exception as e:
            logger.error("Failed to get tool info for %s: %s", tool_name, e)
            return None
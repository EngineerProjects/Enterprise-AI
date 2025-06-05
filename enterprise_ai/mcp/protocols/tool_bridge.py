"""
Tool bridge for converting between Enterprise AI tools and MCP format.

This module provides bridging functionality to integrate existing
Enterprise AI tools with the MCP protocol.
"""

import inspect
from typing import Any, Dict, List, Optional, Set, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tool.core.base import BaseTool, ToolCapability
from enterprise_ai.tool.core.registry import ToolRegistry

logger = get_logger("mcp.tool_bridge")


class ToolBridge:
    """Bridges Enterprise AI tools to MCP protocol format."""
    
    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        """Initialize the tool bridge."""
        self.tool_registry = tool_registry or ToolRegistry()
        self._tool_definitions_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("ToolBridge initialized")
    
    def get_mcp_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all tools in MCP-compatible format.
        
        Returns:
            List of tool definitions in MCP format
        """
        try:
            tools = self.tool_registry.get_all_tool_classes()
            mcp_definitions = []
            
            for tool_name, tool_instance in tools.items():
                mcp_def = self.tool_to_mcp_definition(tool_instance, tool_name)
                if mcp_def:
                    mcp_definitions.append(mcp_def)
            
            logger.info("Generated %d MCP tool definitions", len(mcp_definitions))
            return mcp_definitions
            
        except Exception as e:
            logger.error("Failed to get MCP tool definitions: %s", e)
            return []
    
    def tool_to_mcp_definition(
        self, 
        tool: BaseTool, 
        tool_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a BaseTool to MCP tool definition format.
        
        Args:
            tool: The tool instance to convert
            tool_name: Optional tool name override
            
        Returns:
            MCP tool definition or None if conversion fails
        """
        try:
            name = tool_name or getattr(tool, 'name', tool.__class__.__name__.lower())
            
            # Check cache first
            if name in self._tool_definitions_cache:
                return self._tool_definitions_cache[name]
            
            # Build MCP definition
            mcp_def = {
                "name": name,
                "description": self._get_tool_description(tool),
                "inputSchema": self._get_tool_input_schema(tool),
                "metadata": self._get_tool_metadata(tool)
            }
            
            # Cache the definition
            self._tool_definitions_cache[name] = mcp_def
            
            return mcp_def
            
        except Exception as e:
            logger.error("Failed to convert tool %s to MCP format: %s", 
                        getattr(tool, 'name', 'unknown'), e)
            return None
    
    def _get_tool_description(self, tool: "BaseTool") -> str:
        """Extract tool description from tool class or instance."""
        # If it's a class (Type[BaseTool]), access class-level field defaults
        if isinstance(tool, type):
            # Get field defaults from pydantic model fields
            if hasattr(tool, 'model_fields') and 'description' in tool.model_fields:
                desc_field = tool.model_fields['description']
                if hasattr(desc_field, 'default') and desc_field.default:
                    return desc_field.default
            
            # Fallback to class docstring
            if tool.__doc__:
                return tool.__doc__.strip()
            
            return f"Tool: {tool.__name__}"
        
        # If it's an instance, use instance attributes
        else:
            if hasattr(tool, 'description') and tool.description:
                return tool.description
            elif hasattr(tool, '__doc__') and tool.__doc__:
                return tool.__doc__.strip()
            elif hasattr(tool, 'execute') and tool.execute.__doc__:
                return tool.execute.__doc__.strip()
            else:
                return f"Tool: {tool.__class__.__name__}"
    
    def _get_tool_input_schema(self, tool: "BaseTool") -> Dict[str, Any]:
        """Extract tool input schema from the tool class or instance."""
        try:
            # Handle tool classes (Type[BaseTool])
            if isinstance(tool, type):
                # Get parameters from class-level field defaults
                if hasattr(tool, 'model_fields') and 'parameters' in tool.model_fields:
                    params_field = tool.model_fields['parameters']
                    if hasattr(params_field, 'default') and params_field.default:
                        return self._convert_parameters_to_schema(params_field.default)
                
                # Try to get schema from execute method signature
                if hasattr(tool, 'execute'):
                    return self._extract_schema_from_method(tool.execute)
            
            # Handle tool instances
            else:
                # Try to get schema from tool parameters
                if hasattr(tool, 'parameters') and tool.parameters:
                    return self._convert_parameters_to_schema(tool.parameters)
                
                # Try to get schema from execute method signature
                if hasattr(tool, 'execute'):
                    return self._extract_schema_from_method(tool.execute)
            
            # Fallback to basic schema
            return {
                "type": "object",
                "properties": {},
                "required": []
            }
            
        except Exception as e:
            logger.warning("Failed to extract input schema for tool %s: %s", 
                          getattr(tool, 'name', 'unknown'), e)
            return {
                "type": "object",
                "properties": {},
                "required": []
            }
    
    def _convert_parameters_to_schema(self, parameters: Any) -> Dict[str, Any]:
        """Convert tool parameters to JSON schema format."""
        if isinstance(parameters, dict):
            return parameters
        
        # If it's a Pydantic model
        if hasattr(parameters, 'model_json_schema'):
            return parameters.model_json_schema()
        elif hasattr(parameters, 'schema'):
            return parameters.schema()
        
        # Fallback
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _extract_schema_from_method(self, method) -> Dict[str, Any]:
        """Extract JSON schema from method signature."""
        try:
            sig = inspect.signature(method)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue
                
                param_schema = self._param_to_schema(param)
                properties[param_name] = param_schema
                
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
        except Exception as e:
            logger.warning("Failed to extract schema from method: %s", e)
            return {
                "type": "object",
                "properties": {},
                "required": []
            }
    
    def _param_to_schema(self, param: inspect.Parameter) -> Dict[str, Any]:
        """Convert method parameter to JSON schema."""
        schema = {"type": "string"}  # Default type
        
        # Try to infer type from annotation
        if param.annotation != inspect.Parameter.empty:
            annotation = param.annotation
            
            if annotation == str:
                schema["type"] = "string"
            elif annotation == int:
                schema["type"] = "integer"
            elif annotation == float:
                schema["type"] = "number"
            elif annotation == bool:
                schema["type"] = "boolean"
            elif annotation == list:
                schema["type"] = "array"
            elif annotation == dict:
                schema["type"] = "object"
            elif hasattr(annotation, '__origin__'):
                # Handle generic types like List[str], Optional[int], etc.
                if annotation.__origin__ == list:
                    schema["type"] = "array"
                elif annotation.__origin__ == dict:
                    schema["type"] = "object"
                elif annotation.__origin__ == Union:
                    # Handle Optional types
                    args = annotation.__args__
                    if len(args) == 2 and type(None) in args:
                        non_none_type = args[0] if args[1] == type(None) else args[1]
                        schema = self._type_to_schema(non_none_type)
        
        # Add description from docstring if available
        if hasattr(param, 'description'):
            schema["description"] = param.description
        
        return schema
    
    def _type_to_schema(self, type_hint: Any) -> Dict[str, Any]:
        """Convert Python type hint to JSON schema."""
        if type_hint == str:
            return {"type": "string"}
        elif type_hint == int:
            return {"type": "integer"}
        elif type_hint == float:
            return {"type": "number"}
        elif type_hint == bool:
            return {"type": "boolean"}
        elif type_hint == list:
            return {"type": "array"}
        elif type_hint == dict:
            return {"type": "object"}
        else:
            return {"type": "string"}  # Fallback
    
    def _get_tool_metadata(self, tool: "BaseTool") -> Dict[str, Any]:
        """Extract tool metadata from tool class or instance."""
        metadata = {}
        
        # Handle tool classes (Type[BaseTool])
        if isinstance(tool, type):
            # Get capabilities from class-level field defaults
            if hasattr(tool, 'model_fields'):
                if 'capabilities' in tool.model_fields:
                    cap_field = tool.model_fields['capabilities']
                    if hasattr(cap_field, 'default') and cap_field.default:
                        metadata["capabilities"] = list(cap_field.default)
                
                if 'version' in tool.model_fields:
                    ver_field = tool.model_fields['version']
                    if hasattr(ver_field, 'default') and ver_field.default:
                        metadata["version"] = ver_field.default
                
                if 'config' in tool.model_fields:
                    config_field = tool.model_fields['config']
                    if hasattr(config_field, 'default') and config_field.default:
                        if hasattr(config_field.default, 'danger_level'):
                            metadata["danger_level"] = config_field.default.danger_level
        
        # Handle tool instances
        else:
            # Add capabilities
            if hasattr(tool, 'capabilities'):
                metadata["capabilities"] = list(tool.capabilities)
            
            # Add configuration
            if hasattr(tool, 'config') and tool.config:
                config_dict = tool.config.dict() if hasattr(tool.config, 'dict') else dict(tool.config)
                metadata["config"] = config_dict
            
            # Add version
            if hasattr(tool, 'version'):
                metadata["version"] = tool.version
            
            # Add category
            if hasattr(tool, 'category'):
                metadata["category"] = tool.category
            
            # Add danger level for approval decisions
            if hasattr(tool, 'config') and hasattr(tool.config, 'danger_level'):
                metadata["danger_level"] = tool.config.danger_level
        
        return metadata
    
    def mcp_call_to_tool_call(self, mcp_call: Dict[str, Any]) -> ToolCall:
        """
        Convert MCP call format to Enterprise AI ToolCall.
        
        Args:
            mcp_call: MCP format tool call
            
        Returns:
            Enterprise AI ToolCall instance
        """
        try:
            function_data = mcp_call.get("function", {})
            return ToolCall(
                id=mcp_call.get("id", ""),
                type=mcp_call.get("type", "function"),
                function={
                    "name": function_data.get("name", ""),
                    "arguments": function_data.get("arguments", {})
                }
            )
        except Exception as e:
            logger.error("Failed to convert MCP call to ToolCall: %s", e)
            raise
    
    def tool_result_to_mcp_result(self, tool_result: ToolResult) -> Dict[str, Any]:
        """
        Convert Enterprise AI ToolResult to MCP result format.
        
        Args:
            tool_result: Enterprise AI ToolResult
            
        Returns:
            MCP format result
        """
        try:
            mcp_result = {
                "tool_call_id": tool_result.tool_call_id,
                "name": tool_result.name,
                "success": tool_result.success,
                "result": tool_result.result,
                "metadata": tool_result.metadata or {}
            }
            
            if tool_result.error:
                mcp_result["error"] = tool_result.error
            
            if tool_result.execution_time is not None:
                mcp_result["execution_time"] = tool_result.execution_time
            
            return mcp_result
            
        except Exception as e:
            logger.error("Failed to convert ToolResult to MCP format: %s", e)
            raise
    
    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool instance by name."""
        return self.tool_registry.get_tool_class(tool_name)
    
    def refresh_tool_definitions(self) -> None:
        """Refresh cached tool definitions."""
        self._tool_definitions_cache.clear()
        logger.info("Tool definitions cache refreshed")
    
    def get_bridge_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        total_tools = len(self.tool_registry.get_all_tool_classes())
        cached_definitions = len(self._tool_definitions_cache)
        
        return {
            "total_tools": total_tools,
            "cached_definitions": cached_definitions,
            "cache_hit_rate": cached_definitions / max(1, total_tools),
        }
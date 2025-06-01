"""
Tool conversion for OpenAI provider using Enterprise AI schema classes.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolDefinition

logger = get_logger("llm.openai.tools")


class OpenAIToolConverter:
    """Tool converter for OpenAI format using Enterprise AI schemas."""

    @staticmethod
    def normalize_tools(tools: Sequence[Union[Dict[str, Any], Callable, ToolDefinition]]) -> List[Dict[str, Any]]:
        """Normalize tools to OpenAI format using schema classes."""
        normalized = []
        
        for tool in tools:
            try:
                if isinstance(tool, ToolDefinition):
                    # Already a schema class - use directly
                    normalized.append(tool.to_dict())
                elif callable(tool):
                    # Convert function to ToolDefinition
                    tool_def = OpenAIToolConverter._function_to_tool_definition(tool)
                    normalized.append(tool_def.to_dict())
                elif isinstance(tool, dict):
                    # Validate and normalize dict through schema
                    tool_def = OpenAIToolConverter._dict_to_tool_definition(tool)
                    normalized.append(tool_def.to_dict())
                else:
                    logger.warning(f"Unsupported tool format: {type(tool)}")
            except Exception as e:
                logger.error(f"Failed to normalize tool: {e}")
        
        return normalized

    @staticmethod
    def _function_to_tool_definition(func: Callable) -> ToolDefinition:
        """Convert a Python function to ToolDefinition schema class."""
        import inspect
        
        try:
            # Get function signature and docstring
            sig = inspect.signature(func)
            doc_string = inspect.getdoc(func) or ""
            
            # Parse function information
            description = doc_string.split('\n')[0] if doc_string else f"Function {func.__name__}"
            
            # Build parameters
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # Determine parameter type
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    type_mapping = {
                        int: "integer",
                        float: "number", 
                        bool: "boolean",
                        list: "array",
                        dict: "object",
                        str: "string"
                    }
                    param_type = type_mapping.get(param.annotation, "string")
                
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }
                
                # Required if no default value
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            return ToolDefinition.create_function_tool(
                name=func.__name__,
                description=description,
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            )
            
        except Exception as e:
            logger.error(f"Error converting function {func.__name__} to tool: {e}")
            # Return minimal valid tool
            return ToolDefinition.create_function_tool(
                name=func.__name__,
                description=f"Function {func.__name__}",
                parameters={"type": "object", "properties": {}, "required": []}
            )

    @staticmethod
    def _dict_to_tool_definition(tool_dict: Dict[str, Any]) -> ToolDefinition:
        """Convert dictionary to ToolDefinition with validation."""
        try:
            # Try direct schema conversion first
            return ToolDefinition.from_dict(tool_dict)
        except Exception:
            # Fallback: normalize the dictionary structure
            normalized = {
                "type": "function",
                "function": {
                    "name": tool_dict.get("name", "unknown_function"),
                    "description": tool_dict.get("description", ""),
                    "parameters": tool_dict.get("parameters", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            return ToolDefinition.from_dict(normalized)
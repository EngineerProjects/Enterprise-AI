"""
Shared tool conversion utilities using Enterprise AI schemas.
Eliminates duplication between providers.
"""

import inspect
from typing import Any, Callable, Dict, List

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolDefinition

logger = get_logger("schema.tool_utils")


class ToolConverter:
    """Shared tool conversion logic using schemas."""
    
    @staticmethod
    def function_to_tool_definition(func: Callable) -> ToolDefinition:
        """Convert Python function to ToolDefinition schema (shared logic)."""
        try:
            sig = inspect.signature(func)
            doc_string = inspect.getdoc(func) or ""
            
            # Simple docstring parsing
            description = doc_string.split('\n')[0] if doc_string else f"Function {func.__name__}"
            
            # Build parameters
            properties = {}
            required = []
            
            type_mapping = {
                int: "integer", float: "number", bool: "boolean",
                list: "array", dict: "object", str: "string"
            }
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                param_type = type_mapping.get(param.annotation, "string")
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }
                
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
            logger.error(f"Error converting function {func.__name__}: {e}")
            return ToolDefinition.create_function_tool(
                name=func.__name__,
                description=f"Function {func.__name__}",
                parameters={"type": "object", "properties": {}, "required": []}
            )
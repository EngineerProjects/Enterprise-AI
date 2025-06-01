"""
Tool conversion for OpenAI provider using Enterprise AI schema classes.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolDefinition
from enterprise_ai.schema.tool_utils import ToolConverter  # Use shared converter

logger = get_logger("llm.openai.tools")


class OpenAIToolConverter:
    """Tool converter for OpenAI format using Enterprise AI schemas."""

    @staticmethod
    def normalize_tools(tools: Sequence[Union[Dict[str, Any], Callable, ToolDefinition]]) -> List[Dict[str, Any]]:
        """Normalize tools to OpenAI format using shared schema logic."""
        normalized = []
        
        for tool in tools:
            try:
                if isinstance(tool, ToolDefinition):
                    # Already a schema class - use directly
                    normalized.append(tool.to_dict())
                elif callable(tool):
                    # Use shared conversion logic from schema
                    tool_def = ToolConverter.function_to_tool_definition(tool)
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
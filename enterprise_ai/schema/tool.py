"""
Tool calling schema for Enterprise AI.

This module defines models for handling tool/function calls across LLM providers.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Function(BaseModel):
    """Represents a function call in a tool call."""
    
    name: str = Field(..., description="Name of the function to call")
    arguments: str = Field(..., description="JSON string of function arguments")


class ToolCall(BaseModel):
    """Represents a tool/function call in a message."""
    
    id: str = Field(..., description="Unique identifier for the tool call")
    type: str = Field(default="function", description="Type of tool call")
    function: Function = Field(..., description="Function call details")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        """Create ToolCall from dictionary."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "function"),
            function=Function(
                name=data["function"]["name"],
                arguments=data["function"]["arguments"]
            )
        )


class ToolChoice:
    """Tool choice options for LLM calls."""
    
    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


# Type aliases for tool choice
TOOL_CHOICE_VALUES = (ToolChoice.NONE, ToolChoice.AUTO, ToolChoice.REQUIRED)
TOOL_CHOICE_TYPE = str  # Can be "none", "auto", "required", or dict for specific function
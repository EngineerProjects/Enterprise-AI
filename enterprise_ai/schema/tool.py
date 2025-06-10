"""
Tool calling schema for Enterprise AI.

This module defines models for handling tool/function calls across LLM providers,
enhanced for the new architecture with better validation and conversion support.
"""

import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class Function(BaseModel):
    """Represents a function call in a tool call."""
    
    name: str = Field(..., description="Name of the function to call")
    arguments: Union[str, Dict[str, Any]] = Field(..., description="Function arguments as JSON string or dict")
    
    @field_validator('arguments', mode='before')
    @classmethod
    def validate_arguments(cls, v):
        """Ensure arguments is properly formatted."""
        if isinstance(v, dict):
            return json.dumps(v)
        elif isinstance(v, str):
            # Validate that it's valid JSON
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return "{}"
        else:
            return "{}"

    def get_arguments_dict(self) -> Dict[str, Any]:
        """Get arguments as a dictionary."""
        if isinstance(self.arguments, dict):
            return self.arguments
        try:
            return json.loads(self.arguments)
        except json.JSONDecodeError:
            return {}

    def set_arguments_dict(self, args: Dict[str, Any]) -> None:
        """Set arguments from a dictionary."""
        self.arguments = json.dumps(args)


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
        function_data = data.get("function", {})
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "function"),
            function=Function(
                name=function_data.get("name", ""),
                arguments=function_data.get("arguments", "{}")
            )
        )

    @classmethod
    def create(
        cls, 
        name: str, 
        arguments: Union[Dict[str, Any], str], 
        id: Optional[str] = None,
        type: str = "function"
    ) -> "ToolCall":
        """Create a ToolCall with convenient parameters."""
        import time
        
        if id is None:
            id = f"call_{int(time.time() * 1000)}"
        
        return cls(
            id=id,
            type=type,
            function=Function(name=name, arguments=arguments)
        )

    def get_function_name(self) -> str:
        """Get the function name."""
        return self.function.name

    def get_arguments(self) -> Dict[str, Any]:
        """Get function arguments as dictionary."""
        return self.function.get_arguments_dict()

    def __str__(self) -> str:
        """String representation."""
        return f"ToolCall({self.function.name}, args={len(self.get_arguments())} keys)"


class ToolChoice:
    """Tool choice options for LLM calls."""
    
    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"
    
    @classmethod
    def function(cls, name: str) -> Dict[str, Any]:
        """Create a specific function choice."""
        return {
            "type": "function",
            "function": {"name": name}
        }

    @classmethod
    def validate(cls, choice: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Validate tool choice value."""
        if isinstance(choice, str):
            if choice in (cls.NONE, cls.AUTO, cls.REQUIRED):
                return choice
            else:
                raise ValueError(f"Invalid tool choice string: {choice}")
        elif isinstance(choice, dict):
            if choice.get("type") == "function" and "function" in choice:
                return choice
            else:
                raise ValueError(f"Invalid tool choice dict: {choice}")
        else:
            raise ValueError(f"Tool choice must be string or dict, got {type(choice)}")


class ToolDefinition(BaseModel):
    """Represents a tool definition for LLM providers."""
    
    type: str = Field(default="function", description="Type of tool")
    function: Dict[str, Any] = Field(..., description="Function definition")
    
    @classmethod
    def create_function_tool(
        cls,
        name: str,
        description: str,
        parameters: Dict[str, Any]
    ) -> "ToolDefinition":
        """Create a function tool definition."""
        return cls(
            type="function",
            function={
                "name": name,
                "description": description,
                "parameters": parameters
            }
        )
    
    def get_name(self) -> str:
        """Get tool name."""
        return self.function.get("name", "")
    
    def get_description(self) -> str:
        """Get tool description."""
        return self.function.get("description", "")
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get tool parameters schema."""
        return self.function.get("parameters", {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "function": self.function
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "function"),
            function=data.get("function", {})
        )

class ToolResult(BaseModel):
    """Represents the result of a tool/function call execution."""
    
    tool_call_id: str = Field(..., description="ID of the tool call this result is for")
    name: str = Field(..., description="Name of the tool that was called")
    result: Union[str, Dict[str, Any], List[Any]] = Field(..., description="Result of the tool execution")
    success: bool = Field(default=True, description="Whether the tool call was successful")
    error: Optional[str] = Field(default=None, description="Error message if tool call failed")
    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def to_message_content(self) -> str:
        """Convert result to content for a tool message."""
        if not self.success and self.error:
            return f"Error: {self.error}"
        
        if isinstance(self.result, str):
            return self.result
        elif isinstance(self.result, (dict, list)):
            return json.dumps(self.result, indent=2)
        else:
            return str(self.result)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResult":
        """Create from dictionary."""
        return cls(
            tool_call_id=data["tool_call_id"],
            name=data["name"],
            result=data["result"],
            success=data.get("success", True),
            error=data.get("error"),
            execution_time=data.get("execution_time"),
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def success(
        cls,
        tool_call_id: str,
        name: str,
        result: Union[str, Dict[str, Any], List[Any]],
        execution_time: Optional[float] = None,
        **metadata: Any
    ) -> "ToolResult":
        """Create a successful tool result."""
        return cls(
            tool_call_id=tool_call_id,
            name=name,
            result=result,
            success=True,
            execution_time=execution_time,
            metadata=metadata,
        )
    
    @classmethod  
    def create_error(
        cls,
        tool_call_id: str,
        name: str,
        error: str,
        execution_time: Optional[float] = None,
        **metadata: Any
    ) -> "ToolResult":
        """Create an error tool result."""
        return cls(
            tool_call_id=tool_call_id,
            name=name,
            result="",
            success=False,
            error=error,
            execution_time=execution_time,
            metadata=metadata,
        )
    

# Type aliases for tool choice
TOOL_CHOICE_VALUES = (ToolChoice.NONE, ToolChoice.AUTO, ToolChoice.REQUIRED)
TOOL_CHOICE_TYPE = Union[str, Dict[str, Any]]  # Can be "none", "auto", "required", or dict for specific function
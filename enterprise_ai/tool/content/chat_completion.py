"""Chat completion tool for Enterprise AI."""

from typing import Any, Dict, List, Optional, Type, Union, TypeVar, cast, get_args, get_origin

from pydantic import BaseModel, Field, field_validator

from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool

# Define a type variable for more flexibility
T = TypeVar("T")


@register_tool(category="content")
class CreateChatCompletion(BaseTool):
    """Tool for creating structured chat completions with specific formats."""

    name: str = "create_chat_completion"
    description: str = "Creates a structured completion with specified output formatting."

    # Type mapping for JSON schema
    type_mapping: Dict[Type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }

    class Config:
        """Configuration for this model."""

        arbitrary_types_allowed = True

    def __init__(self, response_type: Optional[Type] = str) -> None:
        """Initialize with a specific response type."""
        # Initialize BaseTool first with required attributes
        super().__init__(
            name=self.name,
            description=self.description,
            parameters=self._build_parameters(response_type),
        )
        self.response_type = response_type
        self.required = ["response"]

    def _build_parameters(self, response_type: Optional[Type] = None) -> Dict[str, Any]:
        """Build parameters schema based on response type."""
        if response_type is str or response_type is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "The response text that should be delivered to the user.",
                    },
                },
                "required": ["response"],
            }

        if isinstance(response_type, type) and issubclass(response_type, BaseModel):
            schema = response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", ["response"]),
            }

        return self._create_type_schema(response_type)

    def _create_type_schema(self, type_hint: Optional[Type]) -> Dict[str, Any]:
        """Create a JSON schema for the given type."""
        if type_hint is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "Generic response content",
                    }
                },
                "required": ["response"],
            }

        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # Handle primitive types
        if origin is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": self.type_mapping.get(type_hint, "string"),
                        "description": f"Response of type {getattr(type_hint, '__name__', 'unknown')}",
                    }
                },
                "required": ["response"],
            }

        # Handle List type
        if origin is list:
            # Create a safe schema for list items
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "array",
                        "items": self._get_type_info_safe(args[0] if args else Any),
                    }
                },
                "required": ["response"],
            }

        # Handle Dict type
        if origin is dict:
            # Create a safe schema for dict values
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "object",
                        "additionalProperties": self._get_type_info_safe(
                            args[1] if len(args) > 1 else Any
                        ),
                    }
                },
                "required": ["response"],
            }

        # Handle Union type
        if origin is Union:
            return self._create_union_schema(args)

        return {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Generic response content",
                }
            },
            "required": ["response"],
        }

    def _get_type_info(self, type_hint: Type) -> Dict[str, Any]:
        """Get type information for a single type."""
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            return cast(Dict[str, Any], type_hint.model_json_schema())

        return {
            "type": self.type_mapping.get(type_hint, "string"),
            "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
        }

    def _get_type_info_safe(self, type_hint: Any) -> Dict[str, Any]:
        """Safely get type information for any type hint, including non-type objects."""
        # Handle None case
        if type_hint is None:
            return {"type": "null", "description": "Null value"}

        # Handle primitive types that can be directly mapped
        if isinstance(type_hint, type):
            return self._get_type_info(type_hint)

        # Handle typing special forms and other complex types
        origin = get_origin(type_hint)

        # For Union types, create anyOf schema
        if origin is Union:
            args = get_args(type_hint)
            return {"anyOf": [self._get_type_info_safe(arg) for arg in args]}

        # For List, Dict and other container types
        if origin in (list, dict, set, tuple):
            return {
                "type": self.type_mapping.get(origin, "object"),
                "description": f"Container of type {origin.__name__}",
            }

        # Default case for any other type
        return {"type": "string", "description": "Generic value"}

    def _create_union_schema(self, types: tuple) -> Dict[str, Any]:
        """Create schema for Union types."""
        return {
            "type": "object",
            "properties": {"response": {"anyOf": [self._get_type_info_safe(t) for t in types]}},
            "required": ["response"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the chat completion with type conversion.

        Args:
            **kwargs: Response data including:
                required: Optional list of required field names
                response: The response content or fields named in required

        Returns:
            Converted response based on response_type
        """
        # Extract the required fields parameter if provided
        required_fields = kwargs.pop("required", None) or ["response"]

        # Handle case when required is a list
        if isinstance(required_fields, list) and len(required_fields) > 0:
            if len(required_fields) == 1:
                required_field = required_fields[0]
                result = kwargs.get(required_field, "")
            else:
                # Return multiple fields as a dictionary
                result = {field: kwargs.get(field, "") for field in required_fields}
        else:
            required_field = "response"
            result = kwargs.get(required_field, "")

        # Type conversion logic
        if self.response_type is str or self.response_type is None:
            return ToolResult(output=str(result))

        if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
            try:
                converted = self.response_type(**kwargs)
                return ToolResult(output=str(converted))
            except Exception as e:
                return ToolResult(error=f"Type conversion error: {str(e)}")

        if get_origin(self.response_type) in (list, dict):
            return ToolResult(output=str(result))  # Convert to string for output

        try:
            if self.response_type is not None:
                converted = self.response_type(result)
                return ToolResult(output=str(converted))
        except (ValueError, TypeError) as e:
            return ToolResult(error=f"Type conversion error: {str(e)}")

        return ToolResult(output=str(result))

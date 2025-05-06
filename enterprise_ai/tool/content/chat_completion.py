"""Chat completion tool for Enterprise AI."""

from typing import Any, Dict, List, Optional, Set, Type, Union, TypeVar, cast, get_args, get_origin

from pydantic import BaseModel, Field, validator

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

# Define a type variable for more flexibility
T = TypeVar("T")

logger = get_logger("tool.content.chat_completion")


@register_tool(category="content")
class CreateChatCompletion(BaseTool):
    """
    Tool for creating structured formatted content with specific output types.

    Key capabilities:
    * Generate content with controlled structure and formatting
    * Convert outputs to specified types (string, integer, Pydantic models)
    * Support for complex data types including lists and dictionaries
    * Handle JSON schema validation for structured outputs

    Use this tool when:
    * You need to create formatted outputs with specific structure
    * You need to convert response data to specific types
    * You want to validate output against a schema
    * You need to generate structured data that follows a defined format

    Notes:
    * Response type can be specified during initialization
    * Can handle primitive types, lists, dictionaries, and Pydantic models
    * Returns properly formatted and validated results
    """

    name: str = "create_chat_completion"
    description: str = """
    Creates a structured completion with specified output formatting.
    
    * Purpose: Generate formatted content according to specific output types
    * Usage: Used when specific data formats or validation are needed
    * Features: Type conversion, schema validation, support for complex data types
    * Returns: Content formatted according to the specified output type
    
    The tool can output different formats based on the specified response_type
    parameter during initialization, including primitive types, lists, and Pydantic models.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "response": {
                "type": "string",
                "description": "The response text that should be delivered to the user.",
            },
            "required": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of required field names to extract from the result.",
            },
        },
        "required": ["response"],
    }

    # Define capabilities
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.TEXT_GENERATION}

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

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        response_type: Optional[Type] = str,
        **kwargs: Any,
    ) -> None:
        """
        Initialize with standard parameters and a specific response type.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            response_type: Type to convert responses to (default: str)
            **kwargs: Additional keyword arguments
        """
        # Build parameters based on response type if not explicitly provided
        built_parameters = parameters or self._build_parameters(response_type)

        # Initialize BaseTool with required attributes
        super().__init__(
            name=name or self.name,
            description=description or self.description,
            parameters=built_parameters,
        )

        # Store tool configuration
        self.config = config or ToolConfig()

        # Store response type and required fields
        self.response_type = response_type or str
        self.required = ["response"]

        logger.debug(f"CreateChatCompletion initialized with response_type: {response_type}")

    def _build_parameters(self, response_type: Optional[Type] = None) -> Dict[str, Any]:
        """
        Build parameters schema based on response type.

        Args:
            response_type: The type to build parameters for

        Returns:
            A JSON schema object for the parameters
        """
        # Handle string type (default)
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

        # Handle Pydantic models
        if isinstance(response_type, type) and issubclass(response_type, BaseModel):
            schema = response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", ["response"]),
            }

        # Handle other types
        return self._create_type_schema(response_type)

    def _create_type_schema(self, type_hint: Optional[Type]) -> Dict[str, Any]:
        """
        Create a JSON schema for the given type.

        Args:
            type_hint: Type to create schema for

        Returns:
            JSON schema for the specified type
        """
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
        """
        Get type information for a single type.

        Args:
            type_hint: Type to get information for

        Returns:
            Dictionary with type information
        """
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            return cast(Dict[str, Any], type_hint.model_json_schema())

        return {
            "type": self.type_mapping.get(type_hint, "string"),
            "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
        }

    def _get_type_info_safe(self, type_hint: Any) -> Dict[str, Any]:
        """
        Safely get type information for any type hint, including non-type objects.

        Args:
            type_hint: Type hint to get information for

        Returns:
            Dictionary with type information
        """
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
        """
        Create schema for Union types.

        Args:
            types: Tuple of types in the union

        Returns:
            JSON schema for the union type
        """
        return {
            "type": "object",
            "properties": {"response": {"anyOf": [self._get_type_info_safe(t) for t in types]}},
            "required": ["response"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the chat completion with type conversion.

        Args:
            **kwargs: Response data including:
                required: Optional list of required field names
                response: The response content or fields named in required

        Returns:
            Converted response based on response_type
        """
        # Start with basic validation of input
        logger.debug(f"Executing chat completion with params: {kwargs}")

        try:
            # Apply timeout from config if needed
            timeout = self.config.timeout if hasattr(self.config, "timeout") else None

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

            # Validate that we have the required data
            if result == "" and required_field == "response":
                logger.warning("No response data provided")
                return ToolResult(error="No response data provided")

            # Type conversion logic
            logger.debug(f"Converting result to type: {self.response_type}")

            # Convert based on response type
            if self.response_type is str or self.response_type is None:
                logger.debug("Converting to string")
                return ToolResult(output=str(result))

            if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
                try:
                    logger.debug("Converting to Pydantic model")
                    converted = self.response_type(**kwargs)
                    return ToolResult(output=str(converted))
                except Exception as e:
                    logger.error(f"Type conversion error (Pydantic): {e}")
                    return ToolResult(error=f"Type conversion error: {str(e)}")

            if get_origin(self.response_type) in (list, dict):
                logger.debug(f"Converting to container type: {get_origin(self.response_type)}")
                return ToolResult(output=str(result))  # Convert to string for output

            try:
                if self.response_type is not None:
                    logger.debug(f"Converting to specific type: {self.response_type}")
                    converted = self.response_type(result)
                    return ToolResult(output=str(converted))
            except (ValueError, TypeError) as e:
                logger.error(f"Type conversion error: {e}")
                return ToolResult(error=f"Type conversion error: {str(e)}")

            # Default fallback - return as string
            return ToolResult(output=str(result))

        except Exception as e:
            logger.error(f"Unexpected error in chat completion: {e}")
            return ToolResult(error=f"Error executing chat completion: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up any resources used by the tool."""
        # No resources to clean up in this tool
        pass

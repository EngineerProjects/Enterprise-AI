"""Chat completion tool for Enterprise AI."""

from typing import Any, Dict, List, Optional, Set, Type, Union, cast, get_args, get_origin

from pydantic import BaseModel, Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.content.chat_completion")


@register_tool(category="content", capabilities=["content_creation", "text_generation"])
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
    short_description: str = "Generate structured content with specific output formats and schema validation."
    description: str = """
    Creates a structured completion with specified output formatting.

    * Purpose: Generate formatted content according to specific output types
    * Usage: Used when specific data formats or validation are needed
    * Features: Type conversion, schema validation, support for complex data types
    * Returns: Content formatted according to the specified output type

    The tool can output different formats based on the specified response_type
    parameter during initialization, including primitive types, lists, and Pydantic models.
    """

    # Renamed fields without leading underscores
    response_type_internal: Optional[Type] = Field(default=str, exclude=True)
    required_fields: List[str] = Field(default_factory=lambda: ["response"], exclude=True)

    # Type mapping for JSON schema - with annotation
    type_mapping: Dict[Type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }

    # Define capabilities with proper type annotation
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.TEXT_GENERATION}

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        response_type: Optional[Type] = str,
        **kwargs: Any,
    ):
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
        # Store response type in a local variable first (don't set attribute yet)
        temp_response_type = response_type or str

        # Build parameters if not explicitly provided
        if parameters is None:
            # Use static method to build parameters
            parameters = self._build_parameters_static(temp_response_type)

        # Call parent constructor with all parameters
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters,
            **kwargs,
        )

        # Now it's safe to set these attributes after super().__init__()
        self.response_type_internal = temp_response_type

        # Store config
        self.config = config or ToolConfig()

        logger.debug("CreateChatCompletion initialized with response_type: %s", response_type)

    @classmethod
    def _build_parameters_static(cls, response_type: Type) -> dict:
        """Static version of _build_parameters that doesn't rely on instance attributes."""
        required = ["response"]

        if response_type is str:
            return {
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
                "required": required,
            }

        if isinstance(response_type, type) and issubclass(response_type, BaseModel):
            schema = response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema["properties"],
                "required": schema.get("required", required),
            }

        return cls._create_type_schema_static(response_type, required)

    @classmethod
    def _create_type_schema_static(cls, type_hint: Type, required: List[str]) -> dict:
        """Static version of _create_type_schema."""
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # Type mapping for JSON schema
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }

        # Handle primitive types
        if origin is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": type_mapping.get(type_hint, "string"),
                        "description": f"Response of type {getattr(type_hint, '__name__', 'unknown')}",
                    },
                    "required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of required field names to extract from the result.",
                    },
                },
                "required": required,
            }

        # Handle List type
        if origin is list:
            item_type = args[0] if args else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "array",
                        "items": cls._get_type_info_static(item_type)
                        if item_type != Any
                        else {"type": "string"},
                    },
                    "required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of required field names to extract from the result.",
                    },
                },
                "required": required,
            }

        # Handle Dict type
        if origin is dict:
            value_type = args[1] if len(args) > 1 else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "object",
                        "additionalProperties": cls._get_type_info_static(value_type)
                        if value_type != Any
                        else {"type": "string"},
                    },
                    "required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of required field names to extract from the result.",
                    },
                },
                "required": required,
            }

        # Handle Union type
        if origin is Union:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "anyOf": [
                            cls._get_type_info_static(t)
                            if isinstance(t, type)
                            else {"type": "string"}
                            for t in args
                        ]
                    },
                    "required": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of required field names to extract from the result.",
                    },
                },
                "required": required,
            }

        # Default fallback
        return {
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
            "required": required,
        }

    @classmethod
    def _get_type_info_static(cls, type_hint: Any) -> Dict[str, Any]:
        """Static version of _get_type_info."""
        # Type mapping for JSON schema
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }

        # Handle the case where type_hint is a proper class
        if isinstance(type_hint, type):
            if issubclass(type_hint, BaseModel):
                # Check for Pydantic v2 method first, then fall back to v1
                if hasattr(type_hint, "model_json_schema"):
                    schema = type_hint.model_json_schema()  # type: ignore
                    return cast(Dict[str, Any], schema)
                # Fall back to Pydantic v1 method
                elif hasattr(type_hint, "schema"):
                    schema = type_hint.schema()  # type: ignore
                    return cast(Dict[str, Any], schema)

            return {
                "type": type_mapping.get(type_hint, "string"),
                "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
            }

        # Handle special typing forms or other non-type values
        origin = get_origin(type_hint)
        if origin is not None:
            # For container types like List[str], Dict[str, int], etc.
            container_type = type_mapping.get(origin, "string")
            return {
                "type": container_type,
                "description": f"Value of container type {container_type}",
            }

        # Default for Any or unknown types
        return {
            "type": "string",
            "description": "Value of any type",
        }

    def _build_parameters(self) -> dict:
        """Build parameters schema based on response type."""
        return self._build_parameters_static(self.response_type_internal or str)

    def _create_type_schema(self, type_hint: Type) -> dict:
        """Create a JSON schema for the given type."""
        return self._create_type_schema_static(type_hint, self.required_fields)

    def _get_type_info(self, type_hint: Type) -> dict:
        """Get type information for a single type."""
        return self._get_type_info_static(type_hint)

    def _create_union_schema(self, types: tuple) -> dict:
        """Create schema for Union types."""
        return {
            "type": "object",
            "properties": {
                "response": {
                    "anyOf": [self._get_type_info(t) for t in types if isinstance(t, type)]
                },
                "required": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of required field names to extract from the result.",
                },
            },
            "required": self.required_fields,
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
        logger.debug("Executing chat completion with params: %s", kwargs)

        try:
            # Extract the required fields parameter if provided
            required_fields = kwargs.pop("required", None) or self.required_fields

            # Get the response parameter directly - this is the main fix
            response_text = kwargs.get("response", "")
            
            if not response_text:
                # Try alternative parameter names for compatibility
                response_text = kwargs.get("text", kwargs.get("content", ""))
            
            if not response_text:
                logger.warning("No response data provided")
                return ToolResult.create_error(
                    error="No response data provided. Please use 'response' parameter with your text.",
                    tool_name=self.name
                )

            # Special handling for Pydantic models
            if isinstance(self.response_type_internal, type) and issubclass(
                self.response_type_internal, BaseModel
            ):
                logger.debug("Converting to Pydantic model")
                try:
                    # First, check if we received a "response" parameter containing a dict
                    if isinstance(response_text, dict):
                        # Use the nested dict directly
                        converted = self.response_type_internal(**response_text)
                        return ToolResult.create_success(
                            result=str(converted),
                            tool_name=self.name
                        )

                    # Second, check if we have all required fields at the root level
                    model_fields = self.response_type_internal.model_fields
                    has_required_fields = all(
                        f in kwargs for f in model_fields if model_fields[f].is_required()
                    )

                    if has_required_fields:
                        # The model fields are passed directly at root level
                        converted = self.response_type_internal(**kwargs)
                        return ToolResult.create_success(
                            result=str(converted),
                            tool_name=self.name
                        )

                    # If we reach here, we don't have valid input for the model
                    logger.warning("No response data provided for Pydantic model")
                    return ToolResult.create_error(
                        error="No response data provided for Pydantic model",
                        tool_name=self.name
                    )

                except Exception as e:
                    logger.error("Type conversion error (Pydantic): %s", e)
                    return ToolResult.create_error(
                        error=f"Type conversion error: {str(e)}",
                        tool_name=self.name
                    )

            # Handle regular (non-Pydantic-model) case
            # For most cases, we want to return the response_text directly
            logger.debug("Converting result to type: %s", self.response_type_internal)

            # Convert based on response type
            if self.response_type_internal is str or self.response_type_internal is None:
                logger.debug("Returning string response")
                return ToolResult.create_success(
                    result=str(response_text),
                    tool_name=self.name
                )

            # Handle container types (list, dict)
            if get_origin(self.response_type_internal) in (list, dict):
                logger.debug("Converting to container type: %s", get_origin(self.response_type_internal))
                return ToolResult.create_success(
                    result=str(response_text),
                    tool_name=self.name
                )

            # Handle other specific types
            try:
                if self.response_type_internal is not None:
                    logger.debug("Converting to specific type: %s", self.response_type_internal)
                    converted = self.response_type_internal(response_text)
                    return ToolResult.create_success(
                        result=str(converted),
                        tool_name=self.name
                    )
            except (ValueError, TypeError) as e:
                logger.error("Type conversion error: %s", e)
                return ToolResult.create_error(
                    error=f"Type conversion error: {str(e)}",
                    tool_name=self.name
                )

            # Default fallback - return as string
            return ToolResult.create_success(
                result=str(response_text),
                tool_name=self.name
            )

        except Exception as e:
            logger.error("Unexpected error in chat completion: %s", e)
            return ToolResult.create_error(
                error=f"Error executing chat completion: {str(e)}",
                tool_name=self.name
            )

    async def cleanup(self) -> None:
        """Clean up any resources used by the tool."""
        # No resources to clean up in this tool
        pass

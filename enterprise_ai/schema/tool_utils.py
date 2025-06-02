"""
Enhanced shared tool conversion utilities using Enterprise AI schemas.
Eliminates duplication between providers with improved functionality.
"""

import inspect
import json
from typing import Any, Callable, Dict, List, Optional, Type, Union, get_type_hints, get_origin, get_args

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolDefinition

logger = get_logger("schema.tool_utils")


class ToolConverter:
    """Enhanced shared tool conversion logic using schemas."""
    
    # Enhanced type mapping with better coverage
    TYPE_MAPPING = {
        int: "integer",
        float: "number", 
        bool: "boolean",
        str: "string",
        list: "array",
        dict: "object",
        List: "array",
        Dict: "object",
        Optional: "string",  # Fallback for Optional types
        Union: "string",     # Fallback for Union types
    }
    
    @classmethod
    def function_to_tool_definition(cls, func: Callable) -> ToolDefinition:
        """Convert Python function to ToolDefinition schema with enhanced introspection."""
        try:
            sig = inspect.signature(func)
            doc_string = inspect.getdoc(func) or ""
            
            # Enhanced docstring parsing
            description = cls._parse_function_description(func, doc_string)
            
            # Build parameters with type hints
            properties = {}
            required = []
            
            # Get type hints if available
            try:
                type_hints = get_type_hints(func)
            except Exception as e:
                logger.debug(f"Could not get type hints for {func.__name__}: {e}")
                type_hints = {}
            
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'cls', 'kwargs'):
                    continue
                
                # Get parameter type from type hints or annotation
                param_type_info = cls._get_parameter_type_info(
                    param_name, param, type_hints
                )
                
                properties[param_name] = param_type_info
                
                # Check if parameter is required
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
    
    @classmethod
    def _parse_function_description(cls, func: Callable, doc_string: str) -> str:
        """Parse function description from docstring and function name."""
        if doc_string:
            # Use first line of docstring, or first paragraph
            lines = doc_string.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line and not first_line.startswith('Args:'):
                    return first_line
                
            # If first line is empty or Args:, look for the actual description
            for line in lines:
                line = line.strip()
                if line and not line.startswith(('Args:', 'Returns:', 'Raises:', 'Note:')):
                    return line
        
        # Fallback to function name
        return f"Function {func.__name__}"
    
    @classmethod
    def _get_parameter_type_info(
        cls, 
        param_name: str, 
        param: inspect.Parameter, 
        type_hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get enhanced parameter type information."""
        # Start with basic info
        param_info = {
            "description": f"Parameter {param_name}"
        }
        
        # Get type from hints first, then annotation
        param_type = type_hints.get(param_name, param.annotation)
        
        if param_type != inspect.Parameter.empty:
            type_info = cls._analyze_type(param_type)
            param_info.update(type_info)
        else:
            # Fallback to string type
            param_info["type"] = "string"
        
        # Add default value if present
        if param.default != inspect.Parameter.empty:
            try:
                # Try to JSON serialize the default value
                default_value = param.default
                json.dumps(default_value)  # Test if serializable
                param_info["default"] = default_value
            except (TypeError, ValueError):
                # If not serializable, convert to string
                param_info["default"] = str(param.default)
        
        return param_info
    
    @classmethod
    def _analyze_type(cls, type_hint: Any) -> Dict[str, Any]:
        """Analyze a type hint and return JSON schema information."""
        # Handle None type
        if type_hint is type(None):
            return {"type": "null"}
        
        # Handle basic types
        if type_hint in cls.TYPE_MAPPING:
            return {"type": cls.TYPE_MAPPING[type_hint]}
        
        # Handle generic types (List, Dict, Optional, Union, etc.)
        origin = get_origin(type_hint)
        args = get_args(type_hint)
        
        if origin is not None:
            return cls._handle_generic_type(origin, args)
        
        # Handle class types
        if inspect.isclass(type_hint):
            # Check if it's a known type
            if type_hint in cls.TYPE_MAPPING:
                return {"type": cls.TYPE_MAPPING[type_hint]}
            
            # For custom classes, treat as object
            return {
                "type": "object",
                "description": f"Object of type {type_hint.__name__}"
            }
        
        # Fallback to string
        return {"type": "string"}
    
    @classmethod
    def _handle_generic_type(cls, origin: Any, args: tuple) -> Dict[str, Any]:
        """Handle generic types like List[str], Dict[str, int], Optional[str], etc."""
        
        # Handle List types
        if origin is list or origin is List:
            if args:
                item_type = cls._analyze_type(args[0])
                return {
                    "type": "array",
                    "items": item_type
                }
            else:
                return {"type": "array"}
        
        # Handle Dict types
        if origin is dict or origin is Dict:
            result = {"type": "object"}
            if len(args) >= 2:
                # Dict[key_type, value_type]
                value_type = cls._analyze_type(args[1])
                result["additionalProperties"] = value_type
            return result
        
        # Handle Optional types (Union[T, None])
        if origin is Union:
            # Check if it's Optional (Union with None)
            non_none_types = [arg for arg in args if arg is not type(None)]
            if len(non_none_types) == 1 and type(None) in args:
                # This is Optional[T]
                inner_type = cls._analyze_type(non_none_types[0])
                # Optional types can be null
                if isinstance(inner_type.get("type"), str):
                    return {
                        "anyOf": [
                            inner_type,
                            {"type": "null"}
                        ]
                    }
                else:
                    return inner_type
            else:
                # General Union type
                return {
                    "anyOf": [cls._analyze_type(arg) for arg in args]
                }
        
        # Fallback for other generic types
        return {"type": "string"}


# Convenience functions
def convert_function_to_tool_definition(func: Callable) -> ToolDefinition:
    """Convert a function to a ToolDefinition."""
    converter = ToolConverter()
    return converter.function_to_tool_definition(func)


def get_function_schema(func: Callable) -> Dict[str, Any]:
    """Get JSON schema for a function."""
    definition = convert_function_to_tool_definition(func)
    return definition.to_dict()
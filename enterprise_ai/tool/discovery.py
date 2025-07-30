"""
Advanced Tool Discovery and Definition Generation System for Enterprise AI.

This module provides automatic tool discovery, introspection, and definition generation
to enable seamless integration with MCP and agent systems.
"""

import ast
import inspect
import importlib
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, Tuple, Union
from dataclasses import dataclass
from functools import lru_cache
import json
import time

from pydantic import BaseModel

from enterprise_ai.tool.core.base import BaseTool, ToolCapability
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.discovery")


@dataclass
class ToolDefinition:
    """Complete tool definition with metadata."""
    name: str
    description: str
    parameters: Dict[str, Any]
    function_signature: Dict[str, Any]
    capabilities: Set[str]
    version: str
    class_path: str
    module_path: str
    dependencies: List[str]
    examples: List[Dict[str, Any]]
    danger_level: int
    requires_approval: bool
    short_description: str


@dataclass 
class DiscoveryResult:
    """Result of tool discovery operation."""
    tools: Dict[str, ToolDefinition]
    total_discovered: int
    successful_loads: int
    failed_loads: int
    discovery_time: float
    errors: List[str]


class ToolIntrospector:
    """Advanced tool introspection for automatic definition generation."""
    
    @staticmethod
    def extract_function_signature(tool_class: Type[BaseTool]) -> Dict[str, Any]:
        """Extract execute method signature and convert to JSON schema."""
        if not hasattr(tool_class, 'execute'):
            return {"type": "object", "properties": {}, "required": []}
            
        try:
            sig = inspect.signature(tool_class.execute)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ('self', 'kwargs'):
                    continue
                    
                param_info = {
                    "type": "string",  # Default type
                    "description": f"Parameter: {param_name}"
                }
                
                # Extract type hints
                if param.annotation != inspect.Parameter.empty:
                    param_info.update(ToolIntrospector._convert_type_to_schema(param.annotation))
                
                # Check if parameter has default value
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
                else:
                    param_info["default"] = param.default
                    
                properties[param_name] = param_info
            
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract signature for {tool_class.__name__}: {e}")
            return {"type": "object", "properties": {}, "required": []}
    
    @staticmethod
    def _convert_type_to_schema(type_hint: Any) -> Dict[str, Any]:
        """Convert Python type hints to JSON schema types."""
        if hasattr(type_hint, '__origin__'):
            # Handle generic types (List, Dict, Optional, etc.)
            origin = type_hint.__origin__
            if origin is list or origin is List:
                return {"type": "array", "items": {"type": "string"}}
            elif origin is dict or origin is Dict:
                return {"type": "object"}
            elif origin is Union:
                # Handle Optional[Type] which is Union[Type, None]
                args = type_hint.__args__
                if len(args) == 2 and type(None) in args:
                    non_none_type = args[0] if args[1] is type(None) else args[1]
                    schema = ToolIntrospector._convert_type_to_schema(non_none_type)
                    schema["nullable"] = True
                    return schema
                return {"type": "string"}  # Fallback for complex unions
        
        # Handle basic types
        type_mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            list: {"type": "array", "items": {"type": "string"}},
            dict: {"type": "object"},
        }
        
        return type_mapping.get(type_hint, {"type": "string"})
    
    @staticmethod
    def extract_short_description(tool_class: Type[BaseTool]) -> str:
        """Extract or generate a concise description."""
        # Check for explicit short_description attribute
        if hasattr(tool_class, 'short_description'):
            return tool_class.short_description
            
        # Extract from docstring
        if tool_class.__doc__:
            lines = tool_class.__doc__.strip().split('\n')
            first_line = lines[0].strip()
            if first_line and len(first_line) < 100:
                return first_line
                
        # Extract from class description if available
        if hasattr(tool_class, 'description'):
            desc = tool_class.description
            if isinstance(desc, str) and len(desc) < 100:
                return desc
            elif isinstance(desc, str):
                # Take first sentence
                sentences = desc.split('.')
                if sentences and len(sentences[0]) < 100:
                    return sentences[0].strip() + '.'
        
        # Fallback to class name
        return f"Tool: {tool_class.__name__}"


class AutomaticToolDiscovery:
    """
    Advanced automatic tool discovery system.
    
    Scans the entire tool package hierarchy and generates complete tool definitions.
    """
    
    def __init__(self, cache_ttl: int = 300):
        """Initialize with caching support."""
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._cache_time = 0
        self.introspector = ToolIntrospector()
    
    @lru_cache(maxsize=1)
    def discover_all_tools(self, use_cache: bool = True) -> DiscoveryResult:
        """
        Discover all available tools with comprehensive metadata.
        
        Args:
            use_cache: Whether to use cached results
            
        Returns:
            Complete discovery result with all tool definitions
        """
        current_time = time.time()
        
        # Check cache
        if use_cache and self._cache and (current_time - self._cache_time) < self.cache_ttl:
            logger.debug("Using cached tool discovery results")
            return self._cache['result']
        
        start_time = time.time()
        tools = {}
        errors = []
        failed_loads = 0
        
        logger.info("Starting comprehensive tool discovery...")
        
        # Method 1: Discover through filesystem scanning
        filesystem_tools = self._discover_via_filesystem()
        tools.update(filesystem_tools)
        
        # Method 2: Discover through package introspection  
        package_tools, package_errors = self._discover_via_packages()
        tools.update(package_tools)
        errors.extend(package_errors)
        
        # Method 3: Fallback to simple loader for known tools
        try:
            from enterprise_ai.tool.simple_loader import get_all_tools
            simple_tools = get_all_tools()
            
            for name, tool_class in simple_tools.items():
                if name not in tools:
                    try:
                        definition = self._create_tool_definition(name, tool_class)
                        tools[name] = definition
                    except Exception as e:
                        failed_loads += 1
                        errors.append(f"Failed to create definition for {name}: {e}")
                        
        except Exception as e:
            errors.append(f"Simple loader fallback failed: {e}")
        
        discovery_time = time.time() - start_time
        successful_loads = len(tools)
        
        result = DiscoveryResult(
            tools=tools,
            total_discovered=successful_loads + failed_loads,
            successful_loads=successful_loads,
            failed_loads=failed_loads,
            discovery_time=discovery_time,
            errors=errors
        )
        
        # Update cache
        self._cache = {'result': result}
        self._cache_time = current_time
        
        logger.info(
            f"Tool discovery complete: {successful_loads} successful, "
            f"{failed_loads} failed, {discovery_time:.2f}s"
        )
        
        return result
    
    def _discover_via_filesystem(self) -> Dict[str, ToolDefinition]:
        """Discover tools by scanning the filesystem."""
        tools = {}
        
        try:
            import enterprise_ai.tool
            tool_package_path = Path(enterprise_ai.tool.__file__).parent
            
            # Scan all Python files in tool package
            for py_file in tool_package_path.rglob("*.py"):
                if py_file.name.startswith("__") or py_file.name.startswith("test_"):
                    continue
                    
                # Convert path to module name
                relative_path = py_file.relative_to(tool_package_path.parent)
                module_parts = relative_path.with_suffix("").parts
                module_name = ".".join(module_parts)
                
                try:
                    module = importlib.import_module(module_name)
                    
                    # Find BaseTool subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (inspect.isclass(attr) and 
                            issubclass(attr, BaseTool) and 
                            attr != BaseTool):
                            
                            tool_name = self._generate_tool_name(attr)
                            if tool_name not in tools:
                                definition = self._create_tool_definition(tool_name, attr)
                                tools[tool_name] = definition
                                
                except Exception as e:
                    logger.debug(f"Failed to scan {module_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Filesystem discovery failed: {e}")
            
        return tools
    
    def _discover_via_packages(self) -> Tuple[Dict[str, ToolDefinition], List[str]]:
        """Discover tools through package introspection."""
        tools = {}
        errors = []
        
        try:
            import enterprise_ai.tool
            
            # Walk through all subpackages
            for importer, modname, ispkg in pkgutil.walk_packages(
                enterprise_ai.tool.__path__, 
                enterprise_ai.tool.__name__ + "."
            ):
                if "test" in modname or "__pycache__" in modname:
                    continue
                    
                try:
                    module = importlib.import_module(modname)
                    
                    # Find tool classes
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (inspect.isclass(attr) and 
                            issubclass(attr, BaseTool) and 
                            attr != BaseTool):
                            
                            tool_name = self._generate_tool_name(attr)
                            if tool_name not in tools:
                                definition = self._create_tool_definition(tool_name, attr)
                                tools[tool_name] = definition
                                
                except Exception as e:
                    errors.append(f"Failed to load module {modname}: {e}")
                    
        except Exception as e:
            errors.append(f"Package discovery failed: {e}")
            
        return tools, errors
    
    def _generate_tool_name(self, tool_class: Type[BaseTool]) -> str:
        """Generate a consistent tool name from class."""
        # Check if tool has explicit name
        if hasattr(tool_class, 'name') and tool_class.name:
            return tool_class.name
            
        # Convert class name to snake_case
        class_name = tool_class.__name__
        
        # Remove common suffixes
        for suffix in ['Tool', 'Execute', 'Manager']:
            if class_name.endswith(suffix):
                class_name = class_name[:-len(suffix)]
                break
        
        # Convert CamelCase to snake_case
        result = []
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                result.append('_')
            result.append(char.lower())
            
        return ''.join(result)
    
    def _create_tool_definition(self, name: str, tool_class: Type[BaseTool]) -> ToolDefinition:
        """Create a complete tool definition from a tool class."""
        try:
            # Create temporary instance to access properties
            temp_instance = tool_class()
            
            # Extract comprehensive metadata
            return ToolDefinition(
                name=name,
                description=temp_instance.description or f"Tool: {tool_class.__name__}",
                parameters=self._get_tool_parameters(temp_instance, tool_class),
                function_signature=self.introspector.extract_function_signature(tool_class),
                capabilities={str(cap) for cap in temp_instance.capabilities},
                version=temp_instance.version,
                class_path=f"{tool_class.__module__}.{tool_class.__name__}",
                module_path=tool_class.__module__,
                dependencies=temp_instance.dependencies,
                examples=temp_instance.usage_examples,
                danger_level=temp_instance.config.danger_level,
                requires_approval=temp_instance.config.requires_approval,
                short_description=self.introspector.extract_short_description(tool_class)
            )
            
        except Exception as e:
            logger.error(f"Failed to create definition for {name}: {e}")
            # Return minimal definition
            return ToolDefinition(
                name=name,
                description=f"Tool: {tool_class.__name__}",
                parameters={"type": "object", "properties": {}, "required": []},
                function_signature={"type": "object", "properties": {}, "required": []},
                capabilities=set(),
                version="1.0.0",
                class_path=f"{tool_class.__module__}.{tool_class.__name__}",
                module_path=tool_class.__module__,
                dependencies=[],
                examples=[],
                danger_level=0,
                requires_approval=False,
                short_description=f"Tool: {tool_class.__name__}"
            )
    
    def _get_tool_parameters(self, instance: BaseTool, tool_class: Type[BaseTool]) -> Dict[str, Any]:
        """Get tool parameters from instance or generate from signature."""
        # Use explicit parameters if available
        if instance.parameters:
            return instance.parameters
            
        # Generate from function signature
        return self.introspector.extract_function_signature(tool_class)
    
    def get_tool_definitions_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in the format expected by LLM providers.
        
        Returns:
            List of tool definitions compatible with OpenAI/Anthropic function calling
        """
        result = self.discover_all_tools()
        definitions = []
        
        for tool_name, tool_def in result.tools.items():
            definition = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_def.short_description,
                    "parameters": tool_def.parameters
                }
            }
            definitions.append(definition)
            
        return definitions
    
    def get_tool_by_name(self, name: str) -> Optional[ToolDefinition]:
        """Get a specific tool definition by name."""
        result = self.discover_all_tools()
        return result.tools.get(name)
    
    def get_tools_by_capability(self, capability: Union[str, ToolCapability]) -> List[ToolDefinition]:
        """Get all tools that have a specific capability."""
        result = self.discover_all_tools()
        capability_str = str(capability)
        
        return [
            tool_def for tool_def in result.tools.values()
            if capability_str in tool_def.capabilities
        ]
    
    def clear_cache(self) -> None:
        """Clear the discovery cache."""
        self._cache.clear()
        self._cache_time = 0
        # Clear the lru_cache as well
        self.discover_all_tools.cache_clear()


# Singleton instance for global use
_discovery_instance = None

def get_tool_discovery() -> AutomaticToolDiscovery:
    """Get the global tool discovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = AutomaticToolDiscovery()
    return _discovery_instance


# Convenience functions
def discover_tools() -> DiscoveryResult:
    """Convenience function to discover all tools."""
    return get_tool_discovery().discover_all_tools()


def get_llm_tool_definitions() -> List[Dict[str, Any]]:
    """Convenience function to get LLM-compatible tool definitions."""
    return get_tool_discovery().get_tool_definitions_for_llm()


def get_tool_definition(name: str) -> Optional[ToolDefinition]:
    """Convenience function to get a specific tool definition."""
    return get_tool_discovery().get_tool_by_name(name)

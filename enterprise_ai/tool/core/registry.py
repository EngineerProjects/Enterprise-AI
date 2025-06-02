"""
Registry system for Enterprise AI tools.

This module provides a registry for discovering and instantiating tools,
with enhanced capabilities for tool management and discovery.
"""

from typing import Any, Callable, Dict, List, Optional, Set, Type, Tuple, Union
from enum import Enum
import re
import semver
import warnings

from enterprise_ai.logger import get_logger

# This will be imported by annotation only to avoid circular imports
from enterprise_ai.tool.core.base import BaseTool, ToolCapability, ToolConfig

logger = get_logger("tool.registry")


class ToolRegistry:
    """Registry for Enterprise AI tools."""

    _instance = None
    _tools: Dict[str, Type["BaseTool"]] = {}
    _categories: Dict[str, Set[str]] = {}
    _capabilities: Dict[str, Set[str]] = {}
    _versions: Dict[str, Dict[str, Type["BaseTool"]]] = {}
    _initialized: bool = False
    _hooks: Dict[str, List[Callable]] = {
        "pre_register": [],
        "post_register": [],
        "pre_create": [],
        "post_create": [],
    }

    def __new__(cls) -> "ToolRegistry":
        """Create a singleton instance of ToolRegistry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._tools = {}
            self._categories = {}
            self._capabilities = {}
            self._versions = {}
            self._initialized = True

    def add_hook(self, hook_type: str, callback: Callable) -> None:
        """
        Add a hook to the registry.

        Args:
            hook_type: Type of hook ('pre_register', 'post_register', 'pre_create', 'post_create')
            callback: Callback function to be called
        """
        if hook_type not in self._hooks:
            raise ValueError(f"Unknown hook type: {hook_type}")
        self._hooks[hook_type].append(callback)

    def remove_hook(self, hook_type: str, callback: Callable) -> None:
        """
        Remove a hook from the registry.

        Args:
            hook_type: Type of hook
            callback: Callback function to be removed
        """
        if hook_type in self._hooks and callback in self._hooks[hook_type]:
            self._hooks[hook_type].remove(callback)

    def _run_hooks(self, hook_type: str, *args: Any, **kwargs: Any) -> None:
        """Run all hooks of a specified type."""
        for hook in self._hooks.get(hook_type, []):
            try:
                hook(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {hook_type} hook: {str(e)}")

    def register(
        self,
        tool_cls: Type["BaseTool"],
        category: Optional[str] = None,
        capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        version: Optional[str] = None,
    ) -> Type["BaseTool"]:
        """
        Register a tool class with the registry.

        Args:
            tool_cls: The tool class to register
            category: Optional category to classify the tool
            capabilities: Optional list of capabilities the tool provides
            version: Optional version of the tool (defaults to tool_cls.version)

        Returns:
            The registered tool class
        """
        # Run pre-register hooks
        self._run_hooks("pre_register", tool_cls, category, capabilities, version)

        # Get tool info with better fallback handling
        name = getattr(tool_cls, "name", tool_cls.__name__)
        
        # Get description from class definition with multiple fallbacks
        description = ""
        if hasattr(tool_cls, "description"):
            desc_attr = getattr(tool_cls, "description")
            if desc_attr and isinstance(desc_attr, str):
                description = desc_attr.strip()
        
        # If still no description, try docstring
        if not description and tool_cls.__doc__:
            # Use first line of docstring as description
            doc_lines = tool_cls.__doc__.strip().split('\n')
            if doc_lines:
                description = doc_lines[0].strip()
        
        # Final fallback
        if not description:
            logger.warning(f"Tool '{name}' has no description. Tools without descriptions may not be usable by agents.")
            description = f"Tool: {name} (no description available)"

        # Store the description back on the class for consistency
        if not hasattr(tool_cls, "description") or not getattr(tool_cls, "description"):
            tool_cls.description = description
            
        # Get version from the class if not provided
        if version is None:
            version = getattr(tool_cls, "version", "1.0.0")

        # Track versions
        if name not in self._versions:
            self._versions[name] = {}

        # Check if this version already exists
        if version in self._versions[name]:
            existing_cls = self._versions[name][version]
            if existing_cls != tool_cls:
                warnings.warn(f"Tool {name} v{version} is already registered. Overwriting.")

        self._versions[name][version] = tool_cls

        # Always register latest version in the main tools dict
        if name in self._tools:
            existing_version = getattr(self._tools[name], "version", "1.0.0")
            if semver.compare(version, existing_version) > 0:
                # New version is higher, replace in main registry
                self._tools[name] = tool_cls
                logger.debug(f"Upgraded tool '{name}' to version {version}")
            else:
                # Keep existing version in main registry, but still register this version
                logger.debug(f"Registered alternate version {version} of tool '{name}'")
        else:
            # First registration of this tool
            self._tools[name] = tool_cls
            logger.debug(f"Registered tool '{name}' version {version}")

        # Register category
        if category:
            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(name)
            logger.debug(f"Registered tool '{name}' in category '{category}'")

        # Register capabilities
        tool_capabilities: Set[str] = set()
        if capabilities:
            tool_capabilities.update(
                cap.value if isinstance(cap, ToolCapability) else cap for cap in capabilities
            )

        # Also get capabilities from the class if available
        class_capabilities: Set[Union[str, ToolCapability]] = getattr(
            tool_cls, "capabilities", set()
        )
        if class_capabilities:
            tool_capabilities.update(
                cap.value if isinstance(cap, ToolCapability) else cap for cap in class_capabilities
            )

        # Register each capability
        for capability in tool_capabilities:
            if capability not in self._capabilities:
                self._capabilities[capability] = set()
            self._capabilities[capability].add(name)
            logger.debug(f"Registered capability '{capability}' for tool '{name}'")

        # Run post-register hooks
        self._run_hooks("post_register", tool_cls, name, category, capabilities, version)

        return tool_cls

    def get_tool_class(
        self, name: str, version: Optional[str] = None
    ) -> Optional[Type["BaseTool"]]:
        """
        Get a tool class by name and optional version.

        Args:
            name: Name of the tool
            version: Optional specific version to retrieve

        Returns:
            Tool class or None if not found
        """
        if version is None:
            return self._tools.get(name)
        else:
            return self._versions.get(name, {}).get(version)

    def get_all_versions(self, name: str) -> List[str]:
        """
        Get all available versions of a tool.

        Args:
            name: Name of the tool

        Returns:
            List of version strings, sorted by semantic versioning rules
        """
        versions = list(self._versions.get(name, {}).keys())
        return sorted(versions, key=lambda v: semver.VersionInfo.parse(v))

    async def create_tool(
        self,
        name: str,
        version: Optional[str] = None,
        config: Optional[ToolConfig] = None,
        initialize: bool = True,
        **kwargs: Any,
    ) -> Optional["BaseTool"]:
        """
        Create and optionally initialize a tool instance by name.

        Args:
            name: Name of the tool to create
            version: Optional specific version to instantiate
            config: Optional configuration for the tool
            initialize: Whether to call initialize() on the tool
            **kwargs: Additional parameters for tool initialization

        Returns:
            Initialized tool instance or None if creation failed
        """
        # Run pre-create hooks
        self._run_hooks("pre_create", name, version, config, kwargs)

        tool_cls = self.get_tool_class(name, version)
        if not tool_cls:
            logger.error(
                f"Tool class not found: {name}" + (f" version {version}" if version else "")
            )
            return None

        try:
            # Prepare initialization parameters
            init_kwargs = kwargs.copy()
            if config:
                init_kwargs["config"] = config

            # Create instance
            tool_instance = tool_cls(**init_kwargs)

            # Initialize if required and requested
            if initialize and getattr(tool_instance, "requires_initialization", False):
                success = await tool_instance.initialize(**kwargs)
                if not success:
                    logger.error(f"Failed to initialize tool: {name}")
                    return None

            # Run post-create hooks
            self._run_hooks("post_create", tool_instance)

            return tool_instance
        except Exception as e:
            logger.error(f"Error creating tool {name}: {str(e)}")
            return None

    def get_tools_by_category(self, category: str) -> List[Type["BaseTool"]]:
        """Get all tool classes in a category."""
        tool_names = self._categories.get(category, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_tools_by_capability(
        self, capability: Union[str, ToolCapability]
    ) -> List[Type["BaseTool"]]:
        """
        Get all tool classes with a specific capability.

        Args:
            capability: Capability to search for (string or ToolCapability enum)

        Returns:
            List of tool classes with the specified capability
        """
        if isinstance(capability, ToolCapability):
            capability = capability.value

        tool_names = self._capabilities.get(capability, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def search_tools(
        self,
        query: str = "",
        categories: Optional[List[str]] = None,
        capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        match_all_capabilities: bool = False,
    ) -> List[Type["BaseTool"]]:
        """
        Search for tools based on multiple criteria.

        Args:
            query: Text to search in tool names and descriptions
            categories: Optional list of categories to filter by
            capabilities: Optional list of capabilities to filter by
            match_all_capabilities: If True, tools must have all capabilities
                                  If False, tools must have at least one capability

        Returns:
            List of tool classes matching the criteria
        """
        result_set = set(self._tools.values())

        # Filter by query if provided
        if query:
            query_regex = re.compile(query, re.IGNORECASE)
            query_matches = set()

            for name, tool_cls in self._tools.items():
                if query_regex.search(name):
                    query_matches.add(tool_cls)
                    continue

                description = getattr(tool_cls, "description", "")
                if description and query_regex.search(description):
                    query_matches.add(tool_cls)

            result_set = result_set.intersection(query_matches)

        # Filter by categories if provided
        if categories:
            category_tools: Set[Type["BaseTool"]] = set()
            for category in categories:
                category_tool_names = self._categories.get(category, set())
                category_tools.update(
                    self._tools[name] for name in category_tool_names if name in self._tools
                )
            result_set = result_set.intersection(category_tools)

        # Filter by capabilities if provided
        if capabilities:
            cap_values = [
                cap.value if isinstance(cap, ToolCapability) else cap for cap in capabilities
            ]

            if match_all_capabilities:
                # Must have all capabilities
                for capability in cap_values:
                    capability_tool_names = self._capabilities.get(capability, set())
                    capability_tools = {
                        self._tools[name] for name in capability_tool_names if name in self._tools
                    }
                    result_set = result_set.intersection(capability_tools)
            else:
                # Must have at least one capability
                capability_tools = set()
                for capability in cap_values:
                    capability_tool_names = self._capabilities.get(capability, set())
                    capability_tools.update(
                        self._tools[name] for name in capability_tool_names if name in self._tools
                    )
                result_set = result_set.intersection(capability_tools)

        return list(result_set)

    def get_all_tool_classes(self) -> Dict[str, Type["BaseTool"]]:
        """Get all registered tool classes."""
        return self._tools.copy()

    def get_all_category_names(self) -> List[str]:
        """Get all registered category names."""
        return list(self._categories.keys())

    def get_all_capability_names(self) -> List[str]:
        """Get all registered capability names."""
        # Make sure capabilities are properly counted
        capabilities = set()
        
        # Collect capabilities from all registered tools
        for tool_cls in self._tools.values():
            tool_capabilities = getattr(tool_cls, "capabilities", set())
            for cap in tool_capabilities:
                if isinstance(cap, ToolCapability):
                    capabilities.add(cap.value)
                else:
                    capabilities.add(str(cap))
        
        return list(capabilities)

    def get_tool_info(self, name: str) -> Dict[str, Any]:
        """
        Get detailed information about a registered tool.

        Args:
            name: Name of the tool

        Returns:
            Dictionary with tool information or empty dict if not found
        """
        tool_cls = self.get_tool_class(name)
        if not tool_cls:
            return {}

        # Get all versions
        versions = self.get_all_versions(name)
        latest_version = versions[-1] if versions else None

        # Get categories
        categories = [category for category, tools in self._categories.items() if name in tools]

        # Get capabilities
        capabilities = [
            capability for capability, tools in self._capabilities.items() if name in tools
        ]

        return {
            "name": name,
            "description": getattr(tool_cls, "description", ""),
            "versions": versions,
            "latest_version": latest_version,
            "categories": categories,
            "capabilities": capabilities,
            "parameters": getattr(tool_cls, "parameters", {}),
            "requires_initialization": getattr(tool_cls, "requires_initialization", False),
            "dependencies": getattr(tool_cls, "dependencies", []),
            "authorization_required": getattr(tool_cls, "authorization_required", False),
        }


# Singleton registry instance
_registry = ToolRegistry()


def register_tool(
    category: Optional[str] = None,
    capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    version: Optional[str] = None,
) -> Callable[[Type["BaseTool"]], Type["BaseTool"]]:
    """
    Decorator to register a tool class with the registry.

    Args:
        category: Optional category to classify the tool
        capabilities: Optional list of capabilities the tool provides
        version: Optional version of the tool

    Returns:
        A decorator function that registers the tool
    """

    def decorator(cls: Type["BaseTool"]) -> Type["BaseTool"]:
        return _registry.register(cls, category, capabilities, version)

    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _registry


def search_tools(
    query: str = "",
    categories: Optional[List[str]] = None,
    capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    match_all_capabilities: bool = False,
) -> List[Type["BaseTool"]]:
    """
    Search for tools based on multiple criteria.

    Args:
        query: Text to search in tool names and descriptions
        categories: Optional list of categories to filter by
        capabilities: Optional list of capabilities to filter by
        match_all_capabilities: If True, tools must have all capabilities

    Returns:
        List of tool classes matching the criteria
    """
    return get_registry().search_tools(query, categories, capabilities, match_all_capabilities)


async def create_tool(
    name: str,
    version: Optional[str] = None,
    config: Optional[ToolConfig] = None,
    initialize: bool = True,
    **kwargs: Any,
) -> Optional["BaseTool"]:
    """
    Create and optionally initialize a tool instance by name.

    Args:
        name: Name of the tool to create
        version: Optional specific version to instantiate
        config: Optional configuration for the tool
        initialize: Whether to call initialize() on the tool
        **kwargs: Additional parameters for tool initialization

    Returns:
        Initialized tool instance or None if creation failed
    """
    return await get_registry().create_tool(name, version, config, initialize, **kwargs)

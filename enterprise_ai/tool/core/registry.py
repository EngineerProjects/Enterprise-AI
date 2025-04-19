"""
Registry system for Enterprise AI tools.

This module provides a registry for discovering and instantiating tools.
"""

from typing import Any, Callable, Dict, List, Optional, Type, Set

from enterprise_ai.logger import get_logger

# This will be imported by annotation only to avoid circular imports
from enterprise_ai.tool.core.base import BaseTool

logger = get_logger("tool.registry")


class ToolRegistry:
    """Registry for Enterprise AI tools."""

    _instance = None
    _tools: Dict[str, Type["BaseTool"]] = {}
    _categories: Dict[str, Set[str]] = {}
    _initialized: bool = False

    def __new__(cls) -> "ToolRegistry":
        """Create a singleton instance of ToolRegistry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._tools = {}
            self._categories = {}
            self._initialized = True

    def register(
        self, tool_cls: Type["BaseTool"], category: Optional[str] = None
    ) -> Type["BaseTool"]:
        """
        Register a tool class with the registry.

        Args:
            tool_cls: The tool class to register
            category: Optional category to classify the tool

        Returns:
            The registered tool class
        """
        name = getattr(tool_cls, "name", tool_cls.__name__)
        self._tools[name] = tool_cls

        if category:
            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(name)
            logger.debug(f"Registered tool '{name}' in category '{category}'")
        else:
            logger.debug(f"Registered tool '{name}' without category")

        return tool_cls

    def get_tool_class(self, name: str) -> Optional[Type["BaseTool"]]:
        """Get a tool class by name."""
        return self._tools.get(name)

    def create_tool(self, name: str, **kwargs: Any) -> Optional["BaseTool"]:
        """Create a tool instance by name."""
        tool_cls = self.get_tool_class(name)
        if tool_cls:
            return tool_cls(**kwargs)
        return None

    def get_tools_by_category(self, category: str) -> List[Type["BaseTool"]]:
        """Get all tool classes in a category."""
        tool_names = self._categories.get(category, set())
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_all_tool_classes(self) -> Dict[str, Type["BaseTool"]]:
        """Get all registered tool classes."""
        return self._tools.copy()

    def get_all_category_names(self) -> List[str]:
        """Get all registered category names."""
        return list(self._categories.keys())


# Singleton registry instance
_registry = ToolRegistry()


def register_tool(category: Optional[str] = None) -> Callable[[Type["BaseTool"]], Type["BaseTool"]]:
    """
    Decorator to register a tool class with the registry.

    Args:
        category: Optional category to classify the tool

    Returns:
        A decorator function that registers the tool
    """

    def decorator(cls: Type["BaseTool"]) -> Type["BaseTool"]:
        return _registry.register(cls, category)

    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _registry

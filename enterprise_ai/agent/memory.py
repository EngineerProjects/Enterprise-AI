"""
Agent memory implementations for Enterprise AI.

This module provides implementations of the AgentMemory protocol
defined in types.py, allowing agents to store and retrieve information.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Generic, TypeVar

from enterprise_ai.agent.types import AgentMemory
from enterprise_ai.logger import get_logger

logger = get_logger("agent.memory")

T = TypeVar("T")


class DictMemory(AgentMemory):
    """Dictionary-based implementation of agent memory.

    This implementation stores data in a simple key-value dictionary.
    It provides basic memory functionality with optional persistence.
    """

    def __init__(self) -> None:
        """Initialize a new dictionary-based memory."""
        self._store: Dict[str, Any] = {}

    def add(self, key: str, value: Any) -> None:
        """Add an item to memory.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        self._store[key] = value
        logger.debug(f"Added memory: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item from memory.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default if not found
        """
        value = self._store.get(key, default)
        logger.debug(f"Retrieved memory: {key}")
        return value

    def forget(self, key: str) -> None:
        """Remove an item from memory.

        Args:
            key: The key to remove
        """
        if key in self._store:
            del self._store[key]
            logger.debug(f"Removed memory: {key}")

    def clear(self) -> None:
        """Clear all memory."""
        self._store.clear()
        logger.debug("Cleared all memory")

    def get_all(self) -> Dict[str, Any]:
        """Get all stored memory items.

        Returns:
            Dictionary of all memory items
        """
        return self._store.copy()

    def contains(self, key: str) -> bool:
        """Check if memory contains a key.

        Args:
            key: The key to check

        Returns:
            True if the key exists, False otherwise
        """
        return key in self._store

    def keys(self) -> Set[str]:
        """Get all keys in memory.

        Returns:
            Set of all keys
        """
        return set(self._store.keys())


class NamespacedMemory(AgentMemory):
    """Namespaced memory implementation.

    This implementation organizes memory into namespaces, allowing for
    better organization of memory items by category.
    """

    def __init__(self) -> None:
        """Initialize a new namespaced memory."""
        self._spaces: Dict[str, Dict[str, Any]] = {}
        self._default_space = "default"

    def _ensure_namespace(self, namespace: str) -> None:
        """Ensure a namespace exists.

        Args:
            namespace: Namespace to ensure
        """
        if namespace not in self._spaces:
            self._spaces[namespace] = {}

    def add(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """Add an item to memory.

        Args:
            key: The key to store the value under
            value: The value to store
            namespace: Optional namespace (uses default if None)
        """
        ns = namespace or self._default_space
        self._ensure_namespace(ns)
        self._spaces[ns][key] = value
        logger.debug(f"Added memory: {ns}.{key}")

    def get(self, key: str, default: Any = None, namespace: Optional[str] = None) -> Any:
        """Get an item from memory.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            namespace: Optional namespace (searches default if None)

        Returns:
            The stored value or default if not found
        """
        ns = namespace or self._default_space
        if ns not in self._spaces or key not in self._spaces[ns]:
            return default
        value = self._spaces[ns].get(key, default)
        logger.debug(f"Retrieved memory: {ns}.{key}")
        return value

    def forget(self, key: str, namespace: Optional[str] = None) -> None:
        """Remove an item from memory.

        Args:
            key: The key to remove
            namespace: Optional namespace (uses default if None)
        """
        ns = namespace or self._default_space
        if ns in self._spaces and key in self._spaces[ns]:
            del self._spaces[ns][key]
            logger.debug(f"Removed memory: {ns}.{key}")

    def clear(self, namespace: Optional[str] = None) -> None:
        """Clear all memory or a specific namespace.

        Args:
            namespace: Optional namespace to clear (clears all if None)
        """
        if namespace:
            if namespace in self._spaces:
                self._spaces[namespace].clear()
                logger.debug(f"Cleared namespace: {namespace}")
        else:
            self._spaces.clear()
            # Restore the default namespace
            self._spaces[self._default_space] = {}
            logger.debug("Cleared all memory")

    def get_namespace(self, namespace: str) -> Dict[str, Any]:
        """Get all items in a namespace.

        Args:
            namespace: Namespace to retrieve

        Returns:
            Dictionary of all items in the namespace or empty dict if not found
        """
        return self._spaces.get(namespace, {}).copy()

    def list_namespaces(self) -> List[str]:
        """Get all namespace names.

        Returns:
            List of all namespace names
        """
        return list(self._spaces.keys())


class ScopedMemory(AgentMemory):
    """Scoped memory with automatic cleanup for temporary data.

    This implementation provides scoped memory that automatically manages
    the lifecycle of temporary data, similar to stack frames in programming.
    """

    def __init__(self) -> None:
        """Initialize a new scoped memory."""
        self._global: Dict[str, Any] = {}
        self._scopes: List[Dict[str, Any]] = [{}]  # Start with one scope

    def add(self, key: str, value: Any, global_scope: bool = False) -> None:
        """Add an item to memory.

        Args:
            key: The key to store the value under
            value: The value to store
            global_scope: Whether to store in global scope
        """
        if global_scope:
            self._global[key] = value
            logger.debug(f"Added global memory: {key}")
        else:
            self._scopes[-1][key] = value
            logger.debug(f"Added scoped memory: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item from memory.

        Searches from current scope up to global scope.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default if not found
        """
        # Search in current scope first, then in outer scopes,
        # and finally in global scope
        for scope in reversed(self._scopes):
            if key in scope:
                return scope[key]

        # If not found in any scope, check global
        return self._global.get(key, default)

    def forget(self, key: str, global_scope: bool = False) -> None:
        """Remove an item from memory.

        Args:
            key: The key to remove
            global_scope: Whether to remove from global scope
        """
        if global_scope:
            if key in self._global:
                del self._global[key]
                logger.debug(f"Removed global memory: {key}")
        else:
            if key in self._scopes[-1]:
                del self._scopes[-1][key]
                logger.debug(f"Removed scoped memory: {key}")

    def clear(self, global_scope: bool = False) -> None:
        """Clear memory.

        Args:
            global_scope: Whether to clear global scope or just current scope
        """
        if global_scope:
            self._global.clear()
            self._scopes = [{}]
            logger.debug("Cleared all memory")
        else:
            self._scopes[-1].clear()
            logger.debug("Cleared current scope")

    def push_scope(self) -> None:
        """Push a new scope onto the stack."""
        self._scopes.append({})
        logger.debug("Pushed new memory scope")

    def pop_scope(self) -> Dict[str, Any]:
        """Pop the current scope from the stack.

        Returns:
            The popped scope

        Raises:
            RuntimeError: If attempting to pop the last scope
        """
        if len(self._scopes) <= 1:
            raise RuntimeError("Cannot pop the last memory scope")

        popped = self._scopes.pop()
        logger.debug("Popped memory scope")
        return popped


# Factory function to create memory implementations
def create_memory(memory_type: str = "dict") -> AgentMemory:
    """Create a memory implementation by type.

    Args:
        memory_type: Type of memory to create ("dict", "namespaced", or "scoped")

    Returns:
        AgentMemory implementation

    Raises:
        ValueError: If an unknown memory type is specified
    """
    if memory_type == "dict":
        return DictMemory()
    elif memory_type == "namespaced":
        return NamespacedMemory()
    elif memory_type == "scoped":
        return ScopedMemory()
    else:
        raise ValueError(f"Unknown memory type: {memory_type}")

"""
Agent memory implementations for Enterprise AI.

This module provides implementations of the AgentMemory protocol
defined in types.py, allowing agents to store and retrieve information.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Generic, TypeVar, Union, cast
import uuid

from enterprise_ai.agent.core.types import AgentMemory
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.result import ToolResult, ToolFailure

logger = get_logger("agent.memory")

T = TypeVar("T")


class DictMemory(AgentMemory):
    """Dictionary-based implementation of agent memory.

    This implementation stores data in a simple key-value dictionary.
    It provides basic memory functionality with optional persistence.
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        """Initialize a new dictionary-based memory.
        
        Args:
            persist_path: Optional path to persist memory
        """
        self._store: Dict[str, Any] = {}
        self._persist_path = persist_path
        self._last_saved: Optional[datetime] = None
        
        # Load from persist path if available
        if self._persist_path and os.path.exists(self._persist_path):
            try:
                self.load()
            except Exception as e:
                logger.warning(f"Failed to load memory from {self._persist_path}: {e}")

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
        
    def save(self) -> bool:
        """Save memory to disk if persist_path is set.
        
        Returns:
            True if saved successfully or no persist_path, False otherwise
        """
        if not self._persist_path:
            return True
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            
            # Prepare data for serialization
            serialized_data = {}
            for key, value in self._store.items():
                try:
                    # Check if value has to_dict method
                    if hasattr(value, 'to_dict') and callable(getattr(value, 'to_dict')):
                        serialized_data[key] = {
                            'value': value.to_dict(),
                            'type': type(value).__name__
                        }
                    else:
                        # Store primitive types directly
                        serialized_data[key] = {
                            'value': value,
                            'type': type(value).__name__
                        }
                except Exception as e:
                    logger.warning(f"Failed to serialize {key}: {e}")
                    # Skip this value
                    continue
                
            # Write to file
            with open(self._persist_path, 'w') as f:
                json.dump(serialized_data, f)
                
            self._last_saved = datetime.now()
            logger.debug(f"Memory saved to {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory to {self._persist_path}: {e}")
            return False
            
    def load(self) -> bool:
        """Load memory from disk if persist_path is set.
        
        Returns:
            True if loaded successfully or no persist_path, False otherwise
        """
        if not self._persist_path or not os.path.exists(self._persist_path):
            return False
            
        try:
            with open(self._persist_path, 'r') as f:
                serialized_data = json.load(f)
                
            # Clear current memory
            self._store.clear()
            
            # Load data
            for key, data in serialized_data.items():
                value = data.get('value')
                # Note: We're not reconstructing custom types here,
                # just loading what was serialized
                self._store[key] = value
                
            logger.debug(f"Memory loaded from {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load memory from {self._persist_path}: {e}")
            return False
            
    async def add_async(self, key: str, value: Any) -> None:
        """Add an item to memory asynchronously.
        
        Args:
            key: The key to store the value under
            value: The value to store
        """
        # This is a simple wrapper - in a real implementation, 
        # you might want to use an async storage backend
        self.add(key, value)
        
    async def get_async(self, key: str, default: Any = None) -> Any:
        """Get an item from memory asynchronously.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The stored value or default if not found
        """
        # This is a simple wrapper - in a real implementation,
        # you might want to use an async storage backend
        return self.get(key, default)
        
    async def save_async(self) -> bool:
        """Save memory to disk asynchronously if persist_path is set.
        
        Returns:
            True if saved successfully or no persist_path, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save)
        
    async def load_async(self) -> bool:
        """Load memory from disk asynchronously if persist_path is set.
        
        Returns:
            True if loaded successfully or no persist_path, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load)


class NamespacedMemory(AgentMemory):
    """Namespaced memory implementation.

    This implementation organizes memory into namespaces, allowing for
    better organization of memory items by category.
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        """Initialize a new namespaced memory.
        
        Args:
            persist_path: Optional path to persist memory
        """
        self._spaces: Dict[str, Dict[str, Any]] = {}
        self._default_space = "default"
        self._persist_path = persist_path
        self._last_saved: Optional[datetime] = None
        
        # Initialize default space
        self._spaces[self._default_space] = {}
        
        # Load from persist path if available
        if self._persist_path and os.path.exists(self._persist_path):
            try:
                self.load()
            except Exception as e:
                logger.warning(f"Failed to load memory from {self._persist_path}: {e}")

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
        
    def contains(self, key: str, namespace: Optional[str] = None) -> bool:
        """Check if memory contains a key.

        Args:
            key: The key to check
            namespace: Optional namespace (uses default if None)

        Returns:
            True if the key exists, False otherwise
        """
        ns = namespace or self._default_space
        return ns in self._spaces and key in self._spaces[ns]
        
    def keys(self, namespace: Optional[str] = None) -> Set[str]:
        """Get all keys in memory or in a namespace.

        Args:
            namespace: Optional namespace (gets keys in all spaces if None)

        Returns:
            Set of all keys
        """
        if namespace:
            return set(self._spaces.get(namespace, {}).keys())
        
        # Collect keys from all namespaces
        all_keys = set()
        for space in self._spaces.values():
            all_keys.update(space.keys())
        return all_keys
        
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all stored memory items grouped by namespace.

        Returns:
            Dictionary of all memory items by namespace
        """
        return {ns: data.copy() for ns, data in self._spaces.items()}
        
    def save(self) -> bool:
        """Save memory to disk if persist_path is set.
        
        Returns:
            True if saved successfully or no persist_path, False otherwise
        """
        if not self._persist_path:
            return True
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            
            # Prepare data for serialization
            serialized_data = {}
            for namespace, space in self._spaces.items():
                serialized_data[namespace] = {}
                for key, value in space.items():
                    try:
                        # Check if value has to_dict method
                        if hasattr(value, 'to_dict') and callable(getattr(value, 'to_dict')):
                            serialized_data[namespace][key] = {
                                'value': value.to_dict(),
                                'type': type(value).__name__
                            }
                        else:
                            # Store primitive types directly
                            serialized_data[namespace][key] = {
                                'value': value,
                                'type': type(value).__name__
                            }
                    except Exception as e:
                        logger.warning(f"Failed to serialize {namespace}.{key}: {e}")
                        # Skip this value
                        continue
                
            # Write to file
            with open(self._persist_path, 'w') as f:
                json.dump(serialized_data, f)
                
            self._last_saved = datetime.now()
            logger.debug(f"Memory saved to {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save memory to {self._persist_path}: {e}")
            return False
            
    def load(self) -> bool:
        """Load memory from disk if persist_path is set.
        
        Returns:
            True if loaded successfully or no persist_path, False otherwise
        """
        if not self._persist_path or not os.path.exists(self._persist_path):
            return False
            
        try:
            with open(self._persist_path, 'r') as f:
                serialized_data = json.load(f)
                
            # Clear current memory
            self._spaces.clear()
            
            # Load data
            for namespace, space_data in serialized_data.items():
                self._spaces[namespace] = {}
                for key, data in space_data.items():
                    value = data.get('value')
                    # Note: We're not reconstructing custom types here,
                    # just loading what was serialized
                    self._spaces[namespace][key] = value
                
            # Ensure default namespace exists
            if self._default_space not in self._spaces:
                self._spaces[self._default_space] = {}
                
            logger.debug(f"Memory loaded from {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load memory from {self._persist_path}: {e}")
            return False
            
    async def add_async(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        """Add an item to memory asynchronously.
        
        Args:
            key: The key to store the value under
            value: The value to store
            namespace: Optional namespace (uses default if None)
        """
        # This is a simple wrapper for now
        self.add(key, value, namespace)
        
    async def get_async(self, key: str, default: Any = None, namespace: Optional[str] = None) -> Any:
        """Get an item from memory asynchronously.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            namespace: Optional namespace (searches default if None)
            
        Returns:
            The stored value or default if not found
        """
        return self.get(key, default, namespace)
        
    async def save_async(self) -> bool:
        """Save memory to disk asynchronously if persist_path is set.
        
        Returns:
            True if saved successfully or no persist_path, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save)
        
    async def load_async(self) -> bool:
        """Load memory from disk asynchronously if persist_path is set.
        
        Returns:
            True if loaded successfully or no persist_path, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.load)


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
        
    def get_all(self) -> Dict[str, Any]:
        """Get all stored memory items from current scope and global.

        Returns:
            Dictionary of all memory items
        """
        # Start with global memory
        result = self._global.copy()
        
        # Add current scope, overriding globals if keys overlap
        result.update(self._scopes[-1])
        
        return result
        
    def contains(self, key: str, check_outer_scopes: bool = True) -> bool:
        """Check if memory contains a key.

        Args:
            key: The key to check
            check_outer_scopes: Whether to check in outer scopes and global

        Returns:
            True if the key exists, False otherwise
        """
        # Check current scope first
        if key in self._scopes[-1]:
            return True
            
        # Check outer scopes and global if requested
        if check_outer_scopes:
            # Check outer scopes
            for scope in reversed(self._scopes[:-1]):
                if key in scope:
                    return True
                    
            # Check global scope
            return key in self._global
            
        return False
        
    def keys(self, current_scope_only: bool = False) -> Set[str]:
        """Get all keys in memory.

        Args:
            current_scope_only: Whether to get keys from current scope only

        Returns:
            Set of all keys
        """
        if current_scope_only:
            return set(self._scopes[-1].keys())
            
        # Collect keys from all scopes and global
        all_keys = set(self._global.keys())
        for scope in self._scopes:
            all_keys.update(scope.keys())
            
        return all_keys
        
    async def add_async(self, key: str, value: Any, global_scope: bool = False) -> None:
        """Add an item to memory asynchronously.
        
        Args:
            key: The key to store the value under
            value: The value to store
            global_scope: Whether to store in global scope
        """
        self.add(key, value, global_scope)
        
    async def get_async(self, key: str, default: Any = None) -> Any:
        """Get an item from memory asynchronously.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The stored value or default if not found
        """
        return self.get(key, default)


class ToolMemory(NamespacedMemory):
    """Specialized memory for tool-related information.
    
    This implementation extends NamespacedMemory with specific methods
    for storing and retrieving tool-related data.
    """
    
    def __init__(self, persist_path: Optional[str] = None) -> None:
        """Initialize a new tool memory.
        
        Args:
            persist_path: Optional path to persist memory
        """
        super().__init__(persist_path)
        
        # Initialize tool-specific namespaces
        self._ensure_namespace("tool_results")
        self._ensure_namespace("tool_history")
        self._ensure_namespace("tool_usage")
        self._ensure_namespace("tool_context")
        
    def store_tool_result(self, tool_name: str, result: ToolResult, context: Optional[Dict[str, Any]] = None) -> str:
        """Store a tool execution result.
        
        Args:
            tool_name: Name of the tool
            result: Result of tool execution
            context: Optional context information
            
        Returns:
            ID of the stored result
        """
        # Generate a unique ID for this result
        result_id = str(uuid.uuid4())
        
        # Store result data
        result_data = {
            "id": result_id,
            "tool_name": tool_name,
            "timestamp": datetime.now().isoformat(),
            "success": result.error is None,
            "error": result.error,
            "result": result.output,
        }
        
        # Add context if provided
        if context:
            result_data["context"] = context
            
        # Add result to tool_results namespace
        self.add(result_id, result_data, namespace="tool_results")
        
        # Update tool history
        self._update_tool_history(tool_name, result_id, result.error is None)
        
        # Update tool usage metrics
        self._update_tool_usage(tool_name, result.error is None)
        
        return result_id
        
    def get_tool_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get a stored tool result by ID.
        
        Args:
            result_id: ID of the result to retrieve
            
        Returns:
            Result data or None if not found
        """
        return self.get(result_id, namespace="tool_results")
        
    def get_tool_results(self, tool_name: Optional[str] = None, limit: int = 10, 
                         success_only: bool = False) -> List[Dict[str, Any]]:
        """Get recent tool results.
        
        Args:
            tool_name: Optional tool name to filter by
            limit: Maximum number of results to return
            success_only: Whether to return only successful results
            
        Returns:
            List of result data
        """
        results = []
        
        # Get all results
        all_results = self.get_namespace("tool_results")
        
        # Filter and sort results
        filtered_results = []
        for result_id, result_data in all_results.items():
            # Filter by tool name if specified
            if tool_name and result_data.get("tool_name") != tool_name:
                continue
                
            # Filter by success if requested
            if success_only and not result_data.get("success", False):
                continue
                
            filtered_results.append(result_data)
            
        # Sort by timestamp (newest first)
        filtered_results.sort(
            key=lambda x: x.get("timestamp", ""), 
            reverse=True
        )
        
        # Apply limit
        return filtered_results[:limit]
        
    def _update_tool_history(self, tool_name: str, result_id: str, success: bool) -> None:
        """Update the history for a specific tool.
        
        Args:
            tool_name: Name of the tool
            result_id: ID of the result
            success: Whether the execution was successful
        """
        # Get current history
        history = self.get(tool_name, [], namespace="tool_history")
        
        # Add new entry
        history_entry = {
            "result_id": result_id,
            "timestamp": datetime.now().isoformat(),
            "success": success,
        }
        
        # Update history (keep most recent 100 entries)
        history.append(history_entry)
        history = history[-100:]
        
        # Store updated history
        self.add(tool_name, history, namespace="tool_history")
        
    def _update_tool_usage(self, tool_name: str, success: bool) -> None:
        """Update usage metrics for a specific tool.
        
        Args:
            tool_name: Name of the tool
            success: Whether the execution was successful
        """
        # Get current usage metrics
        usage = self.get(tool_name, {
            "total_uses": 0,
            "successful_uses": 0,
            "failed_uses": 0,
            "first_used": datetime.now().isoformat(),
            "last_used": None,
        }, namespace="tool_usage")
        
        # Update metrics
        usage["total_uses"] += 1
        if success:
            usage["successful_uses"] += 1
        else:
            usage["failed_uses"] += 1
        usage["last_used"] = datetime.now().isoformat()
        
        # Store updated metrics
        self.add(tool_name, usage, namespace="tool_usage")
        
    def get_tool_usage(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage metrics for a tool or all tools.
        
        Args:
            tool_name: Optional name of the tool
            
        Returns:
            Dictionary of usage metrics
        """
        if tool_name:
            # Get metrics for a specific tool
            return self.get(tool_name, {
                "total_uses": 0,
                "successful_uses": 0,
                "failed_uses": 0,
            }, namespace="tool_usage")
        else:
            # Get metrics for all tools
            usages = self.get_namespace("tool_usage")
            
            # Calculate aggregate metrics
            total_uses = sum(usage.get("total_uses", 0) for usage in usages.values())
            successful_uses = sum(usage.get("successful_uses", 0) for usage in usages.values())
            failed_uses = sum(usage.get("failed_uses", 0) for usage in usages.values())
            
            return {
                "total_uses": total_uses,
                "successful_uses": successful_uses,
                "failed_uses": failed_uses,
                "success_rate": (successful_uses / total_uses) if total_uses > 0 else 0,
                "tool_count": len(usages),
            }
            
    def get_tool_history(self, tool_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get execution history for a specific tool.
        
        Args:
            tool_name: Name of the tool
            limit: Maximum number of history entries to return
            
        Returns:
            List of history entries
        """
        history = self.get(tool_name, [], namespace="tool_history")
        
        # Return most recent entries first
        return history[-limit:][::-1]
        
    def store_tool_context(self, tool_name: str, context: Dict[str, Any]) -> None:
        """Store context information for a tool.
        
        Args:
            tool_name: Name of the tool
            context: Context information
        """
        self.add(tool_name, context, namespace="tool_context")
        
    def get_tool_context(self, tool_name: str) -> Dict[str, Any]:
        """Get context information for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool context or empty dict if not found
        """
        return self.get(tool_name, {}, namespace="tool_context")
        
    def clear_tool_data(self, tool_name: Optional[str] = None) -> None:
        """Clear data for a specific tool or all tools.
        
        Args:
            tool_name: Optional name of the tool
        """
        if tool_name:
            # Clear data for a specific tool
            self.forget(tool_name, namespace="tool_history")
            self.forget(tool_name, namespace="tool_usage")
            self.forget(tool_name, namespace="tool_context")
            
            # Clear results for this tool
            all_results = self.get_namespace("tool_results").copy()
            for result_id, result_data in all_results.items():
                if result_data.get("tool_name") == tool_name:
                    self.forget(result_id, namespace="tool_results")
        else:
            # Clear all tool data
            self.clear(namespace="tool_results")
            self.clear(namespace="tool_history")
            self.clear(namespace="tool_usage")
            self.clear(namespace="tool_context")


class VectorMemory(AgentMemory):
    """Memory implementation that supports vector embeddings.
    
    This implementation provides methods for storing and retrieving
    data using vector embeddings for similarity search.
    """
    
    def __init__(self, vector_dimension: int = 1536, persist_path: Optional[str] = None) -> None:
        """Initialize a new vector memory.
        
        Args:
            vector_dimension: Dimension of embedding vectors
            persist_path: Optional path to persist memory
        """
        self._dimension = vector_dimension
        self._store: Dict[str, Any] = {}
        self._vectors: Dict[str, List[float]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._persist_path = persist_path
        self._last_saved: Optional[datetime] = None
        
        # Load from persist path if available
        if self._persist_path and os.path.exists(self._persist_path):
            try:
                self.load()
            except Exception as e:
                logger.warning(f"Failed to load vector memory from {self._persist_path}: {e}")
                
    def add(self, key: str, value: Any, vector: Optional[List[float]] = None, 
           metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an item to memory with vector embedding.

        Args:
            key: The key to store the value under
            value: The value to store
            vector: Optional embedding vector
            metadata: Optional metadata for the item
        """
        self._store[key] = value
        
        # Store vector if provided, otherwise use empty vector
        if vector is not None:
            # Ensure vector has correct dimension
            if len(vector) != self._dimension:
                logger.warning(
                    f"Vector dimension mismatch: expected {self._dimension}, got {len(vector)}"
                )
                # Pad or truncate vector to correct dimension
                if len(vector) < self._dimension:
                    vector = vector + [0.0] * (self._dimension - len(vector))
                else:
                    vector = vector[:self._dimension]
                    
            self._vectors[key] = vector
        elif key not in self._vectors:
            # Initialize with zeros if no vector provided and none exists
            self._vectors[key] = [0.0] * self._dimension
            
        # Store metadata if provided
        if metadata is not None:
            self._metadata[key] = metadata
        elif key not in self._metadata:
            self._metadata[key] = {}
            
        logger.debug(f"Added vector memory: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item from memory.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default if not found
        """
        value = self._store.get(key, default)
        logger.debug(f"Retrieved vector memory: {key}")
        return value
        
    def get_with_metadata(self, key: str) -> Tuple[Any, Dict[str, Any]]:
        """Get an item and its metadata from memory.
        
        Args:
            key: The key to retrieve
            
        Returns:
            Tuple of (value, metadata)
        """
        value = self._store.get(key)
        metadata = self._metadata.get(key, {})
        return value, metadata

    def forget(self, key: str) -> None:
        """Remove an item from memory.

        Args:
            key: The key to remove
        """
        if key in self._store:
            del self._store[key]
        if key in self._vectors:
            del self._vectors[key]
        if key in self._metadata:
            del self._metadata[key]
            
        logger.debug(f"Removed vector memory: {key}")

    def clear(self) -> None:
        """Clear all memory."""
        self._store.clear()
        self._vectors.clear()
        self._metadata.clear()
        logger.debug("Cleared all vector memory")

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
        
    def search_by_vector(self, query_vector: List[float], limit: int = 5) -> List[Tuple[str, float]]:
        """Search for items similar to the query vector.
        
        Args:
            query_vector: Vector to search for
            limit: Maximum number of results to return
            
        Returns:
            List of (key, similarity_score) tuples
        """
        # Ensure query vector has correct dimension
        if len(query_vector) != self._dimension:
            logger.warning(
                f"Query vector dimension mismatch: expected {self._dimension}, got {len(query_vector)}"
            )
            # Pad or truncate vector to correct dimension
            if len(query_vector) < self._dimension:
                query_vector = query_vector + [0.0] * (self._dimension - len(query_vector))
            else:
                query_vector = query_vector[:self._dimension]
        
        # Calculate cosine similarity with all vectors
        similarities = []
        for key, vector in self._vectors.items():
            similarity = self._cosine_similarity(query_vector, vector)
            similarities.append((key, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N results
        return similarities[:limit]
    
    def search_by_metadata(self, query: Dict[str, Any], partial_match: bool = True) -> List[str]:
        """Search for items by metadata.
        
        Args:
            query: Metadata to search for
            partial_match: Whether to allow partial metadata matches
            
        Returns:
            List of matching keys
        """
        matching_keys = []
        
        for key, metadata in self._metadata.items():
            if partial_match:
                # Check if metadata contains all key-value pairs in query
                if all(k in metadata and metadata[k] == v for k, v in query.items()):
                    matching_keys.append(key)
            else:
                # Check if metadata is exactly equal to query
                if metadata == query:
                    matching_keys.append(key)
                    
        return matching_keys
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (-1 to 1)
        """
        # Edge case: zero vectors
        if all(x == 0 for x in vec1) or all(x == 0 for x in vec2):
            return 0.0
            
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        mag1 = sum(a * a for a in vec1) ** 0.5
        mag2 = sum(b * b for b in vec2) ** 0.5
        
        # Calculate cosine similarity
        return dot_product / (mag1 * mag2)
        
    def save(self) -> bool:
        """Save memory to disk if persist_path is set.
        
        Returns:
            True if saved successfully or no persist_path, False otherwise
        """
        if not self._persist_path:
            return True
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            
            # Prepare data for serialization
            data = {
                "dimension": self._dimension,
                "store": self._store,
                "vectors": self._vectors,
                "metadata": self._metadata,
            }
                
            # Write to file
            with open(self._persist_path, 'w') as f:
                json.dump(data, f)
                
            self._last_saved = datetime.now()
            logger.debug(f"Vector memory saved to {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save vector memory to {self._persist_path}: {e}")
            return False
            
    def load(self) -> bool:
        """Load memory from disk if persist_path is set.
        
        Returns:
            True if loaded successfully or no persist_path, False otherwise
        """
        if not self._persist_path or not os.path.exists(self._persist_path):
            return False
            
        try:
            with open(self._persist_path, 'r') as f:
                data = json.load(f)
                
            # Load dimension
            self._dimension = data.get("dimension", self._dimension)
            
            # Load data
            self._store = data.get("store", {})
            self._vectors = data.get("vectors", {})
            self._metadata = data.get("metadata", {})
                
            logger.debug(f"Vector memory loaded from {self._persist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load vector memory from {self._persist_path}: {e}")
            return False
            
    async def add_async(self, key: str, value: Any, vector: Optional[List[float]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an item to memory asynchronously.
        
        Args:
            key: The key to store the value under
            value: The value to store
            vector: Optional embedding vector
            metadata: Optional metadata for the item
        """
        self.add(key, value, vector, metadata)
        
    async def get_async(self, key: str, default: Any = None) -> Any:
        """Get an item from memory asynchronously.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The stored value or default if not found
        """
        return self.get(key, default)
        
    async def search_by_vector_async(self, query_vector: List[float], limit: int = 5) -> List[Tuple[str, float]]:
        """Search for items similar to the query vector asynchronously.
        
        Args:
            query_vector: Vector to search for
            limit: Maximum number of results to return
            
        Returns:
            List of (key, similarity_score) tuples
        """
        # Run in thread pool to avoid blocking the event loop for large collections
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search_by_vector, query_vector, limit)


class MCPIntegratedMemory(NamespacedMemory):
    """Memory implementation with MCP integration.
    
    This implementation synchronizes memory with MCP sessions,
    providing seamless tool context sharing.
    """
    
    def __init__(self, session_id: Optional[str] = None, persist_path: Optional[str] = None) -> None:
        """Initialize a new MCP-integrated memory.
        
        Args:
            session_id: Optional ID of the MCP session to integrate with
            persist_path: Optional path to persist memory
        """
        super().__init__(persist_path)
        self._session_id = session_id
        self._mcp_client = None
        
        # Initialize MCP-specific namespaces
        self._ensure_namespace("mcp")
        self._ensure_namespace("tool_data")
        
        # Initialize client if session ID provided
        if self._session_id:
            self._init_mcp_client()
            
    def _init_mcp_client(self) -> None:
        """Initialize the MCP client."""
        try:
            # Lazy import to avoid circular imports
            from enterprise_ai.mcp.client import MCPClient
            
            self._mcp_client = MCPClient(self._session_id, create_if_not_exists=True)
            logger.debug(f"Initialized MCP client for session {self._session_id}")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self._mcp_client = None
            
    def set_session_id(self, session_id: str) -> None:
        """Set the MCP session ID.
        
        Args:
            session_id: ID of the MCP session
        """
        self._session_id = session_id
        
        # Re-initialize MCP client
        self._init_mcp_client()
            
    def add(self, key: str, value: Any, namespace: Optional[str] = None, sync_with_mcp: bool = False) -> None:
        """Add an item to memory.

        Args:
            key: The key to store the value under
            value: The value to store
            namespace: Optional namespace (uses default if None)
            sync_with_mcp: Whether to sync this value with MCP session
        """
        # Add to local memory
        super().add(key, value, namespace)
        
        # Sync with MCP if requested
        if sync_with_mcp and self._mcp_client:
            try:
                context_key = f"{namespace}.{key}" if namespace else key
                self._mcp_client.set_context(context_key, value)
                logger.debug(f"Synced {context_key} with MCP session")
            except Exception as e:
                logger.warning(f"Failed to sync {key} with MCP session: {e}")
                
    def sync_from_mcp(self, namespace: str = "mcp") -> bool:
        """Sync memory from MCP session.
        
        Args:
            namespace: Namespace to store MCP context in
            
        Returns:
            True if sync succeeded, False otherwise
        """
        if not self._mcp_client:
            logger.warning("Cannot sync from MCP: client not initialized")
            return False
            
        try:
            # Get session info
            session_info = self._mcp_client.get_session_info()
            if not session_info:
                logger.warning("Failed to get MCP session info")
                return False
                
            # Store session info
            self.add("session_info", session_info, namespace=namespace)
            
            # Get available tools
            tools = self._mcp_client.discover_tools()
            self.add("available_tools", tools, namespace=namespace)
            
            # Get tools metadata
            tools_metadata = {}
            for tool in tools:
                if "function" in tool and "name" in tool["function"]:
                    tool_name = tool["function"]["name"]
                    tool_info = self._mcp_client.get_tool_info(tool_name)
                    tools_metadata[tool_name] = tool_info
                    
            self.add("tools_metadata", tools_metadata, namespace=namespace)
            
            logger.debug(f"Synced memory from MCP session {self._session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync from MCP session: {e}")
            return False
            
    def store_tool_result_with_mcp(self, tool_name: str, result: ToolResult, 
                                  context: Optional[Dict[str, Any]] = None) -> str:
        """Store a tool execution result and sync with MCP.
        
        Args:
            tool_name: Name of the tool
            result: Result of tool execution
            context: Optional context information
            
        Returns:
            ID of the stored result
        """
        # Generate unique ID
        result_id = str(uuid.uuid4())
        
        # Store result data
        result_data = {
            "id": result_id,
            "tool_name": tool_name,
            "timestamp": datetime.now().isoformat(),
            "success": result.error is None,
            "error": result.error,
            "result": result.output,
            "context": context or {},
        }
        
        # Store in local memory
        self.add(result_id, result_data, namespace="tool_data")
        
        # Sync with MCP if client is available
        if self._mcp_client:
            try:
                # Store minimal information in MCP context to avoid potential size limits
                mcp_result_data = {
                    "id": result_id,
                    "tool_name": tool_name,
                    "timestamp": datetime.now().isoformat(),
                    "success": result.error is None,
                }
                
                self._mcp_client.set_context(f"tool_results.{result_id}", mcp_result_data)
                logger.debug(f"Synced tool result {result_id} with MCP session")
            except Exception as e:
                logger.warning(f"Failed to sync tool result with MCP session: {e}")
                
        return result_id
        
    async def sync_from_mcp_async(self, namespace: str = "mcp") -> bool:
        """Sync memory from MCP session asynchronously.
        
        Args:
            namespace: Namespace to store MCP context in
            
        Returns:
            True if sync succeeded, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_from_mcp, namespace)


# Factory function to create memory implementations
def create_memory(
    memory_type: str = "dict", 
    persist_path: Optional[str] = None,
    mcp_session_id: Optional[str] = None,
    **kwargs: Any
) -> AgentMemory:
    """Create a memory implementation by type.

    Args:
        memory_type: Type of memory to create
        persist_path: Optional path for persistence
        mcp_session_id: Optional MCP session ID for integrated memory
        **kwargs: Additional arguments for specific memory types

    Returns:
        AgentMemory implementation

    Raises:
        ValueError: If an unknown memory type is specified
    """
    if memory_type == "dict":
        return DictMemory(persist_path=persist_path)
    elif memory_type == "namespaced":
        return NamespacedMemory(persist_path=persist_path)
    elif memory_type == "scoped":
        return ScopedMemory()
    elif memory_type == "tool":
        return ToolMemory(persist_path=persist_path)
    elif memory_type == "vector":
        vector_dimension = kwargs.get("vector_dimension", 1536)
        return VectorMemory(vector_dimension=vector_dimension, persist_path=persist_path)
    elif memory_type == "mcp":
        return MCPIntegratedMemory(session_id=mcp_session_id, persist_path=persist_path)
    else:
        raise ValueError(f"Unknown memory type: {memory_type}")
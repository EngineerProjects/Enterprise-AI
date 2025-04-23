"""
Task node implementations for Enterprise AI workflows.

This module provides concrete implementations of workflow nodes
that can be used to build workflows.
"""

import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Union, cast

from enterprise_ai.flow.types import NodeProtocol, NodeStatus
from enterprise_ai.logger import get_logger

logger = get_logger("flow.node")


class BaseNode(NodeProtocol):
    """Base implementation of a workflow node."""

    def __init__(
        self,
        name: str,
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
    ):
        """Initialize a base node.

        Args:
            name: Human-readable name
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
        """
        self._id = node_id or str(uuid.uuid4())
        self._name = name
        self._dependencies = dependencies or set()
        self._status = NodeStatus.PENDING
        self._result: Dict[str, Any] = {}

    @property
    def id(self) -> str:
        """Get node ID."""
        return self._id

    @property
    def name(self) -> str:
        """Get node name."""
        return self._name

    @property
    def status(self) -> NodeStatus:
        """Get node status."""
        return self._status

    @status.setter
    def status(self, status: NodeStatus) -> None:
        """Set node status."""
        self._status = status

    @property
    def dependencies(self) -> Set[str]:
        """Get IDs of nodes this node depends on."""
        return self._dependencies.copy()

    def set_dependencies(self, dependencies: Set[str]) -> None:
        """Set the node's dependencies (used by SequentialWorkflow)."""
        self._dependencies = dependencies

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node with the given context.

        Args:
            context: Workflow execution context

        Returns:
            Result dictionary to add to the workflow context
        """
        # Base implementation does nothing
        logger.info(f"Executing node {self._id} ({self._name})")
        self._status = NodeStatus.RUNNING

        try:
            # Execute node-specific logic
            self._result = await self._execute_internal(context)
            self._status = NodeStatus.COMPLETED
            logger.info(f"Node {self._id} ({self._name}) completed successfully")
            return self._result
        except Exception as e:
            self._status = NodeStatus.FAILED
            logger.error(f"Node {self._id} ({self._name}) failed: {e}")
            self._result = {"error": str(e)}
            raise

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Internal node execution logic to be overridden by subclasses.

        Args:
            context: Workflow execution context

        Returns:
            Result dictionary to add to the workflow context
        """
        # Base implementation returns empty result
        return {}

    def can_execute(self, completed_nodes: Set[str]) -> bool:
        """Check if this node's dependencies are satisfied.

        Args:
            completed_nodes: Set of completed node IDs

        Returns:
            True if all dependencies are satisfied, False otherwise
        """
        return self._dependencies.issubset(completed_nodes)


class FunctionNode(BaseNode):
    """Node that executes a function."""

    def __init__(
        self,
        name: str,
        function: Callable[[Dict[str, Any]], Union[Any, Awaitable[Any]]],
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
    ):
        """Initialize a function node.

        Args:
            name: Human-readable name
            function: Function to execute when the node runs
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
        """
        super().__init__(name, dependencies, node_id)
        self._function = function

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the function with the given context.

        Args:
            context: Workflow execution context

        Returns:
            Result of the function execution
        """
        try:
            result = self._function(context)
            # Handle both synchronous and asynchronous functions
            if hasattr(result, "__await__"):
                result = await result
            return {"result": result}
        except Exception as e:
            logger.error(f"Error executing function in node {self._id}: {e}")
            raise

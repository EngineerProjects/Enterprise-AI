"""
Workflow implementations for Enterprise AI.

This module provides concrete implementations of workflows
that can be used to orchestrate tasks.
"""

import uuid
import asyncio
from typing import Any, Dict, List, Optional, Sequence, Set, cast

from enterprise_ai.flow.types import NodeProtocol, WorkflowProtocol, WorkflowStatus, NodeStatus
from enterprise_ai.logger import get_logger

logger = get_logger("flow.workflow")


class BaseWorkflow(WorkflowProtocol):
    """Base implementation of a workflow."""

    def __init__(
        self,
        name: str,
        workflow_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a base workflow.

        Args:
            name: Human-readable name
            workflow_id: Optional workflow ID (generated if not provided)
            initial_context: Optional initial workflow context
        """
        self._id = workflow_id or str(uuid.uuid4())
        self._name = name
        self._nodes: Dict[str, NodeProtocol] = {}
        self._status = WorkflowStatus.PENDING
        self._context = initial_context or {}
        self._completed_nodes: Set[str] = set()
        self._failed_nodes: Set[str] = set()

    @property
    def id(self) -> str:
        """Get workflow ID."""
        return self._id

    @property
    def name(self) -> str:
        """Get workflow name."""
        return self._name

    @property
    def status(self) -> WorkflowStatus:
        """Get workflow status."""
        return self._status

    @status.setter
    def status(self, value: WorkflowStatus) -> None:
        self._status = value

    @status.setter
    def status(self, status: WorkflowStatus) -> None:
        """Set workflow status."""
        self._status = status

    @property
    def nodes(self) -> Dict[str, NodeProtocol]:
        """Get all nodes in this workflow."""
        return self._nodes.copy()

    @property
    def context(self) -> Dict[str, Any]:
        """Get workflow execution context."""
        return self._context.copy()

    def add_node(self, node: NodeProtocol) -> None:
        """Add a node to the workflow.

        Args:
            node: Node to add

        Raises:
            ValueError: If a node with the same ID already exists
        """
        if node.id in self._nodes:
            raise ValueError(f"Node with ID {node.id} already exists in workflow")

        # Verify that all dependencies exist
        for dep_id in node.dependencies:
            if dep_id not in self._nodes:
                raise ValueError(f"Dependency {dep_id} not found in workflow")

        self._nodes[node.id] = node
        logger.debug(f"Added node {node.id} to workflow {self._id}")

    def get_ready_nodes(self) -> List[NodeProtocol]:
        """Get nodes that are ready to execute.

        Returns:
            List of nodes that have all dependencies satisfied and are not completed
        """
        result = []

        for node in self._nodes.values():
            # Skip nodes that are already completed or running
            if node.status in [NodeStatus.COMPLETED, NodeStatus.RUNNING, NodeStatus.FAILED]:
                continue

            # Check if all dependencies are satisfied
            if node.can_execute(self._completed_nodes):
                result.append(node)

        return result

    async def execute(self) -> Dict[str, Any]:
        """Execute the entire workflow.

        Returns:
            Final workflow context
        """
        if self._status == WorkflowStatus.RUNNING:
            logger.warning(f"Workflow {self._id} is already running")
            return self._context

        if self._status == WorkflowStatus.COMPLETED:
            logger.warning(f"Workflow {self._id} is already completed")
            return self._context

        self._status = WorkflowStatus.RUNNING
        logger.info(f"Starting execution of workflow {self._id} ({self._name})")

        try:
            while self._status == WorkflowStatus.RUNNING:
                # Get ready nodes
                ready_nodes = self.get_ready_nodes()

                if not ready_nodes:
                    # If no nodes are ready, check if we're done
                    if len(self._completed_nodes) + len(self._failed_nodes) == len(self._nodes):
                        if len(self._failed_nodes) > 0:
                            self._status = WorkflowStatus.FAILED
                        else:
                            self._status = WorkflowStatus.COMPLETED
                        break

                    # If we're not done but no nodes are ready, we might be waiting for async tasks
                    await asyncio.sleep(0.1)
                    continue

                # Execute ready nodes
                for node in ready_nodes:
                    try:
                        node.status = NodeStatus.RUNNING
                        result = await node.execute(self._context)

                        # Update workflow context with node result
                        if isinstance(result, dict):
                            self._context.update(result)

                        # Mark node as completed
                        self._completed_nodes.add(node.id)
                    except Exception as e:
                        # Mark node as failed
                        self._failed_nodes.add(node.id)
                        logger.error(f"Node {node.id} failed: {e}")

            logger.info(f"Workflow {self._id} completed with status {self._status.name}")
            return self._context
        except Exception as e:
            self._status = WorkflowStatus.FAILED
            logger.error(f"Workflow {self._id} failed: {e}")
            raise

    def pause(self) -> None:
        """Pause workflow execution."""
        if self._status == WorkflowStatus.RUNNING:
            self._status = WorkflowStatus.PAUSED
            logger.info(f"Workflow {self._id} paused")

    def resume(self) -> None:
        """Resume workflow execution."""
        if self._status == WorkflowStatus.PAUSED:
            self._status = WorkflowStatus.RUNNING
            logger.info(f"Workflow {self._id} resumed")

    def cancel(self) -> None:
        """Cancel workflow execution."""
        self._status = WorkflowStatus.CANCELLED
        logger.info(f"Workflow {self._id} cancelled")


class SequentialWorkflow(BaseWorkflow):
    """Workflow that executes nodes in a specific sequence."""

    def __init__(
        self,
        name: str,
        nodes: Optional[Sequence[NodeProtocol]] = None,
        workflow_id: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a sequential workflow.

        Args:
            name: Human-readable name
            nodes: Optional list of nodes to add in sequence
            workflow_id: Optional workflow ID (generated if not provided)
            initial_context: Optional initial workflow context
        """
        super().__init__(name, workflow_id, initial_context)

        # Add nodes in sequence if provided
        if nodes:
            prev_node_id = None
            for node in nodes:
                if prev_node_id:
                    # Create a new set of dependencies including the previous node
                    new_deps = node.dependencies.copy()
                    new_deps.add(prev_node_id)

                    # Use the method defined in NodeProtocol to set dependencies
                    node.set_dependencies(new_deps)

                self.add_node(node)
                prev_node_id = node.id

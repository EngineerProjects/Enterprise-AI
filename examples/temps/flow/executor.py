"""
Workflow execution system for Enterprise AI.

This module provides the execution engine for workflows,
handling the scheduling and monitoring of workflow execution.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Set, cast

from enterprise_ai.flow.types import NodeProtocol, WorkflowProtocol, WorkflowExecutorProtocol
from enterprise_ai.flow.types import NodeStatus, WorkflowStatus
from enterprise_ai.logger import get_logger

logger = get_logger("flow.executor")


class WorkflowExecutor(WorkflowExecutorProtocol):
    """Engine for executing workflows."""

    def __init__(self, max_concurrent_nodes: int = 10):
        """Initialize a workflow executor.

        Args:
            max_concurrent_nodes: Maximum number of nodes to execute concurrently
        """
        self._max_concurrent_nodes = max_concurrent_nodes
        self._running_workflows: Dict[str, WorkflowProtocol] = {}
        self._node_execution_times: Dict[
            str, Dict[str, float]
        ] = {}  # workflow_id -> {node_id -> execution_time}

    async def execute_workflow(self, workflow: WorkflowProtocol) -> Dict[str, Any]:
        """Execute a workflow to completion.

        Args:
            workflow: Workflow to execute

        Returns:
            Final workflow context
        """
        workflow_id = workflow.id
        self._running_workflows[workflow_id] = workflow
        self._node_execution_times[workflow_id] = {}

        logger.info(f"Starting execution of workflow {workflow_id} ({workflow.name})")
        workflow.status = WorkflowStatus.RUNNING

        try:
            # Execute until completion
            while workflow.status == WorkflowStatus.RUNNING:
                # Get ready nodes
                ready_nodes = workflow.get_ready_nodes()

                if not ready_nodes:
                    # Check if workflow is complete
                    all_nodes = set(workflow.nodes.keys())
                    completed_nodes = {
                        n.id for n in workflow.nodes.values() if n.status == NodeStatus.COMPLETED
                    }
                    failed_nodes = {
                        n.id for n in workflow.nodes.values() if n.status == NodeStatus.FAILED
                    }

                    if completed_nodes.union(failed_nodes) == all_nodes:
                        if failed_nodes:
                            workflow.status = WorkflowStatus.FAILED
                        else:
                            workflow.status = WorkflowStatus.COMPLETED
                        break

                    # If not complete, wait a bit and check again
                    await asyncio.sleep(0.1)
                    continue

                # Limit number of concurrent executions
                tasks = []
                for node in ready_nodes[: self._max_concurrent_nodes]:
                    tasks.append(self.execute_node(node, workflow.context))

                # Wait for all tasks to complete
                if tasks:
                    await asyncio.gather(*tasks)

            # Remove from running workflows
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]

            logger.info(f"Workflow {workflow_id} completed with status {workflow.status.name}")
            return workflow.context
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            logger.error(f"Workflow {workflow_id} failed: {e}")

            # Remove from running workflows
            if workflow_id in self._running_workflows:
                del self._running_workflows[workflow_id]

            raise

    async def execute_node(self, node: NodeProtocol, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single node.

        Args:
            node: Node to execute
            context: Workflow execution context

        Returns:
            Node execution result
        """
        node_id = node.id
        logger.info(f"Executing node {node_id} ({node.name})")

        start_time = time.time()
        try:
            result = await node.execute(context)

            # Record execution time
            for workflow_id, workflow in self._running_workflows.items():
                if node_id in workflow.nodes:
                    self._node_execution_times[workflow_id][node_id] = time.time() - start_time
                    break

            return result
        except Exception as e:
            # Record execution time even on failure
            for workflow_id, workflow in self._running_workflows.items():
                if node_id in workflow.nodes:
                    self._node_execution_times[workflow_id][node_id] = time.time() - start_time
                    break

            logger.error(f"Node {node_id} execution failed: {e}")
            raise

    def pause_workflow(self, workflow_id: str) -> None:
        """Pause a running workflow.

        Args:
            workflow_id: ID of the workflow to pause
        """
        if workflow_id in self._running_workflows:
            workflow = self._running_workflows[workflow_id]
            workflow.pause()
            logger.info(f"Workflow {workflow_id} paused")

    def resume_workflow(self, workflow_id: str) -> None:
        """Resume a paused workflow.

        Args:
            workflow_id: ID of the workflow to resume
        """
        if workflow_id in self._running_workflows:
            workflow = self._running_workflows[workflow_id]
            workflow.resume()
            logger.info(f"Workflow {workflow_id} resumed")

    def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a workflow execution.

        Args:
            workflow_id: ID of the workflow to cancel
        """
        if workflow_id in self._running_workflows:
            workflow = self._running_workflows[workflow_id]
            workflow.cancel()
            logger.info(f"Workflow {workflow_id} cancelled")

            # Remove from running workflows
            del self._running_workflows[workflow_id]

    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """Get the status of a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Workflow status or None if not found
        """
        if workflow_id in self._running_workflows:
            return self._running_workflows[workflow_id].status
        return None

    def get_node_stats(self, workflow_id: str) -> Dict[str, Dict[str, Any]]:
        """Get execution statistics for nodes in a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Dictionary mapping node IDs to statistics
        """
        if workflow_id not in self._running_workflows:
            return {}

        workflow = self._running_workflows[workflow_id]
        stats = {}

        for node_id, node in workflow.nodes.items():
            stats[node_id] = {
                "name": node.name,
                "status": node.status.name,
                "execution_time": self._node_execution_times.get(workflow_id, {}).get(node_id, 0),
            }

        return stats

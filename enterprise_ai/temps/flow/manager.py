"""
Workflow management system for Enterprise AI.

This module provides a high-level API for managing workflows,
including creation, execution, monitoring, and persistence.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.flow.types import WorkflowProtocol, WorkflowStatus
from enterprise_ai.flow.executor import WorkflowExecutor
from enterprise_ai.logger import get_logger

logger = get_logger("flow.manager")


class WorkflowManager:
    """Manager for workflow creation, execution, and monitoring."""

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize a workflow manager.

        Args:
            storage_dir: Optional directory for workflow storage
        """
        self._executor = WorkflowExecutor()
        self._workflows: Dict[str, WorkflowProtocol] = {}
        self._execution_history: Dict[str, List[Dict[str, Any]]] = {}
        self._storage_dir = storage_dir

        # Create storage directory if specified and it doesn't exist
        if self._storage_dir and not os.path.exists(self._storage_dir):
            os.makedirs(self._storage_dir, exist_ok=True)

    def register_workflow(self, workflow: WorkflowProtocol) -> str:
        """Register a workflow with the manager.

        Args:
            workflow: Workflow to register

        Returns:
            Workflow ID
        """
        workflow_id = workflow.id
        self._workflows[workflow_id] = workflow
        logger.info(f"Registered workflow {workflow_id} ({workflow.name})")
        return workflow_id

    async def execute_workflow(
        self,
        workflow_id: str,
        wait_for_completion: bool = True,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[WorkflowStatus, Dict[str, Any]]:
        """Execute a workflow.

        Args:
            workflow_id: ID of the workflow to execute
            wait_for_completion: Whether to wait for workflow completion
            initial_context: Optional initial context for the workflow

        Returns:
            Tuple of (workflow status, context)

        Raises:
            ValueError: If the workflow is not found
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self._workflows[workflow_id]

        # Initialize execution history record
        history_record = {
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "start_time": time.time(),
            "status": WorkflowStatus.RUNNING.name,
            "initial_context": initial_context or {},
        }

        # Add initial context if provided
        if initial_context:
            for key, value in initial_context.items():
                workflow.context[key] = value

        # Execute workflow
        try:
            # Start workflow execution
            workflow.status = WorkflowStatus.RUNNING

            if wait_for_completion:
                # Execute and wait for completion
                context = await self._executor.execute_workflow(workflow)

                # Update history record
                history_record["end_time"] = time.time()
                start_time = cast(float, history_record["start_time"])
                end_time = cast(float, history_record["end_time"])
                history_record["duration"] = end_time - start_time
                history_record["status"] = workflow.status.name
                history_record["final_context"] = context

                # Add to execution history
                self._add_to_execution_history(workflow_id, history_record)

                return workflow.status, context
            else:
                # Start execution without waiting
                asyncio.create_task(self._execute_and_record(workflow, history_record))
                return WorkflowStatus.RUNNING, workflow.context
        except Exception as e:
            # Update history record
            history_record["end_time"] = time.time()
            start_time = cast(float, history_record["start_time"])
            end_time = cast(float, history_record["end_time"])
            history_record["duration"] = end_time - start_time
            history_record["status"] = WorkflowStatus.FAILED.name
            history_record["error"] = str(e)

            # Add to execution history
            self._add_to_execution_history(workflow_id, history_record)

            logger.error(f"Workflow {workflow_id} execution failed: {e}")
            workflow.status = WorkflowStatus.FAILED

            raise

    async def _execute_and_record(
        self, workflow: WorkflowProtocol, history_record: Dict[str, Any]
    ) -> None:
        """Execute a workflow and record history.

        Args:
            workflow: Workflow to execute
            history_record: History record to update
        """
        try:
            # Execute workflow
            context = await self._executor.execute_workflow(workflow)

            # Update history record
            history_record["end_time"] = time.time()
            history_record["duration"] = history_record["end_time"] - history_record["start_time"]
            history_record["status"] = workflow.status.name
            history_record["final_context"] = context
        except Exception as e:
            # Update history record
            history_record["end_time"] = time.time()
            history_record["duration"] = history_record["end_time"] - history_record["start_time"]
            history_record["status"] = WorkflowStatus.FAILED.name
            history_record["error"] = str(e)

            logger.error(f"Workflow {workflow.id} execution failed: {e}")
            workflow.status = WorkflowStatus.FAILED
        finally:
            # Add to execution history
            self._add_to_execution_history(workflow.id, history_record)

    def _add_to_execution_history(self, workflow_id: str, record: Dict[str, Any]) -> None:
        """Add a record to execution history.

        Args:
            workflow_id: ID of the workflow
            record: History record to add
        """
        if workflow_id not in self._execution_history:
            self._execution_history[workflow_id] = []

        self._execution_history[workflow_id].append(record)

        # Save to disk if storage directory is specified
        if self._storage_dir:
            self._save_execution_history(workflow_id)

    def _save_execution_history(self, workflow_id: str) -> None:
        """Save execution history to disk.

        Args:
            workflow_id: ID of the workflow to save history for
        """
        if not self._storage_dir:
            return

        history_file = os.path.join(self._storage_dir, f"{workflow_id}_history.json")

        try:
            with open(history_file, "w") as f:
                json.dump(self._execution_history[workflow_id], f, indent=2, default=str)
            logger.debug(f"Saved execution history for workflow {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to save execution history for workflow {workflow_id}: {e}")

    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """Get the current status of a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            Workflow status or None if not found
        """
        if workflow_id in self._workflows:
            return self._workflows[workflow_id].status
        return None

    def get_workflow_execution_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get execution history for a workflow.

        Args:
            workflow_id: ID of the workflow

        Returns:
            List of execution history records
        """
        return self._execution_history.get(workflow_id, [])

    def get_all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered workflows.

        Returns:
            Dictionary mapping workflow IDs to workflow information
        """
        result = {}

        for workflow_id, workflow in self._workflows.items():
            result[workflow_id] = {
                "name": workflow.name,
                "status": workflow.status.name,
                "node_count": len(workflow.nodes),
                "execution_count": len(self._execution_history.get(workflow_id, [])),
            }

        return result

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow.

        Args:
            workflow_id: ID of the workflow to pause

        Returns:
            True if workflow was paused, False otherwise
        """
        if workflow_id in self._workflows:
            workflow = self._workflows[workflow_id]
            if workflow.status == WorkflowStatus.RUNNING:
                self._executor.pause_workflow(workflow_id)
                return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow.

        Args:
            workflow_id: ID of the workflow to resume

        Returns:
            True if workflow was resumed, False otherwise
        """
        if workflow_id in self._workflows:
            workflow = self._workflows[workflow_id]
            if workflow.status == WorkflowStatus.PAUSED:
                self._executor.resume_workflow(workflow_id)
                return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow execution.

        Args:
            workflow_id: ID of the workflow to cancel

        Returns:
            True if workflow was cancelled, False otherwise
        """
        if workflow_id in self._workflows:
            workflow = self._workflows[workflow_id]
            if workflow.status in [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]:
                self._executor.cancel_workflow(workflow_id)
                return True
        return False

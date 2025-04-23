"""
Flow control nodes for Enterprise AI workflows.

This module provides special nodes for controlling workflow execution,
including conditional branching and parallel execution.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Union

from enterprise_ai.flow.node import BaseNode
from enterprise_ai.flow.types import NodeStatus
from enterprise_ai.logger import get_logger

logger = get_logger("flow.nodes.control")


class ConditionalNode(BaseNode):
    """Node that executes conditionally based on a predicate."""

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        then_node: BaseNode,
        else_node: Optional[BaseNode] = None,
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
    ):
        """Initialize a conditional node.

        Args:
            name: Human-readable name
            condition: Function that takes the context and returns a boolean
            then_node: Node to execute if condition is True
            else_node: Optional node to execute if condition is False
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
        """
        super().__init__(name, dependencies, node_id)
        self._condition = condition
        self._then_node = then_node
        self._else_node = else_node

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node based on the condition.

        Args:
            context: Workflow execution context

        Returns:
            Result from the selected branch
        """
        # Evaluate condition
        condition_result = self._condition(context)
        logger.info(f"Condition evaluated to {condition_result} in node {self.id}")

        # Execute appropriate branch
        if condition_result:
            logger.info(f"Executing 'then' branch: {self._then_node.name}")
            return await self._then_node.execute(context)
        elif self._else_node:
            logger.info(f"Executing 'else' branch: {self._else_node.name}")
            return await self._else_node.execute(context)
        else:
            logger.info("No 'else' branch specified, returning empty result")
            return {}


class ParallelNode(BaseNode):
    """Node that executes multiple child nodes in parallel."""

    def __init__(
        self,
        name: str,
        nodes: List[BaseNode],
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
        merge_results: bool = True,
    ):
        """Initialize a parallel node.

        Args:
            name: Human-readable name
            nodes: List of nodes to execute in parallel
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
            merge_results: Whether to merge results from all nodes or just return the first
        """
        super().__init__(name, dependencies, node_id)
        self._nodes = nodes
        self._merge_results = merge_results

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all child nodes in parallel.

        Args:
            context: Workflow execution context

        Returns:
            Combined results from all child nodes
        """
        logger.info(f"Executing {len(self._nodes)} nodes in parallel")

        # Create tasks for all nodes
        tasks = [node.execute(context) for node in self._nodes]

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        if not self._merge_results:
            # Just return the first successful result
            for result in results:
                if isinstance(result, dict):
                    return result
            return {}

        # Merge all results
        merged_results = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Node {self._nodes[i].id} failed: {result}")
                self._nodes[i].status = NodeStatus.FAILED
            elif isinstance(result, dict):
                merged_results.update(result)

        return merged_results


class RetryNode(BaseNode):
    """Node that retries a child node multiple times until success."""

    def __init__(
        self,
        name: str,
        node: BaseNode,
        max_attempts: int = 3,
        delay: float = 1.0,
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
    ):
        """Initialize a retry node.

        Args:
            name: Human-readable name
            node: Node to retry
            max_attempts: Maximum number of retry attempts
            delay: Delay between retries in seconds
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
        """
        super().__init__(name, dependencies, node_id)
        self._node = node
        self._max_attempts = max_attempts
        self._delay = delay

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the child node with retries.

        Args:
            context: Workflow execution context

        Returns:
            Result from the child node
        """
        attempt = 0
        last_error = None

        while attempt < self._max_attempts:
            attempt += 1
            logger.info(f"Attempt {attempt}/{self._max_attempts} for node {self._node.id}")

            try:
                # Reset node status if this isn't the first attempt
                if attempt > 1:
                    self._node.status = NodeStatus.PENDING

                # Execute the node
                result = await self._node.execute(context)

                # If successful, return the result
                return result
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                last_error = e

                # Wait before retrying
                if attempt < self._max_attempts:
                    await asyncio.sleep(self._delay)

        # If we get here, all attempts failed
        self.status = NodeStatus.FAILED
        if last_error:
            raise RuntimeError(
                f"All {self._max_attempts} attempts failed. Last error: {last_error}"
            )
        else:
            raise RuntimeError(f"All {self._max_attempts} attempts failed.")

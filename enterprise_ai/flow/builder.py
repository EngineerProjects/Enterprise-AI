"""
Workflow builder for Enterprise AI.

This module provides a fluent API for building workflows.
"""

from typing import Any, Callable, Dict, List, Optional, Set, Union

from enterprise_ai.agent.types import AgentProtocol
from enterprise_ai.flow.node import BaseNode, FunctionNode
from enterprise_ai.flow.nodes.agent import AgentTaskNode
from enterprise_ai.flow.nodes.team import TeamTaskNode
from enterprise_ai.flow.nodes.control import ConditionalNode, ParallelNode, RetryNode
from enterprise_ai.flow.workflow import BaseWorkflow, SequentialWorkflow
from enterprise_ai.flow.types import FlowTeamProtocol
from enterprise_ai.logger import get_logger

logger = get_logger("flow.builder")


class WorkflowBuilder:
    """Builder for creating workflows using a fluent API."""

    def __init__(self, name: str, workflow_id: Optional[str] = None):
        """Initialize a workflow builder.

        Args:
            name: Name of the workflow
            workflow_id: Optional workflow ID
        """
        self._name = name
        self._workflow_id = workflow_id
        self._nodes: List[BaseNode] = []
        self._current_dependencies: Set[str] = set()

    def add_function(
        self,
        name: str,
        function: Callable[[Dict[str, Any]], Any],
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add a function node to the workflow.

        Args:
            name: Name of the node
            function: Function to execute
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        node = FunctionNode(
            name=name,
            function=function,
            dependencies=self._current_dependencies.copy(),
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def add_agent_task(
        self,
        name: str,
        agent: AgentProtocol,
        task_description: str,
        result_key: str = "result",
        timeout: float = 60.0,
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add an agent task node to the workflow.

        Args:
            name: Name of the node
            agent: Agent to assign the task to
            task_description: Description of the task
            result_key: Key to use for storing the result in the context
            timeout: Maximum time to wait for task completion in seconds
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        node = AgentTaskNode(
            name=name,
            agent=agent,
            task_description=task_description,
            dependencies=self._current_dependencies.copy(),
            result_key=result_key,
            timeout=timeout,
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def add_team_task(
        self,
        name: str,
        team: FlowTeamProtocol,
        task_description: str,
        target_agent_id: Optional[str] = None,
        result_key: str = "result",
        timeout: float = 300.0,
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add a team task node to the workflow.

        Args:
            name: Name of the node
            team: Team to assign the task to
            task_description: Description of the task
            target_agent_id: Optional ID of a specific agent in the team
            result_key: Key to use for storing the result in the context
            timeout: Maximum time to wait for task completion in seconds
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        node = TeamTaskNode(
            name=name,
            team=team,
            task_description=task_description,
            target_agent_id=target_agent_id,
            dependencies=self._current_dependencies.copy(),
            result_key=result_key,
            timeout=timeout,
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def add_condition(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        then_builder: Callable[["WorkflowBuilder"], None],
        else_builder: Optional[Callable[["WorkflowBuilder"], None]] = None,
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add a conditional branch to the workflow.

        Args:
            name: Name of the node
            condition: Function that takes the context and returns a boolean
            then_builder: Function that builds the 'then' branch
            else_builder: Optional function that builds the 'else' branch
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        # Create builders for each branch
        then_branch_builder = WorkflowBuilder(f"{name}_then")
        then_builder(then_branch_builder)

        else_branch_builder = None
        if else_builder:
            else_branch_builder = WorkflowBuilder(f"{name}_else")
            else_builder(else_branch_builder)

        # Create the conditional node
        node = ConditionalNode(
            name=name,
            condition=condition,
            then_node=then_branch_builder.build_as_node(f"{name}_then"),
            else_node=else_branch_builder.build_as_node(f"{name}_else")
            if else_branch_builder
            else None,
            dependencies=self._current_dependencies.copy(),
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def add_parallel(
        self,
        name: str,
        branch_builders: List[Callable[["WorkflowBuilder"], None]],
        merge_results: bool = True,
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add parallel branches to the workflow.

        Args:
            name: Name of the node
            branch_builders: List of functions that build each branch
            merge_results: Whether to merge results from all branches
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        # Create a builder for each branch
        branch_nodes = []
        for i, branch_builder in enumerate(branch_builders):
            branch_name = f"{name}_branch_{i}"
            branch_workflow_builder = WorkflowBuilder(branch_name)
            branch_builder(branch_workflow_builder)
            branch_nodes.append(branch_workflow_builder.build_as_node(branch_name))

        # Create the parallel node
        node = ParallelNode(
            name=name,
            nodes=branch_nodes,
            dependencies=self._current_dependencies.copy(),
            merge_results=merge_results,
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def add_retry(
        self,
        name: str,
        node_builder: Callable[["WorkflowBuilder"], None],
        max_attempts: int = 3,
        delay: float = 1.0,
        node_id: Optional[str] = None,
    ) -> "WorkflowBuilder":
        """Add a retry node to the workflow.

        Args:
            name: Name of the node
            node_builder: Function that builds the node to retry
            max_attempts: Maximum number of retry attempts
            delay: Delay between retries in seconds
            node_id: Optional node ID

        Returns:
            Self for method chaining
        """
        # Create a builder for the node to retry
        retry_node_builder = WorkflowBuilder(f"{name}_inner")
        node_builder(retry_node_builder)

        # Create the retry node
        node = RetryNode(
            name=name,
            node=retry_node_builder.build_as_node(f"{name}_inner"),
            max_attempts=max_attempts,
            delay=delay,
            dependencies=self._current_dependencies.copy(),
            node_id=node_id,
        )
        self._nodes.append(node)

        # Update current dependencies to include this node
        self._current_dependencies = {node.id}

        return self

    def build(self) -> BaseWorkflow:
        """Build the workflow.

        Returns:
            Built workflow
        """
        workflow = SequentialWorkflow(
            name=self._name,
            nodes=self._nodes,
            workflow_id=self._workflow_id,
        )
        logger.info(f"Built workflow {workflow.id} with {len(self._nodes)} nodes")
        return workflow

    def build_as_node(self, name: Optional[str] = None) -> BaseNode:
        """Build the workflow as a single node.

        Args:
            name: Optional name for the node (defaults to workflow name)

        Returns:
            Node that executes the workflow
        """
        workflow = self.build()

        # Create a node that executes the workflow
        return FunctionNode(
            name=name or self._name,
            function=lambda context: workflow.execute(),
            dependencies=set(),
        )

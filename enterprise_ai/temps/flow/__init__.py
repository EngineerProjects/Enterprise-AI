"""
Workflow management for Enterprise AI.

This module provides functionality for defining, executing, and
managing workflows that orchestrate AI agents and teams.
"""

from enterprise_ai.flow.types import (
    NodeStatus,
    WorkflowStatus,
    NodeProtocol,
    WorkflowProtocol,
    WorkflowExecutorProtocol,
    FlowTeamProtocol,
)
from enterprise_ai.flow.node import BaseNode, FunctionNode
from enterprise_ai.flow.workflow import BaseWorkflow, SequentialWorkflow
from enterprise_ai.flow.executor import WorkflowExecutor
from enterprise_ai.flow.builder import WorkflowBuilder
from enterprise_ai.flow.factory import WorkflowFactory
from enterprise_ai.flow.manager import WorkflowManager

# Import specialized nodes
from enterprise_ai.flow.nodes.agent import AgentTaskNode
from enterprise_ai.flow.nodes.team import TeamTaskNode
from enterprise_ai.flow.nodes.control import ConditionalNode, ParallelNode, RetryNode

__all__ = [
    # Types
    "NodeStatus",
    "WorkflowStatus",
    "NodeProtocol",
    "WorkflowProtocol",
    "WorkflowExecutorProtocol",
    "FlowTeamProtocol",
    # Base Classes
    "BaseNode",
    "FunctionNode",
    "BaseWorkflow",
    "SequentialWorkflow",
    "WorkflowExecutor",
    # Specialized Nodes
    "AgentTaskNode",
    "TeamTaskNode",
    "ConditionalNode",
    "ParallelNode",
    "RetryNode",
    # High-level API
    "WorkflowBuilder",
    "WorkflowFactory",
    "WorkflowManager",
]

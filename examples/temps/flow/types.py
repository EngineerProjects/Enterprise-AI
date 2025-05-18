"""
Core type definitions for Enterprise AI workflow system.

This module defines the protocols and types for workflows, task nodes,
and execution engines that form the foundation of the flow system.
"""

from abc import abstractmethod
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Set, Union, Callable, Tuple

from enterprise_ai.agent.core.types import AgentProtocol, Task, TaskStatus
from enterprise_ai.team.types import TeamProtocol


# ────────────────────────────────
# Enums
# ────────────────────────────────


class NodeStatus(Enum):
    """Status of a workflow node."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()
    BLOCKED = auto()


class WorkflowStatus(Enum):
    """Status of a workflow execution."""

    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


# ────────────────────────────────
# Core Protocols
# ────────────────────────────────


class NodeProtocol(Protocol):
    """Protocol for workflow nodes."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def status(self) -> NodeStatus: ...

    @status.setter
    def status(self, value: NodeStatus) -> None: ...

    @property
    def dependencies(self) -> Set[str]: ...

    def set_dependencies(self, dependencies: Set[str]) -> None: ...

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]: ...

    def can_execute(self, completed_nodes: Set[str]) -> bool: ...


class WorkflowProtocol(Protocol):
    """Protocol for workflows."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def status(self) -> WorkflowStatus: ...

    @status.setter
    def status(self, value: WorkflowStatus) -> None: ...

    @property
    def nodes(self) -> Dict[str, NodeProtocol]: ...

    @property
    def context(self) -> Dict[str, Any]: ...

    def add_node(self, node: NodeProtocol) -> None: ...

    def get_ready_nodes(self) -> List[NodeProtocol]: ...

    async def execute(self) -> Dict[str, Any]: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def cancel(self) -> None: ...


class WorkflowExecutorProtocol(Protocol):
    """Protocol for workflow executors."""

    async def execute_workflow(self, workflow: WorkflowProtocol) -> Dict[str, Any]: ...

    async def execute_node(self, node: NodeProtocol, context: Dict[str, Any]) -> Dict[str, Any]: ...

    def pause_workflow(self, workflow_id: str) -> None: ...

    def resume_workflow(self, workflow_id: str) -> None: ...

    def cancel_workflow(self, workflow_id: str) -> None: ...


# ────────────────────────────────
# Optional Extensions for Team Flow Features
# ────────────────────────────────


class FlowTeamProtocol(TeamProtocol, Protocol):
    """Extended team protocol for flow system with coordinator support."""

    def get_task_status(self, task_id: str) -> Optional[Tuple[TaskStatus, str]]: ...

    def collect_result(self, task_id: str) -> Optional[Any]: ...

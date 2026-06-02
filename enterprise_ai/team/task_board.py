from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from enterprise_ai.memory.team import TeamMemory


class TaskStatus(str, Enum):
    pending = "pending"
    claimed = "claimed"
    done = "done"
    failed = "failed"


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    posted_by: str = ""
    claimed_by: str | None = None
    status: TaskStatus = TaskStatus.pending
    result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_at: datetime | None = None
    completed_at: datetime | None = None

    def __str__(self) -> str:
        claimer = f" → {self.claimed_by}" if self.claimed_by else ""
        return f"[{self.status.value.upper()}] {self.title}{claimer} (#{self.id[:8]})"


class TaskBoard:
    """
    Shared task queue for a team of agents.

    Any agent can post a task. Any agent can claim a pending task.
    Claimed tasks are owned by the claiming agent until completed or failed.

    This replaces a central orchestrator: instead of a manager telling
    each agent what to do, agents check the board and claim work autonomously.
    """

    def __init__(self, memory: TeamMemory | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._memory = memory

    async def post(self, title: str, description: str, posted_by: str, **metadata: Any) -> Task:
        task = Task(title=title, description=description, posted_by=posted_by, metadata=metadata)
        async with self._lock:
            self._tasks[task.id] = task
        self._event.set()
        self._event.clear()
        return task

    async def claim(self, task_id: str, agent_id: str) -> Task | None:
        """Claim a pending task. Returns None if already claimed or not found."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.pending:
                return None
            task.status = TaskStatus.claimed
            task.claimed_by = agent_id
            task.claimed_at = datetime.now(timezone.utc)
            return task

    async def claim_next(self, agent_id: str, timeout: float | None = None) -> Task | None:
        """Claim the next available pending task. Waits up to timeout seconds."""
        deadline = asyncio.get_event_loop().time() + (timeout or 0)
        while True:
            async with self._lock:
                for task in self._tasks.values():
                    if task.status == TaskStatus.pending:
                        task.status = TaskStatus.claimed
                        task.claimed_by = agent_id
                        task.claimed_at = datetime.now(timezone.utc)
                        return task
            if timeout is None:
                return None
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                return None
            try:
                await asyncio.wait_for(asyncio.shield(self._event.wait()), timeout=min(remaining, 1.0))
            except asyncio.TimeoutError:
                pass

    async def complete(self, task_id: str, result: str = "") -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.claimed:
                return False
            task.status = TaskStatus.done
            task.result = result
            task.completed_at = datetime.now(timezone.utc)
        if self._memory is not None and task is not None:
            content = f"Task completed: {task.title}\n\nResult: {result}"
            await self._memory.write(content=content, source="task", agent_id=task.claimed_by or "", task_id=task_id, title=task.title)
        return True

    async def fail(self, task_id: str, reason: str = "") -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != TaskStatus.claimed:
                return False
            task.status = TaskStatus.failed
            task.result = reason
            task.completed_at = datetime.now(timezone.utc)
        if self._memory is not None and task is not None:
            content = f"Task failed: {task.title}\n\nReason: {reason}"
            await self._memory.write(content=content, source="task", agent_id=task.claimed_by or "", task_id=task_id, title=task.title)
        return True

    def pending_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.pending]

    def tasks_by(self, agent_id: str) -> list[Task]:
        return [t for t in self._tasks.values() if t.claimed_by == agent_id]

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def all(self) -> list[Task]:
        return list(self._tasks.values())

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for t in self._tasks.values():
            counts[t.status.value] = counts.get(t.status.value, 0) + 1
        return " | ".join(f"{s}: {n}" for s, n in counts.items()) or "empty"

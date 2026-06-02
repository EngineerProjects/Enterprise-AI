from __future__ import annotations

import asyncio
from typing import Callable

from enterprise_ai.sandbox.base import Sandbox

SandboxFactory = Callable[[], Sandbox]


class SandboxManager:
    """
    Manages the lifecycle of multiple sandboxes.

    Each agent gets its own sandbox. The manager ensures all sandboxes
    are properly stopped when the manager is closed, even on errors.

    Usage:
        manager = SandboxManager(factory=lambda: LocalSandbox(working_dir=tmpdir))
        sb = await manager.acquire(agent_id="agent-1")
        await sb.exec("ls")
        await manager.release("agent-1")
        await manager.close()  # stops all remaining sandboxes
    """

    def __init__(self, factory: SandboxFactory | None = None) -> None:
        self._factory = factory
        self._sandboxes: dict[str, Sandbox] = {}
        self._lock = asyncio.Lock()

    def set_factory(self, factory: SandboxFactory) -> None:
        self._factory = factory

    async def acquire(self, agent_id: str, factory: SandboxFactory | None = None) -> Sandbox:
        async with self._lock:
            if agent_id in self._sandboxes:
                return self._sandboxes[agent_id]

            fn = factory or self._factory
            if fn is None:
                raise RuntimeError("No sandbox factory configured")

            sandbox = fn()
            await sandbox.start()
            self._sandboxes[agent_id] = sandbox
            return sandbox

    async def release(self, agent_id: str) -> None:
        async with self._lock:
            sandbox = self._sandboxes.pop(agent_id, None)
        if sandbox is not None:
            await sandbox.stop()

    async def close(self) -> None:
        async with self._lock:
            ids = list(self._sandboxes.keys())
        await asyncio.gather(*[self.release(aid) for aid in ids], return_exceptions=True)

    def get(self, agent_id: str) -> Sandbox | None:
        return self._sandboxes.get(agent_id)

    def __len__(self) -> int:
        return len(self._sandboxes)

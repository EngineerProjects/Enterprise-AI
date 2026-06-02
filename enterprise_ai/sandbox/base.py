from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecResult:
    output: str
    exit_code: int
    timed_out: bool = False

    @property
    def error(self) -> bool:
        return self.exit_code != 0 or self.timed_out


class Sandbox(ABC):
    """Base contract for all sandbox backends."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def exec(self, command: str, timeout: float = 30.0) -> ExecResult: ...

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None: ...

    @abstractmethod
    async def read_file(self, path: str) -> str: ...

    async def __aenter__(self) -> Sandbox:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()

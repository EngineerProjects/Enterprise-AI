from __future__ import annotations

from enterprise_ai.schema import ToolSchema
from enterprise_ai.tools.contract import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all(self) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.is_available()]

    def schemas(self) -> list[ToolSchema]:
        return [t.to_schema() for t in self._tools.values() if t.is_available()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

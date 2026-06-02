from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from enterprise_ai.schema import ToolResult, ToolSchema

if TYPE_CHECKING:
    from enterprise_ai.tools.context import ToolContext


class BaseTool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]

    @abstractmethod
    async def call(self, input: Any, ctx: ToolContext) -> ToolResult:
        # input is typed as Any here so mypy doesn't complain about concrete subclasses
        # using their specific input type (e.g. BashInput). At runtime, parse_input
        # guarantees the correct type is passed.
        ...

    def is_enabled(self, ctx: ToolContext) -> bool:
        return True

    def is_concurrency_safe(self) -> bool:
        return True

    def to_schema(self) -> ToolSchema:
        schema = self.input_schema.model_json_schema()
        schema.pop("title", None)
        return ToolSchema(name=self.name, description=self.description, input_schema=schema)

    def parse_input(self, raw: dict[str, Any]) -> BaseModel:
        return self.input_schema.model_validate(raw)

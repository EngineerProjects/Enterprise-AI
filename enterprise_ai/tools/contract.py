from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel

from enterprise_ai.schema import ToolResult, ToolSchema

if TYPE_CHECKING:
    from enterprise_ai.tools.context import ToolContext


class BaseTool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]

    # Optional availability gate evaluated at registry query time.
    # Return False to hide this tool from the LLM when a dependency is missing
    # (e.g. missing API key, unavailable binary, disabled feature flag).
    # None means always available.
    check_fn: Callable[[], bool] | None = None

    @abstractmethod
    async def call(self, input: Any, ctx: ToolContext) -> ToolResult:
        # input is typed as Any here so mypy doesn't complain about concrete subclasses
        # using their specific input type (e.g. BashInput). At runtime, parse_input
        # guarantees the correct type is passed.
        ...

    def is_enabled(self, ctx: ToolContext) -> bool:
        return True

    def is_available(self) -> bool:
        """Return False when check_fn indicates the tool's dependency is unavailable."""
        return self.check_fn is None or self.check_fn()

    def is_deferrable(self) -> bool:
        """
        Return True if this tool can be deferred behind the tool search bridge.

        Deferrable tools are hidden from the LLM context when the registry
        exceeds the token threshold, and are only accessible via tool_search /
        tool_describe / tool_call. MCPTool overrides this to return True.
        """
        return False

    def is_concurrency_safe(self) -> bool:
        return True

    def to_schema(self) -> ToolSchema:
        schema = self.input_schema.model_json_schema()
        schema.pop("title", None)
        return ToolSchema(name=self.name, description=self.description, input_schema=schema)

    def parse_input(self, raw: dict[str, Any]) -> BaseModel:
        return self.input_schema.model_validate(raw)

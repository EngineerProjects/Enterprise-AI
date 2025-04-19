"""
Tool result definitions for Enterprise AI.

This module defines the classes for representing tool execution results.
"""

from typing import Any, Optional, Union, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T", bound="ToolResult")


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self) -> bool:
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult") -> "ToolResult":
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ) -> Optional[str]:
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self) -> str:
        return f"Error: {self.error}" if self.error else str(self.output)

    def replace(self, **kwargs: Any) -> "ToolResult":
        """Returns a new ToolResult with the given fields replaced."""
        return type(self)(**{**self.dict(), **kwargs})


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""

    pass


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""

    pass

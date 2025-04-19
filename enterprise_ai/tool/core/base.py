"""
Base tool definitions for Enterprise AI.

This module defines the abstract base classes for all tools in the framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from enterprise_ai.exceptions import EnterpriseAIError


class ToolError(EnterpriseAIError):
    """Error raised by tools during execution."""

    def __init__(self, message: str = "Tool execution error") -> None:
        self.message = message
        super().__init__(self.message)


class BaseTool(ABC, BaseModel):
    """Base class for all tools in Enterprise AI."""

    name: str
    description: str
    parameters: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters."""
        pass

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

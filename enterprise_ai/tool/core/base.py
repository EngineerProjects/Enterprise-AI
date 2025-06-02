"""
Base tool definitions for Enterprise AI.

This module defines the abstract base classes for all tools in the framework,
including enhanced capabilities, versioning, and lifecycle management.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Callable

from pydantic import BaseModel, Field, field_validator

from enterprise_ai.exceptions import EnterpriseAIError


class ToolState(str, Enum):
    """Enum representing the possible states of a tool."""

    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    TERMINATED = "terminated"


class ToolCapability(str, Enum):
    """Enum representing common tool capabilities."""

    FILE_ACCESS = "file_access"
    NETWORK_ACCESS = "network_access"
    CODE_EXECUTION = "code_execution"
    API_ACCESS = "api_access"
    DATA_PROCESSING = "data_processing"
    IMAGE_PROCESSING = "image_processing"
    TEXT_GENERATION = "text_generation"
    VECTOR_DB = "vector_db"
    AGENT_INTERACTION = "agent_interaction"
    BROWSER_CONTROL = "browser_control"
    TERMINAL_ACCESS = "terminal_access"
    PLANNING = "planning"
    SEARCH = "search"
    UTILITY = "utility"


class ToolConfig(BaseModel):
    """Configuration for tool instances."""

    timeout: Optional[float] = Field(default=60.0, description="Maximum execution time in seconds")
    max_retries: Optional[int] = Field(default=3, description="Maximum number of retry attempts")
    cache_results: Optional[bool] = Field(
        default=False, description="Whether to cache results of tool execution"
    )
    cache_ttl: Optional[int] = Field(
        default=300, description="Time-to-live for cached results in seconds"
    )
    sandbox_enabled: Optional[bool] = Field(
        default=True, description="Whether to run the tool in a sandbox environment"
    )
    custom_config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: dict(), description="Tool-specific configuration parameters"
    )

    @field_validator("timeout")
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        """Validate the timeout value."""
        if v is not None and v <= 0:
            raise ValueError("Timeout must be positive")
        return v

    @field_validator("max_retries")
    def validate_max_retries(cls, v: Optional[int]) -> Optional[int]:
        """Validate the max_retries value."""
        if v is not None and v < 0:
            raise ValueError("Max retries cannot be negative")
        return v


class ToolError(EnterpriseAIError):
    """Error raised by tools during execution."""

    def __init__(
        self, message: str = "Tool execution error", error_code: Optional[str] = None
    ) -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class BaseTool(ABC, BaseModel):
    """
    Base class for all tools in Enterprise AI.

    Enhanced with capabilities, versioning, and lifecycle management.
    Uses unified result system to eliminate redundancy.
    """

    name: str = Field(description="Unique name of the tool")
    description: str = Field(description="Human-readable description of what the tool does")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON Schema of parameters required by the tool"
    )
    version: str = Field(default="1.0.0", description="Semantic version of the tool implementation")
    capabilities: Set[Union[str, ToolCapability]] = Field(
        default_factory=set, description="Set of capabilities this tool provides"
    )
    config: ToolConfig = Field(default_factory=ToolConfig, description="Tool configuration")
    state: ToolState = Field(default=ToolState.IDLE, description="Current state of the tool")
    requires_initialization: bool = Field(
        default=False, description="Whether this tool requires explicit initialization before use"
    )
    usage_examples: List[Dict[str, Any]] = Field(
        default_factory=list, description="Examples of how to use this tool"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="List of other tools this tool depends on"
    )
    authorization_required: bool = Field(
        default=False, description="Whether this tool requires authorization"
    )
    last_execution_time: Optional[float] = Field(default=None, exclude=True)
    execution_count: int = Field(default=0, exclude=True)
    on_state_change: List[Callable[[ToolState], None]] = Field(default_factory=list, exclude=True)

    model_config = {"arbitrary_types_allowed": True, "populate_by_name": True}

    def __init__(self, **data: Any) -> None:
        """Initialize the tool with provided data."""
        super().__init__(**data)
        # Initialize private attributes that are not properly handled by pydantic
        self._on_state_change: List[Callable[[ToolState], None]] = []
        self._execution_count: int = 0
        self._last_execution_time: Optional[float] = None
        self._validate_capabilities()

    def _validate_capabilities(self) -> None:
        """Validate that all capabilities are valid."""
        valid_capabilities = {item.value for item in ToolCapability}
        invalid_capabilities = [
            cap
            for cap in self.capabilities
            if isinstance(cap, str) and cap not in valid_capabilities
        ]
        if invalid_capabilities:
            raise ValueError(f"Invalid capabilities: {', '.join(invalid_capabilities)}")

    def register_state_change_handler(self, handler: Callable[[ToolState], None]) -> None:
        """Register a handler to be called when the tool's state changes."""
        if handler not in self._on_state_change:
            self._on_state_change.append(handler)

    def unregister_state_change_handler(self, handler: Callable[[ToolState], None]) -> None:
        """Unregister a state change handler."""
        if handler in self._on_state_change:
            self._on_state_change.remove(handler)

    def _update_state(self, new_state: ToolState) -> None:
        """Update the tool's state and notify handlers."""
        _ = self.state  # Old state
        self.state = new_state

        # Notify handlers of state change
        for handler in self._on_state_change:
            try:
                handler(new_state)
            except Exception as e:
                # Log error but don't propagate
                import logging

                logging.error(f"Error in state change handler: {e}")

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize the tool if required.

        Args:
            **kwargs: Tool-specific initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        if not self.requires_initialization:
            return True

        # Default implementation does nothing, but subclasses can override
        return True

    async def __call__(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters."""
        from enterprise_ai.tool.core.result import ToolResult, ToolFailure
        
        self._update_state(ToolState.RUNNING)
        try:
            self._execution_count += 1
            import time

            self._last_execution_time = time.time()
            result = await self.execute(**kwargs)
            self._update_state(ToolState.IDLE)
            
            # Ensure we return a ToolResult
            if not isinstance(result, ToolResult):
                return ToolResult.create_success(
                    result=result,
                    tool_name=self.name
                )
            return result
        except Exception as e:
            self._update_state(ToolState.ERROR)
            if isinstance(e, ToolError):
                return ToolFailure.create(error=str(e), tool_name=self.name)
            return ToolFailure.create(error=str(e), tool_name=self.name)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters."""
        pass

    async def cleanup(self) -> None:
        """
        Clean up any resources used by the tool.

        This method should be called when the tool is no longer needed.
        """
        self._update_state(ToolState.TERMINATED)
        # Default implementation does nothing, but subclasses can override

    def to_param(self) -> Dict[str, Any]:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {},
            },
        }

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for this tool."""
        return {
            "executions": self._execution_count,
            "last_execution": self._last_execution_time,
            "state": self.state,
        }

    def has_capability(self, capability: Union[str, ToolCapability]) -> bool:
        """Check if this tool has a specific capability."""
        if isinstance(capability, ToolCapability):
            capability = capability.value
        return capability in self.capabilities

    def get_usage_example(self, index: int = 0) -> Optional[Dict[str, Any]]:
        """Get a usage example for this tool."""
        if not self.usage_examples or index >= len(self.usage_examples):
            return None
        return self.usage_examples[index]

    def add_usage_example(self, example: Dict[str, Any]) -> None:
        """Add a usage example for this tool."""
        self.usage_examples.append(example)
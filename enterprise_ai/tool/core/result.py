"""
Unified tool result system for Enterprise AI.

This module provides result classes that are compatible with both the core tool system
and the LLM integration system, eliminating redundancy.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import json
import uuid

from pydantic import BaseModel, Field

# Import the schema ToolResult as the base
from enterprise_ai.schema.tool import ToolResult as SchemaToolResult


class ToolResultMetadata(BaseModel):
    """Enhanced metadata for tool execution results."""

    execution_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this execution",
    )
    start_time: Optional[datetime] = Field(
        default_factory=datetime.now, description="Time when execution started"
    )
    end_time: Optional[datetime] = Field(default=None, description="Time when execution completed")
    tool_name: Optional[str] = Field(
        default=None, description="Name of the tool that produced this result"
    )
    tool_version: Optional[str] = Field(
        default=None, description="Version of the tool that produced this result"
    )
    cache_hit: bool = Field(
        default=False, description="Whether this result was retrieved from cache"
    )
    session_id: Optional[str] = Field(
        default=None, description="ID of the session that produced this result"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters used for this execution"
    )

    def complete(self) -> "ToolResultMetadata":
        """Mark as complete and calculate execution time."""
        self.end_time = datetime.now()
        return self

    def get_execution_time(self) -> Optional[float]:
        """Get execution time in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class ToolResult(SchemaToolResult):
    """
    Unified ToolResult that extends the schema version with additional core features.
    
    This eliminates redundancy by using the schema ToolResult as the base
    and adding only the additional features needed by the core system.
    """
    
    # Additional fields for core functionality
    base64_image: Optional[str] = Field(
        default=None, description="Base64-encoded image data if the result includes an image"
    )
    system_message: Optional[str] = Field(
        default=None, description="System message related to the execution"
    )
    result_type: Optional[str] = Field(default=None, description="Type of the result data")
    enhanced_metadata: Optional[ToolResultMetadata] = Field(
        default=None, description="Enhanced metadata for core tool usage"
    )

    def __init__(self, **data: Any) -> None:
        # Handle legacy 'output' parameter by mapping it to 'result'
        if 'output' in data and 'result' not in data:
            data['result'] = data.pop('output')
        
        # Handle system -> system_message mapping
        if 'system' in data and 'system_message' not in data:
            data['system_message'] = data.pop('system')
            
        super().__init__(**data)

    @property
    def output(self) -> Any:
        """Backward compatibility property."""
        return self.result

    @output.setter
    def output(self, value: Any) -> None:
        """Backward compatibility setter."""
        self.result = value

    def complete(self) -> "ToolResult":
        """Mark the execution as complete and calculate execution time."""
        if self.enhanced_metadata:
            self.enhanced_metadata.complete()
            # Update execution_time from enhanced metadata
            exec_time = self.enhanced_metadata.get_execution_time()
            if exec_time is not None:
                self.execution_time = exec_time
        return self

    def set_tool_info(self, tool_name: str, tool_version: str = "1.0.0") -> "ToolResult":
        """Set tool information in the metadata."""
        if self.enhanced_metadata is None:
            self.enhanced_metadata = ToolResultMetadata()
        self.enhanced_metadata.tool_name = tool_name
        self.enhanced_metadata.tool_version = tool_version
        
        # Also set in the base metadata for consistency
        self.name = tool_name
        
        return self

    def to_display_format(self) -> str:
        """Convert result to a display-friendly format."""
        if not self.success and self.error:
            return f"Error: {self.error}"
        elif self.result is not None:
            if isinstance(self.result, str):
                return self.result
            elif isinstance(self.result, (dict, list)):
                return json.dumps(self.result, indent=2, default=str)
            else:
                return str(self.result)
        else:
            return "No output"

    @classmethod
    def from_exception(cls, exception: Exception, context: Optional[str] = None) -> "ToolResult":
        """Create a ToolResult from an exception."""
        error_message = f"{type(exception).__name__}: {str(exception)}"
        if context:
            error_message = f"{context}: {error_message}"

        result = cls(
            tool_call_id="",
            name=context or "unknown",
            result="",
            success=False,
            error=error_message,
            enhanced_metadata=ToolResultMetadata()
        )
        result.complete()
        return result

    @classmethod
    def create_success(
        cls,
        result: Any,
        tool_name: str = "unknown",
        tool_call_id: str = "",
        **kwargs: Any
    ) -> "ToolResult":
        """Create a successful ToolResult."""
        return cls(
            tool_call_id=tool_call_id,
            name=tool_name,
            result=result,
            success=True,
            enhanced_metadata=ToolResultMetadata(),
            **kwargs
        )

    @classmethod
    def create_error(
        cls,
        error: str,
        tool_name: str = "unknown", 
        tool_call_id: str = "",
        **kwargs: Any
    ) -> "ToolResult":
        """Create an error ToolResult."""
        return cls(
            tool_call_id=tool_call_id,
            name=tool_name,
            result="",
            success=False,
            error=error,
            enhanced_metadata=ToolResultMetadata(),
            **kwargs
        )


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as CLI output."""

    formatted_output: Optional[str] = Field(
        default=None, description="Formatted output for CLI display"
    )

    def get_display_text(self) -> str:
        """Get formatted text for display in CLI."""
        if self.formatted_output:
            return self.formatted_output
        else:
            return self.to_display_format()


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""

    error_code: Optional[str] = Field(
        default=None, description="Error code for programmatic handling"
    )
    retryable: bool = Field(default=False, description="Whether this failure can be retried")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for resolving the failure"
    )

    def __init__(self, **data: Any) -> None:
        # Ensure this is marked as a failure
        data['success'] = False
        super().__init__(**data)

    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion for resolving the failure."""
        self.suggestions.append(suggestion)

    @classmethod
    def create(
        cls, 
        error: str, 
        tool_name: str = "unknown",
        tool_call_id: str = "",
        error_code: Optional[str] = None, 
        retryable: bool = False
    ) -> "ToolFailure":
        """Create a new ToolFailure with the given error."""
        result = cls(
            tool_call_id=tool_call_id,
            name=tool_name,
            result="",
            error=error,
            error_code=error_code,
            retryable=retryable,
            enhanced_metadata=ToolResultMetadata()
        )
        result.complete()
        return result
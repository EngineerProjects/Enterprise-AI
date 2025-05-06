"""
Tool result definitions for Enterprise AI.

This module defines the classes for representing tool execution results,
with enhanced capabilities for result tracking and validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, TypeVar
import json
import uuid

from pydantic import BaseModel, Field, field_validator


T = TypeVar("T", bound="ToolResult")


class ToolResultMetadata(BaseModel):
    """Metadata for tool execution results."""

    execution_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this execution",
    )
    start_time: datetime = Field(
        default_factory=datetime.now, description="Time when execution started"
    )
    end_time: Optional[datetime] = Field(default=None, description="Time when execution completed")
    execution_time_ms: Optional[float] = Field(
        default=None, description="Execution time in milliseconds"
    )
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
    tags: Set[str] = Field(default_factory=set, description="Tags associated with this execution")


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    output: Any = Field(default=None, description="Output data from the tool execution")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    base64_image: Optional[str] = Field(
        default=None, description="Base64-encoded image data if the result includes an image"
    )
    system: Optional[str] = Field(
        default=None, description="System message related to the execution"
    )
    metadata: Optional[ToolResultMetadata] = Field(
        default=None, description="Metadata about the execution"
    )
    result_type: Optional[str] = Field(default=None, description="Type of the result data")

    class Config:
        arbitrary_types_allowed = True

    @field_validator("metadata", mode="before")
    def set_metadata_default(cls, v):
        """Set default metadata if none is provided."""
        return v or ToolResultMetadata()

    def add_tag(self, tag: str) -> None:
        """Add a tag to the result metadata."""
        if self.metadata is None:
            self.metadata = ToolResultMetadata()
        self.metadata.tags.add(tag)

    def complete(self) -> "ToolResult":
        """Mark the execution as complete and calculate execution time."""
        try:
            if self.metadata:
                self.metadata.end_time = datetime.now()
                if self.metadata.start_time:
                    delta = self.metadata.end_time - self.metadata.start_time
                    self.metadata.execution_time_ms = delta.total_seconds() * 1000
        except Exception as e:
            # If there's an error completing the result, log it but don't crash
            import logging

            logging.warning(f"Error completing tool result: {e}")
        return self

    def set_tool_info(self, tool_name: str, tool_version: str = "1.0.0") -> "ToolResult":
        """Set tool information in the metadata."""
        if self.metadata is None:
            self.metadata = ToolResultMetadata()
        self.metadata.tool_name = tool_name
        self.metadata.tool_version = tool_version
        return self

    def __bool__(self) -> bool:
        """Return True if the result has any content."""
        return self.output is not None or self.error is not None or self.base64_image is not None

    def __add__(self, other: "ToolResult") -> "ToolResult":
        """Combine two tool results."""

        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ) -> Optional[str]:
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        # Create combined metadata
        combined_metadata = None
        if self.metadata or other.metadata:
            if self.metadata and other.metadata:
                # Use the earlier metadata as base and add tags from both
                if self.metadata.start_time and other.metadata.start_time:
                    base_metadata = (
                        self.metadata
                        if self.metadata.start_time <= other.metadata.start_time
                        else other.metadata
                    )
                else:
                    base_metadata = self.metadata or other.metadata

                combined_metadata = ToolResultMetadata(**base_metadata.dict())

                # Combine tags from both
                if self.metadata and self.metadata.tags:
                    combined_metadata.tags.update(self.metadata.tags)
                if other.metadata and other.metadata.tags:
                    combined_metadata.tags.update(other.metadata.tags)

            else:
                combined_metadata = self.metadata or other.metadata

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
            metadata=combined_metadata,
        )

    def __str__(self) -> str:
        """String representation of the result."""
        if self.error:
            return f"Error: {self.error}"
        elif self.output is not None:
            return str(self.output)
        else:
            return "Empty result"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        result = {
            "output": self.output,
            "error": self.error,
            "system": self.system,
        }

        # Add image if present
        if self.base64_image:
            result["has_image"] = True

        # Add metadata if present
        if self.metadata:
            meta_dict = self.metadata.dict()
            # Convert datetime objects to string for JSON serialization
            if meta_dict.get("start_time"):
                meta_dict["start_time"] = meta_dict["start_time"].isoformat()
            if meta_dict.get("end_time"):
                meta_dict["end_time"] = meta_dict["end_time"].isoformat()
            result["metadata"] = meta_dict

        # Add result type if present
        if self.result_type:
            result["result_type"] = self.result_type

        return result

    def to_json(self) -> str:
        """Convert the result to a JSON string."""
        return json.dumps(self.to_dict())

    def replace(self, **kwargs: Any) -> "ToolResult":
        """Return a new ToolResult with the given fields replaced."""
        return self.__class__(**{**self.dict(), **kwargs})

    @classmethod
    def from_exception(cls, exception: Exception, context: Optional[str] = None) -> "ToolResult":
        """Create a ToolResult from an exception."""
        error_message = f"{type(exception).__name__}: {str(exception)}"
        if context:
            error_message = f"{context}: {error_message}"

        result = cls(error=error_message)
        result.complete()
        return result


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""

    formatted_output: Optional[str] = Field(
        default=None, description="Formatted output for CLI display"
    )

    def get_display_text(self) -> str:
        """Get formatted text for display in CLI."""
        if self.formatted_output:
            return self.formatted_output
        elif self.error:
            return f"Error: {self.error}"
        elif self.output is not None:
            return str(self.output)
        else:
            return "No output"


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""

    error_code: Optional[str] = Field(
        default=None, description="Error code for programmatic handling"
    )
    retryable: bool = Field(default=False, description="Whether this failure can be retried")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for resolving the failure"
    )

    def add_suggestion(self, suggestion: str) -> None:
        """Add a suggestion for resolving the failure."""
        self.suggestions.append(suggestion)

    @classmethod
    def create(
        cls, error: str, error_code: Optional[str] = None, retryable: bool = False
    ) -> "ToolFailure":
        """Create a new ToolFailure with the given error."""
        result = cls(error=error, error_code=error_code, retryable=retryable)
        result.complete()
        return result

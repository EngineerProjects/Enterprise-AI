"""
LLM-related schemas for Enterprise AI.

This module defines data models related to LLM configuration and responses.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from enterprise_ai.schema.tool import ToolCall


@dataclass
class CompletionOptions:
    """Options for LLM completion requests."""

    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop: Optional[List[str]] = None
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


class ModelInfo:
    """Information about an LLM model's capabilities and constraints."""

    def __init__(
        self,
        id: str,
        provider: str,
        max_tokens: int,
        features: Optional[Set[str]] = None,
        context_window: Optional[int] = None,
        description: Optional[str] = None,
    ):
        """Initialize model information.

        Args:
            id: Model identifier
            provider: Provider identifier
            max_tokens: Maximum tokens for generation
            features: Set of supported features
            context_window: Maximum context window size
            description: Model description
        """
        self.id = id
        self.provider = provider
        self.max_tokens = max_tokens
        self.features = features or set()
        self.context_window = context_window or max_tokens * 4  # Estimate if not provided
        self.description = description

    def supports_feature(self, feature: str) -> bool:
        """Check if the model supports a specific feature.

        Args:
            feature: Feature to check

        Returns:
            True if the feature is supported, False otherwise
        """
        return feature in self.features

    def to_dict(self) -> Dict[str, Any]:
        """Convert model info to dictionary.

        Returns:
            Dictionary representation of model info
        """
        return {
            "id": self.id,
            "provider": self.provider,
            "max_tokens": self.max_tokens,
            "features": list(self.features),
            "context_window": self.context_window,
            "description": self.description,
        }

class LLMResponse:
    """Represents an LLM response with potential tool calls."""
    
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        finish_reason: Optional[str] = None,
        usage_metadata: Optional[Dict[str, Any]] = None
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage_metadata = usage_metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage_metadata": self.usage_metadata
        }
        
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
            
        return result
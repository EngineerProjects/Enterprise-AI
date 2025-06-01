"""
LLM-related schemas for Enterprise AI.

This module defines data models related to LLM configuration and responses,
enhanced for the new provider architecture.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

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
    timeout: Optional[float] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None and key != "extra_params":
                result[key] = value
        
        # Add extra params
        result.update(self.extra_params)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompletionOptions":
        """Create from dictionary."""
        known_fields = {
            "temperature", "max_tokens", "top_p", "presence_penalty", 
            "frequency_penalty", "stop", "stream", "timeout", "tools", "tool_choice"
        }
        
        kwargs = {}
        extra_params = {}
        
        for key, value in data.items():
            if key in known_fields:
                kwargs[key] = value
            else:
                extra_params[key] = value
        
        kwargs["extra_params"] = extra_params
        return cls(**kwargs)


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
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize model information.

        Args:
            id: Model identifier
            provider: Provider identifier
            max_tokens: Maximum tokens for generation
            features: Set of supported features
            context_window: Maximum context window size
            description: Model description
            metadata: Additional model metadata
        """
        self.id = id
        self.provider = provider
        self.max_tokens = max_tokens
        self.features = features or set()
        self.context_window = context_window or max_tokens * 4  # Estimate if not provided
        self.description = description
        self.metadata = metadata or {}

    def supports_feature(self, feature: str) -> bool:
        """Check if the model supports a specific feature.

        Args:
            feature: Feature to check

        Returns:
            True if the feature is supported, False otherwise
        """
        return feature in self.features

    def supports_any_feature(self, *features: str) -> bool:
        """Check if the model supports any of the given features."""
        return any(feature in self.features for feature in features)

    def supports_all_features(self, *features: str) -> bool:
        """Check if the model supports all of the given features."""
        return all(feature in self.features for feature in features)

    def add_feature(self, feature: str) -> None:
        """Add a feature to the model."""
        self.features.add(feature)

    def remove_feature(self, feature: str) -> None:
        """Remove a feature from the model."""
        self.features.discard(feature)

    def get_effective_max_tokens(self, requested: Optional[int] = None) -> int:
        """Get effective max tokens considering model limits."""
        if requested is None:
            return self.max_tokens
        return min(requested, self.max_tokens)

    def estimate_context_usage(self, prompt_tokens: int, max_completion: Optional[int] = None) -> Dict[str, int]:
        """Estimate context window usage."""
        completion_tokens = max_completion or self.max_tokens
        total_tokens = prompt_tokens + completion_tokens
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "context_window": self.context_window,
            "remaining_context": max(0, self.context_window - total_tokens),
            "context_utilization_pct": min(100, (total_tokens / self.context_window) * 100),
        }

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
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Create ModelInfo from dictionary."""
        features = set(data.get("features", []))
        return cls(
            id=data["id"],
            provider=data["provider"],
            max_tokens=data["max_tokens"],
            features=features,
            context_window=data.get("context_window"),
            description=data.get("description"),
            metadata=data.get("metadata", {}),
        )

    def __str__(self) -> str:
        """String representation."""
        feature_count = len(self.features)
        return f"ModelInfo({self.id} | {self.provider} | {feature_count} features)"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (
            f"ModelInfo(id='{self.id}', provider='{self.provider}', "
            f"max_tokens={self.max_tokens}, features={self.features}, "
            f"context_window={self.context_window})"
        )


class LLMResponse:
    """Represents an LLM response with potential tool calls and metadata."""
    
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        finish_reason: Optional[str] = None,
        usage_metadata: Optional[Dict[str, Any]] = None,
        response_metadata: Optional[Dict[str, Any]] = None,
        is_partial: bool = False,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize LLM response.
        
        Args:
            content: Response content text
            tool_calls: List of tool calls made by the model
            finish_reason: Reason the response finished
            usage_metadata: Token usage and other usage info
            response_metadata: Additional response metadata
            is_partial: Whether this is a partial streaming response
            provider: LLM provider name
            model: Model name
        """
        self.content = content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage_metadata = usage_metadata or {}
        self.response_metadata = response_metadata or {}
        self.is_partial = is_partial
        self.provider = provider
        self.model = model

    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)

    def has_content(self) -> bool:
        """Check if response has content."""
        return bool(self.content)

    def is_complete(self) -> bool:
        """Check if response is complete (not partial)."""
        return not self.is_partial

    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage information."""
        return {
            "prompt_tokens": self.usage_metadata.get("prompt_tokens", 0),
            "completion_tokens": self.usage_metadata.get("completion_tokens", 0),
            "total_tokens": self.usage_metadata.get("total_tokens", 0),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage_metadata": self.usage_metadata,
            "response_metadata": self.response_metadata,
            "is_partial": self.is_partial,
            "provider": self.provider,
            "model": self.model,
        }
        
        if self.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
            
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMResponse":
        """Create from dictionary."""
        tool_calls = []
        if "tool_calls" in data and data["tool_calls"]:
            tool_calls = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]
        
        return cls(
            content=data.get("content"),
            tool_calls=tool_calls,
            finish_reason=data.get("finish_reason"),
            usage_metadata=data.get("usage_metadata", {}),
            response_metadata=data.get("response_metadata", {}),
            is_partial=data.get("is_partial", False),
            provider=data.get("provider"),
            model=data.get("model"),
        )

    def __str__(self) -> str:
        """String representation."""
        content_preview = (self.content or "")[:50]
        if len(content_preview) < len(self.content or ""):
            content_preview += "..."
        
        parts = []
        if self.has_tool_calls():
            parts.append(f"tools:{len(self.tool_calls)}")
        if self.is_partial:
            parts.append("partial")
        if self.provider:
            parts.append(f"provider:{self.provider}")
        
        suffix = f" ({', '.join(parts)})" if parts else ""
        return f"LLMResponse: {content_preview}{suffix}"


@dataclass
class StreamingResponse:
    """Represents a streaming response chunk."""
    
    chunk: LLMResponse
    is_final: bool = False
    chunk_index: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "chunk": self.chunk.to_dict(),
            "is_final": self.is_final,
            "chunk_index": self.chunk_index,
        }

@dataclass
class ProviderInfo:
    """Information about an LLM provider."""
    
    name: str
    description: str
    base_url: Optional[str] = None
    supported_models: List[str] = field(default_factory=list)
    features: Set[str] = field(default_factory=set)
    configuration: Dict[str, Any] = field(default_factory=dict)
    is_available: bool = True
    
    def supports_feature(self, feature: str) -> bool:
        """Check if provider supports a feature."""
        return feature in self.features
    
    def add_model(self, model_name: str) -> None:
        """Add a supported model."""
        if model_name not in self.supported_models:
            self.supported_models.append(model_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "base_url": self.base_url,
            "supported_models": self.supported_models,
            "features": list(self.features),
            "configuration": self.configuration,
            "is_available": self.is_available,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderInfo":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            base_url=data.get("base_url"),
            supported_models=data.get("supported_models", []),
            features=set(data.get("features", [])),
            configuration=data.get("configuration", {}),
            is_available=data.get("is_available", True),
        )


@dataclass  
class ModelCapabilities:
    """Detailed model capabilities information."""
    
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_vision: bool = False
    supports_async: bool = False
    supports_batch: bool = False
    max_context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    supported_formats: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    specializations: List[str] = field(default_factory=list)
    
    def to_feature_set(self) -> Set[str]:
        """Convert capabilities to feature set."""
        features = set()
        if self.supports_streaming:
            features.add("streaming")
        if self.supports_tools:
            features.add("tools")
        if self.supports_vision:
            features.add("vision")
        if self.supports_async:
            features.add("async")
        if self.supports_batch:
            features.add("batch")
        return features
    
    def update_from_features(self, features: Set[str]) -> None:
        """Update capabilities from feature set."""
        self.supports_streaming = "streaming" in features
        self.supports_tools = "tools" in features
        self.supports_vision = "vision" in features
        self.supports_async = "async" in features
        self.supports_batch = "batch" in features
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "supports_streaming": self.supports_streaming,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_async": self.supports_async,
            "supports_batch": self.supports_batch,
            "max_context_window": self.max_context_window,
            "max_output_tokens": self.max_output_tokens,
            "supported_formats": self.supported_formats,
            "languages": self.languages,
            "specializations": self.specializations,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelCapabilities":
        """Create from dictionary."""
        return cls(
            supports_streaming=data.get("supports_streaming", False),
            supports_tools=data.get("supports_tools", False),
            supports_vision=data.get("supports_vision", False),
            supports_async=data.get("supports_async", False),
            supports_batch=data.get("supports_batch", False),
            max_context_window=data.get("max_context_window"),
            max_output_tokens=data.get("max_output_tokens"),
            supported_formats=data.get("supported_formats", []),
            languages=data.get("languages", []),
            specializations=data.get("specializations", []),
        )
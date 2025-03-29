"""
Type definitions specific to the LLM subsystem.

This module extends the core type system with LLM-specific protocols and type
annotations, enabling consistent typing across the LLM components without
creating circular dependencies.
"""

from datetime import datetime
from enum import Enum, auto
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Set,
    TypedDict,
    TypeVar,
    Union,
    runtime_checkable,
)

from enterprise_ai.types import (
    MessageProtocol,
    ToolCallProtocol,
    ProviderProtocol,
    StreamingProviderProtocol,
    Serializable,
)

# Type variables for generic typing
T = TypeVar("T")
P = TypeVar("P", bound=ProviderProtocol)


# -----------------------------------------------------------------------------
# LLM Feature and Capability Types
# -----------------------------------------------------------------------------


class FeatureSupport(str, Enum):
    """Support levels for LLM features."""

    NONE = "none"
    BASIC = "basic"
    FULL = "full"


class ModelCapability(str, Enum):
    """Capabilities that LLM models might support."""

    VISION = "vision"  # Image understanding
    TOOLS = "tools"  # Function/tool calling
    EMBEDDINGS = "embeddings"  # Vector embeddings
    CODE = "code"  # Code generation/comprehension
    RAG = "rag"  # Retrieval augmented generation
    JSON_MODE = "json_mode"  # Structured JSON output
    STREAMING = "streaming"  # Streaming responses


# Mode enumerations for different LLM settings
class ResponseFormat(str, Enum):
    """Response format options for LLM requests."""

    TEXT = "text"  # Default text completion
    JSON = "json"  # JSON mode
    XML = "xml"  # XML formatting
    MARKDOWN = "markdown"  # Markdown formatting


class TokenUsage(TypedDict, total=False):
    """Token usage information for an LLM request."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# -----------------------------------------------------------------------------
# LLM Response Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class LLMResponseProtocol(Protocol):
    """Protocol for LLM responses."""

    message: MessageProtocol
    usage: TokenUsage
    model: str
    provider_id: str
    provider_type: str
    created_at: datetime
    finish_reason: Optional[str]
    response_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        ...


@runtime_checkable
class StreamChunkProtocol(Protocol):
    """Protocol for streaming response chunks."""

    delta: Dict[str, Any]
    response_id: str
    model: str
    provider_id: str
    provider_type: str
    created_at: datetime
    finish_reason: Optional[str]
    index: int
    is_last: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        ...


# -----------------------------------------------------------------------------
# Provider Configuration Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class LLMCredentialsProtocol(Protocol):
    """Protocol for LLM provider credentials."""

    api_key: Optional[str]
    api_base: Optional[str]
    api_version: Optional[str]
    organization: Optional[str]

    def is_valid(self) -> bool:
        """Check if the credentials are valid."""
        ...

    def get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests."""
        ...


@runtime_checkable
class ModelParametersProtocol(Protocol):
    """Protocol for LLM model parameters."""

    temperature: float
    max_tokens: Optional[int]
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    response_format: Optional[ResponseFormat]
    stop_sequences: Optional[List[str]]

    def to_provider_dict(self, provider_type: str) -> Dict[str, Any]:
        """Convert to provider-specific parameter dictionary."""
        ...


# -----------------------------------------------------------------------------
# Token Management Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class TokenizerProtocol(Protocol):
    """Protocol for tokenizers."""

    def encode(self, text: str) -> List[int]:
        """Encode text to tokens."""
        ...

    def decode(self, tokens: List[int]) -> str:
        """Decode tokens to text."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text."""
        ...

    def count_message_tokens(self, messages: List[MessageProtocol]) -> int:
        """Count tokens in a list of messages."""
        ...


@runtime_checkable
class TokenCounterProtocol(Protocol):
    """Protocol for token counters with provider-specific logic."""

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text."""
        ...

    def count_message_tokens(self, messages: List[MessageProtocol]) -> int:
        """Count tokens in a list of messages."""
        ...

    def get_max_tokens(self, model: str) -> int:
        """Get the maximum token limit for a model."""
        ...


# -----------------------------------------------------------------------------
# Image Handling Protocols
# -----------------------------------------------------------------------------


class ImageDetail(str, Enum):
    """Image detail levels for vision models."""

    LOW = "low"
    HIGH = "high"
    AUTO = "auto"


@runtime_checkable
class ImageProcessorProtocol(Protocol):
    """Protocol for image processing."""

    def encode_image(self, image_path: str) -> str:
        """Encode an image to base64 string."""
        ...

    def encode_image_bytes(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 string."""
        ...

    def validate_image(self, image_path: str) -> bool:
        """Validate image format and size."""
        ...

    def resize_image(self, image_path: str, max_dim: int) -> bytes:
        """Resize an image to fit within max dimensions."""
        ...


# -----------------------------------------------------------------------------
# Provider Registry and Selection Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ProviderRegistryProtocol(Protocol):
    """Protocol for provider registry."""

    def register_provider(self, provider_type: str, provider_class: type) -> None:
        """Register a provider class."""
        ...

    def get_provider_class(self, provider_type: str) -> Optional[type]:
        """Get provider class by type."""
        ...

    def create_provider(self, provider_type: str, model: str, **kwargs: Any) -> ProviderProtocol:
        """Create a provider instance."""
        ...

    def list_provider_types(self) -> List[str]:
        """List all registered provider types."""
        ...


@runtime_checkable
class ModelRegistryProtocol(Protocol):
    """Protocol for model registry."""

    def register_model(
        self,
        model_id: str,
        provider_type: str,
        context_window: int,
        capabilities: Dict[ModelCapability, FeatureSupport],
    ) -> None:
        """Register a model with its capabilities."""
        ...

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a model."""
        ...

    def find_models_with_capability(
        self, capability: ModelCapability, min_support: FeatureSupport = FeatureSupport.BASIC
    ) -> List[str]:
        """Find models supporting a capability."""
        ...

    def get_context_window(self, model_id: str) -> int:
        """Get context window size for a model."""
        ...


# -----------------------------------------------------------------------------
# LLM Service Types
# -----------------------------------------------------------------------------


# Request and response types for LLM service
class LLMRequest(TypedDict, total=False):
    """Request parameters for the LLM service."""

    messages: List[Dict[str, Any]]
    model: Optional[str]
    provider: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    stop: Optional[List[str]]
    response_format: Optional[Dict[str, str]]
    tools: Optional[List[Dict[str, Any]]]
    tool_choice: Optional[Union[str, Dict[str, str]]]
    user: Optional[str]
    stream: bool


# Callback types for streaming responses
StreamCallback = Callable[[StreamChunkProtocol], None]
AsyncStreamCallback = Callable[[StreamChunkProtocol], Any]  # Any to accommodate coroutines


# -----------------------------------------------------------------------------
# Type Aliases for LLM Operations
# -----------------------------------------------------------------------------

# Provider-specific types
ProviderType = Literal["openai", "anthropic", "ollama", "cohere", "huggingface", "custom"]

# Completion mode types
CompletionMode = Literal["sync", "async", "stream", "stream_async"]

# Tool mode types
ToolMode = Literal["none", "auto", "required"]

# Token counting modes
CountMode = Literal["exact", "approximate"]

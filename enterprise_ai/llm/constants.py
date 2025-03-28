"""
Constants specific to the LLM subsystem.

This module defines only the truly static constants related to the LLM functionality,
while dynamic model information is handled by the model_registry module.
"""

from typing import Dict, Final, List, Set

# -----------------------------------------------------------------------------
# LLM Provider Constants
# -----------------------------------------------------------------------------

# Provider identifiers
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_ANTHROPIC: Final[str] = "anthropic"
PROVIDER_OLLAMA: Final[str] = "ollama"

# Supported providers
SUPPORTED_PROVIDERS: Final[Set[str]] = {
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
}

# -----------------------------------------------------------------------------
# API Path Templates
# -----------------------------------------------------------------------------

# OpenAI API endpoints
OPENAI_CHAT_COMPLETION_PATH: Final[str] = "chat/completions"
OPENAI_EMBEDDINGS_PATH: Final[str] = "embeddings"
OPENAI_IMAGES_PATH: Final[str] = "images/generations"

# Anthropic API endpoints
ANTHROPIC_COMPLETION_PATH: Final[str] = "complete"
ANTHROPIC_MESSAGES_PATH: Final[str] = "messages"

# Ollama API endpoints
OLLAMA_GENERATE_PATH: Final[str] = "api/generate"
OLLAMA_CHAT_PATH: Final[str] = "api/chat"
OLLAMA_TAGS_PATH: Final[str] = "api/tags"
OLLAMA_SHOW_PATH: Final[str] = "api/show"

# -----------------------------------------------------------------------------
# Token Encoding Constants
# -----------------------------------------------------------------------------

# Token encoding formats
TOKEN_ENCODING_CL100K: Final[str] = "cl100k_base"  # For GPT-4, Claude
TOKEN_ENCODING_P50K: Final[str] = "p50k_base"  # For GPT-3
TOKEN_ENCODING_R50K: Final[str] = "r50k_base"  # For earlier models

# Default encodings by provider (fallback when model-specific encoding unknown)
DEFAULT_ENCODINGS: Final[Dict[str, str]] = {
    PROVIDER_OPENAI: TOKEN_ENCODING_CL100K,
    PROVIDER_ANTHROPIC: TOKEN_ENCODING_CL100K,
    PROVIDER_OLLAMA: TOKEN_ENCODING_CL100K,
}

# -----------------------------------------------------------------------------
# Format and Content Constants
# -----------------------------------------------------------------------------

# Maximum sizes for different content types for upload
MAX_IMAGE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_DIMENSION: Final[int] = 8192  # 8K pixels (max for most APIs)
SUPPORTED_IMAGE_FORMATS: Final[Set[str]] = {"jpeg", "jpg", "png", "webp", "gif"}

# Image quality/detail levels
IMAGE_DETAIL_LOW: Final[str] = "low"
IMAGE_DETAIL_HIGH: Final[str] = "high"
IMAGE_DETAIL_AUTO: Final[str] = "auto"

# -----------------------------------------------------------------------------
# Capability Definitions
# -----------------------------------------------------------------------------

# Capability types (used for consistent capability representation)
CAPABILITY_VISION: Final[str] = "vision"
CAPABILITY_TOOLS: Final[str] = "tools"
CAPABILITY_JSON_MODE: Final[str] = "json_mode"
CAPABILITY_STREAMING: Final[str] = "streaming"


# Support level definitions
class SupportLevel:
    """Enum-like class for feature support levels."""

    NONE = 0
    BASIC = 1
    FULL = 2

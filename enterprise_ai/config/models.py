"""
Configuration models for Enterprise AI.

This module defines Pydantic models that represent configuration structures
for different components of the Enterprise AI framework. These models provide
validation, type checking, and default values for configuration options.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Literal

from pydantic import BaseModel, Field, model_validator, validator

from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    DEFAULT_REQUEST_TIMEOUT,
    STREAMING_REQUEST_TIMEOUT,
    DEFAULT_CACHE_TTL,
    MAX_CACHE_SIZE_MB,
    MAX_CACHE_ENTRIES,
    MODEL_CONTEXT_SIZES,
    DEFAULT_MODELS,
    PROVIDER_RATE_LIMITS,
    MAX_RETRIES,
)


# -----------------------------------------------------------------------------
# Path and Directory Configuration
# -----------------------------------------------------------------------------


class PathConfig(BaseModel):
    """Configuration for system paths and directories."""

    # Base directories
    workspace_root: Path = Field(
        default_factory=lambda: Path(os.getcwd()) / "workspace",
        description="Root directory for workspace files",
    )
    logs_dir: Optional[Path] = Field(
        default=None, description="Directory for log files (defaults to workspace_root/logs)"
    )
    cache_dir: Optional[Path] = Field(
        default=None, description="Directory for cache files (defaults to workspace_root/cache)"
    )
    config_dir: Optional[Path] = Field(
        default=None,
        description="Directory for configuration files (defaults to workspace_root/config)",
    )
    templates_dir: Optional[Path] = Field(
        default=None,
        description="Directory for template files (defaults to workspace_root/templates)",
    )

    @model_validator(mode="after")
    def set_default_paths(self) -> "PathConfig":
        """Set default paths based on workspace root."""
        # Set default paths if not explicitly provided
        if self.logs_dir is None:
            self.logs_dir = self.workspace_root / "logs"

        if self.cache_dir is None:
            self.cache_dir = self.workspace_root / "cache"

        if self.config_dir is None:
            self.config_dir = self.workspace_root / "config"

        if self.templates_dir is None:
            self.templates_dir = self.workspace_root / "templates"

        return self

    def ensure_directories_exist(self) -> None:
        """Create all configured directories if they don't exist."""
        self.workspace_root.mkdir(exist_ok=True, parents=True)

        # Check for None before calling mkdir
        if self.logs_dir is not None:
            self.logs_dir.mkdir(exist_ok=True, parents=True)

        if self.cache_dir is not None:
            self.cache_dir.mkdir(exist_ok=True, parents=True)

        if self.config_dir is not None:
            self.config_dir.mkdir(exist_ok=True, parents=True)

        if self.templates_dir is not None:
            self.templates_dir.mkdir(exist_ok=True, parents=True)


# -----------------------------------------------------------------------------
# LLM Configuration Models
# -----------------------------------------------------------------------------


class LLMProviderSettings(BaseModel):
    """Configuration for an LLM provider."""

    model: str = Field(..., description="Model name")
    base_url: Optional[str] = Field(None, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key")
    api_type: str = Field(..., description="Provider type (openai, anthropic, ollama, etc.)")
    api_version: Optional[str] = Field(None, description="API version")
    organization: Optional[str] = Field(None, description="Organization ID (for OpenAI)")

    # Model parameters
    temperature: float = Field(DEFAULT_TEMPERATURE, description="Sampling temperature")
    max_tokens: Optional[int] = Field(DEFAULT_MAX_TOKENS, description="Maximum tokens to generate")
    top_p: float = Field(DEFAULT_TOP_P, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(0.0, description="Frequency penalty")
    presence_penalty: float = Field(0.0, description="Presence penalty")

    # Provider-specific parameters
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Additional parameters")

    @validator("api_key", pre=True)
    def validate_api_key(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Validate API key and check for environment variables."""
        if v is not None:
            return v

        # Look for environment variables based on provider type
        api_type = values.get("api_type", "").lower()
        if api_type == "openai":
            return os.environ.get("OPENAI_API_KEY")
        elif api_type == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")

        return None

    @validator("base_url", pre=True)
    def validate_base_url(cls, v: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Set default base URL based on provider type if not specified."""
        if v is not None:
            return v

        api_type = values.get("api_type", "").lower()
        if api_type == "openai":
            return "https://api.openai.com/v1"
        elif api_type == "anthropic":
            return "https://api.anthropic.com/v1"
        elif api_type == "ollama":
            return "http://localhost:11434"

        return None

    @validator("model", pre=True)
    def validate_model(cls, v: str, values: Dict[str, Any]) -> str:
        """Set default model based on provider type if not specified."""
        if v:
            return v

        api_type = values.get("api_type", "").lower()
        return DEFAULT_MODELS.get(api_type, DEFAULT_MODELS["default"])


class CacheConfig(BaseModel):
    """Configuration for the LLM response cache."""

    use_cache: bool = Field(True, description="Whether to use caching")
    cache_type: Literal["memory", "disk", "hybrid"] = Field(
        "hybrid", description="Type of cache to use"
    )
    ttl: Optional[int] = Field(
        DEFAULT_CACHE_TTL, description="Time-to-live in seconds (None for no expiration)"
    )
    max_size_mb: int = Field(
        MAX_CACHE_SIZE_MB, description="Maximum cache size in MB (for disk cache)"
    )
    cache_dir: Optional[Path] = Field(
        None, description="Directory for cache files (for disk cache)"
    )
    max_entries: int = Field(
        MAX_CACHE_ENTRIES, description="Maximum number of cache entries (for memory cache)"
    )
    promotion_policy: Literal["read", "write", "both"] = Field(
        "both", description="When to promote items from disk to memory in hybrid cache"
    )
    synchronize_writes: bool = Field(
        False, description="Whether to wait for disk writes to complete"
    )
    retention: Optional[str] = Field("7 days", description="How long to retain cache files")


class RequestTimeouts(BaseModel):
    """Timeout configuration for the LLM service."""

    default_timeout: float = Field(
        DEFAULT_REQUEST_TIMEOUT, description="Default timeout for all requests"
    )
    connect_timeout: Optional[float] = Field(None, description="Connection timeout in seconds")
    read_timeout: Optional[float] = Field(None, description="Read timeout in seconds")
    streaming_timeout: Optional[float] = Field(
        STREAMING_REQUEST_TIMEOUT, description="Timeout for streaming requests"
    )
    async_timeout: Optional[float] = Field(None, description="Timeout for async requests")

    @model_validator(mode="after")
    def set_default_timeouts(self) -> "RequestTimeouts":
        """Set default timeouts based on default_timeout if not specified."""
        if self.connect_timeout is None:
            self.connect_timeout = self.default_timeout

        if self.read_timeout is None:
            self.read_timeout = self.default_timeout

        if self.async_timeout is None:
            self.async_timeout = self.default_timeout

        return self

    def as_dict(self) -> Dict[str, float | None]:
        """Convert to dictionary for httpx."""
        return {
            "default": self.default_timeout,
            "connect": self.connect_timeout,
            "read": self.read_timeout,
        }


class ModelSelectionStrategy(BaseModel):
    """Strategy for model selection and fallback."""

    preferred_model: str = Field("", description="Preferred model name")
    fallback_models: Optional[List[str]] = Field(
        None, description="List of fallback models in order of preference"
    )
    auto_fallback: bool = Field(True, description="Whether to automatically suggest fallbacks")
    capability_requirements: Dict[str, bool] = Field(
        default_factory=dict, description="Required capabilities (vision, tools, etc.)"
    )
    max_cost_tier: Optional[int] = Field(
        None, description="Maximum cost tier (1-5, None for no limit)"
    )
    fallback_across_providers: bool = Field(
        False, description="Whether to fallback to different providers"
    )
    provider_preferences: List[str] = Field(
        default_factory=list, description="List of preferred providers in order"
    )


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    max_retries: int = Field(MAX_RETRIES, description="Maximum number of retry attempts")
    initial_delay: float = Field(1.0, description="Initial delay between retries in seconds")
    max_delay: float = Field(60.0, description="Maximum delay between retries in seconds")
    backoff_strategy: Literal["constant", "linear", "exponential", "fibonacci", "jitter"] = Field(
        "exponential", description="Strategy for calculating delay between retries"
    )
    jitter_factor: float = Field(0.25, description="Random factor for jitter strategy (0.0 to 1.0)")
    retry_on_timeout: bool = Field(True, description="Whether to retry on timeout errors")
    retry_on_connection_error: bool = Field(
        True, description="Whether to retry on connection errors"
    )
    retry_on_server_error: bool = Field(True, description="Whether to retry on 5xx server errors")
    retry_on_rate_limit: bool = Field(
        True, description="Whether to retry on rate limit errors (429)"
    )


class OrchestratorConfig(BaseModel):
    """Configuration for request orchestration."""

    max_concurrent_requests: int = Field(10, description="Maximum concurrent requests")
    max_queue_size: int = Field(100, description="Maximum size of the request queue")
    rate_limits: Dict[str, float] = Field(
        default_factory=lambda: PROVIDER_RATE_LIMITS.copy(), description="Rate limits by provider"
    )
    priority_levels: int = Field(4, description="Number of priority levels")
    adaptive_scaling: bool = Field(True, description="Whether to dynamically adjust concurrency")
    max_retries: int = Field(
        MAX_RETRIES, description="Maximum number of retries for failed requests"
    )
    enable_deduplication: bool = Field(True, description="Whether to enable request deduplication")
    deduplication_ttl: float = Field(5.0, description="Time-to-live for deduplication entries")
    enable_circuit_breaker: bool = Field(True, description="Whether to enable circuit breakers")
    circuit_breaker_threshold: int = Field(5, description="Failure threshold for circuit breakers")
    circuit_breaker_timeout: float = Field(
        30.0, description="Recovery timeout for circuit breakers"
    )


class OllamaConfig(BaseModel):
    """Configuration specific to Ollama provider."""

    auto_pull: bool = Field(
        True, description="Whether to automatically pull models if not available"
    )
    timeout: float = Field(900.0, description="Timeout for Ollama operations in seconds")
    fallback_model: str = Field(
        "llama3", description="Fallback model if requested model is unavailable"
    )
    model_cache_size: int = Field(3, description="Maximum number of models to keep loaded")
    connection_pool_size: int = Field(
        10, description="Size of the connection pool for HTTP requests"
    )
    keep_alive: bool = Field(True, description="Whether to keep models loaded in memory")
    strict_validation: bool = Field(
        False, description="Whether to raise an exception if model validation fails"
    )
    host: str = Field("localhost", description="Ollama server host")
    port: int = Field(11434, description="Ollama server port")
    secure: bool = Field(False, description="Whether to use HTTPS for connections")


class LLMServiceConfig(BaseModel):
    """Main configuration for the LLM service."""

    # Provider and model selection
    provider_name: Optional[str] = Field(None, description="Provider to use (default: from config)")
    model_name: Optional[str] = Field(None, description="Model to use (default: from config)")

    # API credentials and endpoints
    api_key: Optional[str] = Field(None, description="API key (overrides provider config)")
    api_base: Optional[str] = Field(None, description="API base URL (overrides provider config)")
    api_version: Optional[str] = Field(None, description="API version (overrides provider config)")
    organization: Optional[str] = Field(None, description="Organization ID (for OpenAI)")

    # Configuration components
    paths: PathConfig = Field(
        default_factory=lambda: PathConfig(), description="Path configuration"
    )
    cache_config: CacheConfig = Field(
        default_factory=lambda: CacheConfig(
            use_cache=True,
            cache_type="hybrid",
            ttl=DEFAULT_CACHE_TTL,
            max_size_mb=MAX_CACHE_SIZE_MB,
            cache_dir=None,
            max_entries=MAX_CACHE_ENTRIES,
            promotion_policy="both",
            synchronize_writes=False,
            retention="7 days",
        ),
        description="Cache configuration",
    )
    retry_config: RetryConfig = Field(
        default_factory=lambda: RetryConfig(
            max_retries=MAX_RETRIES,
            initial_delay=1.0,
            max_delay=60.0,
            backoff_strategy="exponential",
            jitter_factor=0.25,
            retry_on_timeout=True,
            retry_on_connection_error=True,
            retry_on_server_error=True,
            retry_on_rate_limit=True,
        ),
        description="Retry configuration",
    )
    timeouts: RequestTimeouts = Field(
        default_factory=lambda: RequestTimeouts(
            default_timeout=DEFAULT_REQUEST_TIMEOUT,
            connect_timeout=None,
            read_timeout=None,
            streaming_timeout=STREAMING_REQUEST_TIMEOUT,
            async_timeout=None,
        ),
        description="Timeout configuration",
    )
    model_selection: ModelSelectionStrategy = Field(
        default_factory=lambda: ModelSelectionStrategy(
            preferred_model="",
            fallback_models=None,
            auto_fallback=True,
            capability_requirements={},
            max_cost_tier=None,
            fallback_across_providers=False,
            provider_preferences=[],
        ),
        description="Model selection strategy",
    )
    orchestrator_config: OrchestratorConfig = Field(
        default_factory=lambda: OrchestratorConfig(
            max_concurrent_requests=10,
            max_queue_size=100,
            rate_limits=PROVIDER_RATE_LIMITS.copy(),
            priority_levels=4,
            adaptive_scaling=True,
            max_retries=MAX_RETRIES,
            enable_deduplication=True,
            deduplication_ttl=5.0,
            enable_circuit_breaker=True,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=30.0,
        ),
        description="Request orchestration configuration",
    )
    ollama_config: Optional[OllamaConfig] = Field(None, description="Ollama-specific configuration")

    # Model parameters
    temperature: Optional[float] = Field(
        None, description="Model temperature (overrides provider config)"
    )
    max_tokens: Optional[int] = Field(
        None, description="Maximum tokens to generate (overrides provider config)"
    )

    # Service settings
    validate_model: bool = Field(False, description="Whether to validate the model with the API")
    strict_validation: bool = Field(
        False, description="Whether to raise an exception if model doesn't exist"
    )
    connection_pool_size: int = Field(10, description="Size of the connection pool")
    enable_metrics: bool = Field(True, description="Whether to collect metrics")
    log_level: str = Field("INFO", description="Logging level")
    enable_provider_pooling: bool = Field(False, description="Whether to enable provider pooling")
    provider_pool_size: Tuple[int, int] = Field(
        (1, 5), description="Min and max provider pool size"
    )

    @model_validator(mode="after")
    def setup_path_defaults(self) -> "LLMServiceConfig":
        """Set up default paths for cache_dir if not specified."""
        # If cache_dir not explicitly set, use the one from paths
        if (
            self.cache_config
            and self.cache_config.cache_dir is None
            and self.paths.cache_dir is not None
        ):
            self.cache_config.cache_dir = self.paths.cache_dir / "llm"

        # Ensure directories exist
        self.paths.ensure_directories_exist()

        # Create LLM cache directory
        if self.cache_config and self.cache_config.cache_dir is not None:
            self.cache_config.cache_dir.mkdir(exist_ok=True, parents=True)

        return self

    @model_validator(mode="after")
    def set_ollama_defaults(self) -> "LLMServiceConfig":
        """Set default Ollama configuration if needed."""
        # Initialize Ollama config if provider might be Ollama
        provider = self.provider_name or "default"
        if provider.lower() == "ollama" and self.ollama_config is None:
            self.ollama_config = OllamaConfig(
                auto_pull=True,
                timeout=900.0,
                fallback_model="llama3",
                model_cache_size=3,
                connection_pool_size=10,
                keep_alive=True,
                strict_validation=False,
                host="localhost",
                port=11434,
                secure=False,
            )

        return self


# -----------------------------------------------------------------------------
# Provider-Specific Configurations
# -----------------------------------------------------------------------------


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""

    # API details
    api_type: Literal["openai", "azure", "azure_ad"] = Field(
        "openai", description="OpenAI API type"
    )
    api_version: Optional[str] = Field(None, description="API version (required for Azure)")
    deployment_name: Optional[str] = Field(None, description="Deployment name (for Azure)")
    organization: Optional[str] = Field(None, description="Organization ID")

    # Advanced settings
    max_retries: int = Field(3, description="Maximum number of retries")
    timeout: float = Field(60.0, description="Request timeout in seconds")
    default_headers: Dict[str, str] = Field(
        default_factory=dict, description="Default headers to include in requests"
    )


class AnthropicConfig(BaseModel):
    """Anthropic-specific configuration."""

    max_tokens_to_sample: int = Field(1024, description="Maximum number of tokens to sample")
    stop_sequences: List[str] = Field(
        default_factory=list, description="Sequences that will cause the model to stop generating"
    )
    top_k: Optional[int] = Field(
        None, description="Only sample from the top K options for each subsequent token"
    )
    default_headers: Dict[str, str] = Field(
        default_factory=dict, description="Default headers to include in requests"
    )


# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------


class LogConfig(BaseModel):
    """Configuration for the logging system."""

    level: str = Field("INFO", description="Default logging level")
    format: str = Field(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        description="Log message format",
    )
    log_to_console: bool = Field(True, description="Whether to log to console")
    log_to_file: bool = Field(True, description="Whether to log to file")
    log_dir: Optional[Path] = Field(None, description="Directory for log files")
    log_file_name: str = Field("enterprise_ai_{time}.log", description="Log file name pattern")
    rotation: str = Field("10 MB", description="When to rotate log files")
    retention: str = Field("30 days", description="How long to keep log files")
    compression: Optional[str] = Field("zip", description="Compression format for rotated logs")

    @model_validator(mode="after")
    def set_log_dir(self) -> "LogConfig":
        """Set log_dir from PathConfig if not explicitly provided."""
        from enterprise_ai.constants import LOGS_DIR

        if self.log_dir is None:
            # Use constant as fallback since we might not have access to the full config here
            self.log_dir = LOGS_DIR

        return self


# -----------------------------------------------------------------------------
# Main Configuration
# -----------------------------------------------------------------------------


class AppConfig(BaseModel):
    """Main application configuration."""

    # Core components
    paths: PathConfig = Field(
        default_factory=lambda: PathConfig(), description="Path configuration"
    )
    logging: LogConfig = Field(
        default_factory=lambda: LogConfig(
            level="INFO",
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            log_to_console=True,
            log_to_file=True,
            log_dir=None,
            log_file_name="enterprise_ai_{time}.log",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
        ),
        description="Logging configuration",
    )

    # LLM configurations
    llm: Dict[str, LLMProviderSettings] = Field(..., description="LLM configurations")
    llm_service: Optional[LLMServiceConfig] = Field(None, description="LLM service configuration")
    cache_config: Optional[CacheConfig] = Field(None, description="Cache configuration")
    timeouts: Optional[RequestTimeouts] = Field(None, description="Request timeout configuration")
    model_selection: Optional[ModelSelectionStrategy] = Field(
        None, description="Model selection strategy"
    )
    orchestrator_config: Optional[OrchestratorConfig] = Field(
        None, description="Request orchestration configuration"
    )
    ollama_config: Optional[OllamaConfig] = Field(None, description="Ollama-specific configuration")

    # Provider-specific configurations
    openai_config: Optional[OpenAIConfig] = Field(None, description="OpenAI-specific configuration")
    anthropic_config: Optional[AnthropicConfig] = Field(
        None, description="Anthropic-specific configuration"
    )

    # Sandbox configuration
    sandbox_config: Optional[Dict[str, Any]] = Field(None, description="Sandbox configuration")

    @model_validator(mode="after")
    def initialize_service_config(self) -> "AppConfig":
        """Initialize LLM service configuration if not explicitly provided."""
        if self.llm_service is None:
            self.llm_service = LLMServiceConfig(
                provider_name=None,
                model_name=None,
                api_key=None,
                api_base=None,
                api_version=None,
                organization=None,
                ollama_config=None,
                temperature=None,
                max_tokens=None,
                validate_model=False,
                strict_validation=False,
                connection_pool_size=10,
                enable_metrics=True,
                log_level="INFO",
                enable_provider_pooling=False,
                provider_pool_size=(1, 5),
            )

        # Set path-related values
        if self.logging and self.logging.log_dir is None and hasattr(self.paths, "logs_dir"):
            self.logging.log_dir = self.paths.logs_dir

        # Initialize sub-configurations
        if self.cache_config is None:
            self.cache_config = CacheConfig(
                use_cache=True,
                cache_type="hybrid",
                ttl=DEFAULT_CACHE_TTL,
                max_size_mb=MAX_CACHE_SIZE_MB,
                cache_dir=None,
                max_entries=MAX_CACHE_ENTRIES,
                promotion_policy="both",
                synchronize_writes=False,
                retention="7 days",
            )

        if self.timeouts is None:
            self.timeouts = RequestTimeouts(
                default_timeout=DEFAULT_REQUEST_TIMEOUT,
                connect_timeout=None,
                read_timeout=None,
                streaming_timeout=STREAMING_REQUEST_TIMEOUT,
                async_timeout=None,
            )

        if self.model_selection is None:
            self.model_selection = ModelSelectionStrategy(
                preferred_model="",
                fallback_models=None,
                auto_fallback=True,
                capability_requirements={},
                max_cost_tier=None,
                fallback_across_providers=False,
                provider_preferences=[],
            )

        if self.orchestrator_config is None:
            self.orchestrator_config = OrchestratorConfig(
                max_concurrent_requests=10,
                max_queue_size=100,
                rate_limits=PROVIDER_RATE_LIMITS.copy(),
                priority_levels=4,
                adaptive_scaling=True,
                max_retries=MAX_RETRIES,
                enable_deduplication=True,
                deduplication_ttl=5.0,
                enable_circuit_breaker=True,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=30.0,
            )

        return self

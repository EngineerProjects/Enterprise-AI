"""
Shared configuration utilities for Enterprise AI LLM providers.

CREATED: Eliminates configuration duplication across LLM providers
by providing common parameter mapping and validation logic.
"""

import os
from typing import Any, Dict, List, Optional, Union

from enterprise_ai.logger import get_logger

logger = get_logger("llm.shared.config")


class BaseConfigHelper:
    """Base configuration helper with common patterns for all LLM providers."""
    
    # Common parameter names and their types
    COMMON_PARAMS = {
        "temperature": float,
        "max_tokens": int,
        "top_p": float,
        "top_k": int,
        "stream": bool,
        "stop": (str, list),
        "seed": int,
    }
    
    @classmethod
    def validate_common_params(cls, **kwargs: Any) -> Dict[str, Any]:
        """
        Validate common parameters across providers.
        
        Returns:
            Dictionary of validated parameters
        """
        validated = {}
        
        for param_name, param_type in cls.COMMON_PARAMS.items():
            if param_name in kwargs and kwargs[param_name] is not None:
                value = kwargs[param_name]
                
                # Type validation
                if isinstance(param_type, tuple):
                    if not any(isinstance(value, t) for t in param_type):
                        logger.warning(f"Parameter {param_name} should be one of {param_type}, got {type(value)}")
                        continue
                elif not isinstance(value, param_type):
                    try:
                        # Try to convert
                        value = param_type(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Parameter {param_name} should be {param_type}, got {type(value)}")
                        continue
                
                # Range validation for specific parameters
                if param_name == "temperature" and not 0.0 <= value <= 2.0:
                    logger.warning(f"Temperature {value} outside recommended range 0.0-2.0")
                elif param_name == "top_p" and not 0.0 <= value <= 1.0:
                    logger.warning(f"top_p {value} outside valid range 0.0-1.0")
                elif param_name == "max_tokens" and value <= 0:
                    logger.warning(f"max_tokens {value} must be positive")
                    continue
                
                validated[param_name] = value
        
        return validated
    
    @classmethod
    def get_env_config(
        cls, 
        provider_name: str, 
        config_keys: List[str],
        defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get configuration from environment variables with fallbacks.
        
        Args:
            provider_name: Provider name (e.g., "ollama", "openai")
            config_keys: List of configuration keys to look for
            defaults: Default values for keys
            
        Returns:
            Dictionary of configuration values
        """
        defaults = defaults or {}
        config = {}
        
        for key in config_keys:
            # Try provider-specific env var first
            env_key = f"ENTERPRISE_AI_{provider_name.upper()}_{key.upper()}"
            value = os.environ.get(env_key)
            
            # Try generic env var
            if value is None:
                env_key = f"{provider_name.upper()}_{key.upper()}"
                value = os.environ.get(env_key)
            
            # Use default if provided
            if value is None and key in defaults:
                value = defaults[key]
            
            if value is not None:
                # Try to convert to appropriate type
                if key in cls.COMMON_PARAMS:
                    param_type = cls.COMMON_PARAMS[key]
                    try:
                        if isinstance(param_type, tuple):
                            # For union types like (str, list), try string first
                            config[key] = str(value)
                        else:
                            config[key] = param_type(value)
                    except (ValueError, TypeError):
                        config[key] = value
                else:
                    config[key] = value
        
        return config
    
    @classmethod
    def merge_configs(cls, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.
        Later configs override earlier ones.
        """
        merged = {}
        for config in configs:
            if config:
                merged.update(config)
        return merged


class TimeoutHelper:
    """Helper for calculating smart timeouts based on model and request characteristics."""
    
    # Timeout multipliers for different scenarios
    MULTIPLIERS = {
        "vision": 2.0,
        "tools": 1.5,
        "large_model": 1.8,
        "streaming": 0.8,
        "reasoning": 2.5,
    }
    
    # Model size indicators
    LARGE_MODEL_INDICATORS = ["70b", "65b", "180b", "mixtral", "34b", "32b", "405b"]
    VISION_INDICATORS = ["vision", "llava", "bakllava", "moondream", "claude-3", "gpt-4o"]
    REASONING_INDICATORS = ["o1", "o3", "reasoning"]
    
    @classmethod
    def calculate_timeout(
        cls,
        base_timeout: float,
        model_name: str,
        has_images: bool = False,
        has_tools: bool = False,
        is_streaming: bool = False,
        **kwargs: Any
    ) -> float:
        """
        Calculate smart timeout based on request characteristics.
        
        Args:
            base_timeout: Base timeout value
            model_name: Model name to analyze
            has_images: Whether request includes images
            has_tools: Whether request uses tools
            is_streaming: Whether request is streaming
            **kwargs: Additional context
            
        Returns:
            Calculated timeout value
        """
        timeout = base_timeout
        model_lower = model_name.lower()
        
        # Vision model adjustments
        if has_images or any(indicator in model_lower for indicator in cls.VISION_INDICATORS):
            timeout *= cls.MULTIPLIERS["vision"]
        
        # Large model adjustments
        if any(indicator in model_lower for indicator in cls.LARGE_MODEL_INDICATORS):
            timeout *= cls.MULTIPLIERS["large_model"]
        
        # Reasoning model adjustments
        if any(indicator in model_lower for indicator in cls.REASONING_INDICATORS):
            timeout *= cls.MULTIPLIERS["reasoning"]
        
        # Tool calling adjustments
        if has_tools:
            timeout *= cls.MULTIPLIERS["tools"]
        
        # Streaming adjustments (faster response expected)
        if is_streaming:
            timeout *= cls.MULTIPLIERS["streaming"]
        
        # Ensure minimum timeout
        return max(timeout, 10.0)


class ModelCapabilityHelper:
    """Helper for determining model capabilities."""
    
    CAPABILITY_INDICATORS = {
        "vision": ["vision", "llava", "bakllava", "moondream", "claude-3", "gpt-4o"],
        "tools": ["gpt-4", "gpt-3.5", "claude-3", "llama", "mistral", "gemini"],
        "reasoning": ["o1", "o3", "reasoning"],
        "streaming": ["gpt", "claude", "llama", "mistral", "gemini"],
        "multimodal": ["vision", "llava", "bakllava", "moondream", "claude-3", "gpt-4o"],
    }
    
    @classmethod
    def supports_capability(cls, model_name: str, capability: str) -> bool:
        """
        Check if a model supports a specific capability.
        
        Args:
            model_name: Model name to check
            capability: Capability to check for
            
        Returns:
            True if model likely supports the capability
        """
        if capability not in cls.CAPABILITY_INDICATORS:
            return False
        
        model_lower = model_name.lower()
        indicators = cls.CAPABILITY_INDICATORS[capability]
        
        return any(indicator in model_lower for indicator in indicators)
    
    @classmethod
    def get_model_capabilities(cls, model_name: str) -> List[str]:
        """
        Get list of capabilities supported by a model.
        
        Args:
            model_name: Model name to analyze
            
        Returns:
            List of supported capabilities
        """
        capabilities = []
        
        for capability, indicators in cls.CAPABILITY_INDICATORS.items():
            if cls.supports_capability(model_name, capability):
                capabilities.append(capability)
        
        return capabilities


# Convenience functions
def validate_llm_params(**kwargs: Any) -> Dict[str, Any]:
    """Validate common LLM parameters."""
    return BaseConfigHelper.validate_common_params(**kwargs)


def get_smart_timeout(base_timeout: float, model_name: str, **context: Any) -> float:
    """Get smart timeout for a model and context."""
    return TimeoutHelper.calculate_timeout(base_timeout, model_name, **context)


def check_model_capability(model_name: str, capability: str) -> bool:
    """Check if model supports capability."""
    return ModelCapabilityHelper.supports_capability(model_name, capability)

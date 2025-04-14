"""
Base LLM provider implementation.

This module defines the base class for all LLM providers.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Set

from enterprise_ai.constants import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, DEFAULT_TOP_P, ModelFeature
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.base")

class LLMProvider(abc.ABC):
    """
    Base class for LLM providers.
    
    This class defines the interface that all LLM providers must implement.
    """
    
    def __init__(
        self,
        model_name: str,
        **kwargs: Any
    ):
        """
        Initialize the provider.
        
        Args:
            model_name: Name of the model to use
            **kwargs: Additional provider-specific parameters
        """
        self.model_name = model_name
        self.config = kwargs
        
        # Store start time for metrics
        self._start_time = time.time()
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        
        # Initialize model info
        self._model_info = None
    
    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name
    
    @abc.abstractmethod
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion for the given messages.
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion
            
        Returns:
            Generated message
        """
        pass
    
    @abc.abstractmethod
    def get_model_info(self) -> ModelInfo:
        """
        Get information about the model.
        
        Returns:
            ModelInfo object with capabilities and limitations
        """
        if self._model_info is not None:
            return self._model_info
        
        # This should be implemented by subclasses to detect model capabilities
        raise NotImplementedError("Subclasses must implement get_model_info()")
    
    def get_model_features(self) -> Set[str]:
        """
        Get the set of features supported by the model.
        
        Returns:
            Set of feature strings
        """
        return self.get_model_info().features
    
    def supports_feature(self, feature: str) -> bool:
        """
        Check if the model supports a specific feature.
        
        Args:
            feature: Feature to check
            
        Returns:
            True if supported, False otherwise
        """
        return feature in self.get_model_features()
    
    def track_request(self, success: bool) -> None:
        """
        Track request metrics.
        
        Args:
            success: Whether the request was successful
        """
        self._request_count += 1
        if success:
            self._success_count += 1
        else:
            self._error_count += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get usage metrics for this provider.
        
        Returns:
            Dictionary of metrics
        """
        uptime = time.time() - self._start_time
        return {
            "provider": self.__class__.__name__,
            "model": self.model_name,
            "uptime_seconds": uptime,
            "request_count": self._request_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": self._success_count / max(1, self._request_count),
        }
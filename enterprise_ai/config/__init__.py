"""
Configuration system for Enterprise AI.

This module provides a centralized way to manage configuration.
"""

from enterprise_ai.config.base import get_config, load_config

__all__ = ["get_config", "load_config"]
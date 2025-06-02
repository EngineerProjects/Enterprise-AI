"""
Tool-specific constants for Enterprise AI.

This module contains execution modes and other tool-related constants
to avoid circular imports and improve separation of concerns.
"""

from enum import Enum


class ExecutionMode(str, Enum):
    """Enum representing tool execution modes."""
    
    AUTO = "auto"          # Execute immediately without approval
    MANUAL = "manual"      # Require human approval before execution
    HYBRID = "hybrid"      # Safe tools auto-execute, dangerous require approval
    DISABLED = "disabled"  # Tool calls are extracted but never executed


class SandboxMode(str, Enum):
    """Enum representing sandbox execution modes."""
    
    NONE = "none"          # Execute locally without sandbox
    UNIFIED = "unified"    # All tools share one sandbox container
    INDIVIDUAL = "individual"  # Each tool gets its own sandbox
    HYBRID = "hybrid"      # Some tools local, some sandboxed based on capabilities
"""
Team tool integration for Enterprise AI.

This module provides functionality for tool sharing and coordination
between agents within a team, building upon the agent tool system.
"""

from enterprise_ai.team.tools.registry import TeamToolRegistry, ToolAccessLevel, ToolRegistration
from enterprise_ai.team.tools.sharing import (
    ToolSharingPolicy,
    DefaultSharingPolicy,
    HierarchicalSharingPolicy,
    TaskBasedSharingPolicy,
    CapabilityBasedSharingPolicy,
    ToolSharingManager,
    SharingApproval,
    SharingRequest,
)
from enterprise_ai.team.tools.access_control import (
    ToolPermissionFlag,
    ToolAccessRule,
    EnhancedAccessControl,
    EnhancedSharingPolicy,
)

__all__ = [
    # Tool registry
    "TeamToolRegistry",
    "ToolAccessLevel",
    "ToolRegistration",
    
    # Tool sharing
    "ToolSharingPolicy",
    "DefaultSharingPolicy",
    "HierarchicalSharingPolicy",
    "TaskBasedSharingPolicy",
    "CapabilityBasedSharingPolicy",
    "ToolSharingManager",
    "SharingApproval",
    "SharingRequest",
    
    # Enhanced access control
    "ToolPermissionFlag",
    "ToolAccessRule", 
    "EnhancedAccessControl",
    "EnhancedSharingPolicy",
]

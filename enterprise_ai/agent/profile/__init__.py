"""
Enterprise AI Agent Profile Module.

Provides intelligent agent profiling with minimal essential information,
capacity tracking, and smart team collaboration capabilities.
"""

from enterprise_ai.schema.agent_profile import (
    AgentProfile,
    AgentRoleInfo,
    AgentCapacity,
    AgentStatus
)
from enterprise_ai.agent.profile.capacity import (
    CapacityManager,
    CapacityMetrics,
    WorkloadLevel
)
from enterprise_ai.agent.profile.manager import ProfileManager

__all__ = [
    # Core profile classes
    "AgentProfile",
    "AgentRoleInfo", 
    "AgentCapacity",
    "AgentStatus",
    
    # Capacity management
    "CapacityManager",
    "CapacityMetrics",
    "WorkloadLevel",
    
    # Profile management
    "ProfileManager"
]

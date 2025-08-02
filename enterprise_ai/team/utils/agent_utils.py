"""
Shared agent utilities to eliminate code duplication across team module.
"""

from typing import TYPE_CHECKING
from enterprise_ai.team.core.enums import AgentCapacity

if TYPE_CHECKING:
    from enterprise_ai.agent import Agent


class AgentUtilities:
    """Centralized utilities for agent operations - eliminates duplication."""
    
    @staticmethod
    def get_agent_name(agent: 'Agent') -> str:
        """
        Consistent agent name extraction used throughout team module.
        
        For team collaboration, we prioritize the agent name (human-friendly identifier)
        over the profile name (role description). Profile names are used for capabilities.
        
        Args:
            agent: Agent instance
            
        Returns:
            Agent name as string
        """
        # Prioritize agent name for team member identification
        if hasattr(agent, 'name') and agent.name:
            return agent.name
        # Fallback to profile name if agent name not available
        if AgentUtilities.has_valid_profile(agent):
            return agent.profile().name
        return agent.__class__.__name__.lower()
    
    @staticmethod
    def has_valid_profile(agent: 'Agent') -> bool:
        """Check if agent has a valid profile - optimized single check."""
        return hasattr(agent, 'profile') and callable(getattr(agent, 'profile', None))
    
    @staticmethod
    def get_agent_workload(agent: 'Agent') -> float:
        """Get agent's current workload safely."""
        if AgentUtilities.has_valid_profile(agent):
            return agent.profile().capacity.workload
        return 0.0
    
    @staticmethod
    def is_agent_available(agent: 'Agent', max_workload: float = 0.8) -> bool:
        """Check if agent is available for new tasks."""
        if not AgentUtilities.has_valid_profile(agent):
            return True  # Assume available if no profile
        profile = agent.profile()
        return profile.capacity.is_available and profile.capacity.workload <= max_workload
    
    @staticmethod
    def check_availability(capacity: float, current_load: float, status: AgentCapacity, threshold: float = 0.1) -> bool:
        """
        Standardized availability check with configurable threshold.
        
        Args:
            capacity: Agent's total capacity (0.0 to 1.0)
            current_load: Current workload (0.0 to 1.0)
            status: Agent capacity status
            threshold: Minimum available capacity required
            
        Returns:
            True if agent is available for new tasks
        """
        return (capacity - current_load) > threshold and status == AgentCapacity.AVAILABLE
    
    @staticmethod
    def calculate_available_capacity(capacity: float, current_load: float) -> float:
        """
        Calculate available capacity with bounds checking.
        
        Args:
            capacity: Total capacity
            current_load: Current load
            
        Returns:
            Available capacity (0.0 to 1.0)
        """
        return max(0.0, capacity - current_load)

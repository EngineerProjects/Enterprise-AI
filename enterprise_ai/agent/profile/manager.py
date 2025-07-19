"""
Enterprise AI Agent Profile - Profile Manager.

Manages minimal agent profiles with intelligent querying capabilities.
NO hardcoded skills/capabilities - agents derive everything on-demand.
"""

from typing import Dict, List, Optional, Any, Tuple

from enterprise_ai.schema.agent_profile import AgentProfile, AgentRoleInfo, AgentStatus
from enterprise_ai.agent.profile.capacity import CapacityManager, CapacityMetrics
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.profile.manager")


class ProfileManager:
    """
    Manages minimal agent profiles with intelligent capabilities.
    
    Stores only essential profile data. Agents derive skills and capabilities
    on-demand through intelligent querying of role descriptions and available tools.
    """
    
    def __init__(self):
        """Initialize profile manager."""
        self._profiles: Dict[str, AgentProfile] = {}
        self._capacity_manager = CapacityManager()
    
    def create_profile_from_mcp(
        self, 
        name: str, 
        role_name: str,
        role_description: Optional[str],
        mcp,  # MCP instance to get tools
        initial_workload: float = 0.0
    ) -> AgentProfile:
        """
        Create agent profile with automatic tool detection from MCP.
        
        Args:
            name: Agent name
            role_name: Role name
            role_description: Role description
            mcp: MCP instance to detect available tools
            initial_workload: Initial workload (0.0 to 1.0)
            
        Returns:
            Created AgentProfile
        """
        # Get available tools from MCP
        available_tools = mcp.get_available_tools() if mcp else []
        
        # Create profile
        profile = AgentProfile.create(
            name=name,
            role_name=role_name,
            role_description=role_description,
            available_tools=available_tools,
            initial_workload=initial_workload,
            status=AgentStatus.AVAILABLE
        )
        
        # Store profile
        self._profiles[name.lower()] = profile
        
        logger.info(f"Created profile for agent '{name}' with {len(available_tools)} tools")
        return profile
    
    def create_profile(
        self,
        name: str,
        role_name: str,
        role_description: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
        initial_workload: float = 0.0
    ) -> AgentProfile:
        """
        Create agent profile manually.
        
        Args:
            name: Agent name
            role_name: Role name
            role_description: Optional role description
            available_tools: List of available tools
            initial_workload: Initial workload
            
        Returns:
            Created AgentProfile
        """
        profile = AgentProfile.create(
            name=name,
            role_name=role_name,
            role_description=role_description,
            available_tools=available_tools or [],
            initial_workload=initial_workload
        )
        
        self._profiles[name.lower()] = profile
        logger.info(f"Created manual profile for agent '{name}'")
        return profile
    
    def get_profile(self, name: str) -> Optional[AgentProfile]:
        """Get agent profile by name."""
        return self._profiles.get(name.lower())
    
    def get_all_profiles(self) -> List[AgentProfile]:
        """Get all agent profiles."""
        return list(self._profiles.values())
    
    def update_agent_tools(self, name: str, mcp) -> bool:
        """
        Update agent's available tools from current MCP state.
        
        Args:
            name: Agent name
            mcp: Current MCP instance
            
        Returns:
            True if profile was updated, False if agent not found
        """
        profile = self.get_profile(name)
        if not profile:
            return False
        
        # Get current tools from MCP
        current_tools = mcp.get_available_tools() if mcp else []
        old_tools = set(profile.available_tools)
        new_tools = set(current_tools)
        
        # Update tools
        profile.update_tools(current_tools)
        
        # Log changes
        added = new_tools - old_tools
        removed = old_tools - new_tools
        
        if added:
            logger.info(f"Agent '{name}' gained tools: {', '.join(added)}")
        if removed:
            logger.info(f"Agent '{name}' lost tools: {', '.join(removed)}")
        
        return True
    
    def update_capacity(
        self, 
        name: str, 
        workload: Optional[float] = None,
        status: Optional[AgentStatus] = None
    ) -> bool:
        """
        Update agent capacity information.
        
        Args:
            name: Agent name
            workload: New workload (0.0 to 1.0)
            status: New status
            
        Returns:
            True if updated, False if agent not found
        """
        profile = self.get_profile(name)
        if not profile:
            return False
        
        # Track changes for analytics
        old_workload = profile.capacity.workload
        old_status = profile.capacity.status
        
        # Update workload
        if workload is not None:
            profile.capacity.update_workload(workload)
            self._capacity_manager.track_workload_change(name, old_workload, workload)
        
        # Update status
        if status is not None:
            profile.capacity.set_status(status)
            self._capacity_manager.track_status_change(name, old_status, status)
        
        return True
    
    def find_agents_with_tools(self, required_tools: List[str], require_all: bool = False) -> List[AgentProfile]:
        """
        Find agents that have specific tools.
        
        Args:
            required_tools: List of required tool names
            require_all: If True, agent must have ALL tools; if False, ANY tool
            
        Returns:
            List of matching agent profiles, sorted by availability
        """
        matching_agents = []
        
        for profile in self._profiles.values():
            if require_all:
                if profile.has_all_tools(required_tools):
                    matching_agents.append(profile)
            else:
                if profile.has_any_tools(required_tools):
                    matching_agents.append(profile)
        
        # Sort by availability (most available first)
        matching_agents.sort(key=lambda p: p.capacity.workload)
        return matching_agents
    
    def find_agents_with_role(self, role_pattern: str) -> List[AgentProfile]:
        """
        Find agents matching a role pattern.
        
        Args:
            role_pattern: Role name or description pattern to match
            
        Returns:
            List of matching agent profiles, sorted by availability
        """
        matching_agents = []
        
        for profile in self._profiles.values():
            if profile.matches_role_pattern(role_pattern):
                matching_agents.append(profile)
        
        # Sort by availability
        matching_agents.sort(key=lambda p: p.capacity.workload)
        return matching_agents
    
    def find_available_agents(self, max_workload: float = 0.7) -> List[AgentProfile]:
        """
        Find agents available for new tasks.
        
        Args:
            max_workload: Maximum workload to consider available
            
        Returns:
            List of available agent profiles, sorted by workload
        """
        available_agents = [
            profile for profile in self._profiles.values()
            if profile.capacity.is_available and profile.capacity.workload <= max_workload
        ]
        
        # Sort by workload (least loaded first)
        available_agents.sort(key=lambda p: p.capacity.workload)
        return available_agents
    
    def find_best_agent_for_query(
        self, 
        query: str,
        preferred_tools: Optional[List[str]] = None,
        max_workload: float = 0.8
    ) -> Optional[AgentProfile]:
        """
        Find the best agent for a natural language query.
        
        Uses intelligent matching based on role descriptions and tools.
        NO hardcoded skills - derives from actual profile data.
        
        Args:
            query: Natural language description of what's needed
            preferred_tools: Preferred tools for the task
            max_workload: Maximum acceptable workload
            
        Returns:
            Best matching agent profile or None
        """
        candidates = []
        query_lower = query.lower()
        
        for profile in self._profiles.values():
            # Skip overloaded agents
            if profile.capacity.workload > max_workload:
                continue
            
            # Skip unavailable agents
            if not profile.capacity.is_available:
                continue
            
            # Calculate match score based on actual profile data
            score = 0.0
            
            # Role name matching
            if profile.role.name.lower() in query_lower:
                score += 40
            
            # Role description matching (most important)
            if profile.role.description:
                desc_words = profile.role.description.lower().split()
                query_words = query_lower.split()
                matching_words = sum(1 for word in desc_words if word in query_words)
                if matching_words > 0:
                    score += matching_words * 10  # 10 points per matching word
            
            # Tool matching
            if preferred_tools:
                tool_matches = sum(1 for tool in preferred_tools if profile.has_tool(tool))
                score += tool_matches * 15  # 15 points per matching tool
            
            # Available tool relevance to query
            tool_matches = sum(1 for tool in profile.available_tools if tool.lower() in query_lower)
            score += tool_matches * 8  # 8 points per relevant tool
            
            # Availability bonus (lower workload = higher score)
            availability_bonus = (1.0 - profile.capacity.workload) * 10
            score += availability_bonus
            
            if score > 0:
                candidates.append((profile, score))
        
        if not candidates:
            return None
        
        # Sort by score (highest first), then by workload (lowest first)
        candidates.sort(key=lambda x: (-x[1], x[0].capacity.workload))
        
        return candidates[0][0]
    
    def query_team_expertise(self, query: str) -> List[Tuple[AgentProfile, float]]:
        """
        Query team for expertise matching using natural language.
        
        NO hardcoded skills - matches against actual role descriptions and tools.
        
        Args:
            query: Natural language query about needed expertise
            
        Returns:
            List of (agent_profile, relevance_score) tuples, sorted by relevance
        """
        query_lower = query.lower()
        matches = []
        
        for profile in self._profiles.values():
            score = 0.0
            
            # Role name exact match
            if profile.role.name.lower() in query_lower:
                score += 30
            
            # Role description word matching
            if profile.role.description:
                desc_lower = profile.role.description.lower()
                desc_words = desc_lower.split()
                query_words = query_lower.split()
                
                # Direct phrase matching (higher score)
                if any(phrase in desc_lower for phrase in query_words if len(phrase) > 3):
                    score += 25
                
                # Individual word matching
                word_matches = sum(1 for word in desc_words if word in query_words and len(word) > 2)
                score += word_matches * 5
            
            # Tool name matching
            tool_matches = sum(1 for tool in profile.available_tools if tool.lower() in query_lower)
            score += tool_matches * 15
            
            if score > 0:
                matches.append((profile, score))
        
        # Sort by score (highest first)
        matches.sort(key=lambda x: -x[1])
        return matches
    
    def get_team_capacity_metrics(self) -> CapacityMetrics:
        """Get team-wide capacity metrics."""
        profiles = list(self._profiles.values())
        return self._capacity_manager.analyze_team_capacity(profiles)
    
    def get_capacity_recommendations(self) -> List[Dict[str, Any]]:
        """Get recommendations for capacity optimization."""
        profiles = list(self._profiles.values())
        return self._capacity_manager.suggest_workload_optimization(profiles)
    
    def get_agent_capacity_assessment(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed capacity assessment for specific agent."""
        profile = self.get_profile(name)
        if not profile:
            return None
        
        return self._capacity_manager.assess_agent_capacity(profile)
    
    def remove_profile(self, name: str) -> bool:
        """Remove agent profile."""
        name_lower = name.lower()
        if name_lower in self._profiles:
            del self._profiles[name_lower]
            logger.info(f"Removed profile for agent '{name}'")
            return True
        return False
    
    def export_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Export all profiles to minimal dictionary format."""
        return {name: profile.to_dict() for name, profile in self._profiles.items()}
    
    def import_profiles(self, profiles_data: Dict[str, Dict[str, Any]]) -> int:
        """
        Import profiles from dictionary format.
        
        Returns:
            Number of profiles imported
        """
        imported = 0
        for name, data in profiles_data.items():
            try:
                profile = AgentProfile.from_dict(data)
                self._profiles[name.lower()] = profile
                imported += 1
            except Exception as e:
                logger.error(f"Failed to import profile for '{name}': {e}")
        
        logger.info(f"Imported {imported} agent profiles")
        return imported

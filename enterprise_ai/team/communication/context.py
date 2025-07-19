"""
Enterprise AI Team - Team Context Builder.

Automatically builds team awareness context for agent prompts.
"""

from typing import Dict, List, Optional, Any
from enterprise_ai.schema.agent_profile import AgentProfile
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.communication.context")


class TeamContextBuilder:
    """
    Builds team context information for agent prompts.
    
    Automatically generates team member information that gets injected
    into agent system prompts to enable natural @mention communication.
    """
    
    def __init__(self):
        """Initialize team context builder."""
        pass
    
    def build_team_context(self, current_agent_name: str, team_agents: Dict[str, Any]) -> str:
        """
        Build team context string for a specific agent.
        
        Args:
            current_agent_name: Name of the agent receiving the context
            team_agents: Dictionary of agent_name -> agent objects
            
        Returns:
            Team context string to inject into system prompt
        """
        if not team_agents:
            return ""
        
        # Get current agent info
        current_agent = team_agents.get(current_agent_name)
        if not current_agent or not hasattr(current_agent, 'profile') or not current_agent.profile:
            return ""
            
        current_profile = current_agent.profile
        
        # Get other team members (exclude current agent)
        team_members = {
            name: agent for name, agent in team_agents.items()
            if name != current_agent_name and hasattr(agent, 'profile') and agent.profile
        }
        
        if not team_members:
            return ""
        
        # Build context string with personal identity
        context_parts = [
            "\n# YOUR IDENTITY & TEAM COLLABORATION CONTEXT",
            f"Your name is {current_agent_name.title()} and you are a {current_profile.role.name}.",
            f"Role: {current_profile.role.description}",
            f"Your available tools: {', '.join(current_profile.available_tools)}",
            "",
            "You are working as part of a team. Here are your teammates:",
            ""
        ]
        
        for name, agent in team_members.items():
            profile = agent.profile
            
            # Build member info
            status = profile.capacity.status.value
            workload = f"{profile.capacity.workload * 100:.0f}%"
            availability = "🟢 Available" if profile.capacity.is_available else "🔴 Busy"
            
            member_info = [
                f"**@{name}** - {profile.role.name.title()}",
                f"  Role: {profile.role.description}",
                f"  Status: {availability} (Workload: {workload})",
                f"  Tools: {', '.join(profile.available_tools)}"  # Show ALL tools, no truncation
            ]
            
            context_parts.extend(member_info)
            context_parts.append("")
        
        # Add communication guidelines
        context_parts.extend([
            "## Team Communication Guidelines:",
            f"- Always use @agent_name when addressing teammates (e.g., @{list(team_members.keys())[0] if team_members else 'teammate'})",
            "- Use @team to broadcast messages to all team members", 
            "- If you receive a message not intended for you, politely redirect it",
            "- Collaborate naturally and ask for help when needed",
            "- Share relevant findings and insights with the team",
            f"- Remember: Your name is {current_agent_name} - respond only to messages addressed to @{current_agent_name}",
            ""
        ])
        
        return "\n".join(context_parts)
    
    def get_team_member_names(self, team_agents: Dict[str, Any]) -> List[str]:
        """Get list of all team member names."""
        return list(team_agents.keys())
    
    def is_team_member(self, name: str, team_agents: Dict[str, Any]) -> bool:
        """Check if name is a valid team member."""
        return name in team_agents
    
    def get_available_members(self, team_agents: Dict[str, Any]) -> List[str]:
        """Get list of currently available team members."""
        return [
            name for name, agent in team_agents.items()
            if hasattr(agent, 'profile') and agent.profile and agent.profile.capacity.is_available
        ]
    
    def get_members_with_tool(self, tool_name: str, team_agents: Dict[str, Any]) -> List[str]:
        """Get team members who have access to a specific tool."""
        return [
            name for name, agent in team_agents.items()
            if hasattr(agent, 'profile') and agent.profile and agent.profile.has_tool(tool_name)
        ]
    
    def get_members_by_role_pattern(self, pattern: str, team_agents: Dict[str, Any]) -> List[str]:
        """Get team members whose role matches a pattern."""
        pattern_lower = pattern.lower()
        return [
            name for name, agent in team_agents.items()
            if hasattr(agent, 'profile') and agent.profile and agent.profile.matches_role_pattern(pattern_lower)
        ]

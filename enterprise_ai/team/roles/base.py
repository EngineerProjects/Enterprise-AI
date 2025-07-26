"""
Team role base definitions.

Simple role-based behavior using agent profiles.
"""

from abc import ABC, abstractmethod
from enterprise_ai.agent import Agent
from enterprise_ai.team.core import TeamRole, TeamTask


class TeamMember:
    """Base class for team members with capacity management."""
    
    def __init__(self, agent: Agent, role: TeamRole, capacity: float = 1.0):
        self.agent = agent
        self.role = role
        self.capacity = capacity  # 0.0 to 1.0
        self.current_load = 0.0
        
    @property
    def available_capacity(self) -> float:
        """Get available capacity (0.0 to 1.0)."""
        return max(0.0, self.capacity - self.current_load)
    
    @property
    def is_available(self) -> bool:
        """Check if member has capacity for new tasks."""
        return self.available_capacity > 0.1
    
    def update_load(self, load: float) -> None:
        """Update current workload."""
        self.current_load = max(0.0, min(self.capacity, load))


class BaseTeamRole(TeamMember):
    """Base class for team roles."""
    
    def __init__(self, agent: Agent, role: TeamRole):
        super().__init__(agent, role)
        
    def can_handle_task(self, task: TeamTask) -> bool:
        """Check if this role can handle the given task."""
        if not self.is_available:
            return False
        return self._evaluate_task_compatibility(task)
    
    @abstractmethod
    def _evaluate_task_compatibility(self, task: TeamTask) -> bool:
        """Evaluate if role can handle specific task type."""
        pass
    
    @abstractmethod
    async def execute_task(self, task: TeamTask) -> str:
        """Execute assigned task."""
        pass


class SpecialistRole(BaseTeamRole):
    """Specialist role - capabilities determined by agent profile."""
    
    def __init__(self, agent: Agent):
        super().__init__(agent, TeamRole.SPECIALIST)
        
    def _evaluate_task_compatibility(self, task: TeamTask) -> bool:
        """Check if agent has relevant tools for the task."""
        if not hasattr(self.agent, 'profile') or not self.agent.profile:
            return False
            
        available_tools = self.agent.profile.available_tools
        task_description = task.description.lower()
        
        # Simple tool matching based on task content
        tool_keywords = {
            'python': ['code', 'script', 'develop', 'program'],
            'bash': ['command', 'system', 'run'],
            'web_search': ['research', 'search', 'find', 'investigate'],
            'browser': ['web', 'browse', 'navigate', 'website'],
            'file': ['file', 'document', 'read', 'write'],
            'planning': ['plan', 'organize', 'structure', 'design']
        }
        
        # Check if agent has tools relevant to task
        for tool in available_tools:
            tool_lower = tool.lower()
            for tool_type, keywords in tool_keywords.items():
                if tool_type in tool_lower:
                    if any(keyword in task_description for keyword in keywords):
                        return True
        
        return True  # Default: available agents can try tasks
    
    async def execute_task(self, task: TeamTask) -> str:
        """Execute task using agent capabilities."""
        self.current_load += 0.3
        
        try:
            result = await self.agent.process(task.description)
            task.status = "completed"
            return result
            
        except Exception as e:
            task.status = "failed"
            raise e
            
        finally:
            self.current_load = max(0.0, self.current_load - 0.3)

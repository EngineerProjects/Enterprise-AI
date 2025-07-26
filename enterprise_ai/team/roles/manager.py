"""
Manager role implementation.

Simple manager role for team coordination and delegation.
"""

from typing import Dict, Optional
from enterprise_ai.agent import Agent
from enterprise_ai.team.core import TeamRole, TeamTask
from enterprise_ai.team.roles.base import BaseTeamRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.manager")


class ManagerRole(BaseTeamRole):
    """Manager role for team coordination and task delegation."""
    
    def __init__(self, agent: Agent, management_scope: str = "general"):
        super().__init__(agent, TeamRole.MANAGER)
        self.management_scope = management_scope
        self.delegated_tasks: Dict[str, TeamTask] = {}
        
    def _evaluate_task_compatibility(self, task: TeamTask) -> bool:
        """Managers can handle coordination and management tasks."""
        task_type = task.metadata.get('type', '').lower()
        task_desc = task.description.lower()
        
        # Managers handle coordination, planning, and delegation
        management_keywords = ['coordinate', 'manage', 'delegate', 'plan', 'organize', 'lead']
        return any(keyword in task_type or keyword in task_desc for keyword in management_keywords)
    
    async def execute_task(self, task: TeamTask) -> str:
        """Execute management task - coordination and delegation."""
        self.current_load += 0.2
        
        try:
            # For complex tasks, plan delegation strategy
            if self._requires_delegation(task):
                return await self._plan_delegation(task)
            else:
                # Handle simple management tasks directly
                management_prompt = f"As a team manager, handle this task: {task.description}"
                return await self.agent.process(management_prompt)
                
        finally:
            self.current_load = max(0.0, self.current_load - 0.2)
    
    def _requires_delegation(self, task: TeamTask) -> bool:
        """Check if task requires delegation to specialists."""
        technical_keywords = ['code', 'develop', 'research', 'analyze', 'implement', 'build', 'create']
        task_desc = task.description.lower()
        return any(keyword in task_desc for keyword in technical_keywords)
    
    async def _plan_delegation(self, task: TeamTask) -> str:
        """Plan how to delegate task to team members."""
        delegation_prompt = f"""
        As a team manager, plan how to delegate this task: {task.description}
        
        Consider:
        1. What subtasks are needed?
        2. What specialist skills are required?
        3. How should the work be coordinated?
        4. What is the expected timeline?
        
        Provide a delegation plan.
        """
        
        delegation_plan = await self.agent.process(delegation_prompt)
        
        # Track delegated task
        self.delegated_tasks[task.id] = task
        task.status = "delegated"
        
        logger.info(f"Manager planned delegation for task {task.id}")
        return delegation_plan
    
    def get_delegation_status(self) -> Dict[str, str]:
        """Get status of all delegated tasks."""
        return {task_id: task.status for task_id, task in self.delegated_tasks.items()}
    
    def update_task_status(self, task_id: str, status: str) -> bool:
        """Update status of a delegated task."""
        if task_id in self.delegated_tasks:
            self.delegated_tasks[task_id].status = status
            logger.info(f"Updated task {task_id} status to {status}")
            return True
        return False

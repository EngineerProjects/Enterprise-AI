"""
Hierarchical collaboration pattern.

Implements manager-specialist hierarchy for structured team collaboration.
"""

from typing import List, Dict, Optional, Any
import asyncio
from enterprise_ai.team.core import TeamTask, TeamRole, TeamMember
from enterprise_ai.team.roles.manager import ManagerRole
from enterprise_ai.team.roles.base import SpecialistRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.hierarchical")


class HierarchicalCollaboration:
    """Implements hierarchical collaboration with manager oversight."""
    
    def __init__(self):
        self.manager: Optional[ManagerRole] = None
        self.specialists: Dict[str, SpecialistRole] = {}
        self.delegation_tree: Dict[str, List[str]] = {}  # manager_id -> [specialist_ids]
        
    def set_manager(self, manager: ManagerRole) -> None:
        """Set team manager."""
        self.manager = manager
        manager_name = self._get_agent_name(manager.agent)
        self.delegation_tree[manager_name] = []
        logger.info(f"Set hierarchical manager: {manager_name}")
    
    def add_specialist(self, specialist: SpecialistRole) -> None:
        """Add specialist under manager supervision."""
        specialist_name = self._get_agent_name(specialist.agent)
        self.specialists[specialist_name] = specialist
        
        if self.manager:
            manager_name = self._get_agent_name(self.manager.agent)
            self.delegation_tree[manager_name].append(specialist_name)
        
        logger.info(f"Added specialist: {specialist_name} ({specialist.domain})")
    
    async def execute_hierarchical_task(self, task: TeamTask) -> str:
        """Execute task using hierarchical delegation."""
        if not self.manager:
            raise Exception("No manager assigned for hierarchical execution")
        
        # Manager analyzes and breaks down task
        breakdown = await self._manager_task_breakdown(task)
        
        # Execute subtasks through specialists
        if breakdown.get("requires_delegation", False):
            return await self._execute_with_delegation(task, breakdown)
        else:
            # Manager handles directly
            return await self.manager.execute_task(task)
    
    async def _manager_task_breakdown(self, task: TeamTask) -> Dict[str, Any]:
        """Manager analyzes task and creates breakdown."""
        analysis_prompt = f"""
        Analyze this task for hierarchical execution: {task.description}
        
        Available specialists: {list(self.specialists.keys())}
        
        Determine:
        1. Can you handle this directly? (yes/no)
        2. Does it require delegation? (yes/no)
        3. Which specialists would be best suited?
        4. How should the task be broken down?
        
        Respond in a structured format.
        """
        
        analysis = await self.manager.agent.process(analysis_prompt)
        
        # Parse analysis (simplified - in production, use structured parsing)
        requires_delegation = "delegation" in analysis.lower() and "yes" in analysis.lower()
        
        return {
            "requires_delegation": requires_delegation,
            "analysis": analysis,
            "suitable_specialists": self._identify_suitable_specialists(task)
        }
    
    async def _execute_with_delegation(self, task: TeamTask, breakdown: Dict[str, Any]) -> str:
        """Execute task through specialist delegation."""
        suitable_specialists = breakdown["suitable_specialists"]
        
        if not suitable_specialists:
            # No suitable specialists, manager handles directly
            return await self.manager.execute_task(task)
        
        # Create subtasks for specialists
        subtasks = await self._create_subtasks(task, suitable_specialists)
        
        # Execute subtasks concurrently
        results = await self._execute_subtasks_concurrently(subtasks)
        
        # Manager synthesizes results
        synthesis_prompt = f"""
        Synthesize these specialist results into a final response:
        
        Original task: {task.description}
        Specialist results: {results}
        
        Provide a comprehensive final answer.
        """
        
        final_result = await self.manager.agent.process(synthesis_prompt)
        
        logger.info(f"Hierarchical task completed with {len(results)} specialist contributions")
        return final_result
    
    async def _create_subtasks(self, main_task: TeamTask, specialists: List[str]) -> List[tuple]:
        """Create subtasks for each specialist."""
        subtasks = []
        
        for specialist_name in specialists:
            specialist = self.specialists[specialist_name]
            
            # Create specialist-specific subtask
            subtask_prompt = f"""
            As a {specialist.domain} specialist, handle this aspect of the task:
            {main_task.description}
            
            Focus on the {specialist.domain} components and provide your expert input.
            """
            
            subtasks.append((specialist_name, subtask_prompt, specialist))
        
        return subtasks
    
    async def _execute_subtasks_concurrently(self, subtasks: List[tuple]) -> Dict[str, str]:
        """Execute subtasks concurrently across specialists."""
        async def execute_subtask(specialist_name: str, prompt: str, specialist: SpecialistRole):
            try:
                result = await specialist.agent.process(prompt)
                return specialist_name, result
            except Exception as e:
                logger.error(f"Subtask failed for {specialist_name}: {e}")
                return specialist_name, f"Error: {e}"
        
        # Execute all subtasks concurrently
        tasks = [execute_subtask(name, prompt, spec) for name, prompt, spec in subtasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert to dictionary
        result_dict = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                specialist_name, output = result
                result_dict[specialist_name] = output
        
        return result_dict
    
    def _identify_suitable_specialists(self, task: TeamTask) -> List[str]:
        """Identify specialists suitable for the task."""
        suitable = []
        
        for specialist_name, specialist in self.specialists.items():
            if specialist.can_handle_task(task):
                suitable.append(specialist_name)
        
        # If no perfect matches, include all available specialists
        if not suitable:
            suitable = [name for name, spec in self.specialists.items() if spec.is_available]
        
        return suitable[:3]  # Limit to 3 specialists for manageable coordination
    
    def get_hierarchy_status(self) -> Dict[str, Any]:
        """Get current hierarchy status."""
        manager_name = self._get_agent_name(self.manager.agent) if self.manager else None
        
        return {
            "manager": manager_name,
            "specialists": list(self.specialists.keys()),
            "delegation_tree": dict(self.delegation_tree),
            "available_specialists": [
                name for name, spec in self.specialists.items() if spec.is_available
            ]
        }
    
    def _get_agent_name(self, agent) -> str:
        """Extract agent name consistently."""
        if hasattr(agent, 'profile') and agent.profile and hasattr(agent.profile, 'name'):
            return agent.profile.name
        if hasattr(agent, 'name'):
            return agent.name
        return agent.__class__.__name__.lower()

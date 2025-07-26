"""
Team coordinator for orchestrating multi-agent activities.

Handles task distribution, coordination, and team synchronization.
"""

from typing import Dict, List, Optional, Any
import asyncio
from enterprise_ai.team.core import TeamTask, TeamRole, CollaborationMode, TeamMember
from enterprise_ai.team.architecture.messaging import TeamMessaging, TeamMessage
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.coordinator")


class TeamCoordinator:
    """Orchestrates team activities and task coordination."""
    
    def __init__(self, collaboration_mode: CollaborationMode = CollaborationMode.HIERARCHICAL):
        self.collaboration_mode = collaboration_mode
        self.messaging = TeamMessaging()
        self.membership = MembershipManager()
        self.active_tasks: Dict[str, TeamTask] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> member_name
        
    async def coordinate_task(self, task: TeamTask) -> str:
        """Coordinate task execution across team members."""
        self.active_tasks[task.id] = task
        
        if self.collaboration_mode == CollaborationMode.HIERARCHICAL:
            return await self._hierarchical_coordination(task)
        elif self.collaboration_mode == CollaborationMode.PEER_TO_PEER:
            return await self._peer_coordination(task)
        else:  # HYBRID
            return await self._hybrid_coordination(task)
    
    async def _hierarchical_coordination(self, task: TeamTask) -> str:
        """Hierarchical coordination through manager."""
        managers = self.membership.get_members_by_role(TeamRole.MANAGER)
        
        if not managers:
            # No manager, delegate to most suitable specialist
            return await self._direct_assignment(task)
        
        # Assign to available manager
        manager = next((m for m in managers if m.is_available), None)
        if not manager:
            raise Exception("No available manager for task coordination")
        
        # Send coordination message
        coord_msg = self.messaging.create_coordination_message(
            "system", {"description": task.description, "priority": task.priority}
        )
        self.messaging.send_message(coord_msg)
        
        # Manager handles delegation
        self.task_assignments[task.id] = self.membership._get_agent_name(manager.agent)
        result = await manager.execute_task(task)
        
        logger.info(f"Hierarchical coordination completed for task {task.id}")
        return result
    
    async def _peer_coordination(self, task: TeamTask) -> str:
        """Peer-to-peer coordination among specialists."""
        available_members = self.membership.get_available_members()
        
        if not available_members:
            raise Exception("No available team members")
        
        # Find best member for task
        best_member = self._find_best_member_for_task(task, available_members)
        
        if best_member:
            self.task_assignments[task.id] = self.membership._get_agent_name(best_member.agent)
            
            # Notify team about task assignment
            assignment_msg = self.messaging.create_task_assignment(
                "coordinator", 
                self.task_assignments[task.id],
                task.description
            )
            self.messaging.send_message(assignment_msg)
            
            result = await best_member.execute_task(task)
            logger.info(f"Peer coordination completed for task {task.id}")
            return result
        
        raise Exception("No suitable member found for task")
    
    async def _hybrid_coordination(self, task: TeamTask) -> str:
        """Hybrid coordination using both hierarchical and peer approaches."""
        # Try hierarchical first for complex tasks
        if task.priority > 5 or 'complex' in task.description.lower():
            try:
                return await self._hierarchical_coordination(task)
            except Exception:
                logger.info("Hierarchical coordination failed, falling back to peer coordination")
        
        # Fall back to peer coordination
        return await self._peer_coordination(task)
    
    async def _direct_assignment(self, task: TeamTask) -> str:
        """Direct task assignment when no manager available."""
        available_members = self.membership.get_available_members()
        best_member = self._find_best_member_for_task(task, available_members)
        
        if not best_member:
            raise Exception("No suitable member available for direct assignment")
        
        self.task_assignments[task.id] = self.membership._get_agent_name(best_member.agent)
        result = await best_member.execute_task(task)
        
        logger.info(f"Direct assignment completed for task {task.id}")
        return result
    
    def _find_best_member_for_task(self, task: TeamTask, candidates: List[TeamMember]) -> Optional[TeamMember]:
        """Find best team member for specific task."""
        suitable_members = []
        
        for member in candidates:
            if hasattr(member, 'can_handle_task') and member.can_handle_task(task):
                suitable_members.append((member, member.available_capacity))
        
        if not suitable_members:
            # If no perfect match, return member with most capacity
            if candidates:
                return max(candidates, key=lambda m: m.available_capacity)
            return None
        
        # Return member with highest available capacity among suitable ones
        return max(suitable_members, key=lambda x: x[1])[0]
    
    def get_coordination_status(self) -> Dict[str, Any]:
        """Get current coordination status."""
        return {
            "active_tasks": len(self.active_tasks),
            "task_assignments": dict(self.task_assignments),
            "collaboration_mode": self.collaboration_mode.value,
            "available_members": len(self.membership.get_available_members())
        }

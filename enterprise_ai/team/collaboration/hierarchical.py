"""
Hierarchical team implementation for Enterprise AI.

This module provides a team implementation with a manager-worker hierarchy,
supporting top-down decision making and clear lines of authority.
"""

import asyncio
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol, Task
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.team.roles.base import BaseTeamRole, TeamManagerRole

logger = get_logger("team.collaboration.hierarchical")


class DecisionMode(Enum):
    """Decision-making modes in hierarchical teams."""
    MANAGER_ONLY = auto()  # Only manager makes decisions
    MANAGER_DELEGATED = auto()  # Manager delegates selected decisions
    MANAGER_REVIEW = auto()  # Manager reviews decisions before execution


class HierarchicalTeam(BaseTeam):
    """Hierarchical team implementation with manager-worker structure.
    
    This team type implements a traditional hierarchical structure with
    a clear manager-worker relationship. The manager coordinates activities,
    makes key decisions, and delegates tasks to appropriate specialists.
    """
    
    def __init__(
        self,
        team_id: Optional[str] = None,
        name: Optional[str] = None,
        manager_agent: Optional[AgentProtocol] = None,
        decision_mode: Union[DecisionMode, str] = DecisionMode.MANAGER_DELEGATED,
        **kwargs: Any,
    ):
        """Initialize a hierarchical team.
        
        Args:
            team_id: Optional unique identifier
            name: Optional human-readable name
            manager_agent: Optional manager agent to lead the team
            decision_mode: Decision-making mode for the team
            **kwargs: Additional team-specific parameters
        """
        super().__init__(team_id=team_id, name=name, **kwargs)
        
        # Set up decision mode
        self._decision_mode = self._resolve_decision_mode(decision_mode)
        
        # Set up manager if provided
        if manager_agent:
            self._set_manager(manager_agent)
            
        # Configure hierarchical-specific settings
        self._approval_required = self._decision_mode == DecisionMode.MANAGER_REVIEW
        self._pending_decisions: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Initialized hierarchical team {self.id} with {self._decision_mode} decision mode")
    
    @property
    def decision_mode(self) -> DecisionMode:
        """Get the team's decision-making mode.
        
        Returns:
            DecisionMode enum value
        """
        return self._decision_mode
    
    @property
    def manager(self) -> Optional[AgentProtocol]:
        """Get the team manager.
        
        Returns:
            Manager agent or None if not set
        """
        return self._membership.manager
    
    def set_decision_mode(self, mode: Union[DecisionMode, str]) -> None:
        """Set the team's decision-making mode.
        
        Args:
            mode: New decision mode
        """
        self._decision_mode = self._resolve_decision_mode(mode)
        logger.info(f"Changed decision mode for team {self.id} to {self._decision_mode}")
        
        # Update approval requirement
        self._approval_required = self._decision_mode == DecisionMode.MANAGER_REVIEW
    
    def add_member(self, agent: AgentProtocol, role: Optional[Any] = None) -> bool:
        """Add an agent to the team.
        
        Args:
            agent: Agent to add to the team
            role: Optional role for the agent
            
        Returns:
            True if agent was added successfully, False otherwise
        """
        if role == TeamMemberRole.MANAGER:
            # If adding as manager, use our specialized method
            return self._set_manager(agent)
        
        # Use normal BaseTeam implementation for other roles
        result = super().add_member(agent, role)
        
        # Set up reporting relationship to manager if exists
        if result and self.manager and agent.id != self.manager.id:
            self._membership.add_reporting_relationship(agent.id, self.manager.id)
            
        return result
    
    def assign_task(
        self, 
        task: Union[Task, Dict[str, Any]], 
        agent_id: Optional[str] = None
    ) -> bool:
        """Assign a task to the team or a specific team member.
        
        In hierarchical team, task assignment follows management hierarchy.
        
        Args:
            task: Task to assign
            agent_id: Optional ID of the specific agent to assign the task to
            
        Returns:
            True if task was assigned successfully, False otherwise
        """
        # Create team task
        team_task = self._tasks.create_task(task)
        
        # If agent_id is provided and it's not the manager, check if we're in MANAGER_ONLY mode
        if (agent_id and 
            self.manager and 
            agent_id != self.manager.id and 
            self._decision_mode == DecisionMode.MANAGER_ONLY):
            
            logger.info(f"Redirecting task {team_task.id} to manager due to MANAGER_ONLY mode")
            return self._tasks.assign_task(team_task.id, self.manager.id)
        
        # If agent_id is provided and direct assignment is allowed, assign to that agent
        if agent_id and agent_id in self._membership._members:
            return self._tasks.assign_task(team_task.id, agent_id)
            
        # If we have a manager, always assign to manager by default
        if self.manager:
            logger.info(f"Assigning task {team_task.id} to manager {self.manager.id}")
            return self._tasks.assign_task(team_task.id, self.manager.id)
        
        # Otherwise, fall back to standard assignment
        return super().assign_task(team_task, agent_id)
    
    async def process_decision(
        self, 
        decision_type: str, 
        subject: str, 
        agent_id: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a team decision based on decision mode.
        
        Args:
            decision_type: Type of decision being made
            subject: Subject of the decision
            agent_id: ID of the agent making the decision
            data: Additional data for the decision
            
        Returns:
            Decision result dictionary
        """
        # If no manager or agent is the manager, decision is automatically approved
        if not self.manager or agent_id == self.manager.id:
            logger.info(f"Decision {decision_type} auto-approved (from manager or no manager)")
            return {
                "approved": True,
                "result": data,
                "feedback": "Automatically approved"
            }
        
        # In MANAGER_ONLY mode, decisions not from the manager are rejected
        if self._decision_mode == DecisionMode.MANAGER_ONLY:
            logger.info(f"Decision {decision_type} rejected (MANAGER_ONLY mode)")
            return {
                "approved": False,
                "result": None,
                "feedback": "Only the manager can make decisions in this team"
            }
        
        # In MANAGER_DELEGATED mode, check if this decision type is delegated
        if self._decision_mode == DecisionMode.MANAGER_DELEGATED:
            # A real implementation would have a list of delegated decision types
            delegated_types = ["routine_task", "status_update"]
            
            if decision_type in delegated_types:
                logger.info(f"Decision {decision_type} auto-approved (delegated)")
                return {
                    "approved": True,
                    "result": data,
                    "feedback": "Automatically approved (delegated authority)"
                }
        
        # For MANAGER_REVIEW mode or non-delegated decisions, request manager approval
        decision_id = f"decision-{self.id}-{len(self._pending_decisions)}"
        
        # Store pending decision
        self._pending_decisions[decision_id] = {
            "type": decision_type,
            "subject": subject,
            "agent_id": agent_id,
            "data": data,
            "status": "pending"
        }
        
        # In a real implementation, we would asynchronously request manager approval
        # For now, simulate with default approval after delay
        await asyncio.sleep(0.5)  # Simulate processing time
        
        # Auto-approve for demo purposes
        self._pending_decisions[decision_id]["status"] = "approved"
        
        logger.info(f"Decision {decision_id} approved by manager")
        return {
            "approved": True,
            "result": data,
            "feedback": "Approved by manager"
        }
    
    def decompose_task(self, task_id: str, subtasks: List[Any]) -> List[Any]:
        """Decompose a task into subtasks following hierarchical structure.
        
        Args:
            task_id: ID of the parent task
            subtasks: List of subtask descriptions or data
            
        Returns:
            List of created subtask objects
        """
        # Create subtasks using the BaseTeam implementation
        created_subtasks = super().decompose_task(task_id, subtasks)
        
        # In hierarchical teams, manager assigns subtasks to appropriate specialists
        if self.manager:
            parent_task = self._tasks.get_task(task_id)
            
            # Auto-assign subtasks based on specialties
            for subtask in created_subtasks:
                # Find best specialist for this subtask
                # This would be more sophisticated in a real implementation
                specialist_id = self._find_specialist_for_subtask(subtask)
                
                if specialist_id:
                    self._tasks.assign_task(subtask.id, specialist_id)
                    logger.info(f"Manager assigned subtask {subtask.id} to specialist {specialist_id}")
                else:
                    # Assign to manager if no specialist found
                    self._tasks.assign_task(subtask.id, self.manager.id)
                    logger.info(f"No specialist found, assigned subtask {subtask.id} to manager")
        
        return created_subtasks
    
    def _find_specialist_for_subtask(self, subtask: Any) -> Optional[str]:
        """Find the best specialist for a given subtask.
        
        Args:
            subtask: Subtask to find specialist for
            
        Returns:
            ID of the best specialist or None
        """
        # Skip manager when finding specialists
        manager_id = self.manager.id if self.manager else None
        
        # Get all specialists (non-manager members)
        specialists = []
        for agent_id, agent in self._membership._members.items():
            if agent_id != manager_id:
                specialists.append(agent)
        
        if not specialists:
            return None
        
        # In a real implementation, this would match task requirements to specialist capabilities
        # For now, just return the first non-manager agent as a placeholder
        return specialists[0].id
    
    def _resolve_decision_mode(self, mode: Union[DecisionMode, str]) -> DecisionMode:
        """Resolve decision mode from various input types.
        
        Args:
            mode: Decision mode to resolve (enum or string)
            
        Returns:
            Resolved DecisionMode enum value
        """
        if isinstance(mode, DecisionMode):
            return mode
        
        # Convert string to enum
        try:
            mode_upper = mode.upper()
            if mode_upper == "MANAGER_ONLY":
                return DecisionMode.MANAGER_ONLY
            elif mode_upper == "MANAGER_REVIEW":
                return DecisionMode.MANAGER_REVIEW
            else:
                return DecisionMode.MANAGER_DELEGATED
        except (AttributeError, KeyError):
            logger.warning(f"Invalid decision mode string: {mode}, defaulting to MANAGER_DELEGATED")
            return DecisionMode.MANAGER_DELEGATED
    
    def _set_manager(self, agent: AgentProtocol) -> bool:
        """Set an agent as the team manager.
        
        Args:
            agent: Agent to set as manager
            
        Returns:
            True if manager was set successfully, False otherwise
        """
        # First remove the agent if it's already a member
        if self._membership.is_member(agent.id):
            self._membership.remove_member(agent.id)
        
        # Apply manager role if needed
        agent_role = TeamManagerRole()
        
        # Add with manager role
        result = super().add_member(agent, TeamMemberRole.MANAGER)
        
        if result:
            # Set up reporting relationships
            for member_agent in self._membership.get_members():
                if member_agent.id != agent.id:
                    self._membership.add_reporting_relationship(member_agent.id, agent.id)
            
            logger.info(f"Set agent {agent.id} as manager for team {self.id}")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get team status information with hierarchical-specific details.
        
        Returns:
            Dictionary of status information
        """
        status = super().get_status()
        
        # Add hierarchical-specific information
        hierarchical_info = {
            "decision_mode": self._decision_mode.name,
            "approval_required": self._approval_required,
            "pending_decisions": len(self._pending_decisions),
        }
        
        status["hierarchical"] = hierarchical_info
        
        return status

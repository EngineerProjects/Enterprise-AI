"""
Tool sharing policies for Enterprise AI.

This module provides policies that control how tools are shared 
between team members, with different strategies for different
team collaboration patterns.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.team.architecture.task_manager import TaskManager, TeamTask
from enterprise_ai.team.core.types import TeamMemberRole, TeamProtocol
from enterprise_ai.team.tools.registry import TeamToolRegistry, ToolAccessLevel, ToolRegistration
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata

logger = get_logger("team.tools.sharing")


class SharingRequest:
    """Request to share a tool with another agent."""
    
    def __init__(
        self,
        tool_name: str,
        owner_id: str,
        requester_id: str,
        reason: Optional[str] = None,
        task_id: Optional[str] = None,
        temporary: bool = False,
        expiration: Optional[int] = None,
    ):
        """Initialize a sharing request.
        
        Args:
            tool_name: Name of the tool to share
            owner_id: ID of the tool owner
            requester_id: ID of the agent requesting access
            reason: Optional reason for the request
            task_id: Optional ID of the related task
            temporary: Whether this is a temporary share
            expiration: Optional expiration time in seconds
        """
        self.tool_name = tool_name
        self.owner_id = owner_id
        self.requester_id = requester_id
        self.reason = reason
        self.task_id = task_id
        self.temporary = temporary
        self.expiration = expiration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the request
        """
        return {
            "tool_name": self.tool_name,
            "owner_id": self.owner_id,
            "requester_id": self.requester_id,
            "reason": self.reason,
            "task_id": self.task_id,
            "temporary": self.temporary,
            "expiration": self.expiration,
        }


class SharingApproval(Enum):
    """Result of a sharing policy evaluation."""
    
    APPROVED = auto()  # Request is approved
    DENIED = auto()    # Request is denied
    PENDING = auto()   # Request needs explicit approval


class ToolSharingPolicy(ABC):
    """Base class for tool sharing policies.
    
    Tool sharing policies control how tools are shared between team
    members, determining when sharing requires approval and when
    it can be automatic.
    """
    
    def __init__(self, team: "TeamProtocol"):
        """Initialize the sharing policy.
        
        Args:
            team: Team that this policy belongs to
        """
        self._team = team
    
    @abstractmethod
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a tool sharing request.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        pass
    
    @abstractmethod
    def get_policy_description(self) -> str:
        """Get a human-readable description of this policy.
        
        Returns:
            Policy description string
        """
        pass


class DefaultSharingPolicy(ToolSharingPolicy):
    """Default tool sharing policy.
    
    This policy provides the following rules:
    - Owner can share their tools with anyone on the team
    - Manager can approve any sharing request
    - All other sharing requires explicit approval
    """
    
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a sharing request using default rules.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        # Owner can always approve sharing their own tools
        if request.requester_id == request.owner_id:
            return (SharingApproval.APPROVED, "Owner can share their own tools")
        
        # Check if requester is team manager
        is_manager = False
        if membership and membership.manager:
            is_manager = request.requester_id == membership.manager.id
        
        if is_manager:
            return (SharingApproval.APPROVED, "Team manager can approve tool sharing")
        
        # Default to requiring explicit approval
        return (SharingApproval.PENDING, "Requires explicit approval from owner or manager")
    
    def get_policy_description(self) -> str:
        """Get a description of the default sharing policy.
        
        Returns:
            Policy description string
        """
        return (
            "Default Sharing Policy:\n"
            "- Tool owners can share their own tools\n"
            "- Team managers can approve any sharing request\n"
            "- All other sharing requires explicit approval\n"
        )


class HierarchicalSharingPolicy(ToolSharingPolicy):
    """Hierarchical tool sharing policy.
    
    This policy provides the following rules:
    - Owner can share their tools with anyone on the team
    - Manager can approve any sharing request
    - Agents can share with their direct reports
    - Agents can use tools of their manager without approval
    - All other sharing requires explicit approval
    """
    
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a sharing request using hierarchical rules.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        # Owner can always approve sharing their own tools
        if request.requester_id == request.owner_id:
            return (SharingApproval.APPROVED, "Owner can share their own tools")
        
        if not membership:
            # Can't check hierarchy without membership manager
            return (SharingApproval.PENDING, "Cannot verify team hierarchy")
        
        # Check if requester is team manager
        is_manager = False
        if membership.manager:
            is_manager = request.requester_id == membership.manager.id
        
        if is_manager:
            return (SharingApproval.APPROVED, "Team manager can approve tool sharing")
        
        # Check if requester is manager of the owner
        owner_agent = membership.get_member(request.owner_id)
        if owner_agent:
            owner_manager = membership.get_manager_of(request.owner_id)
            if owner_manager and owner_manager.id == request.requester_id:
                return (SharingApproval.APPROVED, "Manager can access team member's tools")
        
        # Check if owner is manager of the requester
        requester_agent = membership.get_member(request.requester_id)
        if requester_agent:
            requester_manager = membership.get_manager_of(request.requester_id)
            if requester_manager and requester_manager.id == request.owner_id:
                return (SharingApproval.APPROVED, "Team member can use manager's tools")
        
        # Default to requiring explicit approval
        return (SharingApproval.PENDING, "Requires explicit approval from owner or manager")
    
    def get_policy_description(self) -> str:
        """Get a description of the hierarchical sharing policy.
        
        Returns:
            Policy description string
        """
        return (
            "Hierarchical Sharing Policy:\n"
            "- Tool owners can share their own tools\n"
            "- Team managers can approve any sharing request\n"
            "- Managers can access their team members' tools\n"
            "- Team members can use their manager's tools\n"
            "- All other sharing requires explicit approval\n"
        )


class TaskBasedSharingPolicy(ToolSharingPolicy):
    """Task-based tool sharing policy.
    
    This policy provides the following rules:
    - Owner can share their tools with anyone on the team
    - Manager can approve any sharing request
    - Agents working on the same task can share tools
    - Agents working on dependent tasks can share tools
    - All other sharing requires explicit approval
    """
    
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a sharing request using task-based rules.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        # Owner can always approve sharing their own tools
        if request.requester_id == request.owner_id:
            return (SharingApproval.APPROVED, "Owner can share their own tools")
        
        # Check if requester is team manager
        is_manager = False
        if membership and membership.manager:
            is_manager = request.requester_id == membership.manager.id
        
        if is_manager:
            return (SharingApproval.APPROVED, "Team manager can approve tool sharing")
        
        # Check if they're working on the same task
        if task_manager and request.task_id:
            task = task_manager.get_task(request.task_id)
            if task:
                # Check if both owner and requester are assigned to this task
                owner_tasks = task_manager.get_agent_tasks(request.owner_id)
                requester_tasks = task_manager.get_agent_tasks(request.requester_id)
                
                owner_task_ids = [t.id for t in owner_tasks]
                requester_task_ids = [t.id for t in requester_tasks]
                
                if request.task_id in owner_task_ids and request.task_id in requester_task_ids:
                    return (
                        SharingApproval.APPROVED, 
                        "Agents working on the same task can share tools"
                    )
                
                # Check for task dependencies
                for owner_task in owner_tasks:
                    for requester_task in requester_tasks:
                        # Check if owner task depends on requester task
                        if requester_task.id in owner_task.dependencies:
                            return (
                                SharingApproval.APPROVED,
                                "Agents working on dependent tasks can share tools"
                            )
                        
                        # Check if requester task depends on owner task
                        if owner_task.id in requester_task.dependencies:
                            return (
                                SharingApproval.APPROVED,
                                "Agents working on dependent tasks can share tools"
                            )
        
        # Default to requiring explicit approval
        return (SharingApproval.PENDING, "Requires explicit approval from owner or manager")
    
    def get_policy_description(self) -> str:
        """Get a description of the task-based sharing policy.
        
        Returns:
            Policy description string
        """
        return (
            "Task-Based Sharing Policy:\n"
            "- Tool owners can share their own tools\n"
            "- Team managers can approve any sharing request\n"
            "- Agents working on the same task can share tools\n"
            "- Agents working on dependent tasks can share tools\n"
            "- All other sharing requires explicit approval\n"
        )


class CapabilityBasedSharingPolicy(ToolSharingPolicy):
    """Capability-based tool sharing policy.
    
    This policy provides the following rules:
    - Owner can share their tools with anyone on the team
    - Manager can approve any sharing request
    - Agents with the required capabilities can use tools
    - Specialized tools require explicit approval
    - All other sharing requires explicit approval
    """
    
    def __init__(
        self,
        team: "TeamProtocol",
        auto_approve_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        specialized_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    ):
        """Initialize the capability-based policy.
        
        Args:
            team: Team that this policy belongs to
            auto_approve_capabilities: Capabilities that can be auto-approved
            specialized_capabilities: Capabilities that require approval
        """
        super().__init__(team)
        
        # Convert capabilities to strings for consistency
        self._auto_approve = set()
        if auto_approve_capabilities:
            for cap in auto_approve_capabilities:
                cap_str = cap.value if hasattr(cap, "value") else str(cap)
                self._auto_approve.add(cap_str)
        
        self._specialized = set()
        if specialized_capabilities:
            for cap in specialized_capabilities:
                cap_str = cap.value if hasattr(cap, "value") else str(cap)
                self._specialized.add(cap_str)
    
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a sharing request using capability-based rules.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        # Owner can always approve sharing their own tools
        if request.requester_id == request.owner_id:
            return (SharingApproval.APPROVED, "Owner can share their own tools")
        
        # Check if requester is team manager
        is_manager = False
        if membership and membership.manager:
            is_manager = request.requester_id == membership.manager.id
        
        if is_manager:
            return (SharingApproval.APPROVED, "Team manager can approve tool sharing")
        
        # Check tool capabilities
        tool_reg = registry.get_tool_registration(request.tool_name)
        if not tool_reg:
            return (SharingApproval.PENDING, "Tool not found in registry")
        
        # Check if this is a specialized tool
        specialized = False
        for cap in tool_reg.capabilities:
            cap_str = cap.value if hasattr(cap, "value") else str(cap)
            if cap_str in self._specialized:
                specialized = True
                break
        
        if specialized:
            return (SharingApproval.PENDING, "Specialized tools require explicit approval")
        
        # Check if tool has auto-approve capabilities
        auto_approve = False
        for cap in tool_reg.capabilities:
            cap_str = cap.value if hasattr(cap, "value") else str(cap)
            if cap_str in self._auto_approve:
                auto_approve = True
                break
        
        if auto_approve:
            # Check if requester has the necessary capabilities
            requester = self._team.get_member(request.requester_id)
            if requester and hasattr(requester, "capabilities"):
                requester_caps = getattr(requester, "capabilities", set())
                
                # Check if requester has the capabilities needed
                has_required_caps = True
                for cap in tool_reg.capabilities:
                    cap_str = cap.value if hasattr(cap, "value") else str(cap)
                    if cap_str in self._auto_approve and cap_str not in requester_caps:
                        has_required_caps = False
                        break
                
                if has_required_caps:
                    return (
                        SharingApproval.APPROVED,
                        "Agent has the required capabilities for this tool"
                    )
        
        # Default to requiring explicit approval
        return (SharingApproval.PENDING, "Requires explicit approval from owner or manager")
    
    def get_policy_description(self) -> str:
        """Get a description of the capability-based sharing policy.
        
        Returns:
            Policy description string
        """
        auto_approve_caps = ", ".join(self._auto_approve) if self._auto_approve else "None"
        specialized_caps = ", ".join(self._specialized) if self._specialized else "None"
        
        return (
            "Capability-Based Sharing Policy:\n"
            "- Tool owners can share their own tools\n"
            "- Team managers can approve any sharing request\n"
            f"- Auto-approve capabilities: {auto_approve_caps}\n"
            f"- Specialized capabilities: {specialized_caps}\n"
            "- Agents with matching capabilities can use tools\n"
            "- Specialized tools require explicit approval\n"
            "- All other sharing requires explicit approval\n"
        )


class ToolSharingManager:
    """Manages tool sharing within a team.
    
    This component implements specific sharing workflows:
    - Processing sharing requests
    - Applying sharing policies
    - Managing temporary shares
    - Recording sharing history
    - Handling approval workflows
    """
    
    def __init__(
        self,
        team: "TeamProtocol",
        registry: TeamToolRegistry,
        membership: Optional[MembershipManager] = None,
        task_manager: Optional[TaskManager] = None,
        policy: Optional[ToolSharingPolicy] = None,
    ):
        """Initialize the tool sharing manager.
        
        Args:
            team: Team that this manager belongs to
            registry: Tool registry for the team
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            policy: Optional sharing policy (default: DefaultSharingPolicy)
        """
        self._team = team
        self._registry = registry
        self._membership = membership
        self._task_manager = task_manager
        self._policy = policy or DefaultSharingPolicy(team)
        
        self._pending_requests: Dict[str, SharingRequest] = {}  # request_id -> request
        self._sharing_history: List[Dict[str, Any]] = []
        self._temporary_shares: Dict[str, asyncio.Task] = {}  # tool_name + agent_id -> task
        
        logger.info(f"Initialized tool sharing manager for team {team.id}")
    
    def set_policy(self, policy: ToolSharingPolicy) -> None:
        """Set the sharing policy.
        
        Args:
            policy: New sharing policy to use
        """
        self._policy = policy
        logger.info(f"Set sharing policy to {policy.__class__.__name__}")
    
    def get_policy(self) -> ToolSharingPolicy:
        """Get the current sharing policy.
        
        Returns:
            Current sharing policy
        """
        return self._policy
    
    async def request_tool_access(
        self,
        agent_id: str,
        tool_name: str,
        reason: Optional[str] = None,
        task_id: Optional[str] = None,
        temporary: bool = False,
        expiration: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Request access to a tool.
        
        Args:
            agent_id: ID of the agent requesting access
            tool_name: Name of the tool
            reason: Optional reason for the request
            task_id: Optional ID of the related task
            temporary: Whether this is a temporary share
            expiration: Optional expiration time in seconds
            
        Returns:
            Tuple of (success, message, request_id)
        """
        # Check if tool exists
        owner_id = self._registry.get_tool_owner(tool_name)
        if not owner_id:
            logger.warning(f"Tool {tool_name} not found in registry")
            return (False, f"Tool not found: {tool_name}", None)
        
        # Check if agent already has access
        if self._registry.can_access_tool(agent_id, tool_name):
            logger.info(f"Agent {agent_id} already has access to tool {tool_name}")
            return (True, "Already has access", None)
        
        # Create the request
        request = SharingRequest(
            tool_name=tool_name,
            owner_id=owner_id,
            requester_id=agent_id,
            reason=reason,
            task_id=task_id,
            temporary=temporary,
            expiration=expiration,
        )
        
        # Evaluate against policy
        approval, message = await self._policy.evaluate_request(
            request=request,
            registry=self._registry,
            membership=self._membership,
            task_manager=self._task_manager,
        )
        
        if approval == SharingApproval.APPROVED:
            # Automatically approve
            access_level = ToolAccessLevel.TEAM_EXECUTE
            
            # Add to allowed agents
            result = self._registry.add_allowed_agent(tool_name, agent_id)
            
            # If temporary, set up expiration
            if temporary and expiration and result:
                await self._setup_temporary_share(tool_name, agent_id, expiration)
            
            # Record in history
            self._record_sharing(
                tool_name=tool_name,
                owner_id=owner_id,
                agent_id=agent_id,
                approved=True,
                approver_id=None,  # Auto-approved
                reason=reason,
                task_id=task_id,
                message=message,
                temporary=temporary,
                expiration=expiration,
            )
            
            return (True, message, None)
        elif approval == SharingApproval.DENIED:
            # Automatically denied
            self._record_sharing(
                tool_name=tool_name,
                owner_id=owner_id,
                agent_id=agent_id,
                approved=False,
                approver_id=None,  # Auto-denied
                reason=reason,
                task_id=task_id,
                message=message,
                temporary=temporary,
                expiration=expiration,
            )
            
            return (False, message, None)
        else:  # PENDING
            # Create pending request
            request_id = f"req-{tool_name}-{agent_id}-{len(self._pending_requests)}"
            self._pending_requests[request_id] = request
            
            logger.info(f"Created pending request {request_id} for tool {tool_name}")
            return (False, "Request pending approval", request_id)
    
    async def approve_request(
        self,
        request_id: str,
        approver_id: str,
        message: Optional[str] = None,
    ) -> bool:
        """Approve a pending tool access request.
        
        Args:
            request_id: ID of the request to approve
            approver_id: ID of the agent approving the request
            message: Optional approval message
            
        Returns:
            True if request was approved, False otherwise
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Request {request_id} not found")
            return False
        
        request = self._pending_requests[request_id]
        
        # Check if approver is authorized
        if approver_id != request.owner_id:
            # Check if approver is team manager
            is_manager = False
            if self._membership and self._membership.manager:
                is_manager = approver_id == self._membership.manager.id
            
            if not is_manager:
                logger.warning(
                    f"Agent {approver_id} not authorized to approve request {request_id}"
                )
                return False
        
        # Add agent to allowed list
        result = self._registry.add_allowed_agent(request.tool_name, request.requester_id)
        
        if result:
            # Notify agent of updated tool access through the team if possible
            requester_agent = self._team.get_member(request.requester_id)
            if requester_agent and hasattr(requester_agent, "_agent_tools_manager"):
                # Force a refresh of the agent's tool cache if it has a tools manager
                logger.info(f"Refreshing tool cache for agent {request.requester_id}")
                
                # This is just a placeholder - implement the actual refresh mechanism
                # based on how your agent tool manager works
                if hasattr(requester_agent._agent_tools_manager, "refresh_tools"):
                    await requester_agent._agent_tools_manager.refresh_tools()
                elif hasattr(requester_agent, "refresh_tools"):
                    await requester_agent.refresh_tools()
            
            # If temporary, set up expiration
            if request.temporary and request.expiration:
                await self._setup_temporary_share(
                    request.tool_name, request.requester_id, request.expiration
                )
            
            # Record in history
            self._record_sharing(
                tool_name=request.tool_name,
                owner_id=request.owner_id,
                agent_id=request.requester_id,
                approved=True,
                approver_id=approver_id,
                reason=request.reason,
                task_id=request.task_id,
                message=message,
                temporary=request.temporary,
                expiration=request.expiration,
            )
            
            # Remove from pending requests
            del self._pending_requests[request_id]
            
            logger.info(f"Approved request {request_id} for tool {request.tool_name}")
            return True
        
        return False
    
    def deny_request(
        self,
        request_id: str,
        denier_id: str,
        message: Optional[str] = None,
    ) -> bool:
        """Deny a pending tool access request.
        
        Args:
            request_id: ID of the request to deny
            denier_id: ID of the agent denying the request
            message: Optional denial message
            
        Returns:
            True if request was denied, False otherwise
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Request {request_id} not found")
            return False
        
        request = self._pending_requests[request_id]
        
        # Check if denier is authorized
        if denier_id != request.owner_id:
            # Check if denier is team manager
            is_manager = False
            if self._membership and self._membership.manager:
                is_manager = denier_id == self._membership.manager.id
            
            if not is_manager:
                logger.warning(
                    f"Agent {denier_id} not authorized to deny request {request_id}"
                )
                return False
        
        # Record in history
        self._record_sharing(
            tool_name=request.tool_name,
            owner_id=request.owner_id,
            agent_id=request.requester_id,
            approved=False,
            approver_id=denier_id,
            reason=request.reason,
            task_id=request.task_id,
            message=message,
            temporary=request.temporary,
            expiration=request.expiration,
        )
        
        # Remove from pending requests
        del self._pending_requests[request_id]
        
        logger.info(f"Denied request {request_id} for tool {request.tool_name}")
        return True
    
    def get_pending_requests(self, owner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending tool access requests.
        
        Args:
            owner_id: Optional ID of the tool owner to filter by
            
        Returns:
            List of pending request dictionaries
        """
        result = []
        
        for request_id, request in self._pending_requests.items():
            if owner_id and request.owner_id != owner_id:
                continue
            
            result.append({
                "request_id": request_id,
                **request.to_dict(),
            })
        
        return result
    
    def get_sharing_history(
        self,
        tool_name: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get tool sharing history.
        
        Args:
            tool_name: Optional tool name to filter by
            agent_id: Optional agent ID to filter by
            
        Returns:
            List of sharing history dictionaries
        """
        result = []
        
        for entry in self._sharing_history:
            if tool_name and entry["tool_name"] != tool_name:
                continue
            
            if agent_id and entry["agent_id"] != agent_id:
                continue
            
            result.append(entry)
        
        return result
    
    def revoke_access(self, tool_name: str, agent_id: str) -> bool:
        """Revoke an agent's access to a tool.
        
        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent to revoke access from
            
        Returns:
            True if access was revoked, False otherwise
        """
        result = self._registry.remove_allowed_agent(tool_name, agent_id)
        
        if result:
            # If there's a temporary share task, cancel it
            key = f"{tool_name}-{agent_id}"
            if key in self._temporary_shares:
                task = self._temporary_shares[key]
                if not task.done():
                    task.cancel()
                del self._temporary_shares[key]
            
            # Record in history
            self._record_sharing(
                tool_name=tool_name,
                owner_id=self._registry.get_tool_owner(tool_name),
                agent_id=agent_id,
                approved=False,
                approver_id=None,
                reason="Access revoked",
                task_id=None,
                message="Access revoked",
                temporary=False,
                expiration=None,
                is_revocation=True,
            )
            
            logger.info(f"Revoked access to tool {tool_name} from agent {agent_id}")
            return True
        
        return False
    
    async def _setup_temporary_share(
        self,
        tool_name: str,
        agent_id: str,
        expiration: int,
    ) -> None:
        """Set up a temporary tool share.
        
        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent with temporary access
            expiration: Expiration time in seconds
        """
        key = f"{tool_name}-{agent_id}"
        
        # Cancel existing task if present
        if key in self._temporary_shares:
            task = self._temporary_shares[key]
            if not task.done():
                task.cancel()
        
        # Create new expiration task
        expiration_task = asyncio.create_task(self._expire_share(tool_name, agent_id, expiration))
        self._temporary_shares[key] = expiration_task
        
        logger.info(
            f"Set up temporary share of tool {tool_name} to agent {agent_id} "
            f"expiring in {expiration} seconds"
        )
    
    async def _expire_share(self, tool_name: str, agent_id: str, expiration: int) -> None:
        """Expire a temporary tool share after the specified time.
        
        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent with temporary access
            expiration: Expiration time in seconds
        """
        try:
            # Wait for expiration time
            await asyncio.sleep(expiration)
            
            # Revoke access
            self.revoke_access(tool_name, agent_id)
            
            logger.info(f"Expired temporary share of tool {tool_name} to agent {agent_id}")
        except asyncio.CancelledError:
            # Task was cancelled (e.g., share was revoked early)
            logger.debug(f"Cancelled expiration task for tool {tool_name}, agent {agent_id}")
        except Exception as e:
            logger.error(f"Error in expire_share for {tool_name}, {agent_id}: {e}")
    
    def _record_sharing(
        self,
        tool_name: str,
        owner_id: Optional[str],
        agent_id: str,
        approved: bool,
        approver_id: Optional[str],
        reason: Optional[str],
        task_id: Optional[str],
        message: Optional[str],
        temporary: bool,
        expiration: Optional[int],
        is_revocation: bool = False,
    ) -> None:
        """Record a sharing action in the history.
        
        Args:
            tool_name: Name of the tool
            owner_id: ID of the tool owner
            agent_id: ID of the agent requesting/receiving access
            approved: Whether the request was approved
            approver_id: ID of the agent that approved/denied the request
            reason: Reason for the request
            task_id: ID of the related task
            message: Approval/denial message
            temporary: Whether this is a temporary share
            expiration: Expiration time in seconds
            is_revocation: Whether this is a revocation
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "owner_id": owner_id,
            "agent_id": agent_id,
            "approved": approved,
            "approver_id": approver_id,
            "reason": reason,
            "task_id": task_id,
            "message": message,
            "temporary": temporary,
            "expiration": expiration,
            "is_revocation": is_revocation,
        }
        
        self._sharing_history.append(entry)

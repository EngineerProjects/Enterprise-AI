"""
Tool sharing system for team collaboration.

Enables secure sharing of tools and capabilities between team members.
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enterprise_ai.team.core import TeamRole, Permission
from enterprise_ai.team.tools.registry import ToolRegistry, RegisteredTool
from enterprise_ai.team.tools.access_control import AccessControlManager
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.tool_sharing")


@dataclass
class SharingRequest:
    """Request to share a tool."""
    id: str
    tool_name: str
    requester: str
    owner: str
    requested_permissions: Set[Permission]
    justification: str
    status: str = "pending"  # pending, approved, denied, expired
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if request has expired."""
        return self.expires_at is not None and datetime.now() > self.expires_at


@dataclass
class SharedTool:
    """Represents a shared tool instance."""
    tool_name: str
    owner: str
    shared_with: str
    permissions: Set[Permission]
    shared_at: datetime
    expires_at: Optional[datetime] = None
    usage_limit: Optional[int] = None
    usage_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if sharing has expired."""
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return True
        return False


class ToolSharingManager:
    """Manages tool sharing between team members."""
    
    def __init__(self, registry: ToolRegistry, access_control: AccessControlManager):
        self.registry = registry
        self.access_control = access_control
        self.sharing_requests: Dict[str, SharingRequest] = {}
        self.shared_tools: Dict[str, SharedTool] = {}  # sharing_id -> SharedTool
        self.auto_approve_rules: List[callable] = []
        
    def request_tool_sharing(
        self, 
        tool_name: str, 
        requester: str, 
        owner: str,
        permissions: Set[Permission],
        justification: str,
        duration_hours: Optional[int] = None
    ) -> str:
        """Request to share a tool."""
        request_id = f"req_{len(self.sharing_requests)}_{int(datetime.now().timestamp())}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        request = SharingRequest(
            id=request_id,
            tool_name=tool_name,
            requester=requester,
            owner=owner,
            requested_permissions=permissions,
            justification=justification,
            expires_at=expires_at
        )
        
        self.sharing_requests[request_id] = request
        
        # Check auto-approval rules
        if self._check_auto_approval(request):
            self.approve_sharing_request(request_id, owner)
        
        logger.info(f"Tool sharing requested: {tool_name} by {requester} from {owner}")
        return request_id
    
    def approve_sharing_request(
        self, 
        request_id: str, 
        approver: str,
        duration_hours: Optional[int] = None,
        usage_limit: Optional[int] = None
    ) -> bool:
        """Approve a sharing request."""
        request = self.sharing_requests.get(request_id)
        
        if not request or request.status != "pending":
            return False
        
        if request.owner != approver:
            logger.warning(f"Non-owner {approver} attempted to approve sharing request {request_id}")
            return False
        
        if request.is_expired():
            request.status = "expired"
            return False
        
        # Create shared tool
        sharing_id = f"share_{len(self.shared_tools)}_{int(datetime.now().timestamp())}"
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        shared_tool = SharedTool(
            tool_name=request.tool_name,
            owner=request.owner,
            shared_with=request.requester,
            permissions=request.requested_permissions,
            shared_at=datetime.now(),
            expires_at=expires_at,
            usage_limit=usage_limit
        )
        
        self.shared_tools[sharing_id] = shared_tool
        request.status = "approved"
        
        # Grant permissions in access control
        for permission in request.requested_permissions:
            self.access_control.grant_permission(
                request.requester, 
                request.tool_name, 
                permission, 
                request.owner
            )
        
        logger.info(f"Approved tool sharing: {request.tool_name} to {request.requester}")
        return True
    
    def deny_sharing_request(self, request_id: str, denier: str, reason: str = "") -> bool:
        """Deny a sharing request."""
        request = self.sharing_requests.get(request_id)
        
        if not request or request.status != "pending":
            return False
        
        if request.owner != denier:
            logger.warning(f"Non-owner {denier} attempted to deny sharing request {request_id}")
            return False
        
        request.status = "denied"
        logger.info(f"Denied tool sharing request {request_id}: {reason}")
        return True
    
    def revoke_tool_sharing(self, sharing_id: str, revoker: str) -> bool:
        """Revoke tool sharing."""
        shared_tool = self.shared_tools.get(sharing_id)
        
        if not shared_tool:
            return False
        
        if shared_tool.owner != revoker:
            logger.warning(f"Non-owner {revoker} attempted to revoke sharing {sharing_id}")
            return False
        
        # Revoke permissions
        for permission in shared_tool.permissions:
            self.access_control.revoke_permission(
                shared_tool.shared_with,
                shared_tool.tool_name,
                permission,
                shared_tool.owner
            )
        
        del self.shared_tools[sharing_id]
        logger.info(f"Revoked tool sharing: {shared_tool.tool_name} from {shared_tool.shared_with}")
        return True
    
    def record_tool_usage(self, member_id: str, tool_name: str) -> None:
        """Record tool usage and update sharing limits."""
        # Find relevant shared tools
        for shared_tool in self.shared_tools.values():
            if (shared_tool.shared_with == member_id and 
                shared_tool.tool_name == tool_name):
                shared_tool.usage_count += 1
                
                # Check if usage limit exceeded
                if (shared_tool.usage_limit and 
                    shared_tool.usage_count >= shared_tool.usage_limit):
                    logger.info(f"Usage limit reached for shared tool {tool_name}")
        
        # Record in registry
        self.registry.record_tool_usage(tool_name, member_id)
    
    def cleanup_expired_shares(self) -> int:
        """Clean up expired sharing arrangements."""
        expired_shares = []
        
        for sharing_id, shared_tool in self.shared_tools.items():
            if shared_tool.is_expired():
                expired_shares.append(sharing_id)
        
        cleaned_count = 0
        for sharing_id in expired_shares:
            shared_tool = self.shared_tools[sharing_id]
            
            # Revoke permissions
            for permission in shared_tool.permissions:
                self.access_control.revoke_permission(
                    shared_tool.shared_with,
                    shared_tool.tool_name,
                    permission,
                    shared_tool.owner
                )
            
            del self.shared_tools[sharing_id]
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired tool shares")
        
        return cleaned_count
    
    def get_sharing_status(self, member_id: str) -> Dict[str, Any]:
        """Get sharing status for a member."""
        owned_tools = []
        shared_with_me = []
        pending_requests = []
        
        for tool_name, tool in self.registry.tools.items():
            if tool.owner == member_id:
                owned_tools.append(tool_name)
        
        for shared_tool in self.shared_tools.values():
            if shared_tool.shared_with == member_id:
                shared_with_me.append({
                    "tool": shared_tool.tool_name,
                    "owner": shared_tool.owner,
                    "permissions": [p.value for p in shared_tool.permissions],
                    "expires_at": shared_tool.expires_at,
                    "usage": f"{shared_tool.usage_count}/{shared_tool.usage_limit or '∞'}"
                })
        
        for request in self.sharing_requests.values():
            if request.requester == member_id and request.status == "pending":
                pending_requests.append({
                    "id": request.id,
                    "tool": request.tool_name,
                    "owner": request.owner,
                    "permissions": [p.value for p in request.requested_permissions]
                })
        
        return {
            "owned_tools": owned_tools,
            "shared_with_me": shared_with_me,
            "pending_requests": pending_requests
        }
    
    def add_auto_approval_rule(self, rule: callable) -> None:
        """Add automatic approval rule."""
        self.auto_approve_rules.append(rule)
    
    def _check_auto_approval(self, request: SharingRequest) -> bool:
        """Check if request should be auto-approved."""
        for rule in self.auto_approve_rules:
            try:
                if rule(request):
                    return True
            except Exception as e:
                logger.error(f"Auto-approval rule failed: {e}")
        
        return False


# Common auto-approval rules
def same_role_approval(member_roles: Dict[str, TeamRole]) -> callable:
    """Auto-approve requests between members of same role."""
    def rule(request: SharingRequest) -> bool:
        requester_role = member_roles.get(request.requester)
        owner_role = member_roles.get(request.owner)
        return requester_role and owner_role and requester_role == owner_role
    
    return rule


def low_risk_tools_approval(low_risk_tools: Set[str]) -> callable:
    """Auto-approve requests for low-risk tools."""
    def rule(request: SharingRequest) -> bool:
        return request.tool_name in low_risk_tools
    
    return rule

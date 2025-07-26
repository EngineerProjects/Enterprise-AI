"""
Tool access control system.

Manages permissions, policies, and secure tool access for team members.
"""

from typing import Dict, Set, List, Optional, Any, Callable
from dataclasses import dataclass
from enterprise_ai.team.core import TeamRole, Permission, AccessLevel
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.access_control")


@dataclass
class AccessPolicy:
    """Defines access policy for a tool."""
    tool_name: str
    access_level: AccessLevel
    allowed_roles: Set[TeamRole] = None
    allowed_members: Set[str] = None
    required_permissions: Set[Permission] = None
    conditions: List[Callable] = None  # Custom access conditions
    
    def __post_init__(self):
        if self.allowed_roles is None:
            self.allowed_roles = set()
        if self.allowed_members is None:
            self.allowed_members = set()
        if self.required_permissions is None:
            self.required_permissions = {Permission.EXECUTE}
        if self.conditions is None:
            self.conditions = []


class AccessControlManager:
    """Manages tool access control and security policies."""
    
    def __init__(self):
        self.policies: Dict[str, AccessPolicy] = {}
        self.member_permissions: Dict[str, Dict[str, Set[Permission]]] = {}  # member -> tool -> permissions
        self.role_permissions: Dict[TeamRole, Dict[str, Set[Permission]]] = {}  # role -> tool -> permissions
        self.access_log: List[Dict[str, Any]] = []
        self.security_violations: List[Dict[str, Any]] = []
        
    def create_policy(self, policy: AccessPolicy, creator: str) -> bool:
        """Create or update access policy."""
        self.policies[policy.tool_name] = policy
        
        self._log_access_event("policy_created", creator, policy.tool_name, 
                              {"access_level": policy.access_level.value})
        
        logger.info(f"Created access policy for tool '{policy.tool_name}' by {creator}")
        return True
    
    def grant_permission(self, member_id: str, tool_name: str, permission: Permission, grantor: str) -> bool:
        """Grant specific permission to member for tool."""
        if not self._can_grant_permission(grantor, tool_name, permission):
            self._log_security_violation("unauthorized_grant_attempt", grantor, tool_name)
            return False
        
        if member_id not in self.member_permissions:
            self.member_permissions[member_id] = {}
        
        if tool_name not in self.member_permissions[member_id]:
            self.member_permissions[member_id][tool_name] = set()
        
        self.member_permissions[member_id][tool_name].add(permission)
        
        self._log_access_event("permission_granted", grantor, tool_name, 
                              {"member": member_id, "permission": permission.value})
        
        logger.info(f"Granted {permission.value} permission on {tool_name} to {member_id}")
        return True
    
    def revoke_permission(self, member_id: str, tool_name: str, permission: Permission, revoker: str) -> bool:
        """Revoke specific permission from member for tool."""
        if not self._can_grant_permission(revoker, tool_name, permission):
            self._log_security_violation("unauthorized_revoke_attempt", revoker, tool_name)
            return False
        
        if (member_id in self.member_permissions and 
            tool_name in self.member_permissions[member_id]):
            self.member_permissions[member_id][tool_name].discard(permission)
            
            self._log_access_event("permission_revoked", revoker, tool_name,
                                  {"member": member_id, "permission": permission.value})
            
            logger.info(f"Revoked {permission.value} permission on {tool_name} from {member_id}")
            return True
        
        return False
    
    def check_access(self, member_id: str, member_role: TeamRole, tool_name: str, 
                    permission: Permission) -> bool:
        """Check if member has permission to access tool."""
        policy = self.policies.get(tool_name)
        
        if not policy:
            # No policy = default public access with execute permission
            result = permission == Permission.EXECUTE
        else:
            result = self._evaluate_policy(member_id, member_role, policy, permission)
        
        # Log access attempt
        self._log_access_event("access_check", member_id, tool_name, 
                              {"permission": permission.value, "granted": result})
        
        if not result:
            self._log_security_violation("access_denied", member_id, tool_name)
        
        return result
    
    def get_accessible_tools(self, member_id: str, member_role: TeamRole) -> Dict[str, Set[Permission]]:
        """Get all tools accessible to member with their permissions."""
        accessible = {}
        
        for tool_name, policy in self.policies.items():
            available_permissions = set()
            
            for permission in Permission:
                if self.check_access(member_id, member_role, tool_name, permission):
                    available_permissions.add(permission)
            
            if available_permissions:
                accessible[tool_name] = available_permissions
        
        return accessible
    
    def audit_access_patterns(self, member_id: Optional[str] = None) -> Dict[str, Any]:
        """Audit access patterns for security analysis."""
        relevant_logs = self.access_log
        
        if member_id:
            relevant_logs = [log for log in self.access_log if log.get("member") == member_id]
        
        # Analyze patterns
        access_counts = {}
        denied_access = {}
        
        for log in relevant_logs:
            if log["event"] == "access_check":
                tool = log["tool"]
                member = log["member"]
                
                key = f"{member}:{tool}"
                access_counts[key] = access_counts.get(key, 0) + 1
                
                if not log["metadata"].get("granted", False):
                    denied_access[key] = denied_access.get(key, 0) + 1
        
        return {
            "total_access_attempts": len(relevant_logs),
            "security_violations": len(self.security_violations),
            "most_accessed_tools": self._get_top_items(access_counts, 5),
            "most_denied_access": self._get_top_items(denied_access, 5),
            "violation_summary": self._summarize_violations()
        }
    
    def _evaluate_policy(self, member_id: str, member_role: TeamRole, 
                        policy: AccessPolicy, permission: Permission) -> bool:
        """Evaluate access policy for member."""
        # Check required permission
        if permission not in policy.required_permissions:
            return False
        
        # Check access level
        if policy.access_level == AccessLevel.PRIVATE:
            return False  # Only owner access (handled elsewhere)
        
        if policy.access_level == AccessLevel.PUBLIC:
            return True
        
        if policy.access_level == AccessLevel.ROLE_RESTRICTED:
            if member_role not in policy.allowed_roles:
                return False
        
        if policy.access_level == AccessLevel.MEMBER_RESTRICTED:
            if member_id not in policy.allowed_members:
                return False
        
        # Check explicit member permissions
        member_perms = self.member_permissions.get(member_id, {}).get(policy.tool_name, set())
        if permission in member_perms:
            return True
        
        # Check role permissions
        role_perms = self.role_permissions.get(member_role, {}).get(policy.tool_name, set())
        if permission in role_perms:
            return True
        
        # Check custom conditions
        for condition in policy.conditions:
            try:
                if not condition(member_id, member_role, permission):
                    return False
            except Exception as e:
                logger.error(f"Access condition check failed: {e}")
                return False
        
        return True
    
    def _can_grant_permission(self, grantor: str, tool_name: str, permission: Permission) -> bool:
        """Check if grantor can grant permission."""
        # For now, only members with ADMIN permission can grant permissions
        grantor_perms = self.member_permissions.get(grantor, {}).get(tool_name, set())
        return Permission.ADMIN in grantor_perms
    
    def _log_access_event(self, event: str, member: str, tool: str, metadata: Dict[str, Any] = None) -> None:
        """Log access event."""
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.now(),
            "event": event,
            "member": member,
            "tool": tool,
            "metadata": metadata or {}
        }
        
        self.access_log.append(log_entry)
        
        # Keep log size manageable
        if len(self.access_log) > 10000:
            self.access_log = self.access_log[-5000:]
    
    def _log_security_violation(self, violation_type: str, member: str, tool: str) -> None:
        """Log security violation."""
        from datetime import datetime
        
        violation = {
            "timestamp": datetime.now(),
            "type": violation_type,
            "member": member,
            "tool": tool
        }
        
        self.security_violations.append(violation)
        logger.warning(f"Security violation: {violation_type} by {member} on {tool}")
    
    def _get_top_items(self, counts: Dict[str, int], limit: int) -> List[tuple]:
        """Get top items by count."""
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:limit]
    
    def _summarize_violations(self) -> Dict[str, int]:
        """Summarize security violations by type."""
        summary = {}
        for violation in self.security_violations:
            vtype = violation["type"]
            summary[vtype] = summary.get(vtype, 0) + 1
        return summary

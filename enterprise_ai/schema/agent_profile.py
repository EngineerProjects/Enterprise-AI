"""
Enterprise AI Agent Profile Schema.

Minimal profile approach - stores only essential collaboration information.
Agents derive skills and capabilities on-demand through intelligent querying.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


class AgentStatus(Enum):
    """Agent availability status."""
    AVAILABLE = "available"
    BUSY = "busy"
    BLOCKED = "blocked"
    OFFLINE = "offline"


@dataclass
class AgentRoleInfo:
    """
    Agent role with name and description.
    
    Simple role information for team collaboration context.
    """
    name: str
    description: Optional[str] = None
    
    def __post_init__(self):
        """Auto-generate description if not provided."""
        if not self.description:
            self.description = f"{self.name.title()} specialist"


@dataclass
class AgentCapacity:
    """
    Agent capacity tracking - workload and status only.
    
    Minimal capacity info for team intelligence.
    """
    workload: float = 0.0  # 0.0 to 1.0 (percentage)
    status: AgentStatus = AgentStatus.AVAILABLE
    last_updated: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate capacity values."""
        if not 0.0 <= self.workload <= 1.0:
            raise ValueError(f"Workload must be between 0.0 and 1.0, got {self.workload}")
    
    @property
    def availability_percentage(self) -> float:
        """Get availability as percentage (inverse of workload)."""
        return round((1.0 - self.workload) * 100, 1)
    
    @property
    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        return self.status == AgentStatus.AVAILABLE and self.workload < 0.9
    
    @property
    def is_overloaded(self) -> bool:
        """Check if agent is overloaded."""
        return self.workload >= 0.9
    
    def update_workload(self, new_workload: float) -> None:
        """Update workload and timestamp."""
        if not 0.0 <= new_workload <= 1.0:
            raise ValueError(f"Workload must be between 0.0 and 1.0, got {new_workload}")
        self.workload = new_workload
        self.last_updated = datetime.now()
        
        # Auto-update status based on workload
        if new_workload >= 0.9:
            self.status = AgentStatus.BUSY
        elif self.status == AgentStatus.BUSY and new_workload < 0.7:
            self.status = AgentStatus.AVAILABLE
    
    def set_status(self, status: AgentStatus) -> None:
        """Update status and timestamp."""
        self.status = status
        self.last_updated = datetime.now()


@dataclass
class AgentProfile:
    """
    Minimal agent profile for team collaboration.
    
    Contains ONLY essential information:
    - name: agent identifier
    - role: name + description for expertise context
    - available_tools: what the agent can do
    - capacity: current workload + status
    
    Everything else (skills, capabilities, etc.) should be derived on-demand.
    """
    name: str
    role: AgentRoleInfo
    available_tools: List[str] = field(default_factory=list)
    capacity: AgentCapacity = field(default_factory=AgentCapacity)
    
    def __post_init__(self):
        """Validate profile data."""
        if not self.name or not self.name.strip():
            raise ValueError("Agent name cannot be empty")
        
        # Ensure name is lowercase for consistency
        self.name = self.name.lower().strip()
        
        # Ensure role is AgentRoleInfo instance
        if isinstance(self.role, str):
            self.role = AgentRoleInfo(name=self.role)
        elif isinstance(self.role, dict):
            self.role = AgentRoleInfo(**self.role)
    
    @classmethod
    def create(
        cls,
        name: str,
        role_name: str,
        role_description: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
        initial_workload: float = 0.0,
        status: AgentStatus = AgentStatus.AVAILABLE
    ) -> "AgentProfile":
        """Create minimal agent profile."""
        role = AgentRoleInfo(name=role_name, description=role_description)
        capacity = AgentCapacity(workload=initial_workload, status=status)
        
        return cls(
            name=name,
            role=role,
            available_tools=available_tools or [],
            capacity=capacity
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to the exact minimal format we agreed on."""
        return {
            "name": self.name,
            "role": {
                "name": self.role.name,
                "description": self.role.description
            },
            "available_tools": self.available_tools,
            "capacity": {
                "workload": self.capacity.workload,
                "status": self.capacity.status.value
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProfile":
        """Create profile from dictionary."""
        # Extract role info
        role_data = data.get("role", {})
        if isinstance(role_data, str):
            role = AgentRoleInfo(name=role_data)
        else:
            role = AgentRoleInfo(
                name=role_data.get("name", "agent"),
                description=role_data.get("description")
            )
        
        # Extract capacity info
        capacity_data = data.get("capacity", {})
        capacity = AgentCapacity(
            workload=capacity_data.get("workload", 0.0),
            status=AgentStatus(capacity_data.get("status", "available"))
        )
        
        return cls(
            name=data["name"],
            role=role,
            available_tools=data.get("available_tools", []),
            capacity=capacity
        )
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has access to a specific tool."""
        return tool_name.lower() in [tool.lower() for tool in self.available_tools]
    
    def has_any_tools(self, tool_names: List[str]) -> bool:
        """Check if agent has any of the specified tools."""
        return any(self.has_tool(tool) for tool in tool_names)
    
    def has_all_tools(self, tool_names: List[str]) -> bool:
        """Check if agent has all of the specified tools."""
        return all(self.has_tool(tool) for tool in tool_names)
    
    def matches_role_pattern(self, pattern: str) -> bool:
        """Check if role name or description contains pattern."""
        pattern_lower = pattern.lower()
        return (
            pattern_lower in self.role.name.lower() or
            (self.role.description and pattern_lower in self.role.description.lower())
        )
    
    def update_tools(self, tools: List[str]) -> None:
        """Update available tools list."""
        self.available_tools = sorted(list(set(tools)))  # Remove duplicates and sort
    
    def add_tool(self, tool_name: str) -> None:
        """Add a single tool if not already present."""
        if not self.has_tool(tool_name):
            self.available_tools.append(tool_name)
            self.available_tools.sort()
    
    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool if present."""
        self.available_tools = [tool for tool in self.available_tools 
                             if tool.lower() != tool_name.lower()]

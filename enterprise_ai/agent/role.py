"""
Enterprise AI Agent - Role Definitions.

Defines the role system that provides system prompts and capabilities for agents.
"""

from typing import List, Optional, Dict, Any
from enterprise_ai.agent.prompts import BASE_SYSTEM_PROMPT


class AgentRole:
    """
    Defines an agent's role through system prompts and capabilities.
    
    Roles encapsulate the system prompt and special capabilities that
    define how an agent behaves and what it specializes in.
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize an agent role.
        
        Args:
            name: Role name
            system_prompt: System prompt defining the role (uses default if None)
            capabilities: List of capabilities this role provides
            description: Human-readable description
            metadata: Additional metadata for the role
        """
        self.name = name
        self.system_prompt = system_prompt or self._generate_default_prompt(name)
        self.capabilities = capabilities or []
        self.description = description or f"{name} Agent"
        self.metadata = metadata or {}
    
    def _generate_default_prompt(self, name: str) -> str:
        """Generate a default system prompt for the role."""
        return f"{BASE_SYSTEM_PROMPT}\n\nYou are {name}, a specialized AI assistant."
    
    @classmethod
    def custom(cls, name: str, system_prompt: str, capabilities: Optional[List[str]] = None) -> "AgentRole":
        """Create a custom role with a specific system prompt."""
        return cls(
            name=name,
            system_prompt=system_prompt,
            capabilities=capabilities or [],
            description=f"Custom {name} agent"
        )
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "AgentRole":
        """
        Create role from configuration dictionary.
        
        Args:
            config: Dictionary with role configuration
                   - name: Role name (required)
                   - system_prompt: System prompt text
                   - description: Role description
                   - capabilities: List of capabilities
                   - metadata: Additional metadata
                   
        Returns:
            AgentRole instance
        """
        return cls(
            name=config["name"],
            system_prompt=config.get("system_prompt"),
            capabilities=config.get("capabilities", []),
            description=config.get("description"),
            metadata=config.get("metadata", {})
        )
    
    def to_config(self) -> Dict[str, Any]:
        """Export role to configuration dictionary."""
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "capabilities": self.capabilities,
            "description": self.description,
            "metadata": self.metadata
        }
    
    def update_from_config(self, config: Dict[str, Any]) -> None:
        """Update role properties from configuration dictionary."""
        if "name" in config:
            self.name = config["name"]
        if "system_prompt" in config:
            self.system_prompt = config["system_prompt"]
        if "capabilities" in config:
            self.capabilities = config["capabilities"]
        if "description" in config:
            self.description = config["description"]
        if "metadata" in config:
            self.metadata.update(config["metadata"])
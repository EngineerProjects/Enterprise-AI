"""
Simple prompt manager for Enterprise AI agents.

Replaces the complex template system with a clean, simple approach.
"""

from typing import Dict, Optional, List
import importlib
from pathlib import Path


class PromptManager:
    """Simple prompt manager following OpenManus approach."""
    
    def __init__(self):
        self._prompt_modules = {}
        self._load_prompt_modules()
    
    def _load_prompt_modules(self):
        """Load all prompt modules dynamically."""
        prompt_dir = Path(__file__).parent
        
        for prompt_file in prompt_dir.glob("*.py"):
            if prompt_file.name in ("__init__.py", "manager.py"):
                continue
            
            module_name = prompt_file.stem
            try:
                module = importlib.import_module(f"enterprise_ai.prompt.{module_name}")
                self._prompt_modules[module_name] = module
            except ImportError as e:
                print(f"Warning: Could not load prompt module {module_name}: {e}")
    
    def get_system_prompt(self, agent_type: str) -> Optional[str]:
        """Get system prompt for an agent type."""
        module = self._prompt_modules.get(agent_type)
        if module and hasattr(module, 'SYSTEM_PROMPT'):
            return module.SYSTEM_PROMPT
        return None
    
    def get_next_step_prompt(self, agent_type: str) -> Optional[str]:
        """Get next step prompt for an agent type."""
        module = self._prompt_modules.get(agent_type)
        if module and hasattr(module, 'NEXT_STEP_PROMPT'):
            return module.NEXT_STEP_PROMPT
        return None
    
    def get_available_types(self) -> List[str]:
        """Get list of available agent types."""
        return list(self._prompt_modules.keys())
    
    def create_contextual_prompt(self, agent_type: str, context: Dict = None) -> Optional[str]:
        """Create a contextualized system prompt."""
        base_prompt = self.get_system_prompt(agent_type)
        if not base_prompt:
            return None
        
        if context:
            context_lines = []
            
            if "available_tools" in context:
                tools = context["available_tools"]
                if tools:
                    context_lines.append(f"**Available MCP Tools**: {', '.join(tools)}")
            
            if "current_task" in context:
                context_lines.append(f"**Current Task**: {context['current_task']}")
            
            if "team_members" in context:
                members = context["team_members"]
                if members:
                    context_lines.append(f"**Team Members**: {', '.join(members)}")
            
            if "memory_summary" in context:
                context_lines.append(f"**Recent Memory**: {context['memory_summary']}")
            
            if context_lines:
                base_prompt += "\n\n**Current Context:**\n" + "\n".join(context_lines)
        
        return base_prompt


# Global instance
_prompt_manager = None

def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

def get_system_prompt(agent_type: str, context: Dict = None) -> Optional[str]:
    """Get system prompt for agent type with optional context."""
    manager = get_prompt_manager()
    if context:
        return manager.create_contextual_prompt(agent_type, context)
    return manager.get_system_prompt(agent_type)

def get_next_step_prompt(agent_type: str) -> Optional[str]:
    """Get next step prompt for agent type."""
    return get_prompt_manager().get_next_step_prompt(agent_type)

def get_available_agent_types() -> List[str]:
    """Get list of available agent types."""
    return get_prompt_manager().get_available_types()

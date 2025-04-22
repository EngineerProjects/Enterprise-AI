"""
Enhanced prompt management functionality.

This module provides the core functionality for loading, formatting,
and managing prompts throughout the Enterprise AI system with support
for composite prompts and tool integration.
"""

import os
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Union, Tuple

from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger

logger = get_logger("prompt.base")


class PromptTemplate:
    """Template for generating prompts with variable substitution."""

    def __init__(self, template: str, metadata: Optional[Dict[str, Any]] = None):
        """Initialize prompt template.

        Args:
            template: Template string with $variable placeholders
            metadata: Optional metadata about the prompt
        """
        self.template_str = template
        self.template = Template(template)
        self.metadata = metadata or {}

    def format(self, **kwargs: Any) -> str:
        """Format the template with the provided values.

        Args:
            **kwargs: Values for template variables

        Returns:
            Formatted prompt string
        """
        try:
            return self.template.safe_substitute(**kwargs)
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            # Fallback to original template if formatting fails
            return self.template_str

    def __str__(self) -> str:
        """String representation of the template."""
        return self.template_str


class PromptLibrary:
    """Manager for accessing and organizing prompts."""

    def __init__(self, prompt_dir: Optional[str] = None):
        """Initialize prompt library.

        Args:
            prompt_dir: Directory containing prompt files
        """
        self.prompt_dir = prompt_dir or get_config(
            "prompt.directory", os.path.join(os.path.dirname(__file__), "templates")
        )
        self._prompts: Dict[str, PromptTemplate] = {}
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompts from the prompt directory."""
        if not os.path.exists(self.prompt_dir):
            logger.warning(f"Prompt directory not found: {self.prompt_dir}")
            return

        # Load prompts from files
        for root, _, files in os.walk(self.prompt_dir):
            for file in files:
                if file.endswith((".txt", ".prompt")):
                    try:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, self.prompt_dir)
                        prompt_id = os.path.splitext(relative_path)[0].replace(os.path.sep, ".")

                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        self._prompts[prompt_id] = PromptTemplate(
                            content,
                            metadata={"source_file": file_path, "category": os.path.basename(root)},
                        )
                        logger.debug(f"Loaded prompt: {prompt_id}")
                    except Exception as e:
                        logger.error(f"Failed to load prompt {file}: {e}")

    def get_prompt(self, prompt_id: str) -> Optional[PromptTemplate]:
        """Get a prompt by ID.

        Args:
            prompt_id: Prompt identifier

        Returns:
            Prompt template if found, None otherwise
        """
        return self._prompts.get(prompt_id)

    def format_prompt(self, prompt_id: str, **kwargs: Any) -> Optional[str]:
        """Get a formatted prompt by ID.

        Args:
            prompt_id: Prompt identifier
            **kwargs: Values for template variables

        Returns:
            Formatted prompt string if found, None otherwise
        """
        prompt = self.get_prompt(prompt_id)
        if prompt:
            return prompt.format(**kwargs)
        return None

    def combine_prompts(self, prompt_ids: List[str], **kwargs: Any) -> Optional[str]:
        """Combine multiple prompts and format them.

        Args:
            prompt_ids: List of prompt identifiers to combine
            **kwargs: Values for template variables

        Returns:
            Combined and formatted prompt string if all prompts found, None otherwise
        """
        prompt_templates = []
        for prompt_id in prompt_ids:
            prompt = self.get_prompt(prompt_id)
            if not prompt:
                logger.error(f"Prompt not found: {prompt_id}")
                return None
            prompt_templates.append(prompt)

        # Combine the templates
        combined_template = "\n\n".join(pt.template_str for pt in prompt_templates)
        combined_prompt = PromptTemplate(combined_template)

        # Format the combined template
        return combined_prompt.format(**kwargs)

    def create_composite_prompt(self, role_id: str, system_id: str, **kwargs: Any) -> Optional[str]:
        """Create a composite prompt combining a role and system prompt.

        Args:
            role_id: Role prompt identifier
            system_id: System prompt identifier
            **kwargs: Values for template variables

        Returns:
            Combined and formatted prompt string if both prompts found, None otherwise
        """
        role_prompt = self.get_prompt(f"roles.{role_id}")
        system_prompt = self.get_prompt(f"system.{system_id}")

        if not role_prompt:
            logger.error(f"Role prompt not found: {role_id}")
            return None

        if not system_prompt:
            logger.error(f"System prompt not found: {system_id}")
            return None

        # Combine the templates
        combined_template = f"{system_prompt.template_str}\n\n{role_prompt.template_str}"
        combined_prompt = PromptTemplate(combined_template)

        # Format the combined template
        return combined_prompt.format(**kwargs)

    def add_prompt(
        self, prompt_id: str, template: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a prompt to the library.

        Args:
            prompt_id: Prompt identifier
            template: Template string
            metadata: Optional metadata
        """
        self._prompts[prompt_id] = PromptTemplate(template, metadata)

    def list_prompts(self) -> Dict[str, List[str]]:
        """List available prompt IDs grouped by category.

        Returns:
            Dictionary of prompt IDs grouped by category
        """
        categories: Dict[str, List[str]] = {}

        for prompt_id, prompt in self._prompts.items():
            category = prompt.metadata.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(prompt_id)

        return categories


# Global prompt library instance
_global_prompt_library: Optional[PromptLibrary] = None


def get_prompt_library() -> PromptLibrary:
    """Get the global prompt library instance.

    Returns:
        Global prompt library
    """
    global _global_prompt_library
    if _global_prompt_library is None:
        _global_prompt_library = PromptLibrary()
    return _global_prompt_library


def get_prompt(prompt_id: str) -> Optional[PromptTemplate]:
    """Get a prompt template by ID.

    Args:
        prompt_id: Prompt identifier

    Returns:
        Prompt template if found, None otherwise
    """
    return get_prompt_library().get_prompt(prompt_id)


def format_prompt(prompt_id: str, **kwargs: Any) -> Optional[str]:
    """Format a prompt by ID.

    Args:
        prompt_id: Prompt identifier
        **kwargs: Values for template variables

    Returns:
        Formatted prompt string if found, None otherwise
    """
    return get_prompt_library().format_prompt(prompt_id, **kwargs)


def combine_prompts(prompt_ids: List[str], **kwargs: Any) -> Optional[str]:
    """Combine multiple prompts and format them.

    Args:
        prompt_ids: List of prompt identifiers to combine
        **kwargs: Values for template variables

    Returns:
        Combined and formatted prompt string if all prompts found, None otherwise
    """
    return get_prompt_library().combine_prompts(prompt_ids, **kwargs)


def create_composite_prompt(role_id: str, system_id: str, **kwargs: Any) -> Optional[str]:
    """Create a composite prompt combining a role and system prompt.

    Args:
        role_id: Role prompt identifier
        system_id: System prompt identifier
        **kwargs: Values for template variables

    Returns:
        Combined and formatted prompt string if both prompts found, None otherwise
    """
    return get_prompt_library().create_composite_prompt(role_id, system_id, **kwargs)

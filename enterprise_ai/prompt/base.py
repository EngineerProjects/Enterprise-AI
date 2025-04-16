"""
Base prompt management functionality.

This module provides the core functionality for loading, formatting,
and managing prompts throughout the Enterprise AI system.
"""

import os
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Union

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
                            content, metadata={"source_file": file_path}
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

    def list_prompts(self) -> List[str]:
        """List available prompt IDs.

        Returns:
            List of prompt IDs
        """
        return list(self._prompts.keys())


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

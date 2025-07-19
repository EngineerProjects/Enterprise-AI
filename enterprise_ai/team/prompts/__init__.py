"""
Enterprise AI Team - Prompts Module.

This module provides prompts for team-based agent coordination and collaboration.
"""

from enterprise_ai.team.prompts.manager import (
    MANAGER_SYSTEM_PROMPT,
    DELEGATION_TEMPLATE,
    AGGREGATION_PROMPT,
    MANAGER_REFLECTION_PROMPT
)

from enterprise_ai.team.prompts.collaboration import (
    COLLABORATION_SYSTEM_PROMPT,
    TASK_PROCESSING_PROMPT,
    INFORMATION_SHARING_PROMPT,
    FEEDBACK_PROMPT,
    COLLABORATION_REQUEST_TEMPLATE
)

__all__ = [
    'MANAGER_SYSTEM_PROMPT',
    'DELEGATION_TEMPLATE',
    'AGGREGATION_PROMPT',
    'MANAGER_REFLECTION_PROMPT',
    'COLLABORATION_SYSTEM_PROMPT',
    'TASK_PROCESSING_PROMPT',
    'INFORMATION_SHARING_PROMPT',
    'FEEDBACK_PROMPT',
    'COLLABORATION_REQUEST_TEMPLATE',
]
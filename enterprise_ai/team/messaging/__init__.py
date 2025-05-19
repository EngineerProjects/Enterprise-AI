"""
Team messaging module for Enterprise AI.

This module provides messaging functionality for team communication,
including routing and broadcast capabilities.
"""

from enterprise_ai.team.messaging.enhanced import (
    EnhancedMessagingManager, 
    MessageRouterStrategy,
    DirectRoutingStrategy,
    HierarchicalRoutingStrategy,
    GroupRoutingStrategy
)

__all__ = [
    "EnhancedMessagingManager",
    "MessageRouterStrategy",
    "DirectRoutingStrategy",
    "HierarchicalRoutingStrategy",
    "GroupRoutingStrategy"
]

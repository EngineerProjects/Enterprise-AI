"""
Enterprise AI Agent Module

This module provides intelligent agents that can reason, plan, and execute
tasks using the MCP (Model Context Protocol) framework.

Key Components:
- BaseAgent: Foundation for all agents
- Reasoning engines: CoT, ReAct, SWE, Browser
- Memory systems: Conversation, task, knowledge
- Specialized agents: Developer, Researcher, Assistant

Usage:
    from enterprise_ai.agent import SimpleAgent
    from enterprise_ai.mcp import EnterpriseMCPServer
    
    # Create MCP server
    server = EnterpriseMCPServer()
    
    # Create agent
    agent = SimpleAgent("assistant", llm_provider, server)
    await agent.initialize()
    
    # Execute task
    result = await agent.execute_task("List files in /tmp directory")
"""

from .base import BaseAgent

__all__ = [
    "BaseAgent",
]

__version__ = "1.0.0"

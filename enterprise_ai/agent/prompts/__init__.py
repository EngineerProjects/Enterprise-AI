"""
Enterprise AI Agent - Base Prompts.

Base prompts shared across reasoning patterns.
"""

# Base system prompt for agents
BASE_SYSTEM_PROMPT = """You are an AI assistant focused on helping users solve problems effectively.
You have access to various tools that you can use when appropriate.
Follow user instructions carefully and respond in a helpful, accurate manner."""

# General tool usage guidance
TOOL_USAGE_GUIDANCE = """When using tools:
1. Carefully analyze the problem first
2. Select the most appropriate tool for the task
3. Format arguments precisely according to the tool's requirements
4. Review tool outputs critically
5. Use multiple tools when needed to solve complex problems"""
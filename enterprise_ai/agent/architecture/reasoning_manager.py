"""
Reasoning framework management for agents.

This module handles the selection, initialization, and management
of reasoning frameworks used by agents to process inputs and tasks.
"""

import asyncio
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union, cast

from enterprise_ai.agent.architecture.errors import AgentError, AgentErrorCode, ErrorManager
from enterprise_ai.agent.architecture.utils import ensure_event_loop
from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol

logger = get_logger("agent.reasoning_manager")


class ReasoningMode(str, Enum):
    """Different reasoning modes an agent can operate in."""
    
    DEFAULT = "default"
    STEP_BY_STEP = "step_by_step"
    PROBLEM_SOLVING = "problem_solving"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    PLANNING = "planning"


class ReasoningManagerConfig:
    """Configuration for the reasoning manager."""
    
    def __init__(
        self,
        default_framework: str = "base",
        auto_select: bool = True,
        context_preservation: bool = True,
        dynamic_adaptation: bool = False,
        reasoning_mode: ReasoningMode = ReasoningMode.DEFAULT,
    ):
        """Initialize reasoning manager configuration.
        
        Args:
            default_framework: Default reasoning framework to use
            auto_select: Whether to automatically select frameworks based on input
            context_preservation: Whether to preserve context between framework switches
            dynamic_adaptation: Whether to dynamically adapt reasoning approach based on performance
            reasoning_mode: Initial reasoning mode
        """
        self.default_framework = default_framework
        self.auto_select = auto_select
        self.context_preservation = context_preservation
        self.dynamic_adaptation = dynamic_adaptation
        self.reasoning_mode = reasoning_mode


class ReasoningManager:
    """Manager for agent reasoning frameworks."""
    
    def __init__(self, agent: Any, config: Optional[ReasoningManagerConfig] = None):
        """Initialize the reasoning manager.
        
        Args:
            agent: The agent instance
            config: Optional reasoning manager configuration
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", "unknown")
        self.config = config or ReasoningManagerConfig()
        self.current_framework_name = self.config.default_framework
        self.current_mode = self.config.reasoning_mode
        self._error_manager = ErrorManager(self.agent_id)
        self._framework_stats: Dict[str, Dict[str, Any]] = {}
        self._framework_context: Dict[str, Dict[str, Any]] = {}
        
        # Import frameworks here to avoid circular imports
        from enterprise_ai.agent.reasoning.base import (
            get_framework, get_framework_descriptions, list_frameworks
        )
        
        self._get_framework = get_framework
        self._get_framework_descriptions = get_framework_descriptions
        self._list_frameworks = list_frameworks
        
        # Initialize framework stats
        for framework_name in self._list_frameworks():
            self._framework_stats[framework_name] = {
                "usage_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "avg_execution_time": 0.0,
                "execution_times": [],
            }
            self._framework_context[framework_name] = {}
        
        logger.info(f"Initialized reasoning manager for agent {self.agent_id}")

    def get_current_framework(self) -> Any:
        """Get the current reasoning framework.
        
        Returns:
            Current reasoning framework
        """
        return self._get_framework(self.current_framework_name)

    def set_framework(self, framework_name: str) -> bool:
        """Set the current reasoning framework.
        
        Args:
            framework_name: Name of the framework to use
            
        Returns:
            True if successful, False if framework not found
        """
        if framework_name not in self._list_frameworks():
            logger.error(f"Unknown reasoning framework: {framework_name}")
            return False
        
        # Store context of current framework if enabled
        if self.config.context_preservation:
            self._store_framework_context()
        
        # Switch framework
        self.current_framework_name = framework_name
        
        # Restore context of new framework if enabled
        if self.config.context_preservation:
            self._restore_framework_context()
        
        logger.info(f"Switched to reasoning framework: {framework_name}")
        return True

    def set_reasoning_mode(self, mode: ReasoningMode) -> None:
        """Set the reasoning mode.
        
        Args:
            mode: New reasoning mode
        """
        self.current_mode = mode
        
        # Automatically select framework based on mode if auto-select is enabled
        if self.config.auto_select:
            framework = self._select_framework_for_mode(mode)
            if framework != self.current_framework_name:
                self.set_framework(framework)
        
        logger.info(f"Set reasoning mode to: {mode}")

    def _select_framework_for_mode(self, mode: ReasoningMode) -> str:
        """Select an appropriate framework for a reasoning mode.
        
        Args:
            mode: Reasoning mode
            
        Returns:
            Selected framework name
        """
        # Map modes to frameworks
        if mode == ReasoningMode.STEP_BY_STEP:
            return "cot"  # Chain of Thought is good for step-by-step reasoning
        elif mode == ReasoningMode.PROBLEM_SOLVING:
            return "react"  # ReAct is good for problem-solving with tools
        elif mode == ReasoningMode.CREATIVE:
            return "cot"  # Chain of Thought can be good for creative tasks too
        elif mode == ReasoningMode.ANALYTICAL:
            return "swe"  # Software Engineering reasoning is good for analytical tasks
        elif mode == ReasoningMode.PLANNING:
            return "mcp"  # MCP is good for planning with tools
        else:
            return self.config.default_framework

    def _store_framework_context(self) -> None:
        """Store context of the current framework."""
        # This would be implemented to capture the state of the current framework
        # that needs to be preserved across framework switches
        pass

    def _restore_framework_context(self) -> None:
        """Restore context of the current framework."""
        # This would be implemented to restore the state of the current framework
        # that was preserved from a previous usage
        pass

    def select_framework_for_input(self, input_text: str) -> str:
        """Select an appropriate framework for a given input.
        
        Args:
            input_text: Input text to analyze
            
        Returns:
            Selected framework name
        """
        # This is a simple implementation that could be enhanced with more sophisticated analysis
        
        # Check for code-related content
        if any(kw in input_text.lower() for kw in ["code", "function", "class", "program", "debug"]):
            return "swe"
        
        # Check for tool-use indications
        if any(kw in input_text.lower() for kw in ["use tool", "search", "look up", "tool", "find"]):
            return "react"
        
        # Check for planning content
        if any(kw in input_text.lower() for kw in ["plan", "steps", "schedule", "organize"]):
            return "mcp"
        
        # Check for reasoning indications
        if any(kw in input_text.lower() for kw in ["explain", "why", "how", "reason", "think"]):
            return "cot"
        
        # Default
        return self.config.default_framework

    def select_framework_for_task(self, task_description: str) -> str:
        """Select an appropriate framework for a given task.
        
        Args:
            task_description: Task description to analyze
            
        Returns:
            Selected framework name
        """
        # Similar to select_framework_for_input but focused on task-specific analysis
        return self.select_framework_for_input(task_description)

    async def process_input(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process input using the appropriate reasoning framework.
        
        Args:
            messages: List of messages to process
            **kwargs: Additional parameters for the framework
            
        Returns:
            Framework-processed response
        """
        # Extract the latest user message for analysis
        latest_user_message = None
        for message in reversed(messages):
            if message.role == "user":
                latest_user_message = message
                break
        
        # Select appropriate framework if auto-select is enabled
        if self.config.auto_select and latest_user_message and latest_user_message.content:
            selected_framework = self.select_framework_for_input(latest_user_message.content)
            if selected_framework != self.current_framework_name:
                self.set_framework(selected_framework)
        
        # Get the framework
        framework = self.get_current_framework()
        
        # Record usage
        self._framework_stats[self.current_framework_name]["usage_count"] += 1
        
        # Process with the framework
        try:
            import time
            start_time = time.time()
            
            # Add any required context to kwargs
            kwargs["reasoning_mode"] = self.current_mode
            
            # Note: We don't add llm_provider to kwargs anymore - it will be retrieved
            # directly from the agent in the reasoning framework to prevent serialization issues
            
            # Process input
            response = await self._process_with_framework(framework, messages, **kwargs)
            
            # Record success and execution time
            execution_time = time.time() - start_time
            self._record_framework_stats(self.current_framework_name, True, execution_time)
            
            return response
        except Exception as e:
            # Record failure
            execution_time = time.time() - start_time
            self._record_framework_stats(self.current_framework_name, False, execution_time)
            
            # Handle error
            error = self._error_manager.handle_error(
                e, error_code=AgentErrorCode.EXECUTION_FAILED,
                context={"framework": self.current_framework_name}
            )
            
            logger.error(f"Error processing input with framework {self.current_framework_name}: {e}")
            
            # Fall back to default framework if different from current
            if self.current_framework_name != self.config.default_framework:
                logger.info(f"Falling back to default framework: {self.config.default_framework}")
                self.set_framework(self.config.default_framework)
                
                try:
                    # Try processing with default framework
                    return await self._process_with_framework(
                        self._get_framework(self.config.default_framework),
                        messages,
                        **kwargs
                    )
                except Exception as fallback_error:
                    # If even the fallback fails, create a simple error message
                    logger.error(f"Fallback framework also failed: {fallback_error}")
                    
                    from enterprise_ai.schema import Message
                    return cast(
                        MessageProtocol,
                        Message.assistant_message(
                            "I'm sorry, I encountered an error processing your request. "
                            "Please try again or rephrase your query."
                        )
                    )
            else:
                # Already using default framework, create error message
                from enterprise_ai.schema import Message
                return cast(
                    MessageProtocol,
                    Message.assistant_message(
                        "I'm sorry, I encountered an error processing your request. "
                        "Please try again or rephrase your query."
                    )
                )
    
    async def _process_with_framework(
        self, framework: Any, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process input with a specific framework.
        
        Args:
            framework: Reasoning framework to use
            messages: List of messages to process
            **kwargs: Additional parameters for the framework
            
        Returns:
            Framework-processed response
        """
        # Check if framework's process_input is async
        if hasattr(framework, "process_input"):
            process_func = getattr(framework, "process_input")
            
            if asyncio.iscoroutinefunction(process_func):
                # Async processing
                return await process_func(self.agent, messages, **kwargs)
            else:
                # Sync processing
                loop = ensure_event_loop()
                return await loop.run_in_executor(
                    None, lambda: process_func(self.agent, messages, **kwargs)
                )
        else:
            raise ValueError(f"Framework {framework} does not implement process_input")

    async def process_task(self, task: Any, **kwargs: Any) -> Any:
        """Process a task using the appropriate reasoning framework.
        
        Args:
            task: Task to process
            **kwargs: Additional parameters for the framework
            
        Returns:
            Framework-processed task status
        """
        # Select appropriate framework if auto-select is enabled
        if self.config.auto_select and hasattr(task, "description"):
            selected_framework = self.select_framework_for_task(task.description)
            if selected_framework != self.current_framework_name:
                self.set_framework(selected_framework)
        
        # Get the framework
        framework = self.get_current_framework()
        
        # Record usage
        self._framework_stats[self.current_framework_name]["usage_count"] += 1
        
        # Process with the framework
        try:
            import time
            start_time = time.time()
            
            # Add any required context to kwargs
            kwargs["reasoning_mode"] = self.current_mode
            
            # Note: We don't add llm_provider to kwargs anymore - it will be retrieved
            # directly from the agent in the reasoning framework to prevent serialization issues
            
            # Process task
            result = await self._process_task_with_framework(framework, task, **kwargs)
            
            # Record success and execution time
            execution_time = time.time() - start_time
            self._record_framework_stats(self.current_framework_name, True, execution_time)
            
            return result
        except Exception as e:
            # Record failure
            execution_time = time.time() - start_time
            self._record_framework_stats(self.current_framework_name, False, execution_time)
            
            # Handle error
            error = self._error_manager.handle_error(
                e, error_code=AgentErrorCode.EXECUTION_FAILED,
                context={"framework": self.current_framework_name}
            )
            
            logger.error(f"Error processing task with framework {self.current_framework_name}: {e}")
            
            # Fall back to default framework if different from current
            if self.current_framework_name != self.config.default_framework:
                logger.info(f"Falling back to default framework: {self.config.default_framework}")
                self.set_framework(self.config.default_framework)
                
                try:
                    # Try processing with default framework
                    return await self._process_task_with_framework(
                        self._get_framework(self.config.default_framework),
                        task,
                        **kwargs
                    )
                except Exception as fallback_error:
                    # If even the fallback fails, return failure
                    logger.error(f"Fallback framework also failed: {fallback_error}")
                    
                    # Return task failure
                    if hasattr(task, "status"):
                        # Assuming TaskStatus enum exists with FAILED attribute
                        task.status = getattr(task, "FAILED", "failed")
                    return task
            else:
                # Already using default framework, return failure
                if hasattr(task, "status"):
                    task.status = getattr(task, "FAILED", "failed")
                return task
    
    async def _process_task_with_framework(
        self, framework: Any, task: Any, **kwargs: Any
    ) -> Any:
        """Process a task with a specific framework.
        
        Args:
            framework: Reasoning framework to use
            task: Task to process
            **kwargs: Additional parameters for the framework
            
        Returns:
            Framework-processed task status
        """
        # Check if framework's process_task is async
        if hasattr(framework, "process_task"):
            process_func = getattr(framework, "process_task")
            
            if asyncio.iscoroutinefunction(process_func):
                # Async processing
                return await process_func(self.agent, task, **kwargs)
            else:
                # Sync processing
                loop = ensure_event_loop()
                return await loop.run_in_executor(
                    None, lambda: process_func(self.agent, task, **kwargs)
                )
        else:
            raise ValueError(f"Framework {framework} does not implement process_task")

    def _record_framework_stats(
        self, framework_name: str, success: bool, execution_time: float
    ) -> None:
        """Record statistics for a framework execution.
        
        Args:
            framework_name: Name of the framework
            success: Whether the execution was successful
            execution_time: Execution time in seconds
        """
        stats = self._framework_stats.get(framework_name, {})
        
        if success:
            stats["success_count"] = stats.get("success_count", 0) + 1
        else:
            stats["failure_count"] = stats.get("failure_count", 0) + 1
        
        execution_times = stats.get("execution_times", [])
        execution_times.append(execution_time)
        stats["execution_times"] = execution_times
        
        # Calculate average execution time
        if execution_times:
            stats["avg_execution_time"] = sum(execution_times) / len(execution_times)
        
        self._framework_stats[framework_name] = stats

    def format_system_prompt(self, base_prompt: str, **kwargs: Any) -> str:
        """Format a system prompt using the current framework.
        
        Args:
            base_prompt: Base system prompt
            **kwargs: Additional formatting parameters
            
        Returns:
            Formatted system prompt
        """
        framework = self.get_current_framework()
        
        if hasattr(framework, "format_system_prompt"):
            return framework.format_system_prompt(self.agent, base_prompt, **kwargs)
        return base_prompt

    def format_tool_instructions(self, tools: List[Dict[str, Any]], **kwargs: Any) -> str:
        """Format tool instructions using the current framework.
        
        Args:
            tools: List of available tools
            **kwargs: Additional formatting parameters
            
        Returns:
            Formatted tool instructions
        """
        framework = self.get_current_framework()
        
        if hasattr(framework, "format_tool_instructions"):
            return framework.format_tool_instructions(self.agent, tools, **kwargs)
        return ""

    def get_framework_stats(self, framework_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a specific framework or all frameworks.
        
        Args:
            framework_name: Optional name of framework to get stats for
            
        Returns:
            Dictionary of framework statistics
        """
        if framework_name:
            return self._framework_stats.get(framework_name, {}).copy()
        return {name: stats.copy() for name, stats in self._framework_stats.items()}

    def get_framework_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available frameworks.
        
        Returns:
            Dictionary mapping framework names to descriptions
        """
        return self._get_framework_descriptions()

    def list_frameworks(self) -> List[str]:
        """List all available framework names.
        
        Returns:
            List of framework names
        """
        return self._list_frameworks()
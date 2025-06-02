"""
Factory functions for Enterprise AI LLM providers.

This module provides factory functions for creating LLM provider instances
with appropriate configurations and enhanced execution control.
"""

from typing import Any, Dict, Optional, Set, Callable

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import ExecutionMode

logger = get_logger("llm.factory")


def create_provider(
    provider_name: str, 
    model_name: str,
    # Enhanced execution parameters
    execution_mode: ExecutionMode = ExecutionMode.AUTO,
    approval_callback: Optional[Callable] = None,
    verbose: bool = False,
    max_tool_iterations: int = 5,
    tool_execution_timeout: float = 30.0,
    allowed_tools: Optional[Set[str]] = None,
    forbidden_tools: Optional[Set[str]] = None,
    hybrid_danger_threshold: int = 2,
    **kwargs: Any
) -> LLMProvider:
    """
    Create an LLM provider instance with enhanced execution control.

    Args:
        provider_name: Name of the provider ("ollama", "openai", etc.)
        model_name: Name of the model to use
        execution_mode: How tools should be executed
        approval_callback: Function for human approval of tool calls
        verbose: Whether to enable verbose logging
        max_tool_iterations: Maximum tool execution rounds
        tool_execution_timeout: Timeout for individual tool execution
        allowed_tools: Set of allowed tool names
        forbidden_tools: Set of forbidden tool names  
        hybrid_danger_threshold: Danger level threshold for hybrid mode
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not supported
        ImportError: If provider dependencies are not available
    """
    provider_lower = provider_name.lower()
    
    # Prepare enhanced execution parameters
    execution_params = {
        "execution_mode": execution_mode,
        "approval_callback": approval_callback,
        "verbose": verbose,
        "max_tool_iterations": max_tool_iterations,
        "tool_execution_timeout": tool_execution_timeout,
        "allowed_tools": allowed_tools,
        "forbidden_tools": forbidden_tools,
        "hybrid_danger_threshold": hybrid_danger_threshold,
    }
    
    if provider_lower == "ollama":
        from enterprise_ai.llm.ollama import OllamaProvider
        return OllamaProvider(
            model_name=model_name, 
            **execution_params,
            **kwargs
        )
    elif provider_lower == "openai":
        from enterprise_ai.llm.openai import OpenAIProvider
        return OpenAIProvider(
            model_name=model_name,
            **execution_params,
            **kwargs
        )
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


def create_provider_with_simple_approval(
    provider_name: str,
    model_name: str,
    **kwargs: Any
) -> LLMProvider:
    """
    Create a provider with a simple console-based approval system.
    
    This is a convenience function for quick setup with human approval.
    """
    def simple_approval_callback(tool_call, approval_message: str) -> bool:
        """Simple console-based approval."""
        print("\n" + "="*60)
        print("TOOL EXECUTION APPROVAL REQUEST")
        print("="*60)
        print(approval_message)
        print("="*60)
        
        while True:
            choice = input("Approve execution? (y/n/d for details): ").lower().strip()
            if choice in ('y', 'yes'):
                return True
            elif choice in ('n', 'no'):
                return False
            elif choice in ('d', 'details'):
                print(f"\nTool Call Details:")
                print(f"Function: {tool_call.function.name}")
                print(f"Arguments: {tool_call.get_arguments()}")
                print(f"ID: {tool_call.id}")
                continue
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'd' for details")
    
    return create_provider(
        provider_name=provider_name,
        model_name=model_name,
        execution_mode=ExecutionMode.MANUAL,
        approval_callback=simple_approval_callback,
        verbose=True,
        **kwargs
    )


def create_provider_with_hybrid_mode(
    provider_name: str,
    model_name: str,
    danger_threshold: int = 2,
    **kwargs: Any
) -> LLMProvider:
    """
    Create a provider with hybrid execution mode.
    
    Safe tools execute automatically, dangerous tools require approval.
    """
    def hybrid_approval_callback(tool_call, approval_message: str) -> bool:
        """Approval callback for dangerous tools in hybrid mode."""
        print(f"\nDANGEROUS TOOL DETECTED: {tool_call.function.name}")
        print("-" * 50)
        print(approval_message)
        print("-" * 50)
        
        choice = input("This tool requires approval. Execute? (y/n): ").lower().strip()
        return choice in ('y', 'yes')
    
    return create_provider(
        provider_name=provider_name,
        model_name=model_name,
        execution_mode=ExecutionMode.HYBRID,
        approval_callback=hybrid_approval_callback,
        hybrid_danger_threshold=danger_threshold,
        verbose=True,
        **kwargs
    )


def list_available_providers() -> Dict[str, str]:
    """
    List available LLM providers.

    Returns:
        Dictionary mapping provider names to descriptions
    """
    return {
        "ollama": "Local Ollama inference server with enhanced execution control",
        "openai": "OpenAI GPT models with Azure/AWS support and execution control",
    }


def get_execution_mode_info() -> Dict[str, str]:
    """
    Get information about available execution modes.
    
    Returns:
        Dictionary describing each execution mode
    """
    return {
        "auto": "Tools execute immediately without human approval",
        "manual": "All tools require human approval before execution", 
        "hybrid": "Safe tools auto-execute, dangerous tools require approval",
        "disabled": "Tool calls are extracted but never executed"
    }
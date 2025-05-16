#!/usr/bin/env python
"""
Coroutine Handling Patch for Enterprise-AI

This script applies a patch to fix coroutine handling issues in the Enterprise-AI 
project, particularly related to the process_message methods and timeouts.
"""

import os
import re
import glob
import asyncio
from typing import List, Dict, Any, Optional, Union, cast, Tuple

def patch_llm_agent():
    """
    Patch the LLMAgent class to properly handle coroutines in process_message.
    """
    file_path = 'enterprise_ai/agent/core/base.py'
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define the pattern for the LLMAgent's process_message method
    process_message_pattern = r'async def process_message\(\s*self,\s*message:.+?return response\s*\n'
    
    # Check if we need to patch - look for async process_message
    if re.search(process_message_pattern, content, re.DOTALL):
        # We need to patch
        print(f"Patching {file_path} - Fixing process_message handling")
        
        # Replace async process_message with aprocess_message and add sync wrapper
        corrected_content = re.sub(
            process_message_pattern,
            'async def aprocess_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:\n    """Process a message asynchronously using the LLM and reasoning framework.\n\n    Args:\n        message: Input message or string\n        **kwargs: Additional parameters for processing\n\n    Returns:\n        Response message\n    """\n    # Convert string to message if needed\n    if isinstance(message, str):\n        input_message = Message.user_message(message)\n    else:\n        input_message = message\n    \n    # Initialize MCP if needed before processing\n    if hasattr(self, "_tools") and self._tools and hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:\n        await self.initialize_mcp()\n    \n    # Record message in conversation history\n    conversation_id = kwargs.get("conversation_id", "default")\n    self._conversation.add_message(input_message, conversation_id=conversation_id)\n    \n    # Get full conversation history\n    messages = self._conversation.get_messages(conversation_id=conversation_id)\n    \n    # Ensure timeout is set to minimum required timeout\n    if "timeout" not in kwargs and hasattr(self, "_llm_provider") and self._llm_provider:\n        # Default to 300 seconds or provider\'s timeout if it\'s higher\n        provider_timeout = getattr(self._llm_provider, "_timeout", 60.0)\n        kwargs["timeout"] = max(300.0, provider_timeout)\n    \n    # Process using execution manager\n    response = await self._execution.process_message(messages, **kwargs)\n    \n    # Record response in conversation history\n    self._conversation.add_message(response, conversation_id=conversation_id)\n    \n    return response\n\n    def process_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:\n        """Process a message synchronously by wrapping the async method.\n\n        Args:\n            message: Input message or string\n            **kwargs: Additional parameters for processing\n\n        Returns:\n            Response message\n        """\n        # Use the proper event loop handling to run the async method\n        try:\n            loop = asyncio.get_event_loop()\n            if loop.is_running():\n                # If we\'re already in an event loop, create a new task\n                # This avoids blocking, but the caller needs to await the result\n                logger.warning(f"Synchronous process_message called in running event loop - returning coroutine. "\n                               f"Use \'await agent.aprocess_message()\' instead.")\n                return self.aprocess_message(message, **kwargs)\n            else:\n                # If no event loop is running, run the coroutine to completion\n                return loop.run_until_complete(self.aprocess_message(message, **kwargs))\n        except RuntimeError:\n            # If there\'s no event loop, create one\n            logger.info("No event loop found, creating one for synchronous process_message")\n            loop = asyncio.new_event_loop()\n            asyncio.set_event_loop(loop)\n            try:\n                return loop.run_until_complete(self.aprocess_message(message, **kwargs))\n            finally:\n                loop.close()\n                asyncio.set_event_loop(None)',
            content, 
            flags=re.DOTALL
        )
        
        # Replace aprocess_conversation method similarly if needed
        
        with open(file_path, 'w') as f:
            f.write(corrected_content)
        
        print(f"Successfully patched {file_path}")
        return True
    else:
        print(f"No need to patch {file_path} - already fixed or not found")
        return False

def patch_factory():
    """
    Patch the factory module to properly handle LLM provider parameters.
    """
    file_path = 'enterprise_ai/agent/core/factory.py'
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find {file_path}")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if we need to add the extract_llm_provider_kwargs function
    if 'def extract_llm_provider_kwargs(' not in content:
        print(f"Patching {file_path} - Adding extract_llm_provider_kwargs function")
        
        # Define the pattern to match the create_agent function definition
        create_agent_pattern = r'def create_agent\(\s*'
        
        # Add the extract_llm_provider_kwargs function before create_agent
        function_def = '''def extract_llm_provider_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Extract LLM provider kwargs from the agent creation kwargs.
    
    Args:
        kwargs: Agent creation kwargs
        
    Returns:
        Dictionary of LLM provider kwargs
    """
    # Extract the llm_provider_kwargs if present
    llm_provider_kwargs = kwargs.pop("llm_provider_kwargs", {}).copy()
    
    # Also check for direct provider parameters in kwargs
    direct_provider_params = {}
    for key in list(kwargs.keys()):
        if key in ("model_name", "base_url", "temperature", "max_tokens", "top_p", "timeout"):
            direct_provider_params[key] = kwargs.pop(key)
    
    # Merge them, with llm_provider_kwargs taking precedence
    return {**direct_provider_params, **llm_provider_kwargs}


'''
        corrected_content = re.sub(create_agent_pattern, function_def + 'def create_agent(', content)
        
        # Update the LLM provider creation part
        llm_provider_pattern = r'# Get LLM provider\s+llm_provider = None\s+provider_name = llm_provider_name or merged_config.get\("llm_provider"\)\s+if provider_name:[^}]*from enterprise_ai.llm import get_default_provider\s+llm_provider = get_default_provider\(\)'
        
        llm_provider_replacement = """# Get LLM provider
        llm_provider = None
        provider_name = llm_provider_name or merged_config.get("llm_provider")
        
        # Extract provider parameters
        provider_kwargs = extract_llm_provider_kwargs(kwargs)
        
        # Create the provider
        if provider_name:
            from enterprise_ai.llm import create_provider
            llm_provider = create_provider(provider_name, **provider_kwargs)
            logger.info(f"Created LLM provider: {provider_name} with parameters: {provider_kwargs}")
        else:
            from enterprise_ai.llm import get_default_provider
            llm_provider = get_default_provider(**provider_kwargs)
            logger.info(f"Created default LLM provider with parameters: {provider_kwargs}")"""
        
        corrected_content = re.sub(llm_provider_pattern, llm_provider_replacement, corrected_content, flags=re.DOTALL)
        
        with open(file_path, 'w') as f:
            f.write(corrected_content)
        
        print(f"Successfully patched {file_path}")
        return True
    else:
        print(f"No need to patch {file_path} - already fixed")
        return False

def patch_example_scripts():
    """
    Ensure all example scripts properly await async calls.
    """
    examples_dir = 'examples/notebooks/agent'
    
    if not os.path.exists(examples_dir):
        print(f"Error: Could not find {examples_dir}")
        return False
    
    # Find all Python files in the examples directory
    python_files = glob.glob(os.path.join(examples_dir, "*.py"))
    
    for file_path in python_files:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check if there are any non-awaited coroutine calls
        non_awaited_pattern = r'([^a]wait\s+)?(\w+_agent)\.aprocess_message\('
        
        matches = re.findall(non_awaited_pattern, content)
        needs_fixing = False
        
        for match in matches:
            if not match[0]:  # No 'await' found
                needs_fixing = True
                break
        
        if needs_fixing:
            print(f"Patching {file_path} - Adding missing awaits")
            
            # Replace non-awaited calls with awaited ones
            corrected_content = re.sub(
                r'([^a]wait\s+)(\w+_agent)\.aprocess_message\(',
                r'await \2.aprocess_message(',
                content
            )
            
            with open(file_path, 'w') as f:
                f.write(corrected_content)
            
            print(f"Successfully patched {file_path}")
        else:
            print(f"No need to patch {file_path} - already correctly awaiting coroutines")
    
    return True

def apply_patches():
    """
    Apply all patches to fix coroutine handling in the codebase.
    """
    print("Applying patches to fix coroutine handling in Enterprise-AI...")
    
    success = True
    success = success and patch_llm_agent()
    success = success and patch_factory()
    success = success and patch_example_scripts()
    
    if success:
        print("\nAll patches applied successfully!")
        print("The patches fixed the following issues:")
        print("1. LLMAgent.process_message now properly handles coroutines")
        print("2. Factory module now correctly extracts and passes LLM provider parameters")
        print("3. Example scripts have been checked to ensure coroutines are properly awaited")
        print("\nRecommendations:")
        print("1. Consider adding proper type hints for coroutines (Awaitable, Coroutine)")
        print("2. Add linting rules to catch unawaited coroutines in future code")
        print("3. Consider making the API more consistent (either all sync or all async)")
        return 0
    else:
        print("\nSome patches could not be applied. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit(apply_patches())

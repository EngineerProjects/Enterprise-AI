"""
Software Engineering (SWE) reasoning framework for Enterprise AI agents.

This module implements the Software Engineering reasoning pattern, which
focuses on systematic software development approaches including planning,
implementation, testing, and debugging of code.
"""

import re
import json
import asyncio
from typing import Any, Dict, List, Optional, Set, Union, cast, Tuple
from datetime import datetime

from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.reasoning.base import ToolBasedReasoning
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts
from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
    validate_tool_parameters,
    get_tool_error_handling_prompt,
)
from enterprise_ai.mcp.utils import format_tool_descriptions

logger = get_logger("agent.reasoning.swe")


class SoftwareEngineeringReasoning(ToolBasedReasoning):
    """
    Software Engineering reasoning framework implementation.

    This framework guides agents through structured software development
    processes, including requirements analysis, design, implementation,
    testing, and debugging, with a focus on code quality and systematic
    problem solving.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the Software Engineering approach.

        This method implements a structured development process with
        methodical reasoning about software tasks and tool usage.

        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional parameters including LLM provider

        Returns:
            Response message
        """
        # Extract LLM provider and remove from kwargs to avoid serialization issues
        llm_provider = kwargs.pop("llm_provider", None)
        if not llm_provider:
            logger.error(f"No LLM provider available for agent {agent.id}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    "I'm unable to process your request due to a configuration issue."
                ),
            )

        # Get the last message
        if not messages:
            logger.error("No messages provided to SWE reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

        # Ensure the system prompt includes SWE instructions
        has_swe_prompt = False
        for idx, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                # Check if system prompt already has SWE instructions
                has_swe_prompt = self._has_swe_instructions(msg.content)

                if not has_swe_prompt:
                    # Replace with SWE prompt
                    tools_description = kwargs.get("tools_description", "")

                    if not tools_description and hasattr(agent, "_tool_manager"):
                        # Get tools description from agent's tool manager
                        tool_manager = getattr(agent, "_tool_manager")
                        if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                            tools_description = tool_manager.get_formatted_tool_descriptions(
                                include_capabilities=True,
                                include_examples=True
                            )

                    # Format SWE system prompt
                    swe_prompt = self.format_system_prompt(
                        agent, msg.content or "", tools_description=tools_description, **kwargs
                    )

                    # Update the system message
                    messages[idx] = cast(MessageProtocol, Message.system_message(swe_prompt))

                break

        # If no system message, add one with SWE instructions
        if not any(msg.role == "system" for msg in messages):
            tools_description = kwargs.get("tools_description", "")

            if not tools_description and hasattr(agent, "_tool_manager"):
                # Get tools description from agent's tool manager
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                    tools_description = tool_manager.get_formatted_tool_descriptions(
                        include_capabilities=True,
                        include_examples=True
                    )

            # Format SWE system prompt
            swe_prompt = self.format_system_prompt(
                agent, "", tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(swe_prompt)))

        # Process previous tool executions and update messages
        updated_messages = self._process_previous_tool_calls(agent, messages, **kwargs)

        # Generate response from LLM
        try:
            # Prepare tools for function calling if supported
            tools_schema = []
            function_calling = False
            
            if hasattr(llm_provider, "supports_feature"):
                function_calling = llm_provider.supports_feature("function_calling")
            
            if function_calling and hasattr(agent, "_tool_manager"):
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_tool_schemas"):
                    # Run in event loop to get tool schemas with focus on development tools
                    loop = self._get_event_loop()
                    tools_schema = loop.run_until_complete(
                        tool_manager.get_tool_schemas(
                            filter_by_capabilities=True
                        )
                    )
                    
                    # Log available development tools
                    dev_tools = [t for t in tools_schema if "code" in str(t).lower() or 
                                  "file" in str(t).lower() or "test" in str(t).lower()]
                    if dev_tools:
                        logger.debug(f"Development tools available: {len(dev_tools)}")

            # Prepare kwargs for LLM completion
            sanitized_kwargs = {k: v for k, v in kwargs.items() if not str(k) == "llm_provider"}
            if tools_schema:
                sanitized_kwargs["tools"] = tools_schema

            # Generate response
            response = llm_provider.complete(updated_messages, **sanitized_kwargs)
            
            # Post-process the response for better development workflows
            processed_response = self._post_process_swe_response(response)
            
            return cast(MessageProtocol, processed_response)
        except Exception as e:
            logger.error(f"Error in SWE reasoning for agent {agent.id}: {e}", exc_info=True)
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _has_swe_instructions(self, prompt: str) -> bool:
        """
        Check if a prompt contains Software Engineering instructions.

        Args:
            prompt: Prompt to check

        Returns:
            True if prompt contains SWE instructions, False otherwise
        """
        swe_indicators = [
            "software engineering",
            "code quality",
            "requirements analysis",
            "design patterns",
            "implementation",
            "testing",
            "debugging",
            "refactoring",
            "code review",
            "version control",
            "documentation",
        ]

        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in swe_indicators)

    def _process_previous_tool_calls(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> List[MessageProtocol]:
        """
        Process any tool calls in previous messages.
        
        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional parameters
            
        Returns:
            Updated list of messages
        """
        # Make a copy to avoid modifying the original
        updated_messages = list(messages)
        
        # Check for the last assistant message
        last_assistant_msg = None
        for msg in reversed(updated_messages):
            if msg.role == "assistant":
                last_assistant_msg = msg
                break

        # Process tool calls if the last assistant message has them
        if last_assistant_msg:
            tool_calls = parse_message_for_tool_calls(last_assistant_msg)

            if tool_calls:
                logger.info(f"Found {len(tool_calls)} tool calls in agent {agent.id} response")

                # Execute tools and add results to messages
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    params = tool_call.get("parameters", {})
                    tool_id = tool_call.get("id")

                    if not tool_name:
                        continue

                    try:
                        # Execute the tool with enhanced error handling for development tools
                        tool_result = self._execute_dev_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Format result as tool response with appropriate response format
                        tool_response = format_tool_response_message(
                            tool_name, tool_result, tool_id,
                            response_format=kwargs.get("tool_response_format", "json")
                        )
                        updated_messages.append(tool_response)

                        logger.info(f"Added tool result for {tool_name} to conversation")
                        
                        # For development tools, add additional guidance for code errors
                        if self._is_development_tool(tool_name) and tool_result.error:
                            error_guidance = self._generate_dev_error_guidance(
                                tool_name, params, tool_result
                            )
                            if error_guidance:
                                updated_messages.append(cast(
                                    MessageProtocol,
                                    Message.user_message(error_guidance)
                                ))
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                        # Add error response
                        error_result = ToolFailure(
                            error=f"Error executing tool: {str(e)}",
                            error_code="EXECUTION_ERROR",
                            metadata=ToolResultMetadata(tool_name=tool_name)
                        )
                        error_response = format_tool_response_message(
                            tool_name, error_result, tool_id
                        )
                        updated_messages.append(error_response)

        return updated_messages

    def _is_development_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is a development tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if the tool is a development tool
        """
        development_tools = [
            "execute_code", "python_execute", "execute_python", "run_code",
            "debug_code", "test_code", "create_file", "read_file", "write_file",
            "view_file", "create_test", "run_test", "generate_docs",
            "git_commit", "version_code", "code_review", "lint_code"
        ]
        
        return tool_name.lower() in [t.lower() for t in development_tools] or \
               any(keyword in tool_name.lower() for keyword in 
                   ["code", "file", "test", "debug", "git", "doc"])

    def _generate_dev_error_guidance(
        self, tool_name: str, params: Dict[str, Any], result: ToolResult
    ) -> Optional[str]:
        """
        Generate guidance for development tool errors.
        
        Args:
            tool_name: Name of the tool
            params: Parameters passed to the tool
            result: Error result from the tool
            
        Returns:
            Guidance message or None
        """
        if not result.error:
            return None
            
        error_msg = result.error
        
        # Syntax error guidance
        if "SyntaxError" in error_msg:
            line_match = re.search(r"line (\d+)", error_msg)
            line_num = line_match.group(1) if line_match else "unknown"
            return (f"There appears to be a syntax error in your code at line {line_num}. "
                   f"Please check for missing parentheses, colons, or other syntax issues. "
                   f"Fix the syntax error and try again.")
                   
        # Import error guidance
        elif "ImportError" or "ModuleNotFoundError" in error_msg:
            module_match = re.search(r"No module named '([^']+)'", error_msg)
            module = module_match.group(1) if module_match else "the requested module"
            return (f"The code is missing a required import for {module}. "
                   f"Please check that you're using standard library modules or "
                   f"provide an implementation for any custom modules.")
                   
        # Type error guidance
        elif "TypeError" in error_msg:
            return (f"There is a type error in your code: {error_msg}. "
                   f"Please check that you're using the correct data types and "
                   f"function signatures.")
                   
        # Name error guidance
        elif "NameError" in error_msg:
            var_match = re.search(r"name '([^']+)' is not defined", error_msg)
            var = var_match.group(1) if var_match else "a variable"
            return (f"The code references {var} which is not defined. "
                   f"Please make sure all variables are properly defined before use.")
                   
        # General code execution guidance
        elif "code execution" in error_msg.lower():
            return (f"The code execution failed. Please review the error message: {error_msg}. "
                   f"Try simplifying your code or breaking it into smaller parts to identify "
                   f"the issue.")
        
        # Default guidance for other errors        
        return (f"There was an error with the {tool_name} tool: {error_msg}. "
               f"Please review your code and fix any issues before trying again.")

    def _execute_dev_tool_with_handling(
        self, agent: AgentProtocol, tool_name: str, params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Execute a development tool with enhanced error handling.
        
        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            params: Parameters for tool execution
            **kwargs: Additional parameters
            
        Returns:
            Tool execution result
        """
        if not hasattr(agent, "_tool_manager"):
            return ToolFailure(
                error="Agent does not have a tool manager",
                error_code="NO_TOOL_MANAGER",
                metadata=ToolResultMetadata(tool_name=tool_name)
            )

        tool_manager = getattr(agent, "_tool_manager")
        
        # Validate parameters against tool schema if validation is enabled
        if hasattr(tool_manager, "get_tool") and kwargs.get("validate_params", True):
            tool = tool_manager.get_tool(tool_name)
            if tool and hasattr(tool, "parameters"):
                valid_params, error_msg = validate_tool_parameters(tool_name, params, tool.parameters)
                if not valid_params:
                    return ToolFailure(
                        error=f"Invalid parameters: {error_msg}",
                        error_code="INVALID_PARAMETERS",
                        retryable=True,
                        metadata=ToolResultMetadata(tool_name=tool_name)
                    )

        # Development-specific parameter handling
        if tool_name.lower() in ["execute_code", "python_execute", "execute_python", "run_code"]:
            # Special handling for code execution
            if "code" in params and params["code"]:
                # Prepend safety imports for code execution if appropriate
                code = params["code"]
                if code.strip().startswith("import") or code.strip().startswith("from"):
                    # The code already has imports, don't modify
                    pass
                elif "python" in tool_name.lower() and not code.strip().startswith("import sys"):
                    # Add safety imports for Python if appropriate and not already present
                    if "import sys" not in code and "import os" not in code:
                        params["code"] = "import sys\nimport os\n\n" + code
        
        # Add version tracking for file operations
        if tool_name.lower() in ["write_file", "create_file"] and "content" in params:
            # Add timestamp comment for versioning if appropriate
            content = params["content"]
            file_path = params.get("file_path", params.get("path", "unknown"))
            
            # Only add versioning comments to appropriate file types
            if any(file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".java", ".c", ".cpp", ".h"]):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Different comment styles for different languages
                if file_path.endswith((".py")):
                    header = f"# Version: Generated on {timestamp}\n# Auto-generated by SWE agent\n\n"
                elif file_path.endswith((".js", ".ts", ".java", ".c", ".cpp", ".h")):
                    header = f"// Version: Generated on {timestamp}\n// Auto-generated by SWE agent\n\n"
                
                # Add the versioning header if not already present
                if not content.startswith(("# Version", "// Version")):
                    params["content"] = header + content

        # Configure execution options
        timeout = kwargs.get("tool_timeout", 15.0)  # Default to shorter timeout for dev tools
        if tool_name.lower() in ["execute_code", "python_execute", "execute_python", "run_code"]:
            # Increase timeout for code execution
            timeout = kwargs.get("code_execution_timeout", 30.0)
            
        retry_count = kwargs.get("retry_count", 1)  # Default to fewer retries for dev tools
        retry_delay = kwargs.get("retry_delay", 1.0)

        try:
            # Execute tool with retry logic
            loop = self._get_event_loop()
            result = loop.run_until_complete(
                tool_manager.execute_tool(
                    tool_name=tool_name,
                    timeout=timeout,
                    retry_count=retry_count,
                    retry_delay=retry_delay,
                    **params
                )
            )
            
            logger.info(f"Executed tool {tool_name} for agent {agent.id}")
            
            # Process result for better development experience
            if isinstance(result, ToolResult):
                # Add documentation generation info if this was a file creation/modification
                if tool_name.lower() in ["write_file", "create_file"] and not result.error:
                    file_path = params.get("file_path", params.get("path", "unknown"))
                    if file_path.endswith(".py"):
                        result.system = (
                            f"File '{file_path}' created/updated successfully. "
                            f"Consider adding docstrings and type hints for better documentation."
                        )
                
                # Enhance code execution output for better readability
                if tool_name.lower() in ["execute_code", "python_execute", "execute_python", "run_code"]:
                    if result.output:
                        if isinstance(result.output, str) and len(result.output) > 1000:
                            # Truncate very long outputs for readability
                            trunc_output = result.output[:1000] + "... [truncated]"
                            return ToolResult(
                                output=trunc_output,
                                system=f"Output truncated. Original length: {len(result.output)} chars.",
                                metadata=result.metadata
                            )
            
            return cast(ToolResult, result)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return ToolFailure(
                error=f"Tool execution error: {str(e)}",
                error_code="EXECUTION_ERROR",
                metadata=ToolResultMetadata(tool_name=tool_name)
            )

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get or create an event loop.
        
        Returns:
            Event loop instance
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _post_process_swe_response(self, response: MessageProtocol) -> MessageProtocol:
        """
        Post-process an LLM response for better development workflows.
        
        Args:
            response: LLM response message
            
        Returns:
            Processed response message
        """
        if not response.content:
            return response
            
        content = response.content
        
        # Enhance code formatting for common languages
        for lang in ["python", "javascript", "typescript", "java", "cpp", "go"]:
            pattern = f"```{lang}(.*?)```"
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                # Check if the code already has proper spacing
                if not match.startswith("\n"):
                    # Add newline after opening code block
                    content = content.replace(f"```{lang}{match}```", f"```{lang}\n{match.lstrip()}```")
        
        # Add missing language annotations for unlabeled code blocks
        if "```\n" in content:
            # Add python as default language for unlabeled code blocks
            content = content.replace("```\n", "```python\n")
        
        # Check for documentation gaps in code
        if "```python" in content.lower():
            python_blocks = re.findall(r"```python\s+(.*?)\s+```", content, re.DOTALL)
            for block in python_blocks:
                if "def " in block and not re.search(r'""".*?"""', block, re.DOTALL) and not block.count('#'):
                    # Code has functions but no docstrings or comments
                    note = ("\n\nNote: Consider adding docstrings to functions for better documentation. "
                            "This helps with code maintainability.")
                    if note not in content:
                        content += note
                        break
        
        # Return the enhanced response
        return Message.assistant_message(content, metadata=response.metadata)

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """
        Process a task using Software Engineering reasoning.

        Args:
            agent: The agent using this reasoning framework
            task: Task to process
            **kwargs: Additional parameters

        Returns:
            Updated task status
        """
        # Extract LLM provider
        llm_provider = kwargs.get("llm_provider")
        if not llm_provider:
            logger.error(f"No LLM provider available for agent {agent.id}")
            task.status = TaskStatus.FAILED
            return task.status

        # Determine if this is a software development task
        is_dev_task = self._is_development_task(task.description)

        # Get tools description
        tools_description = kwargs.get("tools_description", "")

        if not tools_description and hasattr(agent, "_tool_manager"):
            # Get tools description from agent's tool manager
            tool_manager = getattr(agent, "_tool_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions(
                    include_capabilities=True,
                    include_examples=True
                )

        # Get SWE system prompt
        system_prompt = self.format_system_prompt(
            agent, "", tools_description=tools_description, **kwargs
        )

        # Create messages for the task
        messages: List[Message] = []
        messages.append(Message.system_message(system_prompt))

        # For development tasks, add structure to the task
        if is_dev_task:
            messages.append(
                Message.user_message(
                    f"Software Development Task: {task.description}\n\n"
                    f"Please follow a systematic software engineering approach:\n"
                    f"1. Analyze requirements and understand the task\n"
                    f"2. Design a solution with appropriate architecture\n"
                    f"3. Implement the code with good practices\n"
                    f"4. Test your implementation thoroughly\n"
                    f"5. Refactor and optimize as needed\n"
                    f"6. Document your code and solution"
                )
            )
        else:
            messages.append(Message.user_message(f"Task: {task.description}"))

        # Initialize task status and metadata
        task.status = TaskStatus.IN_PROGRESS
        if not task.metadata:
            task.metadata = {}
        
        task.metadata["start_time"] = datetime.now().isoformat()
        task.metadata["is_development_task"] = is_dev_task
        
        # Track development stages for software tasks
        dev_stages = ["requirements", "design", "implementation", "testing", "refactoring", "documentation"]
        current_stage_idx = 0
        if is_dev_task:
            task.metadata["development_stages"] = {
                stage: {"completed": False, "artifacts": []} for stage in dev_stages
            }
            task.metadata["current_stage"] = dev_stages[current_stage_idx]

        # Process with LLM in a loop until task is completed or max iterations reached
        max_iterations = kwargs.get("max_iterations", 15)  # Increase default iterations for dev tasks
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1
            task.metadata["current_iteration"] = current_iteration

            try:
                # Get available tools for function calling
                tools_schema = []
                if hasattr(agent, "_tool_manager"):
                    tool_manager = getattr(agent, "_tool_manager")
                    if hasattr(tool_manager, "get_tool_schemas"):
                        # Run in event loop to get tool schemas
                        loop = self._get_event_loop()
                        tools_schema = loop.run_until_complete(
                            tool_manager.get_tool_schemas(filter_by_capabilities=True)
                        )
                
                # Prepare completion parameters
                completion_kwargs = {}
                if tools_schema:
                    completion_kwargs["tools"] = tools_schema
                
                # Add any additional parameters from kwargs
                for key, value in kwargs.items():
                    if key != "llm_provider" and key != "tools_description":
                        completion_kwargs[key] = value

                # Get response from LLM
                response = llm_provider.complete(
                    [cast(MessageProtocol, msg) for msg in messages],
                    **completion_kwargs
                )
                messages.append(cast(Message, response))

                # Update development stage tracking for dev tasks
                if is_dev_task and response.content:
                    updated_stage_idx = self._detect_dev_stage(response.content, current_stage_idx)
                    if updated_stage_idx > current_stage_idx:
                        # Update task metadata with stage progression
                        current_stage_idx = updated_stage_idx
                        if current_stage_idx < len(dev_stages):
                            current_stage = dev_stages[current_stage_idx]
                            prev_stage = dev_stages[current_stage_idx - 1]
                            
                            # Mark previous stage as completed
                            task.metadata["development_stages"][prev_stage]["completed"] = True
                            task.metadata["current_stage"] = current_stage
                            
                            # Log stage transition
                            logger.info(f"Development task progressed from {prev_stage} to {current_stage}")

                # Check if task appears to be complete
                if self._is_task_completed(response.content or "", is_dev_task):
                    # Mark all remaining stages as completed for dev tasks
                    if is_dev_task:
                        for stage in dev_stages:
                            task.metadata["development_stages"][stage]["completed"] = True
                    break

                # Check for tool calls
                tool_calls = parse_message_for_tool_calls(response)

                if not tool_calls:
                    # No tool calls, add appropriate guidance based on task type
                    if is_dev_task:
                        if current_iteration == 1:
                            # Encourage tool use for first iteration of dev tasks
                            messages.append(
                                Message.user_message(
                                    "Consider using appropriate development tools to help with this task. "
                                    "For example, you might need to write, run, or debug code."
                                )
                            )
                        else:
                            # Guide based on current stage
                            current_stage = dev_stages[current_stage_idx]
                            stage_guidance = self._get_stage_guidance(current_stage)
                            messages.append(Message.user_message(stage_guidance))
                    else:
                        # General follow-up for non-dev tasks
                        messages.append(
                            Message.user_message(
                                "Continue working on this task. Let me know if you need any clarification."
                            )
                        )
                else:
                    # Process each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name", "")
                        params = tool_call.get("parameters", {})
                        tool_id = tool_call.get("id")

                        if not tool_name:
                            continue

                        # Execute tool with enhanced development handling
                        tool_result = self._execute_dev_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Format result as tool response with appropriate format
                        tool_response = format_tool_response_message(
                            tool_name, tool_result, tool_id,
                            response_format=kwargs.get("tool_response_format", "json")
                        )
                        tool_response_message = cast(Message, tool_response)
                        messages.append(tool_response_message)
                        
                        # Track artifacts for dev tasks
                        if is_dev_task:
                            current_stage = dev_stages[current_stage_idx]
                            self._track_dev_artifact(
                                task, tool_name, params, tool_result, current_stage
                            )
                        
                        # Add error guidance for development tools
                        if self._is_development_tool(tool_name) and tool_result.error:
                            error_guidance = self._generate_dev_error_guidance(
                                tool_name, params, tool_result
                            )
                            if error_guidance:
                                messages.append(Message.user_message(error_guidance))

            except Exception as e:
                logger.error(f"Error processing task for agent {agent.id}: {e}", exc_info=True)
                task.status = TaskStatus.FAILED
                task.metadata["error"] = str(e)
                return task.status

        # Store the final response in task metadata
        if not task.metadata:
            task.metadata = {}

        # Extract the final result from messages
        final_response = ""
        for msg in reversed(messages):
            if msg.role == "assistant":
                final_response = msg.content or ""
                break

        task.metadata["response"] = final_response
        task.metadata["iterations"] = current_iteration
        task.metadata["end_time"] = datetime.now().isoformat()
        
        # Generate documentation summary for dev tasks
        if is_dev_task and all(task.metadata["development_stages"][stage]["completed"] 
                              for stage in dev_stages[:4]):  # First 4 stages must be completed
            self._generate_documentation_summary(task)
            
        task.status = TaskStatus.COMPLETED

        return task.status

    def _detect_dev_stage(self, content: str, current_stage_idx: int) -> int:
        """
        Detect the current development stage from content.
        
        Args:
            content: Message content to analyze
            current_stage_idx: Current stage index
            
        Returns:
            Updated stage index
        """
        # Stage transition indicators
        stage_indicators = {
            "requirements": ["requirements gathering", "requirements analysis", "understanding the task"],
            "design": ["design", "architecture", "solution approach", "high-level design"],
            "implementation": ["implementation", "coding", "let's implement", "here's the code", "```python"],
            "testing": ["testing", "test cases", "unit test", "let's test", "validating", "verifying"],
            "refactoring": ["refactoring", "optimization", "improving", "enhance", "clean up"],
            "documentation": ["documentation", "documenting", "adding comments", "docstring", "readme"]
        }
        
        # Convert stage indicators to a list matching the stage order
        stages = ["requirements", "design", "implementation", "testing", "refactoring", "documentation"]
        
        # Figure out the furthest stage mentioned in the content
        furthest_stage_idx = current_stage_idx
        content_lower = content.lower()
        
        for i, stage in enumerate(stages):
            # Only consider stages beyond our current position
            if i > current_stage_idx:
                indicators = stage_indicators[stage]
                if any(indicator in content_lower for indicator in indicators):
                    # Found evidence of this stage
                    furthest_stage_idx = i
        
        # Special case: if the content has code blocks, we're at least at implementation
        if "```" in content and furthest_stage_idx < 2:  # 2 is implementation
            furthest_stage_idx = 2
            
        # Special case: if there are test results, we're at least at testing
        if re.search(r"test.*?pass|fail|error|assert", content_lower) and furthest_stage_idx < 3:  # 3 is testing
            furthest_stage_idx = 3
            
        return furthest_stage_idx

    def _get_stage_guidance(self, stage: str) -> str:
        """
        Get guidance for the current development stage.
        
        Args:
            stage: Current development stage
            
        Returns:
            Guidance message
        """
        guidance = {
            "requirements": (
                "Continue refining your understanding of the requirements. "
                "Make sure you have a clear picture of what needs to be accomplished. "
                "Consider edge cases and constraints."
            ),
            "design": (
                "Continue designing your solution. "
                "Consider the architecture, data structures, and algorithms. "
                "Think about how the components will interact."
            ),
            "implementation": (
                "Continue implementing your solution. "
                "Remember to write clean, maintainable code. "
                "Consider using file operations to save your code and execute_code to test it."
            ),
            "testing": (
                "Continue testing your implementation. "
                "Consider different test cases including edge cases. "
                "Make sure your code handles errors gracefully."
            ),
            "refactoring": (
                "Continue refactoring your code. "
                "Look for opportunities to improve efficiency and readability. "
                "Consider removing redundancy and simplifying complex sections."
            ),
            "documentation": (
                "Continue documenting your solution. "
                "Add clear comments and docstrings to your code. "
                "Summarize your approach and any important details."
            )
        }
        
        return guidance.get(stage, "Continue working on this task. Let me know if you need any clarification.")

    def _track_dev_artifact(
        self, 
        task: Task, 
        tool_name: str, 
        params: Dict[str, Any], 
        result: ToolResult, 
        stage: str
    ) -> None:
        """
        Track development artifacts in task metadata.
        
        Args:
            task: Task to update
            tool_name: Name of the tool
            params: Tool parameters
            result: Tool result
            stage: Current development stage
        """
        # Track artifacts based on tool type
        artifact = None
        
        if tool_name.lower() in ["write_file", "create_file"]:
            # Track file artifacts
            file_path = params.get("file_path", params.get("path", "unknown"))
            artifact = {
                "type": "file",
                "path": file_path,
                "time": datetime.now().isoformat(),
                "success": result.error is None
            }
        elif tool_name.lower() in ["execute_code", "python_execute", "execute_python", "run_code"]:
            # Track code execution artifacts
            code_snippet = params.get("code", "")
            if len(code_snippet) > 100:
                code_snippet = code_snippet[:100] + "..."
                
            artifact = {
                "type": "code_execution",
                "snippet": code_snippet,
                "time": datetime.now().isoformat(),
                "success": result.error is None
            }
        elif "test" in tool_name.lower():
            # Track testing artifacts
            artifact = {
                "type": "test",
                "details": str(params),
                "time": datetime.now().isoformat(),
                "success": result.error is None
            }
        
        # Add artifact to task metadata if we created one
        if artifact and task.metadata and "development_stages" in task.metadata:
            if stage in task.metadata["development_stages"]:
                task.metadata["development_stages"][stage]["artifacts"].append(artifact)

    def _generate_documentation_summary(self, task: Task) -> None:
        """
        Generate a documentation summary for a development task.
        
        Args:
            task: Task to document
        """
        if not task.metadata or "development_stages" not in task.metadata:
            return
            
        # Collect artifacts from all stages
        all_artifacts = []
        dev_stages = task.metadata["development_stages"]
        
        for stage, info in dev_stages.items():
            if info["completed"] and "artifacts" in info:
                for artifact in info["artifacts"]:
                    artifact["stage"] = stage
                    all_artifacts.append(artifact)
        
        # Generate summary if we have artifacts
        if all_artifacts:
            # Get file artifacts
            file_artifacts = [a for a in all_artifacts if a["type"] == "file"]
            file_paths = list(set(a["path"] for a in file_artifacts))
            
            # Get test artifacts
            test_artifacts = [a for a in all_artifacts if a["type"] == "test"]
            test_count = len(test_artifacts)
            test_success = sum(1 for a in test_artifacts if a["success"])
            
            # Create documentation summary
            summary = {
                "files_created": file_paths,
                "file_count": len(file_paths),
                "tests_run": test_count,
                "tests_passed": test_success,
                "development_completed": True,
                "timestamp": datetime.now().isoformat()
            }
            
            task.metadata["documentation_summary"] = summary

    def _is_development_task(self, description: str) -> bool:
        """
        Determine if a task is related to software development.

        Args:
            description: Task description

        Returns:
            True if it's a development task, False otherwise
        """
        dev_keywords = [
            "code",
            "program",
            "develop",
            "implement",
            "function",
            "class",
            "method",
            "script",
            "algorithm",
            "debug",
            "fix",
            "refactor",
            "optimiz",
            "test",
            "software",
            "app",
            "application",
            "website",
            "API",
            "module",
            "programming",
            "developer",
            "library",
            "framework",
        ]

        description_lower = description.lower()
        return any(keyword in description_lower for keyword in dev_keywords)

    def _is_task_completed(self, content: str, is_dev_task: bool) -> bool:
        """
        Check if task completion is indicated in the content.

        Args:
            content: Message content to check
            is_dev_task: Whether this is a development task

        Returns:
            True if task completion is indicated, False otherwise
        """
        # For dev tasks, look for code and completion statements
        if is_dev_task:
            has_code = bool(re.search(r"```\w*\n[\s\S]+?\n```", content))
            completion_patterns = [
                r"finished implementing",
                r"code is complete",
                r"implementation is complete",
                r"the solution is",
                r"final implementation",
                r"complete implementation",
                r"task completed",
                r"completed the task",
                r"the code has been",
                r"solution has been implemented",
                r"all requirements have been met"
            ]
            return has_code and any(
                re.search(pattern, content, re.IGNORECASE) for pattern in completion_patterns
            )
        else:
            # For non-dev tasks, look for general completion indicators
            completion_patterns = [
                r"task completed",
                r"finished the task",
                r"solution is ready",
                r"the answer is",
                r"in conclusion",
                r"task has been completed",
                r"to summarize",
            ]
            return any(
                re.search(pattern, content, re.IGNORECASE) for pattern in completion_patterns
            )

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """
        Format the system prompt for Software Engineering reasoning.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Get tools description
        tools_description = kwargs.get("tools_description", "")
        additional_instructions = kwargs.get("additional_swe_instructions", "")

        # Try to use the SWE prompt template
        swe_prompt = format_prompt(
            "system.swe",
            tools_description=tools_description,
            additional_swe_instructions=additional_instructions,
        )

        if not swe_prompt:
            # Fallback to get_tool_prompt_for_reasoning
            swe_prompt = get_tool_prompt_for_reasoning("swe", tools_description)

        # Add documentation and versioning guidance
        doc_guidance = (
            "\n\nWhen writing code, follow these additional best practices:\n"
            "- Add clear docstrings to functions and classes\n"
            "- Use descriptive variable and function names\n"
            "- Include type hints where applicable\n"
            "- Add comments to explain complex logic\n"
            "- Write modular, testable code\n"
            "- Handle errors and edge cases gracefully\n"
        )
        
        swe_prompt += doc_guidance

        # Combine with base prompt if provided
        if base_prompt:
            base_formatted = format_prompt("system.base", additional_instructions=base_prompt)
            if base_formatted:
                return f"{base_formatted}\n\n{swe_prompt}"

        return swe_prompt

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """
        Format instructions for tool usage with SWE.

        Args:
            agent: The agent using this reasoning framework
            tools: List of available tools
            **kwargs: Additional parameters

        Returns:
            Formatted tool instructions
        """
        # Format tools description
        tools_description = format_tool_descriptions(tools)

        # Use existing prompt template
        additional_instructions = kwargs.get("additional_swe_instructions", "")

        instructions = format_prompt(
            "system.swe",
            tools_description=tools_description,
            additional_swe_instructions=additional_instructions,
        )

        # Fallback to a simple format if the template is not available
        if not instructions:
            logger.warning("SWE prompt template not found, using fallback")
            return get_tool_prompt_for_reasoning("swe", tools_description)

        return instructions

    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Handle the execution of a tool.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            tool_params: Parameters for tool execution
            **kwargs: Additional parameters

        Returns:
            Tool execution result
        """
        return self._execute_dev_tool_with_handling(agent, tool_name, tool_params, **kwargs)

    def parse_tool_calls(self, message: MessageProtocol, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Parse tool calls from a message.

        Args:
            message: Message to parse for tool calls
            **kwargs: Additional parameters

        Returns:
            List of tool calls with name and parameters
        """
        return parse_message_for_tool_calls(message)

    def format_tool_response(self, tool_name: str, tool_result: ToolResult, **kwargs: Any) -> str:
        """
        Format a tool execution result for inclusion in a message.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            **kwargs: Additional parameters

        Returns:
            Formatted tool response
        """
        format_type = kwargs.get("response_format", "default")
        
        if format_type == "react":
            # ReAct format
            if tool_result.error:
                return f"Observation: Error using {tool_name}: {tool_result.error}"
            else:
                # Format based on tool type
                if tool_name in ["execute_code", "run_code", "execute_python"]:
                    return f"Execution result:\n```\n{tool_result.output or 'No output'}\n```"
                elif tool_name in ["read_file", "write_file", "list_files"]:
                    return f"File operation result: {tool_result.output}"
                else:
                    return f"Observation: {tool_result.output}"
        else:
            # Default formatting
            if tool_result.error:
                return f"Error using {tool_name}: {tool_result.error}"
            else:
                # For code execution results, format nicely
                if tool_name in ["execute_code", "run_code", "execute_python"]:
                    return f"Execution result:\n```\n{tool_result.output or 'No output'}\n```"
                # For file operations, be concise
                elif tool_name in ["read_file", "write_file", "list_files"]:
                    return f"File operation result: {tool_result.output}"
                # Default formatting
                else:
                    return f"Tool {tool_name} result: {tool_result.output or 'Success'}"

    def supports_function_calling(self) -> bool:
        """
        Check if this framework supports function calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        return True

    @property
    def name(self) -> str:
        """
        Get the name of this reasoning framework.

        Returns:
            Framework name
        """
        return "swe"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "Software Engineering reasoning framework for systematic development tasks."

    @property
    def requires_tools(self) -> bool:
        """
        Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        return True
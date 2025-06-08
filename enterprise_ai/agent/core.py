"""
Core agent implementation with embedded MCP server - COMPLETE FIX FOR TOOL CALLING.
"""

import asyncio
from typing import Any, Dict, List, Optional, Type, Union

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp import EnterpriseMCPServer, MCPConfig

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.config import AgentConfig

logger = get_optimized_logger("agent.core")


def create_dynamic_agent_class(
    base_llm_class: Type[LLMProvider],
    agent_config: AgentConfig
) -> Type[BaseAgent]:
    """
    Create a dynamic agent class with embedded MCP server.
    
    Args:
        base_llm_class: The LLM provider class to inherit from
        agent_config: Agent configuration
        
    Returns:
        Dynamic agent class: Agent = LLM Provider + MCP Server
    """
    
    class DynamicEnterpriseAgent(base_llm_class, BaseAgent):
        """
        Dynamic agent with embedded MCP server.
        
        This class inherits ALL methods from:
        - LLM Provider: complete(), acomplete(), streaming, etc.
        - Has embedded MCP Server: get_server_info(), tool management, etc.
        """
        
        def __init__(self, **kwargs):
            """Initialize the dynamic agent with embedded MCP server."""
            # Prepare LLM configuration
            llm_config = agent_config.get_llm_config()
            llm_config.update(kwargs)
            
            # Initialize LLM provider
            base_llm_class.__init__(self, **llm_config)
            BaseAgent.__init__(
                self,
                agent_id=agent_config.agent_id,
                name=agent_config.name,
                description=agent_config.description,
                **llm_config
            )
            
            # Initialize embedded MCP server
            mcp_config = MCPConfig.from_dict(agent_config.get_mcp_config())
            self.mcp_server = EnterpriseMCPServer(mcp_config)
            
            # Set approval callback directly on the tool executor
            if agent_config.tool_approval_callback:
                self.mcp_server.tool_executor.set_approval_callback(agent_config.tool_approval_callback)
                if agent_config.verbose:
                    logger.info("Approval callback set for tool execution")
            
            # Agent-specific state
            self.agent_config = agent_config
            self._current_session: Optional[str] = None
            
            logger.info(
                f"Created agent with {base_llm_class.__name__} + MCP Server: {self.agent_name}"
            )
        
        async def _get_or_create_session(self) -> str:
            """Get current session or create via MCP server."""
            if not self._current_session:
                self._current_session = self.mcp_server.session_manager.create_session(self.agent_id)
            return self._current_session
        
        async def _discover_tools(self, tools: Union[str, List[str], List[Dict[str, Any]], None]) -> List[Dict[str, Any]]:
            """
            Discover tools using MCP server capabilities - FIXED FOR OLLAMA.
            """
            if tools is None:
                return []
            
            if isinstance(tools, str):
                if tools.lower() == "all":
                    # Get tools from MCP but convert to proper Ollama format
                    mcp_tools = await self.mcp_server.tool_handler.handle_tool_list_request()
                    ollama_tools = self._convert_mcp_tools_to_ollama_format(mcp_tools)
                    if self.agent_config.verbose:
                        logger.info("Converted %d MCP tools to Ollama format", len(ollama_tools))
                        # Debug: Log first tool structure
                        if ollama_tools:
                            logger.debug(f"First tool structure: {ollama_tools[0]}")
                    return ollama_tools
                else:
                    # Single category
                    category_tools = self.mcp_server.tool_registry.get_tools_by_category(tools)
                    return await self._convert_tool_classes_to_ollama_format(category_tools)
            
            elif isinstance(tools, list):
                if not tools:
                    return []
                
                if isinstance(tools[0], dict):
                    # Already in format - but ensure Ollama compatibility
                    return self._ensure_ollama_tool_format(tools)
                
                # Multiple categories
                all_category_tools = {}
                for category in tools:
                    category_tools = self.mcp_server.tool_registry.get_tools_by_category(category)
                    for tool_cls in category_tools:
                        all_category_tools[tool_cls.__name__] = tool_cls
                
                return await self._convert_tool_classes_to_ollama_format(list(all_category_tools.values()))
            
            return []
        
        def _convert_mcp_tools_to_ollama_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """
            Convert MCP tools to Ollama-specific format.
            """
            ollama_tools = []
            
            for mcp_tool in mcp_tools:
                try:
                    if "function" in mcp_tool:
                        function_data = mcp_tool["function"]
                        
                        # Ensure proper Ollama tool format
                        ollama_tool = {
                            "type": "function",
                            "function": {
                                "name": function_data["name"],
                                "description": function_data.get("description", ""),
                                "parameters": function_data.get("parameters", {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        }
                        
                        # Ensure parameters has proper schema structure
                        if "parameters" in function_data:
                            params = function_data["parameters"]
                            if not isinstance(params, dict):
                                params = {}
                            
                            # Ensure minimum required schema structure
                            if "type" not in params:
                                params["type"] = "object"
                            if "properties" not in params:
                                params["properties"] = {}
                            if "required" not in params:
                                params["required"] = []
                            
                            ollama_tool["function"]["parameters"] = params
                        
                        ollama_tools.append(ollama_tool)
                    else:
                        # Handle case where tool is not in expected format
                        if self.agent_config.verbose:
                            logger.warning(f"MCP tool missing 'function' key: {mcp_tool}")
                        
                except Exception as e:
                    logger.warning(f"Failed to convert MCP tool to Ollama format: {e}")
            
            return ollama_tools
        
        def _ensure_ollama_tool_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """
            Ensure tools are in proper Ollama format.
            """
            return self._convert_mcp_tools_to_ollama_format(tools)
        
        async def _convert_tool_classes_to_ollama_format(self, tool_classes: List[Type]) -> List[Dict[str, Any]]:
            """
            Convert tool classes to Ollama-compatible format.
            """
            definitions = []
            
            for tool_cls in tool_classes:
                try:
                    # Use MCP tool bridge for conversion
                    mcp_def = self.mcp_server.tool_bridge.tool_to_mcp_definition(tool_cls, tool_cls.__name__)
                    if mcp_def:
                        # Convert to proper Ollama format
                        ollama_def = {
                            "type": "function",
                            "function": {
                                "name": mcp_def["name"],
                                "description": mcp_def["description"],
                                "parameters": mcp_def.get("inputSchema", {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        }
                        definitions.append(ollama_def)
                        
                except Exception as e:
                    logger.warning(f"Failed to convert tool {tool_cls.__name__}: {e}")
            
            return definitions
        
        async def execute_tools(
            self,
            tool_calls: List[ToolCall],
            session_id: Optional[str] = None,
            **kwargs: Any
        ) -> List[ToolResult]:
            """Execute tools via MCP server."""
            try:
                if not session_id:
                    session_id = await self._get_or_create_session()
                
                # Use MCP server's tool executor directly
                results = await self.mcp_server.tool_executor.execute_tool_calls(
                    tool_calls=tool_calls,
                    session_id=session_id,
                    context=kwargs
                )
                
                self._track_agent_tool_execution(len(tool_calls))
                return results
                
            except Exception as e:
                self._track_agent_error()
                logger.error(f"Tool execution failed for agent {self.agent_name}: {e}")
                raise
        
        async def chat(
            self,
            messages: List[MessageProtocol],
            tools: Union[str, List[str], List[Dict[str, Any]], None] = "all",
            max_iterations: int = None,
            **kwargs: Any
        ) -> List[MessageProtocol]:
            """
            Chat with tool execution via MCP server - COMPLETE FIX FOR TOOL CALLING.
            """
            if max_iterations is None:
                max_iterations = self.agent_config.max_iterations
            
            try:
                conversation = messages.copy()
                session_id = await self._get_or_create_session()
                
                # Discover and format tools properly for Ollama
                tool_definitions = []
                if self.agent_config.enable_tools and tools is not None:
                    tool_definitions = await self._discover_tools(tools)
                    if self.agent_config.verbose and tool_definitions:
                        tool_names = [t["function"]["name"] for t in tool_definitions]
                        logger.info(f"Discovered {len(tool_definitions)} tools: {tool_names}")
                
                # Tool execution loop
                for iteration in range(max_iterations):
                    if self.agent_config.verbose:
                        logger.info(f"Chat iteration {iteration + 1}/{max_iterations}")
                    
                    # Prepare completion with tools
                    completion_kwargs = kwargs.copy()
                    if tool_definitions:
                        completion_kwargs["tools"] = tool_definitions
                        
                        if self.agent_config.verbose:
                            logger.info(f"Sending {len(tool_definitions)} tools to LLM")
                            logger.debug(f"Tool names: {[t['function']['name'] for t in tool_definitions]}")
                    
                    # Get response with tool calls
                    response, tool_calls = await self.acomplete_with_tool_calls(
                        conversation, **completion_kwargs
                    )
                    
                    conversation.append(response)
                    
                    # Check for tool calls and execute them
                    if not tool_calls:
                        if self.agent_config.verbose:
                            logger.info("No tool calls found, ending iteration loop")
                        break
                    
                    if self.agent_config.verbose:
                        logger.info(f"Executing {len(tool_calls)} tool calls: {[tc.function.name for tc in tool_calls]}")
                    
                    # Execute tools via MCP server
                    tool_results = await self.execute_tools(tool_calls, session_id)
                    
                    # Convert results to messages and add to conversation
                    tool_messages = self.mcp_server.tool_executor.create_tool_messages(tool_results)
                    conversation.extend(tool_messages)
                    
                    if self.agent_config.verbose:
                        logger.info(f"Added {len(tool_messages)} tool result messages to conversation")
                
                self._track_agent_conversation()
                return conversation
                
            except Exception as e:
                self._track_agent_error()
                logger.error(f"Chat failed for agent {self.agent_name}: {e}")
                raise
        
        # 🎯 MCP Server Methods (delegated) - FIXED ASYNC
        
        async def get_available_tools(self) -> List[Dict[str, Any]]:
            """Get available tools via MCP server."""
            return await self.mcp_server.tool_handler.handle_tool_list_request()
        
        async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
            """Get specific tool info via MCP server."""
            return await self.mcp_server.tool_handler.handle_tool_info_request(tool_name)
        
        def get_tool_categories(self) -> Dict[str, List[str]]:
            """Get tools organized by category via MCP server."""
            all_categories = self.mcp_server.tool_registry.get_all_category_names()
            categorized_tools = {}
            
            for category in all_categories:
                tools = self.mcp_server.tool_registry.get_tools_by_category(category)
                categorized_tools[category] = [t.__name__ for t in tools]
            
            return categorized_tools
        
        def get_mcp_server_info(self) -> Dict[str, Any]:
            """Get MCP server information."""
            return self.mcp_server.get_server_info()
        
        async def execute_tool_directly(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a tool directly via MCP server."""
            return await self.mcp_server.execute_tool_directly(
                tool_name=tool_name,
                arguments=arguments,
                session_id=self._current_session,
                agent_id=self.agent_id
            )
        
        def get_agent_info(self) -> Dict[str, Any]:
            """Get comprehensive agent information."""
            base_info = super().get_agent_info()
            
            # Add MCP server info
            mcp_info = self.mcp_server.get_server_info()
            
            base_info.update({
                "llm_provider": agent_config.llm_provider.value,
                "tools_enabled": agent_config.enable_tools,
                "auto_execute_tools": agent_config.auto_execute_tools,
                "tool_approval_required": agent_config.require_tool_approval,
                "current_session": self._current_session,
                "mcp_server_info": mcp_info,
                "tool_categories": list(self.get_tool_categories().keys()),
            })
            return base_info
    
    return DynamicEnterpriseAgent


# Rest remains the same...
class EnterpriseAgent:
    """Main Enterprise AI Agent factory with embedded MCP server."""
    
    def __new__(
        cls,
        config: Optional[AgentConfig] = None,
        **kwargs: Any
    ) -> BaseAgent:
        """Create agent with embedded MCP server."""
        if config is None:
            config = AgentConfig.from_config(**kwargs)
        
        from enterprise_ai.llm.openai import OpenAIProvider
        from enterprise_ai.llm.ollama import OllamaProvider
        
        if config.llm_provider == config.llm_provider.OPENAI:
            base_class = OpenAIProvider
        elif config.llm_provider == config.llm_provider.OLLAMA:
            base_class = OllamaProvider
        else:
            raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")
        
        agent_class = create_dynamic_agent_class(base_class, config)
        return agent_class(**kwargs)
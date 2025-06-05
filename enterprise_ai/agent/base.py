"""
Base Agent implementation for Enterprise AI.

This provides the foundation for all agents in the system.
"""

import uuid
import asyncio
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod

from enterprise_ai.mcp.protocols.mcp_protocol import MCPMessage, MCPMessageType
from enterprise_ai.schema import ToolCall
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.base")


class BaseAgent(ABC):
    """
    Base class for all Enterprise AI agents.
    
    Provides core functionality for:
    - MCP integration
    - Reasoning processes
    - Memory management
    - Tool execution
    """
    
    def __init__(
        self,
        name: str,
        llm_provider,
        mcp_server,
        reasoning_engine=None,
        **kwargs
    ):
        self.name = name
        self.llm = llm_provider
        self.mcp_server = mcp_server
        self.reasoning_engine = reasoning_engine
        
        # Core agent state
        self.session_id: Optional[str] = None
        self.memory: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.tools: List[str] = []
        
        # Configuration
        self.max_iterations = kwargs.get('max_iterations', 10)
        self.verbose = kwargs.get('verbose', False)
        
        logger.info(f"Initialized agent: {self.name}")
    
    async def initialize(self) -> bool:
        """Initialize the agent and create MCP session."""
        try:
            # Create MCP session
            session_response = await self.mcp_server.process_message(
                MCPMessage.create(
                    message_type=MCPMessageType.SESSION_CREATE,
                    data={"agent_id": self.name},
                    agent_id=self.name
                )
            )
            
            if session_response.message_type != MCPMessageType.ERROR:
                self.session_id = session_response.data.get("session_id")
                logger.info(f"Agent {self.name} session created: {self.session_id}")
                return True
            else:
                logger.error(f"Failed to create session for agent {self.name}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing agent {self.name}: {e}")
            return False
    
    async def execute_task(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Main entry point for task execution.
        
        Args:
            task: The task description
            context: Additional context for the task
            
        Returns:
            Task execution result
        """
        if not self.session_id:
            await self.initialize()
        
        # Update context
        if context:
            self.context.update(context)
        
        # Use reasoning engine if available
        if self.reasoning_engine:
            return await self.reasoning_engine.process(task, self)
        else:
            # Simple direct execution
            return await self._simple_execute(task)
    
    async def _simple_execute(self, task: str) -> Dict[str, Any]:
        """Simple task execution without complex reasoning."""
        try:
            # Think about the task
            thought = await self.think(task)
            
            # Decide on action
            action = await self.plan_action(thought)
            
            if action:
                # Execute action
                result = await self.execute_tool(**action)
                
                # Observe result
                observation = await self.observe(result)
                
                return {
                    "success": True,
                    "result": observation,
                    "thought": thought,
                    "action": action
                }
            else:
                return {
                    "success": True,
                    "result": thought,
                    "thought": thought,
                    "action": None
                }
                
        except Exception as e:
            logger.error(f"Error in simple execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "thought": None,
                "action": None
            }
    
    @abstractmethod
    async def think(self, input_text: str) -> str:
        """Generate thoughts/reasoning for the input."""
        pass
    
    @abstractmethod
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan the next action based on current thought."""
        pass
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via MCP."""
        try:
            tool_call = ToolCall.create(
                name=tool_name,
                arguments=arguments,
                id=f"agent_{self.name}_{uuid.uuid4().hex[:8]}"
            )
            
            message = MCPMessage.create(
                message_type=MCPMessageType.TOOL_CALL,
                data={
                    "tool_calls": [tool_call.to_dict()],
                    "context": self.context
                },
                session_id=self.session_id,
                agent_id=self.name
            )
            
            response = await self.mcp_server.process_message(message)
            
            if response.message_type != MCPMessageType.ERROR:
                results = response.data.get("tool_results", [])
                return results[0] if results else {"success": False, "error": "No results"}
            else:
                return {"success": False, "error": response.data.get("error", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"success": False, "error": str(e)}
    
    async def observe(self, result: Dict[str, Any]) -> str:
        """Process and interpret tool execution results."""
        if result.get("success", False):
            return f"Action completed successfully: {result.get('result', 'No details')}"
        else:
            return f"Action failed: {result.get('error', 'Unknown error')}"
    
    def add_to_memory(self, entry: Dict[str, Any]) -> None:
        """Add an entry to agent memory."""
        self.memory.append({
            "timestamp": asyncio.get_event_loop().time(),
            "agent": self.name,
            **entry
        })
    
    def get_memory_summary(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent memory entries."""
        return self.memory[-limit:] if self.memory else []
    
    async def cleanup(self) -> None:
        """Clean up agent resources."""
        if self.session_id:
            try:
                await self.mcp_server.process_message(
                    MCPMessage.create(
                        message_type=MCPMessageType.SESSION_CLOSE,
                        data={"session_id": self.session_id},
                        agent_id=self.name
                    )
                )
                logger.info(f"Agent {self.name} session closed")
            except Exception as e:
                logger.warning(f"Error closing session for agent {self.name}: {e}")

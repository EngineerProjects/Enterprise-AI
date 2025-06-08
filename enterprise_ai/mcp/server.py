"""
Enterprise AI MCP Server implementation.

This module provides the main MCP server that coordinates tool execution,
session management, agent communication, and sandbox integration.
"""

import asyncio
import signal
import sys
from typing import Any, Callable, Dict, List, Optional

from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.registry import ToolRegistry
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client

# Import tools to trigger registration decorators
import enterprise_ai.tool  # This will trigger all tool registration decorators

from enterprise_ai.mcp.config import MCPConfig
from enterprise_ai.mcp.executor import ToolExecutor
from enterprise_ai.mcp.session_manager import SessionManager
from enterprise_ai.mcp.handlers.tool_handler import ToolHandler
from enterprise_ai.mcp.handlers.sandbox_handler import SandboxHandler
from enterprise_ai.mcp.handlers.agent_handler import AgentHandler
from enterprise_ai.mcp.protocols.mcp_protocol import MCPProtocol, MCPMessage, MCPMessageType
from enterprise_ai.mcp.protocols.tool_bridge import ToolBridge

logger = get_logger("mcp.server")


class EnterpriseMCPServer:
    """
    Main MCP server for Enterprise AI.
    
    Coordinates tool execution, session management, agent communication,
    and sandbox integration through a unified MCP protocol interface.
    """
    
    def __init__(self, config: Optional[MCPConfig] = None, approval_callback: Optional[Callable] = None):
        """Initialize the Enterprise MCP server."""
        self.config = config or MCPConfig.from_config()
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize core components
        self.tool_registry = ToolRegistry()
        self.session_manager = SessionManager(
            max_concurrent_sessions=self.config.max_concurrent_sessions,
            session_timeout=self.config.session_timeout,
            cleanup_interval=self.config.session_cleanup_interval,
            verbose=self.config.verbose_logging
        )
        self.tool_executor = ToolExecutor(
            config=self.config,
            session_manager=self.session_manager,
            approval_callback=approval_callback  # ADD THIS
        )
        
        # Initialize protocol and bridge
        self.protocol = MCPProtocol(verbose=self.config.verbose_logging)
        self.tool_bridge = ToolBridge(self.tool_registry)
        
        # Initialize handlers
        self.tool_handler = ToolHandler(
            executor=self.tool_executor,
            session_manager=self.session_manager,
            tool_registry=self.tool_registry
        )
        self.sandbox_handler = SandboxHandler()
        self.agent_handler = AgentHandler(
            max_queue_size=self.config.agent_message_queue_size
        )
        
        # Register message handlers
        self._register_message_handlers()
        
        logger.info("EnterpriseMCPServer initialized with config: %s", self.config.execution_mode)

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback for tool execution."""
        self.tool_executor.set_approval_callback(callback)
    
    def _register_message_handlers(self) -> None:
        """Register handlers for different MCP message types."""
        self.protocol.register_handler(
            MCPMessageType.TOOL_CALL, 
            self._handle_tool_call
        )
        self.protocol.register_handler(
            MCPMessageType.TOOL_LIST, 
            self._handle_tool_list
        )
        self.protocol.register_handler(
            MCPMessageType.TOOL_INFO, 
            self._handle_tool_info
        )
        self.protocol.register_handler(
            MCPMessageType.SESSION_CREATE, 
            self._handle_session_create
        )
        self.protocol.register_handler(
            MCPMessageType.SESSION_CLOSE, 
            self._handle_session_close
        )
        self.protocol.register_handler(
            MCPMessageType.AGENT_REGISTER, 
            self._handle_agent_register
        )
        self.protocol.register_handler(
            MCPMessageType.AGENT_MESSAGE, 
            self._handle_agent_message
        )
        self.protocol.register_handler(
            MCPMessageType.STATUS_REQUEST, 
            self._handle_status_request
        )
    
    async def start(self) -> None:
        """Start the MCP server."""
        if self.is_running:
            logger.warning("Server is already running")
            return
        
        try:
            logger.info("Starting Enterprise MCP Server...")
            
            # Start session manager
            await self.session_manager.start()
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            self.is_running = True
            logger.info("Enterprise MCP Server started successfully")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.error("Failed to start MCP server: %s", e)
            raise
    
    async def stop(self) -> None:
        """Stop the MCP server gracefully."""
        if not self.is_running:
            return
        
        logger.info("Stopping Enterprise MCP Server...")
        
        try:
            # Stop session manager
            await self.session_manager.stop()
            
            # Cleanup sandbox handler
            if self.sandbox_handler.is_available():
                await self.sandbox_handler.cleanup_sandbox()
            
            self.is_running = False
            self._shutdown_event.set()
            
            logger.info("Enterprise MCP Server stopped")
            
        except Exception as e:
            logger.error("Error during server shutdown: %s", e)
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal: %s", sig)
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def process_message(self, message: MCPMessage) -> Optional[MCPMessage]:
        """
        Process an incoming MCP message.
        
        Args:
            message: The MCP message to process
            
        Returns:
            Optional response message
        """
        if not self.is_running:
            return self.protocol.create_error_message(
                error="Server not running",
                error_code="SERVER_NOT_RUNNING"
            )
        
        # Validate message
        if not self.protocol.validate_message(message):
            return self.protocol.create_error_message(
                error="Invalid message format",
                error_code="INVALID_MESSAGE",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
        
        # Process through protocol
        return await self.protocol.process_message(message)
    
    # Message Handlers
    
    async def _handle_tool_call(self, message: MCPMessage) -> MCPMessage:
        """Handle tool call requests."""
        try:
            tool_calls_data = message.data.get("tool_calls", [])
            tool_calls = [self.tool_bridge.mcp_call_to_tool_call(tc) for tc in tool_calls_data]
            
            # Execute tools
            results = await self.tool_handler.handle_tool_execution(
                tool_calls=tool_calls,
                session_id=message.session_id,
                context=message.data.get("context", {})
            )
            
            # Convert results to MCP format
            mcp_results = [self.tool_bridge.tool_result_to_mcp_result(r) for r in results]
            
            return self.protocol.create_tool_result_message(
                tool_results=results,
                session_id=message.session_id,
                agent_id=message.agent_id
            )
            
        except Exception as e:
            logger.error("Tool call handling failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Tool execution failed: {str(e)}",
                error_code="TOOL_EXECUTION_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    async def _handle_tool_list(self, message: MCPMessage) -> MCPMessage:
        """Handle tool list requests."""
        try:
            tools = await self.tool_handler.handle_tool_list_request()
            
            return self.protocol.create_tool_list_message(
                tools=tools,
                session_id=message.session_id,
                agent_id=message.agent_id
            )
            
        except Exception as e:
            logger.error("Tool list handling failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to list tools: {str(e)}",
                error_code="TOOL_LIST_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    async def _handle_tool_info(self, message: MCPMessage) -> MCPMessage:
        """Handle tool info requests."""
        try:
            tool_name = message.data.get("tool_name")
            if not tool_name:
                return self.protocol.create_error_message(
                    error="Tool name required",
                    error_code="MISSING_TOOL_NAME",
                    session_id=message.session_id,
                    agent_id=message.agent_id
                )
            
            tool_info = await self.tool_handler.handle_tool_info_request(tool_name)
            
            if tool_info is None:
                return self.protocol.create_error_message(
                    error=f"Tool not found: {tool_name}",
                    error_code="TOOL_NOT_FOUND",
                    session_id=message.session_id,
                    agent_id=message.agent_id
                )
            
            response_data = {"tool_info": tool_info}
            return MCPMessage.create(
                message_type=MCPMessageType.TOOL_INFO,
                data=response_data,
                session_id=message.session_id,
                agent_id=message.agent_id
            )
            
        except Exception as e:
            logger.error("Tool info handling failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to get tool info: {str(e)}",
                error_code="TOOL_INFO_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    async def _handle_session_create(self, message: MCPMessage) -> MCPMessage:
        """Handle session creation requests."""
        try:
            agent_id = message.data.get("agent_id") or message.agent_id
            session_id = self.session_manager.create_session(agent_id)
            
            response_data = {"session_id": session_id}
            return MCPMessage.create(
                message_type=MCPMessageType.SESSION_CREATE,
                data=response_data,
                session_id=session_id,
                agent_id=agent_id
            )
            
        except Exception as e:
            logger.error("Session creation failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to create session: {str(e)}",
                error_code="SESSION_CREATE_ERROR",
                agent_id=message.agent_id
            )
    
    async def _handle_session_close(self, message: MCPMessage) -> MCPMessage:
        """Handle session close requests."""
        try:
            session_id = message.session_id or message.data.get("session_id")
            if not session_id:
                return self.protocol.create_error_message(
                    error="Session ID required",
                    error_code="MISSING_SESSION_ID",
                    agent_id=message.agent_id
                )
            
            success = self.session_manager.close_session(session_id)
            
            response_data = {"session_id": session_id, "closed": success}
            return MCPMessage.create(
                message_type=MCPMessageType.SESSION_CLOSE,
                data=response_data,
                agent_id=message.agent_id
            )
            
        except Exception as e:
            logger.error("Session close failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to close session: {str(e)}",
                error_code="SESSION_CLOSE_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    async def _handle_agent_register(self, message: MCPMessage) -> MCPMessage:
        """Handle agent registration requests."""
        try:
            agent_id = message.data.get("agent_id") or message.agent_id
            agent_info = message.data.get("agent_info", {})
            
            if not agent_id:
                return self.protocol.create_error_message(
                    error="Agent ID required",
                    error_code="MISSING_AGENT_ID"
                )
            
            success = await self.agent_handler.register_agent(agent_id, agent_info)
            
            response_data = {"agent_id": agent_id, "registered": success}
            return MCPMessage.create(
                message_type=MCPMessageType.AGENT_REGISTER,
                data=response_data,
                agent_id=agent_id
            )
            
        except Exception as e:
            logger.error("Agent registration failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to register agent: {str(e)}",
                error_code="AGENT_REGISTER_ERROR",
                agent_id=message.agent_id
            )
    
    async def _handle_agent_message(self, message: MCPMessage) -> MCPMessage:
        """Handle inter-agent messages."""
        try:
            from_agent = message.data.get("from_agent") or message.agent_id
            to_agent = message.data.get("to_agent")
            content = message.data.get("content")
            message_type_name = message.data.get("message_type_name", "general")
            
            if not all([from_agent, to_agent, content]):
                return self.protocol.create_error_message(
                    error="From agent, to agent, and content required",
                    error_code="MISSING_MESSAGE_DATA",
                    agent_id=message.agent_id
                )
            
            success = await self.agent_handler.send_message(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type=message_type_name,
                content=content
            )
            
            response_data = {"sent": success}
            return MCPMessage.create(
                message_type=MCPMessageType.AGENT_MESSAGE,
                data=response_data,
                agent_id=from_agent
            )
            
        except Exception as e:
            logger.error("Agent message handling failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to handle agent message: {str(e)}",
                error_code="AGENT_MESSAGE_ERROR",
                agent_id=message.agent_id
            )
    
    async def _handle_status_request(self, message: MCPMessage) -> MCPMessage:
        """Handle status requests."""
        try:
            status_data = {
                "server_running": self.is_running,
                "session_stats": self.session_manager.get_session_stats(),
                "execution_stats": self.tool_executor.get_execution_stats(),
                "agent_stats": self.agent_handler.get_communication_stats(),
                "tool_count": len(self.tool_registry.get_all_tool_classes()),
                "sandbox_available": self.sandbox_handler.is_available(),
                "protocol_info": self.protocol.get_protocol_info()
            }
            
            return MCPMessage.create(
                message_type=MCPMessageType.STATUS_REQUEST,
                data=status_data,
                session_id=message.session_id,
                agent_id=message.agent_id
            )
            
        except Exception as e:
            logger.error("Status request handling failed: %s", e)
            return self.protocol.create_error_message(
                error=f"Failed to get status: {str(e)}",
                error_code="STATUS_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    # Public API Methods
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information."""
        return {
            "name": "Enterprise AI MCP Server",
            "version": "1.0.0",
            "running": self.is_running,
            "config": self.config.dict(),
            "stats": {
                "sessions": self.session_manager.get_session_stats(),
                "execution": self.tool_executor.get_execution_stats(),
                "agents": self.agent_handler.get_communication_stats(),
                "tools": len(self.tool_registry.get_all_tool_classes())
            }
        }
    
    async def execute_tool_directly(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool directly (convenience method).
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            session_id: Optional session ID
            agent_id: Optional agent ID
            
        Returns:
            Tool execution result
        """
        from enterprise_ai.schema import ToolCall, FunctionCall
        
        tool_call = ToolCall(
            id=f"direct_{tool_name}",
            type="function",
            function=FunctionCall(name=tool_name, arguments=arguments)
        )
        
        results = await self.tool_executor.execute_tool_calls(
            tool_calls=[tool_call],
            session_id=session_id
        )
        
        if results:
            result = results[0]
            return self.tool_bridge.tool_result_to_mcp_result(result)
        
        return {"success": False, "error": "No result returned"}


# Convenience function for running the server
async def run_mcp_server(config: Optional[MCPConfig] = None) -> None:
    """
    Run the Enterprise MCP server.
    
    Args:
        config: Optional MCP configuration
    """
    server = EnterpriseMCPServer(config)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await server.stop()


if __name__ == "__main__":
    """Run the MCP server from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enterprise AI MCP Server")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Create config
    config = MCPConfig.from_config()
    if args.verbose:
        config.verbose_logging = True
    
    # Run server
    try:
        asyncio.run(run_mcp_server(config))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server failed: %s", e)
        sys.exit(1)
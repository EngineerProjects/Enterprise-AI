"""
Session management for MCP tool execution.

This module manages execution sessions, tracks context, and handles
multi-agent communication sessions.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("mcp.session_manager")


@dataclass
class ExecutionSession:
    """Represents an active tool execution session."""
    
    session_id: str
    agent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # Execution context
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    messages: List[MessageProtocol] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Session state
    is_active: bool = True
    execution_count: int = 0
    error_count: int = 0
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = time.time()
    
    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call to the session."""
        self.tool_calls.append(tool_call)
        self.execution_count += 1
        self.update_activity()
    
    def add_tool_result(self, result: ToolResult) -> None:
        """Add a tool result to the session."""
        self.tool_results.append(result)
        if not result.success:
            self.error_count += 1
        self.update_activity()
    
    def add_message(self, message: MessageProtocol) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.update_activity()
    
    def is_expired(self, timeout: float) -> bool:
        """Check if the session has expired."""
        return time.time() - self.last_activity > timeout
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "is_active": self.is_active,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "tool_calls_count": len(self.tool_calls),
            "tool_results_count": len(self.tool_results),
            "messages_count": len(self.messages),
        }


class SessionManager:
    """Manages execution sessions for the MCP server."""
    
    def __init__(
        self,
        max_concurrent_sessions: int = 10,
        session_timeout: float = 3600.0,
        cleanup_interval: float = 300.0,
        verbose: bool = False
    ):
        """Initialize the session manager."""
        self.max_concurrent_sessions = max_concurrent_sessions
        self.session_timeout = session_timeout
        self.cleanup_interval = cleanup_interval
        self.verbose = verbose
        
        self._sessions: Dict[str, ExecutionSession] = {}
        self._agent_sessions: Dict[str, Set[str]] = {}  # agent_id -> session_ids
        self._cleanup_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("SessionManager initialized with max_sessions=%d, timeout=%.1fs", 
                   max_concurrent_sessions, session_timeout)
    
    async def start(self) -> None:
        """Start the session manager and cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session manager started")
    
    async def stop(self) -> None:
        """Stop the session manager and cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        logger.info("Session manager stopped")
    
    def create_session(self, agent_id: Optional[str] = None) -> str:
        """Create a new execution session."""
        # Check session limits
        if len(self._sessions) >= self.max_concurrent_sessions:
            # Try to clean up expired sessions first
            self._cleanup_expired_sessions()
            
            if len(self._sessions) >= self.max_concurrent_sessions:
                raise RuntimeError(f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached")
        
        session_id = str(uuid.uuid4())
        session = ExecutionSession(
            session_id=session_id,
            agent_id=agent_id
        )
        
        self._sessions[session_id] = session
        
        # Track agent sessions
        if agent_id:
            if agent_id not in self._agent_sessions:
                self._agent_sessions[agent_id] = set()
            self._agent_sessions[agent_id].add(session_id)
        
        if self.verbose:
            logger.info("Created session %s for agent %s", session_id, agent_id or "None")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ExecutionSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_active:
            return session
        return None
    
    def close_session(self, session_id: str) -> bool:
        """Close and remove a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.is_active = False
        
        # Remove from agent tracking
        if session.agent_id and session.agent_id in self._agent_sessions:
            self._agent_sessions[session.agent_id].discard(session_id)
            if not self._agent_sessions[session.agent_id]:
                del self._agent_sessions[session.agent_id]
        
        # Remove from sessions
        del self._sessions[session_id]
        
        if self.verbose:
            logger.info("Closed session %s", session_id)
        
        return True
    
    def get_agent_sessions(self, agent_id: str) -> List[str]:
        """Get all active session IDs for an agent."""
        return list(self._agent_sessions.get(agent_id, set()))
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [session.get_session_info() for session in self._sessions.values()]
    
    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get the context for a session."""
        session = self.get_session(session_id)
        if session:
            return session.context.copy()
        return {}
    
    def update_session_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """Update the context for a session."""
        session = self.get_session(session_id)
        if session:
            session.context.update(context)
            session.update_activity()
            return True
        return False
    
    def add_tool_execution(
        self,
        session_id: str,
        tool_call: ToolCall,
        result: ToolResult
    ) -> bool:
        """Add a tool execution to a session."""
        session = self.get_session(session_id)
        if session:
            session.add_tool_call(tool_call)
            session.add_tool_result(result)
            return True
        return False
    
    def add_session_message(self, session_id: str, message: MessageProtocol) -> bool:
        """Add a message to a session."""
        session = self.get_session(session_id)
        if session:
            session.add_message(message)
            return True
        return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get overall session statistics."""
        active_sessions = len(self._sessions)
        total_executions = sum(s.execution_count for s in self._sessions.values())
        total_errors = sum(s.error_count for s in self._sessions.values())
        
        return {
            "active_sessions": active_sessions,
            "max_sessions": self.max_concurrent_sessions,
            "total_agents": len(self._agent_sessions),
            "total_executions": total_executions,
            "total_errors": total_errors,
            "error_rate": total_errors / max(1, total_executions),
            "session_timeout": self.session_timeout,
        }
    
    def _cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        expired_sessions = []
        
        for session_id, session in self._sessions.items():
            if session.is_expired(self.session_timeout):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.close_session(session_id)
        
        if expired_sessions and self.verbose:
            logger.info("Cleaned up %d expired sessions", len(expired_sessions))
        
        return len(expired_sessions)
    
    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in session cleanup: %s", e)
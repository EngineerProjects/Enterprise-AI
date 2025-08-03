"""
Simplified Tool Call Logger for Enterprise AI - Log Files Only

This module provides comprehensive tool call and output logging using 
ONLY structured .log files (no JSON). Much cleaner and easier to read.

Key Features:
- Saves ALL tool call commands to tool_calls.log
- Saves ALL tool outputs to tool_outputs.log  
- Structured, human-readable format
- Large outputs stored in separate .txt files
- Easy to parse and analyze
- Simple integration with existing systems
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass

from enterprise_ai.schema import ToolCall

# Avoid circular import by using TYPE_CHECKING
if TYPE_CHECKING:
    from enterprise_ai.tool.core.result import ToolResult

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.call_logger")


@dataclass
class ToolCallRecord:
    """Simple record of a tool call for tracking."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    timestamp: datetime
    session_id: Optional[str] = None
    agent_name: Optional[str] = None


@dataclass 
class ToolOutputRecord:
    """Simple record of a tool execution result."""
    call_id: str
    tool_name: str
    success: bool
    result: Any
    error: Optional[str]
    execution_time: Optional[float]
    timestamp: datetime
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    result_size_chars: int = 0
    result_size_tokens: int = 0  # Estimated
    
    def __post_init__(self):
        """Calculate result size after initialization."""
        if self.result is not None:
            result_str = str(self.result)
            self.result_size_chars = len(result_str)
            self.result_size_tokens = self.result_size_chars // 4  # Rough estimate


class SimplifiedToolLogger:
    """
    Simplified tool logger that saves everything to structured .log files only.
    
    File Structure:
    logs/tools/
    ├── tool_calls.log            # All tool call commands (structured)
    ├── tool_outputs.log          # All tool execution results (structured)
    └── large_outputs/            # Separate files for huge outputs
        ├── {call_id}_output.txt
        └── ...
    """
    
    def __init__(self, log_dir: str = "logs/tools", large_output_threshold: int = 10000):
        self.log_dir = Path(log_dir)
        self.large_output_threshold = large_output_threshold  # chars
        self.large_outputs_dir = self.log_dir / "large_outputs"
        
        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.large_outputs_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file paths
        self.calls_log = self.log_dir / "tool_calls.log"
        self.outputs_log = self.log_dir / "tool_outputs.log"
        
        logger.info(f"Simplified Tool Logger initialized: {self.log_dir}")
    
    def log_tool_call(
        self, 
        tool_call: ToolCall, 
        session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        reasoning_context: Optional[str] = None
    ) -> ToolCallRecord:
        """
        Log a tool call command to structured .log file.
        
        Args:
            tool_call: The tool call object
            session_id: Current MCP session ID
            agent_name: Name of the agent making the call
            reasoning_context: Context about why this tool was called
            
        Returns:
            ToolCallRecord for tracking
        """
        record = ToolCallRecord(
            call_id=tool_call.id,
            tool_name=tool_call.function.name,
            arguments=tool_call.function.arguments or {},
            timestamp=datetime.now(),
            session_id=session_id,
            agent_name=agent_name
        )
        
        # Write to structured log
        self._write_call_log(record, reasoning_context)
        
        logger.debug(f"📞 Logged tool call: {tool_call.function.name}({tool_call.id})")
        return record
    
    def log_tool_output(
        self,
        tool_call: ToolCall,
        result: "ToolResult",
        session_id: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> ToolOutputRecord:
        """
        Log a tool execution result to structured .log file.
        
        Args:
            tool_call: The original tool call
            result: The execution result
            session_id: Current MCP session ID  
            agent_name: Name of the agent
            
        Returns:
            ToolOutputRecord for tracking
        """
        # Import locally to avoid circular import
        from enterprise_ai.tool.core.result import ToolResult
        # Determine if output should be stored separately
        result_content = result.result if result.success else result.error
        should_store_separately = False
        original_size = len(str(result_content or ""))
        
        if result_content and original_size > self.large_output_threshold:
            # Store large outputs in separate files
            output_file = self.large_outputs_dir / f"{tool_call.id}_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(str(result_content))
            
            # Replace content with file reference
            result_content = f"LARGE_OUTPUT_FILE:{output_file.name}"
            should_store_separately = True
        
        record = ToolOutputRecord(
            call_id=tool_call.id,
            tool_name=tool_call.function.name,
            success=result.success,
            result=result_content,
            error=result.error if not result.success else None,
            execution_time=result.execution_time,
            timestamp=datetime.now(),
            session_id=session_id,
            agent_name=agent_name
        )
        
        # Override size calculation for large files
        if should_store_separately:
            record.result_size_chars = original_size
            record.result_size_tokens = original_size // 4
        
        # Write to structured log
        self._write_output_log(record, should_store_separately, original_size)
        
        # Log size warning if needed
        if should_store_separately:
            logger.info(
                f"📄 Large output stored separately: {tool_call.function.name} "
                f"({original_size:,} chars) -> {output_file.name}"
            )
        
        logger.debug(f"📤 Logged tool output: {tool_call.function.name}({tool_call.id})")
        return record
    
    def log_tool_execution_pair(
        self,
        tool_call: ToolCall,
        result: "ToolResult",
        session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        reasoning_context: Optional[str] = None
    ) -> tuple[ToolCallRecord, ToolOutputRecord]:
        """
        Log both the tool call and its result as a pair.
        
        This is the main method to use from MCP executor.
        """
        call_record = self.log_tool_call(
            tool_call, session_id, agent_name, reasoning_context
        )
        output_record = self.log_tool_output(
            tool_call, result, session_id, agent_name
        )
        
        return call_record, output_record
    
    def _write_call_log(self, record: ToolCallRecord, reasoning_context: Optional[str] = None) -> None:
        """Write tool call to structured log file."""
        with open(self.calls_log, 'a', encoding='utf-8') as f:
            timestamp = record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            f.write(f"\n{'='*80}\n")
            f.write(f"TOOL CALL: {record.tool_name}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Call ID:     {record.call_id}\n")
            f.write(f"Timestamp:   {timestamp}\n")
            f.write(f"Session:     {record.session_id or 'N/A'}\n")
            f.write(f"Agent:       {record.agent_name or 'N/A'}\n")
            
            if reasoning_context:
                f.write(f"Context:     {reasoning_context}\n")
            
            f.write(f"\nARGUMENTS:\n")
            f.write(f"{'-'*40}\n")
            
            if record.arguments:
                for key, value in record.arguments.items():
                    # Format value nicely
                    if isinstance(value, str) and len(value) > 100:
                        value_display = f"{value[:100]}... [{len(value)} chars total]"
                    else:
                        value_display = str(value)
                    
                    f.write(f"{key:20} : {value_display}\n")
            else:
                f.write("(No arguments)\n")
            
            f.write(f"\n")
    
    def _write_output_log(
        self, 
        record: ToolOutputRecord, 
        stored_separately: bool = False,
        original_size: int = 0
    ) -> None:
        """Write tool output to structured log file."""
        with open(self.outputs_log, 'a', encoding='utf-8') as f:
            timestamp = record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            status = "SUCCESS" if record.success else "FAILED"
            status_symbol = "✅" if record.success else "❌"
            
            f.write(f"\n{'='*80}\n")
            f.write(f"TOOL OUTPUT: {record.tool_name} {status_symbol} [{status}]\n")
            f.write(f"{'='*80}\n")
            f.write(f"Call ID:       {record.call_id}\n")
            f.write(f"Timestamp:     {timestamp}\n")
            f.write(f"Session:       {record.session_id or 'N/A'}\n")
            f.write(f"Agent:         {record.agent_name or 'N/A'}\n")
            
            if record.execution_time:
                f.write(f"Exec Time:     {record.execution_time:.3f}s\n")
            
            f.write(f"Result Size:   {record.result_size_chars:,} chars (~{record.result_size_tokens:,} tokens)\n")
            
            if stored_separately:
                f.write(f"Storage:       Large output stored separately\n")
                f.write(f"Original Size: {original_size:,} chars\n")
            
            f.write(f"\nRESULT:\n")
            f.write(f"{'-'*40}\n")
            
            if record.success:
                result_str = str(record.result or "")
                if stored_separately:
                    f.write(f"📁 {result_str}\n")
                    f.write(f"   (Full content saved to large_outputs/ directory)\n")
                else:
                    # Show full result for small outputs, preview for medium ones
                    if len(result_str) <= 1000:
                        f.write(f"{result_str}\n")
                    else:
                        f.write(f"{result_str[:500]}\n")
                        f.write(f"... [TRUNCATED - {len(result_str)} chars total] ...\n")
                        f.write(f"{result_str[-200:]}\n")
            else:
                f.write(f"ERROR: {record.error}\n")
            
            f.write(f"\n")
    
    def get_large_output(self, call_id: str) -> Optional[str]:
        """Retrieve a large output stored in separate file."""
        output_file = self.large_outputs_dir / f"{call_id}_output.txt"
        
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        return None
    
    def list_session_calls(self, session_id: str) -> List[str]:
        """Get a summary of tool calls for a session by parsing the log file."""
        calls = []
        
        if not self.calls_log.exists():
            return calls
        
        try:
            with open(self.calls_log, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Simple parsing - look for session blocks
            blocks = content.split('=' * 80)
            for block in blocks:
                if f"Session:     {session_id}" in block:
                    lines = block.strip().split('\n')
                    for line in lines:
                        if line.startswith('TOOL CALL:'):
                            tool_name = line.replace('TOOL CALL:', '').strip()
                            calls.append(tool_name)
                            break
        except Exception as e:
            logger.warning(f"Error parsing calls log: {e}")
        
        return calls
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of a session's tool usage."""
        calls = self.list_session_calls(session_id)
        
        # Count tool usage
        tool_counts = {}
        for tool in calls:
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        return {
            "session_id": session_id,
            "total_calls": len(calls),
            "unique_tools": len(tool_counts),
            "tool_usage": tool_counts,
            "log_files": {
                "calls_log": str(self.calls_log),
                "outputs_log": str(self.outputs_log),
                "large_outputs_dir": str(self.large_outputs_dir)
            }
        }


# Global instance
_simplified_logger: Optional[SimplifiedToolLogger] = None

def get_simplified_tool_logger() -> SimplifiedToolLogger:
    """Get the global simplified tool logger instance."""
    global _simplified_logger
    if _simplified_logger is None:
        _simplified_logger = SimplifiedToolLogger()
    return _simplified_logger


def log_tool_execution(
    tool_call: ToolCall,
    result: "ToolResult", 
    session_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    reasoning_context: Optional[str] = None
) -> tuple[ToolCallRecord, ToolOutputRecord]:
    """Convenience function to log tool execution pair."""
    return get_simplified_tool_logger().log_tool_execution_pair(
        tool_call, result, session_id, agent_name, reasoning_context
    )

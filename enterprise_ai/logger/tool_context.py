"""
Minimal ToolExecutionContext for backward compatibility.

This provides a simple context manager that logs to console instead of JSON files.
"""

import time
from datetime import datetime
from typing import Optional
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.execution.context")


class ToolExecutionContext:
    """
    Simplified context manager for tool execution tracking.
    
    Provides basic logging without JSON file complexity.
    """
    
    def __init__(self, tool_name: str, execution_id: Optional[str] = None):
        self.tool_name = tool_name
        self.execution_id = execution_id or f"{tool_name}_{int(time.time() * 1000)}"
        self.start_time = None
        self.insights_count = 0
        self.sources_used = []  # Track sources used
        
    def __enter__(self):
        self.start_time = datetime.now()
        logger.debug(f"🔧 Starting {self.tool_name} execution")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        if exc_type is None:
            logger.debug(f"✅ {self.tool_name} completed in {duration:.2f}s with {self.insights_count} insights, {len(self.sources_used)} sources")
        else:
            logger.debug(f"❌ {self.tool_name} failed after {duration:.2f}s: {exc_val}")
    
    def add_source(self, url: str, content_length: int, **kwargs):
        """Log a source that was used (simplified)."""
        self.sources_used.append(url)
        logger.debug(f"📄 {self.tool_name} used source: {url} ({content_length} chars)")
    
    def add_insights(self, count: int):
        """Track insights generated (simplified)."""
        self.insights_count += count
        logger.debug(f"💡 {self.tool_name} generated {count} insights")

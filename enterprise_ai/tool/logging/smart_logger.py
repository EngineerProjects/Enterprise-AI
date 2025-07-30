"""
Smart Tool Logging System for Enterprise AI

This module provides intelligent, source-focused logging that tracks:
- Actual sources used (not all attempted)
- Tool execution outcomes and performance
- MCP usage patterns and statistics
- Research provenance and audit trails
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Union
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

from enterprise_ai.logger import get_optimized_logger


class LogLevel(str, Enum):
    """Smart log levels for different use cases."""
    SOURCE = "source"        # Actual sources used
    OUTCOME = "outcome"      # Tool execution results
    PERFORMANCE = "performance"  # Timing and stats
    AUDIT = "audit"         # Compliance/verification
    ERROR = "error"         # Problems only


@dataclass
class SourceEvidence:
    """Evidence of an actual source being used for data extraction."""
    url: str
    tool_name: str
    extraction_time: datetime
    content_length: int
    extraction_method: str
    success_score: float  # 0-1, quality of extraction
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_citation(self) -> str:
        """Generate a proper citation for this source."""
        return f"{self.url} (extracted via {self.extraction_method} at {self.extraction_time.strftime('%Y-%m-%d %H:%M:%S')})"


@dataclass
class ToolOutcome:
    """Complete outcome of a tool execution."""
    tool_name: str
    execution_id: str
    start_time: datetime
    end_time: datetime
    success: bool
    sources_used: List[SourceEvidence] = field(default_factory=list)
    insights_generated: int = 0
    tokens_processed: int = 0
    cost_estimate: float = 0.0
    error_details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def sources_count(self) -> int:
        return len(self.sources_used)


@dataclass
class MCPSession:
    """Track an MCP session with intelligent metrics."""
    session_id: str
    start_time: datetime
    tools_executed: List[ToolOutcome] = field(default_factory=list)
    total_sources_used: Set[str] = field(default_factory=set)
    sandbox_usage: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    
    def add_tool_outcome(self, outcome: ToolOutcome) -> None:
        """Add a tool outcome and update session metrics."""
        self.tools_executed.append(outcome)
        
        # Track unique sources across all tools
        for source in outcome.sources_used:
            self.total_sources_used.add(source.url)
        
        # Update performance metrics
        self.performance_metrics[f"{outcome.tool_name}_count"] = (
            self.performance_metrics.get(f"{outcome.tool_name}_count", 0) + 1
        )
        self.performance_metrics[f"{outcome.tool_name}_total_time"] = (
            self.performance_metrics.get(f"{outcome.tool_name}_total_time", 0) + 
            outcome.duration_seconds
        )


class SmartToolLogger:
    """
    Intelligent tool logger that focuses on actionable information.
    
    Key Features:
    - Only logs successful extractions, not attempts
    - Tracks actual sources used for research audit trail  
    - Provides clean usage statistics
    - Generates compliance reports
    """
    
    def __init__(self, log_dir: str = "logs/tools", enable_file_logging: bool = True):
        self.log_dir = Path(log_dir)
        self.enable_file_logging = enable_file_logging
        self.logger = get_optimized_logger("smart_tool_logger")
        
        # In-memory tracking
        self.current_session: Optional[MCPSession] = None
        self.source_registry: Dict[str, SourceEvidence] = {}  # url -> evidence
        self.execution_history: List[ToolOutcome] = []
        
        # Setup log directory
        if self.enable_file_logging:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
        self.logger.info("Smart Tool Logger initialized")
    
    def start_mcp_session(self, session_id: Optional[str] = None) -> str:
        """Start a new MCP session for tracking."""
        if session_id is None:
            session_id = f"mcp_{int(time.time())}"
            
        self.current_session = MCPSession(
            session_id=session_id,
            start_time=datetime.now()
        )
        
        self.logger.info(f"🚀 Started MCP session: {session_id}")
        return session_id
    
    def log_source_used(
        self, 
        url: str, 
        tool_name: str, 
        content_length: int,
        extraction_method: str = "unknown",
        success_score: float = 1.0,
        **metadata
    ) -> None:
        """
        Log that a source was actually used for data extraction.
        
        This is THE KEY METHOD - only call this when you actually extract
        useful data from a source, not when you just attempt to access it.
        """
        evidence = SourceEvidence(
            url=url,
            tool_name=tool_name,
            extraction_time=datetime.now(),
            content_length=content_length,
            extraction_method=extraction_method,
            success_score=success_score,
            metadata=metadata
        )
        
        # Store in registry
        self.source_registry[url] = evidence
        
        # Log for immediate feedback
        self.logger.info(
            f"📄 SOURCE USED: {tool_name} extracted {content_length} chars from {url} "
            f"(method: {extraction_method}, score: {success_score:.2f})"
        )
        
        # File logging
        if self.enable_file_logging:
            self._write_source_log(evidence)
    
    def log_tool_outcome(
        self,
        tool_name: str,
        execution_id: str,
        start_time: datetime,
        success: bool,
        sources_used: Optional[List[str]] = None,
        insights_generated: int = 0,
        error_details: Optional[str] = None,
        **metadata
    ) -> ToolOutcome:
        """Log the complete outcome of a tool execution."""
        
        # Gather source evidence for this execution
        source_evidence = []
        if sources_used:
            for url in sources_used:
                if url in self.source_registry:
                    source_evidence.append(self.source_registry[url])
        
        outcome = ToolOutcome(
            tool_name=tool_name,
            execution_id=execution_id,
            start_time=start_time,
            end_time=datetime.now(),
            success=success,
            sources_used=source_evidence,
            insights_generated=insights_generated,
            error_details=error_details,
            metadata=metadata
        )
        
        # Add to history
        self.execution_history.append(outcome)
        
        # Add to current session
        if self.current_session:
            self.current_session.add_tool_outcome(outcome)
        
        # Smart logging based on outcome
        if success:
            if source_evidence:
                self.logger.info(
                    f"✅ {tool_name} SUCCESS: {len(source_evidence)} sources used, "
                    f"{insights_generated} insights, {outcome.duration_seconds:.1f}s"
                )
            else:
                self.logger.info(
                    f"✅ {tool_name} SUCCESS: {outcome.duration_seconds:.1f}s"
                )
        else:
            self.logger.error(
                f"❌ {tool_name} FAILED: {error_details} ({outcome.duration_seconds:.1f}s)"
            )
        
        # File logging
        if self.enable_file_logging:
            self._write_outcome_log(outcome)
            
        return outcome
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current MCP session."""
        if not self.current_session:
            return {"error": "No active session"}
        
        session = self.current_session
        tools_used = {}
        total_duration = 0
        successful_tools = 0
        
        for outcome in session.tools_executed:
            if outcome.tool_name not in tools_used:
                tools_used[outcome.tool_name] = {
                    "executions": 0,
                    "successes": 0,
                    "total_time": 0,
                    "sources_used": 0
                }
            
            tools_used[outcome.tool_name]["executions"] += 1
            if outcome.success:
                tools_used[outcome.tool_name]["successes"] += 1
                successful_tools += 1
            tools_used[outcome.tool_name]["total_time"] += outcome.duration_seconds
            tools_used[outcome.tool_name]["sources_used"] += len(outcome.sources_used)
            total_duration += outcome.duration_seconds
        
        return {
            "session_id": session.session_id,
            "duration_minutes": (datetime.now() - session.start_time).total_seconds() / 60,
            "tools_used": tools_used,
            "total_executions": len(session.tools_executed),
            "successful_executions": successful_tools,
            "success_rate": successful_tools / max(1, len(session.tools_executed)),
            "unique_sources": len(session.total_sources_used),
            "total_execution_time": total_duration,
            "sources_by_domain": self._group_sources_by_domain(session.total_sources_used)
        }
    
    def get_source_citations(self, tool_name: Optional[str] = None) -> List[str]:
        """
        Get properly formatted citations for all sources used.
        
        This is PERFECT for research audit trails and compliance.
        """
        citations = []
        
        for evidence in self.source_registry.values():
            if tool_name is None or evidence.tool_name == tool_name:
                citations.append(evidence.to_citation())
        
        return sorted(citations)
    
    def get_research_provenance(self, query: str) -> Dict[str, Any]:
        """
        Generate a complete provenance report for research queries.
        
        Perfect for academic/professional research validation.
        """
        if not self.current_session:
            return {"error": "No active session"}
        
        # Find research-related tools
        research_tools = ["web_search", "deep_research", "browser"]
        research_outcomes = [
            outcome for outcome in self.current_session.tools_executed
            if any(tool in outcome.tool_name.lower() for tool in research_tools)
        ]
        
        # Collect all sources with quality scores
        sources_with_quality = []
        for outcome in research_outcomes:
            for source in outcome.sources_used:
                sources_with_quality.append({
                    "url": source.url,
                    "quality_score": source.success_score,
                    "content_length": source.content_length,
                    "extraction_method": source.extraction_method,
                    "tool_used": source.tool_name,
                    "timestamp": source.extraction_time.isoformat()
                })
        
        # Sort by quality score
        sources_with_quality.sort(key=lambda x: x["quality_score"], reverse=True)
        
        return {
            "query": query,
            "total_sources_consulted": len(sources_with_quality),
            "high_quality_sources": [s for s in sources_with_quality if s["quality_score"] > 0.7],
            "research_tools_used": [outcome.tool_name for outcome in research_outcomes],
            "total_research_time": sum(outcome.duration_seconds for outcome in research_outcomes),
            "citations": self.get_source_citations(),
            "source_domains": self._group_sources_by_domain(
                {s["url"] for s in sources_with_quality}
            ),
            "generated_at": datetime.now().isoformat()
        }
    
    def _group_sources_by_domain(self, urls: Set[str]) -> Dict[str, int]:
        """Group sources by domain for analysis."""
        from urllib.parse import urlparse
        
        domains = {}
        for url in urls:
            try:
                domain = urlparse(url).netloc
                domains[domain] = domains.get(domain, 0) + 1
            except Exception:
                domains["unknown"] = domains.get("unknown", 0) + 1
        
        return domains
    
    def _write_source_log(self, evidence: SourceEvidence) -> None:
        """Write source evidence to file."""
        if not self.enable_file_logging:
            return
        
        log_file = self.log_dir / "sources.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(evidence), default=str) + "\n")
    
    def _write_outcome_log(self, outcome: ToolOutcome) -> None:
        """Write tool outcome to file."""
        if not self.enable_file_logging:
            return
        
        log_file = self.log_dir / "outcomes.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(outcome), default=str) + "\n")
    
    def export_session_report(self, format: str = "json") -> str:
        """Export a complete session report for compliance/auditing."""
        if not self.current_session:
            return json.dumps({"error": "No active session"})
        
        report = {
            "session_summary": self.get_session_summary(),
            "detailed_outcomes": [asdict(outcome) for outcome in self.current_session.tools_executed],
            "source_evidence": [asdict(evidence) for evidence in self.source_registry.values()],
            "citations": self.get_source_citations(),
            "export_timestamp": datetime.now().isoformat()
        }
        
        if format.lower() == "json":
            return json.dumps(report, indent=2, default=str)
        else:
            # Could add other formats (CSV, HTML report, etc.)
            return json.dumps(report, default=str)


# Global instance for easy access
_smart_logger: Optional[SmartToolLogger] = None

def get_smart_logger() -> SmartToolLogger:
    """Get the global smart tool logger instance."""
    global _smart_logger
    if _smart_logger is None:
        _smart_logger = SmartToolLogger()
    return _smart_logger


def log_source_used(url: str, tool_name: str, content_length: int, **kwargs) -> None:
    """Convenience function to log a source being used."""
    get_smart_logger().log_source_used(url, tool_name, content_length, **kwargs)


def log_tool_outcome(tool_name: str, execution_id: str, start_time: datetime, 
                    success: bool, **kwargs) -> ToolOutcome:
    """Convenience function to log a tool outcome."""
    return get_smart_logger().log_tool_outcome(
        tool_name, execution_id, start_time, success, **kwargs
    )


# Context managers for easy integration
class ToolExecutionContext:
    """Context manager for tracking tool execution with smart logging."""
    
    def __init__(self, tool_name: str, execution_id: Optional[str] = None):
        self.tool_name = tool_name
        self.execution_id = execution_id or f"{tool_name}_{int(time.time() * 1000)}"
        self.start_time = None
        self.sources_used = []
        self.insights_generated = 0
        self.success = False
        self.error_details = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.success = exc_type is None
        if exc_type:
            self.error_details = str(exc_val)
        
        log_tool_outcome(
            tool_name=self.tool_name,
            execution_id=self.execution_id,
            start_time=self.start_time,
            success=self.success,
            sources_used=self.sources_used,
            insights_generated=self.insights_generated,
            error_details=self.error_details
        )
    
    def add_source(self, url: str, content_length: int, **kwargs):
        """Add a source that was actually used for data extraction."""
        self.sources_used.append(url)
        log_source_used(url, self.tool_name, content_length, **kwargs)
    
    def add_insights(self, count: int):
        """Track insights generated by this tool execution."""
        self.insights_generated += count

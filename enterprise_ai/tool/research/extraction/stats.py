"""
Statistics tracking for content extraction.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ExtractorStats:
    """Statistics for content extraction operations."""
    total_attempts: int = 0
    successful_extractions: int = 0
    method_success: Dict[str, int] = field(default_factory=dict)
    method_attempts: Dict[str, int] = field(default_factory=dict)
    method_times: Dict[str, float] = field(default_factory=dict)
    total_extraction_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_extractions / self.total_attempts) * 100
    
    @property
    def avg_extraction_time(self) -> float:
        """Calculate average extraction time per attempt."""
        if self.total_attempts == 0:
            return 0.0
        return self.total_extraction_time / self.total_attempts
    
    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return time.time() - self.start_time
    
    def track_attempt(self, method: str):
        """Track an extraction attempt."""
        self.total_attempts += 1
        self.method_attempts[method] = self.method_attempts.get(method, 0) + 1
    
    def track_success(self, method: str, extraction_time: float):
        """Track a successful extraction."""
        self.successful_extractions += 1
        self.method_success[method] = self.method_success.get(method, 0) + 1
        self.method_times[method] = self.method_times.get(method, 0) + extraction_time
        self.total_extraction_time += extraction_time
    
    def track_failure(self, extraction_time: float):
        """Track a failed extraction."""
        self.total_extraction_time += extraction_time
    
    def get_method_success_rate(self, method: str) -> float:
        """Get success rate for specific method."""
        attempts = self.method_attempts.get(method, 0)
        if attempts == 0:
            return 0.0
        successes = self.method_success.get(method, 0)
        return (successes / attempts) * 100
    
    def get_method_avg_time(self, method: str) -> float:
        """Get average time for specific method."""
        successes = self.method_success.get(method, 0)
        if successes == 0:
            return 0.0
        total_time = self.method_times.get(method, 0)
        return total_time / successes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary format."""
        method_breakdown = {}
        
        all_methods = set(list(self.method_attempts.keys()) + 
                         list(self.method_success.keys()))
        
        for method in all_methods:
            attempts = self.method_attempts.get(method, 0)
            successes = self.method_success.get(method, 0)
            method_breakdown[method] = {
                "attempts": attempts,
                "successes": successes,
                "success_rate": self.get_method_success_rate(method),
                "avg_time": self.get_method_avg_time(method)
            }
        
        return {
            "success_rate": round(self.success_rate, 1),
            "total_attempts": self.total_attempts,
            "successful_extractions": self.successful_extractions,
            "avg_extraction_time": round(self.avg_extraction_time, 2),
            "total_extraction_time": round(self.total_extraction_time, 2),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "method_breakdown": method_breakdown
        }
    
    def reset(self):
        """Reset all statistics."""
        self.total_attempts = 0
        self.successful_extractions = 0
        self.method_success.clear()
        self.method_attempts.clear()
        self.method_times.clear()
        self.total_extraction_time = 0.0
        self.start_time = time.time()


class StatsTracker:
    """Helper class for tracking extraction statistics."""
    
    def __init__(self):
        """Initialize stats tracker."""
        self.stats = ExtractorStats()
    
    def track_attempt(self, method: str):
        """Track an extraction attempt."""
        self.stats.track_attempt(method)
    
    def track_success(self, method: str, extraction_time: float):
        """Track a successful extraction."""
        self.stats.track_success(method, extraction_time)
    
    def track_failure(self, extraction_time: float):
        """Track a failed extraction."""
        self.stats.track_failure(extraction_time)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return self.stats.to_dict()
    
    def get_legacy_stats(self) -> Dict[str, Any]:
        """
        Get statistics in legacy format for backward compatibility.
        
        Returns stats in the old AdvancedContentExtractor format.
        """
        stats_dict = self.stats.to_dict()
        method_breakdown = stats_dict.get("method_breakdown", {})
        
        return {
            "success_rate": stats_dict.get("success_rate", 0),
            "total_attempts": stats_dict.get("total_attempts", 0),
            "total_successes": stats_dict.get("successful_extractions", 0),
            "method_breakdown": {
                "trafilatura": method_breakdown.get("trafilatura", {}).get("successes", 0),
                "newspaper": method_breakdown.get("newspaper", {}).get("successes", 0),
                "playwright": method_breakdown.get("playwright", {}).get("successes", 0),
                "selenium": method_breakdown.get("selenium", {}).get("successes", 0),
                "failures": (stats_dict.get("total_attempts", 0) - 
                           stats_dict.get("successful_extractions", 0))
            }
        }
    
    def reset(self):
        """Reset statistics."""
        self.stats.reset()

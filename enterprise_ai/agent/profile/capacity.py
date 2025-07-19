"""
Enterprise AI Agent Profile - Capacity Management.

Provides intelligent capacity tracking, workload management, and availability
optimization for team coordination.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from enterprise_ai.schema.agent_profile import AgentCapacity, AgentStatus, AgentProfile
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.profile.capacity")


class WorkloadLevel(Enum):
    """Workload level categories for easy assessment."""
    IDLE = "idle"           # 0.0 - 0.2
    LIGHT = "light"         # 0.2 - 0.5
    MODERATE = "moderate"   # 0.5 - 0.7
    HEAVY = "heavy"         # 0.7 - 0.9
    OVERLOADED = "overloaded"  # 0.9 - 1.0


@dataclass
class CapacityMetrics:
    """Capacity analytics and metrics."""
    total_agents: int
    available_agents: int
    average_workload: float
    workload_distribution: Dict[WorkloadLevel, int]
    overloaded_agents: List[str]
    underutilized_agents: List[str]
    
    @property
    def availability_rate(self) -> float:
        """Percentage of agents available for new tasks."""
        if self.total_agents == 0:
            return 0.0
        return (self.available_agents / self.total_agents) * 100
    
    @property
    def utilization_rate(self) -> float:
        """Average team utilization percentage."""
        return self.average_workload * 100


class CapacityManager:
    """
    Manages agent capacity tracking and optimization.
    
    Provides intelligent workload monitoring, availability assessment,
    and optimization suggestions for team efficiency.
    """
    
    def __init__(self):
        """Initialize capacity manager."""
        self._capacity_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self._status_history: Dict[str, List[Tuple[datetime, AgentStatus]]] = {}
    
    def track_workload_change(self, agent_name: str, old_workload: float, new_workload: float) -> None:
        """Track workload changes for analytics."""
        if agent_name not in self._capacity_history:
            self._capacity_history[agent_name] = []
        
        self._capacity_history[agent_name].append((datetime.now(), new_workload))
        
        # Keep only recent history (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self._capacity_history[agent_name] = [
            (timestamp, workload) for timestamp, workload in self._capacity_history[agent_name]
            if timestamp > cutoff
        ]
        
        if abs(new_workload - old_workload) >= 0.2:  # Significant change
            logger.info(f"Agent {agent_name} workload changed: {old_workload:.1%} → {new_workload:.1%}")
    
    def track_status_change(self, agent_name: str, old_status: AgentStatus, new_status: AgentStatus) -> None:
        """Track status changes for analytics."""
        if agent_name not in self._status_history:
            self._status_history[agent_name] = []
        
        self._status_history[agent_name].append((datetime.now(), new_status))
        
        # Keep only recent history (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self._status_history[agent_name] = [
            (timestamp, status) for timestamp, status in self._status_history[agent_name]
            if timestamp > cutoff
        ]
        
        if old_status != new_status:
            logger.info(f"Agent {agent_name} status changed: {old_status.value} → {new_status.value}")
    
    def get_workload_level(self, workload: float) -> WorkloadLevel:
        """Categorize workload into levels."""
        if workload <= 0.2:
            return WorkloadLevel.IDLE
        elif workload <= 0.5:
            return WorkloadLevel.LIGHT
        elif workload <= 0.7:
            return WorkloadLevel.MODERATE
        elif workload <= 0.9:
            return WorkloadLevel.HEAVY
        else:
            return WorkloadLevel.OVERLOADED
    
    def assess_agent_capacity(self, profile: AgentProfile) -> Dict[str, any]:
        """Assess individual agent capacity and provide recommendations."""
        capacity = profile.capacity
        level = self.get_workload_level(capacity.workload)
        
        # Get recent workload trend
        trend = self._get_workload_trend(profile.name)
        
        # Capacity assessment
        assessment = {
            "agent": profile.name,
            "current_workload": capacity.workload,
            "workload_level": level.value,
            "availability_percentage": capacity.availability_percentage,
            "is_available": capacity.is_available,
            "is_overloaded": capacity.is_overloaded,
            "status": capacity.status.value,
            "trend": trend,
            "recommendations": []
        }
        
        # Generate recommendations
        if level == WorkloadLevel.OVERLOADED:
            assessment["recommendations"].extend([
                "Consider redistributing tasks from this agent",
                "Agent may need assistance or task prioritization",
                "Monitor for potential burnout or blocking issues"
            ])
        elif level == WorkloadLevel.IDLE:
            assessment["recommendations"].extend([
                "Agent available for new high-priority tasks",
                "Consider assigning complex or learning opportunities",
                "Good candidate for helping overloaded teammates"
            ])
        elif trend == "increasing" and level in [WorkloadLevel.MODERATE, WorkloadLevel.HEAVY]:
            assessment["recommendations"].append("Monitor workload - trending toward overload")
        
        return assessment
    
    def analyze_team_capacity(self, profiles: List[AgentProfile]) -> CapacityMetrics:
        """Analyze overall team capacity and distribution."""
        if not profiles:
            return CapacityMetrics(
                total_agents=0,
                available_agents=0,
                average_workload=0.0,
                workload_distribution={level: 0 for level in WorkloadLevel},
                overloaded_agents=[],
                underutilized_agents=[]
            )
        
        # Calculate metrics
        total_agents = len(profiles)
        available_agents = sum(1 for p in profiles if p.capacity.is_available)
        total_workload = sum(p.capacity.workload for p in profiles)
        average_workload = total_workload / total_agents
        
        # Workload distribution
        distribution = {level: 0 for level in WorkloadLevel}
        for profile in profiles:
            level = self.get_workload_level(profile.capacity.workload)
            distribution[level] += 1
        
        # Identify problem agents
        overloaded_agents = [
            p.name for p in profiles 
            if self.get_workload_level(p.capacity.workload) == WorkloadLevel.OVERLOADED
        ]
        
        underutilized_agents = [
            p.name for p in profiles 
            if self.get_workload_level(p.capacity.workload) == WorkloadLevel.IDLE
        ]
        
        return CapacityMetrics(
            total_agents=total_agents,
            available_agents=available_agents,
            average_workload=average_workload,
            workload_distribution=distribution,
            overloaded_agents=overloaded_agents,
            underutilized_agents=underutilized_agents
        )
    
    def suggest_workload_optimization(self, profiles: List[AgentProfile]) -> List[Dict[str, any]]:
        """Suggest workload optimization strategies."""
        metrics = self.analyze_team_capacity(profiles)
        suggestions = []
        
        # High-level team suggestions
        if metrics.availability_rate < 20:  # Less than 20% available
            suggestions.append({
                "type": "team_warning",
                "priority": "high",
                "message": f"Team capacity critical: only {metrics.availability_rate:.1f}% agents available",
                "action": "Consider reducing task load or adding resources"
            })
        
        if metrics.average_workload > 0.8:  # High average workload
            suggestions.append({
                "type": "team_optimization",
                "priority": "medium", 
                "message": f"Team utilization high at {metrics.utilization_rate:.1f}%",
                "action": "Monitor for burnout and consider workload redistribution"
            })
        
        # Specific redistribution suggestions based on actual tools
        overloaded = [p for p in profiles if p.capacity.workload >= 0.9]
        underutilized = [p for p in profiles if p.capacity.workload <= 0.3]
        
        if overloaded and underutilized:
            for over_agent in overloaded:
                for under_agent in underutilized:
                    # Tool compatibility check (no hardcoded skills)
                    compatible_tools = set(over_agent.available_tools) & set(under_agent.available_tools)
                    if compatible_tools:
                        suggestions.append({
                            "type": "redistribution",
                            "priority": "medium",
                            "message": f"Consider redistributing tasks from {over_agent.name} to {under_agent.name}",
                            "details": {
                                "from_agent": over_agent.name,
                                "to_agent": under_agent.name,
                                "from_workload": over_agent.capacity.workload,
                                "to_workload": under_agent.capacity.workload,
                                "compatible_tools": list(compatible_tools)[:3]  # Show first 3
                            }
                        })
        
        return suggestions
    
    def _get_workload_trend(self, agent_name: str) -> str:
        """Get workload trend for an agent (increasing, decreasing, stable)."""
        if agent_name not in self._capacity_history or len(self._capacity_history[agent_name]) < 3:
            return "stable"
        
        recent_workloads = [workload for _, workload in self._capacity_history[agent_name][-5:]]
        
        # Simple trend analysis
        if len(recent_workloads) >= 3:
            first_half = sum(recent_workloads[:len(recent_workloads)//2]) / (len(recent_workloads)//2)
            second_half = sum(recent_workloads[len(recent_workloads)//2:]) / (len(recent_workloads) - len(recent_workloads)//2)
            
            if second_half > first_half + 0.1:
                return "increasing"
            elif second_half < first_half - 0.1:
                return "decreasing"
        
        return "stable"
    
    def get_agent_availability_forecast(self, agent_name: str, hours_ahead: int = 4) -> Dict[str, any]:
        """Forecast agent availability based on trends."""
        if agent_name not in self._capacity_history:
            return {"forecast": "unknown", "confidence": "low"}
        
        trend = self._get_workload_trend(agent_name)
        recent_changes = len([
            1 for timestamp, _ in self._capacity_history[agent_name] 
            if timestamp > datetime.now() - timedelta(hours=2)
        ])
        
        forecast = {
            "trend": trend,
            "recent_activity": "high" if recent_changes >= 3 else "low",
            "confidence": "high" if recent_changes >= 2 else "medium"
        }
        
        # Simple forecast logic
        if trend == "increasing":
            forecast["forecast"] = "likely_busy"
        elif trend == "decreasing":
            forecast["forecast"] = "likely_available"
        else:
            forecast["forecast"] = "stable"
        
        return forecast

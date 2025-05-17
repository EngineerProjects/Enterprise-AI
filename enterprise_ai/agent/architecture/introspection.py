"""
Agent introspection capabilities.

This module provides mechanisms for agents to inspect and adapt
their own capabilities, configuration, and performance.
"""

import asyncio
import inspect
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, cast

from enterprise_ai.agent.architecture.errors import AgentError, AgentErrorCode, ErrorManager
from enterprise_ai.agent.architecture.utils import safe_serialize
from enterprise_ai.logger import get_logger

logger = get_logger("agent.introspection")


class IntrospectionLevel(str, Enum):
    """Levels of introspection detail."""

    MINIMAL = "minimal"  # Basic information only
    STANDARD = "standard"  # Most common information
    DETAILED = "detailed"  # Detailed information
    COMPLETE = "complete"  # All available information


class IntrospectionManagerConfig:
    """Configuration for introspection manager."""

    def __init__(
        self,
        enable_self_monitoring: bool = True,
        enable_dynamic_adaptation: bool = False,
        performance_tracking_interval: float = 60.0,
        default_introspection_level: IntrospectionLevel = IntrospectionLevel.STANDARD,
        expose_internal_structure: bool = False,
    ):
        """Initialize introspection manager configuration.

        Args:
            enable_self_monitoring: Whether to enable self-monitoring
            enable_dynamic_adaptation: Whether to enable dynamic adaptation
            performance_tracking_interval: Interval for performance tracking in seconds
            default_introspection_level: Default level of introspection detail
            expose_internal_structure: Whether to expose internal structure
        """
        self.enable_self_monitoring = enable_self_monitoring
        self.enable_dynamic_adaptation = enable_dynamic_adaptation
        self.performance_tracking_interval = performance_tracking_interval
        self.default_introspection_level = default_introspection_level
        self.expose_internal_structure = expose_internal_structure


class IntrospectionManager:
    """Manager for agent introspection capabilities."""

    def __init__(self, agent: Any, config: Optional[IntrospectionManagerConfig] = None):
        """Initialize the introspection manager.

        Args:
            agent: The agent instance
            config: Optional introspection manager configuration
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", "unknown")
        self.config = config or IntrospectionManagerConfig()
        self._error_manager = ErrorManager(self.agent_id)
        self._performance_metrics: Dict[str, Any] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._start_time = datetime.now()

        logger.info(f"Initialized introspection manager for agent {self.agent_id}")

        # Start self-monitoring if enabled
        if self.config.enable_self_monitoring:
            self.start_monitoring()

    def start_monitoring(self) -> bool:
        """Start performance monitoring.

        Returns:
            True if monitoring was started, False if already running
        """
        if self._monitoring_task is not None and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return False

        # Create monitoring task
        loop = asyncio.get_event_loop()
        self._monitoring_task = loop.create_task(self._monitor_performance())

        logger.info("Started performance monitoring")
        return True

    def stop_monitoring(self) -> bool:
        """Stop performance monitoring.

        Returns:
            True if monitoring was stopped, False if not running
        """
        if self._monitoring_task is None or self._monitoring_task.done():
            logger.warning("Monitoring not running")
            return False

        # Cancel monitoring task
        self._monitoring_task.cancel()

        logger.info("Stopped performance monitoring")
        return True

    async def _monitor_performance(self) -> None:
        """Monitor agent performance periodically."""
        try:
            while True:
                # Collect performance metrics
                self._performance_metrics = self._collect_performance_metrics()

                # Check for adaptation if enabled
                if self.config.enable_dynamic_adaptation:
                    self._adapt_to_performance()

                # Sleep until next collection
                await asyncio.sleep(self.config.performance_tracking_interval)
        except asyncio.CancelledError:
            # Monitoring was cancelled
            logger.info("Performance monitoring cancelled")
        except Exception as e:
            # Handle unexpected error
            error = self._error_manager.handle_error(e, error_code=AgentErrorCode.EXECUTION_FAILED)
            logger.error(f"Error in performance monitoring: {e}")

    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics from all components.

        Returns:
            Dictionary of performance metrics
        """
        metrics: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
        }

        # Collect metrics from each component
        components = [
            ("lifecycle", "_lifecycle"),
            ("tools", "_tools"),
            ("reasoning", "_reasoning"),
            ("conversation", "_conversation"),
            ("execution", "_execution"),
        ]

        for name, attr in components:
            if hasattr(self.agent, attr):
                component = getattr(self.agent, attr)

                # Try to get metrics from the component
                if hasattr(component, "get_metrics"):
                    try:
                        component_metrics = component.get_metrics()
                        metrics[name] = component_metrics
                    except Exception as e:
                        logger.warning(f"Error getting metrics from {name}: {e}")
                elif hasattr(component, "get_status"):
                    try:
                        component_status = component.get_status()
                        metrics[name] = component_status
                    except Exception as e:
                        logger.warning(f"Error getting status from {name}: {e}")

        # Get LLM provider metrics if available
        if hasattr(self.agent, "_llm_provider"):
            llm_provider = getattr(self.agent, "_llm_provider")
            if hasattr(llm_provider, "get_metrics"):
                try:
                    llm_metrics = llm_provider.get_metrics()
                    metrics["llm"] = llm_metrics
                except Exception as e:
                    logger.warning(f"Error getting metrics from LLM provider: {e}")

        return metrics

    def _adapt_to_performance(self) -> None:
        """Dynamically adapt agent configuration based on performance metrics."""
        # This is a placeholder for dynamic adaptation logic
        # In a real implementation, this would adjust agent configuration
        # based on performance metrics
        pass

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics.

        Returns:
            Dictionary of performance metrics
        """
        # If monitoring is enabled, return the latest metrics
        if self.config.enable_self_monitoring:
            return self._performance_metrics

        # Otherwise, collect metrics on-demand
        return self._collect_performance_metrics()

    def get_agent_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities.

        Returns:
            Dictionary of agent capabilities
        """
        capabilities: Dict[str, Any] = {}

        # Get tool capabilities
        if hasattr(self.agent, "_tools"):
            tools = getattr(self.agent, "_tools")
            if hasattr(tools, "capabilities"):
                capabilities["tools"] = list(tools.capabilities)

            # Get available tools
            if hasattr(tools, "list_tools"):
                capabilities["available_tools"] = tools.list_tools()

        # Get reasoning capabilities
        if hasattr(self.agent, "_reasoning"):
            reasoning = getattr(self.agent, "_reasoning")
            if hasattr(reasoning, "list_frameworks"):
                capabilities["reasoning_frameworks"] = reasoning.list_frameworks()

        return capabilities

    def get_component_info(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent component.

        Args:
            component_name: Name of the component

        Returns:
            Dictionary of component information or None if not found
        """
        # Map component names to attributes
        component_map = {
            "lifecycle": "_lifecycle",
            "tools": "_tools",
            "reasoning": "_reasoning",
            "conversation": "_conversation",
            "execution": "_execution",
            "introspection": "_introspection",
            "llm": "_llm_provider",
        }

        if component_name not in component_map:
            return None

        attr_name = component_map[component_name]

        if not hasattr(self.agent, attr_name):
            return None

        component = getattr(self.agent, attr_name)

        # Get component information
        info = {
            "type": type(component).__name__,
        }

        # Check for various informational methods
        if hasattr(component, "get_status"):
            try:
                info["status"] = component.get_status()
            except Exception as e:
                info["status_error"] = str(e)

        if hasattr(component, "get_metrics"):
            try:
                info["metrics"] = component.get_metrics()
            except Exception as e:
                info["metrics_error"] = str(e)

        # Only include internal structure if configured to expose it
        if self.config.expose_internal_structure:
            if hasattr(component, "__dict__"):
                info["attributes"] = {
                    k: safe_serialize(v)
                    for k, v in component.__dict__.items()
                    if not k.startswith("_")
                }

            if hasattr(component, "get_config"):
                try:
                    info["config"] = component.get_config()
                except Exception as e:
                    info["config_error"] = str(e)

        return info

    def get_agent_info(self, level: Optional[IntrospectionLevel] = None) -> Dict[str, Any]:
        """Get comprehensive agent information.

        Args:
            level: Level of introspection detail

        Returns:
            Dictionary of agent information
        """
        # Use specified level or default
        introspection_level = level or self.config.default_introspection_level

        # Base information
        info = {
            "agent_id": self.agent_id,
            "type": type(self.agent).__name__,
            "timestamp": datetime.now().isoformat(),
        }

        # Include capabilities at all levels
        info["capabilities"] = self.get_agent_capabilities()

        # Add components information based on level
        if introspection_level != IntrospectionLevel.MINIMAL:
            components = {}

            for component_name in ["lifecycle", "tools", "reasoning", "conversation", "execution"]:
                component_info = self.get_component_info(component_name)
                if component_info:
                    components[component_name] = component_info

            info["components"] = components

        # Add performance metrics for detailed levels
        if introspection_level in [IntrospectionLevel.DETAILED, IntrospectionLevel.COMPLETE]:
            info["performance"] = self.get_performance_metrics()

        # Add internal structure for complete level
        if (
            introspection_level == IntrospectionLevel.COMPLETE
            and self.config.expose_internal_structure
        ):
            if hasattr(self.agent, "__dict__"):
                info["attributes"] = {
                    k: safe_serialize(v)
                    for k, v in self.agent.__dict__.items()
                    if not k.startswith("_")
                }

            # Include public methods
            methods = {}
            for name, method in inspect.getmembers(self.agent, inspect.ismethod):
                if not name.startswith("_"):
                    methods[name] = str(inspect.signature(method))

            info["methods"] = methods

        return info

    def check_component_health(self, component_name: str) -> Dict[str, Any]:
        """Check the health of a specific component.

        Args:
            component_name: Name of the component

        Returns:
            Dictionary with health status information
        """
        # Get component info
        component_info = self.get_component_info(component_name)

        if not component_info:
            return {
                "name": component_name,
                "status": "not_found",
                "healthy": False,
                "message": f"Component {component_name} not found",
            }

        # Check health based on component type
        health_result = {
            "name": component_name,
            "type": component_info.get("type", "unknown"),
        }

        # Add health check logic here based on component type
        # This is a simplified implementation
        if "status" in component_info:
            health_result["status"] = component_info["status"]

        if "metrics" in component_info:
            # Check for error indicators in metrics
            metrics = component_info["metrics"]
            errors = 0
            total = 0

            # Look for error counts in metrics
            for key, value in metrics.items():
                if "error" in key.lower() and isinstance(value, (int, float)):
                    errors += value
                if "total" in key.lower() and isinstance(value, (int, float)):
                    total += value

            # Determine health based on error ratio
            if total > 0:
                error_ratio = errors / total

                if error_ratio > 0.5:
                    health_result["healthy"] = False
                    health_result["message"] = f"High error ratio: {error_ratio:.2f}"
                elif error_ratio > 0.1:
                    health_result["healthy"] = True
                    health_result["warning"] = f"Elevated error ratio: {error_ratio:.2f}"
                else:
                    health_result["healthy"] = True
                    health_result["message"] = "Component appears healthy"
            else:
                health_result["healthy"] = True
                health_result["message"] = "No activity data available"
        else:
            # Default to healthy if no metrics
            health_result["healthy"] = True
            health_result["message"] = "No health metrics available"

        return health_result

    def check_system_health(self) -> Dict[str, Any]:
        """Check the health of all components.

        Returns:
            Dictionary with system health information
        """
        components = ["lifecycle", "tools", "reasoning", "conversation", "execution"]
        component_health = {
            component: self.check_component_health(component) for component in components
        }

        # Determine overall health
        unhealthy_components = [
            name for name, health in component_health.items() if health.get("healthy") is False
        ]

        warning_components = [
            name for name, health in component_health.items() if "warning" in health
        ]

        if unhealthy_components:
            overall_status = "unhealthy"
            overall_message = f"Unhealthy components: {', '.join(unhealthy_components)}"
        elif warning_components:
            overall_status = "warning"
            overall_message = f"Components with warnings: {', '.join(warning_components)}"
        else:
            overall_status = "healthy"
            overall_message = "All components are healthy"

        return {
            "timestamp": datetime.now().isoformat(),
            "status": overall_status,
            "message": overall_message,
            "components": component_health,
        }

    def diagnose_issue(self, issue_description: str) -> Dict[str, Any]:
        """Diagnose an issue based on a description.

        Args:
            issue_description: Description of the issue

        Returns:
            Dictionary with diagnostic information
        """
        # This is a simplified implementation
        # In a real implementation, this would use more sophisticated diagnostics

        # Get system health
        health = self.check_system_health()

        # Look for key terms in the issue description
        issue_terms = issue_description.lower().split()

        # Map terms to components
        component_terms = {
            "lifecycle": ["start", "init", "create", "terminate", "cleanup"],
            "tools": ["tool", "function", "execute", "action"],
            "reasoning": ["think", "reason", "framework", "process"],
            "conversation": ["message", "chat", "talk", "response"],
            "execution": ["run", "execute", "job", "task"],
        }

        # Count term occurrences
        component_matches = {component: 0 for component in component_terms}

        for term in issue_terms:
            for component, terms in component_terms.items():
                if term in terms:
                    component_matches[component] += 1

        # Find the most mentioned component
        most_mentioned = max(component_matches.items(), key=lambda x: x[1])

        if most_mentioned[1] == 0:
            # No clear component match
            primary_component = None
        else:
            primary_component = most_mentioned[0]

        # Generate diagnostic information
        diagnosis = {
            "issue_description": issue_description,
            "timestamp": datetime.now().isoformat(),
        }

        if primary_component:
            # Get health for the primary component
            component_health = health["components"].get(primary_component, {})

            diagnosis["primary_component"] = primary_component
            diagnosis["component_health"] = component_health

            # Suggest actions based on component health
            if component_health.get("healthy") is False:
                diagnosis["diagnosis"] = (
                    f"Issue appears to be related to the {primary_component} component, which is currently unhealthy."
                )
                diagnosis["suggested_actions"] = [
                    f"Restart the {primary_component} component",
                    "Check logs for errors",
                    f"Check configuration for the {primary_component} component",
                ]
            else:
                diagnosis["diagnosis"] = (
                    f"Issue appears to be related to the {primary_component} component, but the component seems healthy."
                )
                diagnosis["suggested_actions"] = [
                    "Check input parameters",
                    "Verify expected behavior",
                    "Check logs for warnings",
                ]
        else:
            # No clear component match
            diagnosis["diagnosis"] = (
                "Issue description does not clearly match any specific component."
            )
            diagnosis["suggested_actions"] = [
                "Provide more detailed information about the issue",
                "Check logs for errors",
                "Check overall system health",
            ]

        # Add system health
        diagnosis["system_health"] = health

        return diagnosis

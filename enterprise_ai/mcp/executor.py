"""
Simplified MCP Executor - Tool execution focused.

Leverages existing tool infrastructure for clean, simple tool execution.
"""

import asyncio
import inspect
import json
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import ToolCall
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.simple_loader import get_all_tools, get_tool_by_name
from enterprise_ai.tool.discovery import get_tool_discovery, DiscoveryResult
from enterprise_ai.tool.core.base import ToolCapability, ExecutionMode
from enterprise_ai.mcp.sandbox_config import SandboxConfig, DEFAULT_SANDBOX_CONFIG
from enterprise_ai.mcp.enhanced_sandbox import EnhancedSandboxConfig, create_local_config
from enterprise_ai.mcp.sandbox_executor import SimpleMCPExecutor, SandboxToolExecutor

logger = get_optimized_logger("new_mcp.executor")


class ToolMCP:
    """
    Simplified MCP for Enterprise AI - Tool execution only.
    
    Leverages existing ToolRegistry and focuses purely on executing tools
    and returning clean, structured results.
    """

    def __init__(
        self, 
        timeout: float = 30.0, 
        sandbox_config: Optional[Union[SandboxConfig, EnhancedSandboxConfig]] = None, 
        tools: Optional[List[str]] = None
    ):
        """
        Initialize ToolMCP with enhanced sandbox configuration and smart logging.
        
        Args:
            timeout: Default timeout for tool execution
            sandbox_config: Sandbox configuration (legacy SandboxConfig or new EnhancedSandboxConfig)
            tools: Specific list of tools to load (loads all if None)
        """
        self.timeout = timeout
        self._execution_count = 0
        self._failed_count = 0
        
        # Handle both old and new sandbox configurations
        if isinstance(sandbox_config, EnhancedSandboxConfig):
            self.enhanced_sandbox_config = sandbox_config
            # Convert to old format for backward compatibility
            if sandbox_config.enabled:
                # Determine which tools should be sandboxed
                # We'll set this after loading tools
                self.sandbox_config = SandboxConfig(enabled=True)
            else:
                self.sandbox_config = DEFAULT_SANDBOX_CONFIG
        else:
            # Legacy configuration or None
            self.sandbox_config = sandbox_config or DEFAULT_SANDBOX_CONFIG
            self.enhanced_sandbox_config = create_local_config()  # Default to local
        
        # Initialize tool executor
        self.tool_executor = SimpleMCPExecutor(
            tools={},
            execution_timeout=timeout,
            verbose=False
        )
        
        # Load tools first so we can determine sandbox routing
        if tools:
            self._tools = self._load_specific_tools(tools)
        else:
            self._tools = self._load_all_tools()
        
        # Configure sandboxed tools based on enhanced config
        if isinstance(sandbox_config, EnhancedSandboxConfig) and sandbox_config.enabled:
            available_tools = set(self._tools.keys())
            sandboxed_tools = sandbox_config.get_sandboxed_tools(available_tools)
            
            # Update sandbox config with determined tools
            self.sandbox_config.dangerous_tools = sandboxed_tools
            
            logger.info(f"Enhanced sandbox enabled: {len(sandboxed_tools)} tools will run in sandbox")
            logger.info(f"Sandbox summary: {sandbox_config.get_summary()}")
        
        # Initialize sandbox executor if enabled
        self.sandbox_executor = None
        if self.sandbox_config.enabled:
            self.sandbox_executor = SandboxToolExecutor(
                tools={},
                execution_timeout=timeout,
                default_sandbox_mode=self.sandbox_config.default_mode,
                enable_sandbox_routing=True,
                verbose=False
            )
            
        logger.info(f"🔧 ToolMCP initialized with {len(self._tools)} tools")
        if self.enhanced_sandbox_config.enabled:
            logger.info(f"Sandbox configuration: {self.enhanced_sandbox_config.get_summary()}")
        else:
            logger.info("Sandbox: Disabled (all tools run locally)")
            
        # Start logging session (simplified)
        self.session_id = f"mcp_{int(time.time())}"

    def _load_all_tools(self) -> Dict[str, Callable]:
        """Load all available tools using enhanced discovery system with deduplication."""
        tools = {}
        
        try:
            # STEP 1: Load from simple_loader first (authoritative names)
            logger.info("Loading tools from simple_loader (authoritative names)...")
            simple_tools = get_all_tools()
            loaded_classes = set()  # Track which classes we've already loaded
            
            for tool_name, tool_class in simple_tools.items():
                try:
                    tool_instance = tool_class()
                    if hasattr(tool_instance, 'execute'):
                        tools[tool_name] = tool_instance.execute
                        loaded_classes.add(tool_class)  # Remember this class
                        logger.debug(f"Loaded authoritative tool: {tool_name}")
                except Exception as e:
                    logger.warning(f"Failed to load simple_loader tool {tool_name}: {e}")
            
            logger.info(f"Loaded {len(tools)} tools from simple_loader")
            
            # STEP 2: Use enhanced discovery for additional tools (not already loaded)
            logger.info("Discovering additional tools via enhanced discovery...")
            discovery = get_tool_discovery()
            discovery_result = discovery.discover_all_tools()
            
            if discovery_result.errors:
                logger.warning(f"Tool discovery had {len(discovery_result.errors)} errors")
                for error in discovery_result.errors[:3]:  # Log first 3 errors
                    logger.warning(f"Discovery error: {error}")
            
            additional_tools_count = 0
            
            # Add tools from discovery that we don't already have
            for tool_name, tool_def in discovery_result.tools.items():
                try:
                    # Import and check the tool class
                    module_parts = tool_def.class_path.rsplit('.', 1)
                    if len(module_parts) == 2:
                        module_name, class_name = module_parts
                        module = __import__(module_name, fromlist=[class_name])
                        tool_class = getattr(module, class_name)
                        
                        # Skip if we already have this class loaded (prevents duplicates)
                        if tool_class in loaded_classes:
                            logger.debug(f"Skipping duplicate class {tool_class.__name__} (already loaded)")
                            continue
                        
                        # Skip if we already have a tool with this name
                        if tool_name in tools:
                            logger.debug(f"Skipping duplicate name {tool_name}")
                            continue
                        
                        # Add this new tool
                        tool_instance = tool_class()
                        if hasattr(tool_instance, 'execute'):
                            tools[tool_name] = tool_instance.execute
                            loaded_classes.add(tool_class)
                            additional_tools_count += 1
                            logger.debug(f"Loaded additional tool: {tool_name}")
                        else:
                            logger.warning(f"Discovery tool {tool_name} has no execute method")
                            
                except Exception as e:
                    logger.warning(f"Failed to instantiate discovered tool {tool_name}: {e}")
            
            logger.info(f"Added {additional_tools_count} additional tools from discovery")
            logger.info(f"Total unique tools loaded: {len(tools)}")
            
        except Exception as e:
            logger.error(f"Enhanced tool loading failed: {e}")
            
            # FALLBACK: Use only simple_loader if enhanced discovery fails
            logger.info("Using fallback: simple_loader only")
            try:
                simple_tools = get_all_tools()
                for tool_name, tool_class in simple_tools.items():
                    try:
                        tool_instance = tool_class()
                        if hasattr(tool_instance, 'execute'):
                            tools[tool_name] = tool_instance.execute
                            logger.debug(f"Loaded fallback tool: {tool_name}")
                    except Exception as e:
                        logger.warning(f"Failed to load fallback tool {tool_name}: {e}")
            except Exception as e:
                logger.error(f"Even fallback tool loading failed: {e}")
        
        return tools
    
    def _load_specific_tools(self, tool_names: List[str]) -> Dict[str, Callable]:
        """Load specific tools using selective loader to avoid unnecessary imports."""
        from enterprise_ai.tool.simple_loader import get_specific_tools
        
        tools = {}
        
        # Use selective loading to avoid importing unwanted tools
        tool_classes = get_specific_tools(tool_names)
        
        for tool_name, tool_class in tool_classes.items():
            try:
                tool_instance = tool_class()
                if hasattr(tool_instance, 'execute'):
                    tools[tool_name] = tool_instance.execute
                    logger.debug(f"Loaded specific tool: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to load tool {tool_name}: {e}")
        
        logger.info(f"Loaded {len(tools)} specific tools")
        return tools

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function directly."""
        self._tools[name] = func
        self.tool_executor.register_tool(name, func)
        
        # Also register with sandbox executor if enabled
        if self.sandbox_executor:
            self.sandbox_executor.register_tool(name, func)
        
        logger.info("Registered tool: %s", name)

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())

    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute a list of tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool execution results
        """
        if not tool_calls:
            return []

        results = []
        self._execution_count += len(tool_calls)
        
        # Update tool executors with current tools
        self.tool_executor.tools = self._tools
        if self.sandbox_executor:
            self.sandbox_executor.tools = self._tools
        
        try:
            # Determine if we should use sandbox based on config and tool types
            if self.sandbox_executor and self.sandbox_config.enabled:
                # Check if any tools are in the dangerous list
                dangerous_tools = [
                    tc for tc in tool_calls 
                    if tc.function.name in self.sandbox_config.dangerous_tools
                ]
                
                # Split tool calls between dangerous and safe
                safe_tools = [tc for tc in tool_calls if tc not in dangerous_tools]
                
                # Process dangerous tools with sandbox
                if dangerous_tools:
                    sandbox_results = await self.sandbox_executor.aexecute_tool_calls(dangerous_tools)
                    results.extend(sandbox_results)
                
                # Process safe tools directly
                if safe_tools:
                    safe_results = await self.tool_executor.aexecute_tool_calls(safe_tools)
                    results.extend(safe_results)
            else:
                # Process all tools directly
                results = await self.tool_executor.aexecute_tool_calls(tool_calls)
                
            # Track failures
            self._failed_count += sum(1 for r in results if not r.success)
            
            return results
        except Exception as e:
            self._failed_count += len(tool_calls)
            # Create error results for all tool calls
            for tool_call in tool_calls:
                results.append(
                    ToolResult(
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                        result="",
                        success=False,
                        error=f"MCP execution error: {str(e)}"
                    )
                )
            return results

    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with error handling."""
        # This method is deprecated but kept for backward compatibility
        # It now delegates to the tool executor
        if self.sandbox_executor and self.sandbox_config.enabled and tool_call.function.name in self.sandbox_config.dangerous_tools:
            results = await self.sandbox_executor.aexecute_tool_calls([tool_call])
        else:
            results = await self.tool_executor.aexecute_tool_calls([tool_call])
            
        return results[0] if results else ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.function.name,
            result="",
            success=False,
            error="No result returned from tool executor"
        )

    async def _execute_directly(self, tool_call: ToolCall, tool_func: Callable, args: Dict[str, Any], start_time: float) -> ToolResult:
        """Execute tool directly."""
        try:
            if inspect.iscoroutinefunction(tool_func):
                result = await asyncio.wait_for(
                    tool_func(**args), 
                    timeout=self.timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_func(**args)),
                    timeout=self.timeout
                )
            
            execution_time = time.time() - start_time
            
            return self._create_success_result(
                tool_call.id, tool_call.function.name, result, execution_time
            )
            
        except asyncio.TimeoutError:
            self._failed_count += 1
            return self._create_error_result(
                tool_call.id, tool_call.function.name, f"Tool execution timed out after {self.timeout}s"
            )

    async def _execute_in_sandbox(self, tool_call: ToolCall, tool_func: Callable, args: Dict[str, Any], start_time: float) -> ToolResult:
        """Execute tool in sandbox (placeholder for now)."""
        # For now, just execute directly with a note
        # You can integrate actual sandbox execution here later
        logger.info("Tool %s marked for sandbox execution", tool_call.function.name)
        
        result = await self._execute_directly(tool_call, tool_func, args, start_time)
        
        # Add sandbox metadata
        if result.metadata is None:
            result.metadata = {}
        result.metadata["sandbox_intended"] = True
        result.metadata["sandbox_available"] = False  # Change when you integrate actual sandbox
        
        return result

    def _create_success_result(
        self, tool_call_id: str, name: str, result: Any, execution_time: float
    ) -> ToolResult:
        """Create a success ToolResult."""
        # Clean up the result for safe serialization
        cleaned_result = self._clean_result(result)
        
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            result=cleaned_result,
            success=True,
            error=None,
            execution_time=execution_time,
            metadata={}
        )

    def _create_error_result(
        self, tool_call_id: str, name: str, error: str, execution_time: Optional[float] = None
    ) -> ToolResult:
        """Create an error ToolResult."""
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            result="",
            success=False,
            error=error,
            execution_time=execution_time,
            metadata={}
        )

    def _clean_result(self, result: Any) -> Any:
        """Clean result for safe serialization."""
        try:
            if isinstance(result, (str, int, float, bool, list, dict)):
                return result
            else:
                return str(result)
        except Exception:
            return "Result could not be serialized"

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        stats = {
            "total_executions": self._execution_count,
            "successful_executions": self._execution_count - self._failed_count,
            "failed_executions": self._failed_count,
            "success_rate": (self._execution_count - self._failed_count) / max(1, self._execution_count),
            "available_tools": len(self._tools),
            "tool_names": list(self._tools.keys())
        }
        
        # Add executor stats if available
        if hasattr(self.tool_executor, 'get_execution_stats'):
            stats["executor_stats"] = self.tool_executor.get_execution_stats()
            
        # Add sandbox stats if available
        if self.sandbox_executor and hasattr(self.sandbox_executor, 'get_execution_stats'):
            stats["sandbox_stats"] = self.sandbox_executor.get_execution_stats()
            
        return stats

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get comprehensive tool definitions using enhanced discovery system with deduplication.
        
        Returns:
            List of tool definitions in the format expected by LLM providers
        """
        try:
            # FIXED: Only get tool classes for tools that are actually loaded
            # This prevents unnecessary loading of research tools when only python_execute is needed
            
            logger.debug("Getting tool definitions from simple_loader (authoritative)")
            from enterprise_ai.tool.simple_loader import get_specific_tools
            
            # Get only the tools that are actually available/loaded
            available_tool_names = list(self.get_available_tools())
            if not available_tool_names:
                logger.warning("No tools available for definition generation")
                return []
            
            # FIXED: Use selective loading for tool definitions
            simple_tools = get_specific_tools(available_tool_names)
            loaded_classes = set()
            definitions = []
            
            # Create definitions for loaded tools only
            for tool_name, tool_class in simple_tools.items():
                try:
                    tool_instance = tool_class()
                    loaded_classes.add(tool_class)
                    
                    # Get description (prefer short_description)
                    description = getattr(tool_instance, 'short_description', None)
                    if not description:
                        description = getattr(tool_instance, 'description', f"Tool: {tool_name}")
                        if isinstance(description, str) and '\n' in description:
                            description = description.split('\n')[0]  # First line only
                    
                    # Get parameters
                    parameters = getattr(tool_instance, 'parameters', {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                    
                    # Create tool definition
                    definition = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": description,
                            "parameters": parameters
                        }
                    }
                    definitions.append(definition)
                    logger.debug(f"Added authoritative definition: {tool_name}")
                    
                except Exception as e:
                    logger.error(f"Error creating authoritative definition for {tool_name}: {e}")
            
            # STEP 2: Add additional tools from discovery (avoiding duplicates)
            # FIXED: Skip discovery if we only have specific tools to avoid unnecessary imports
            if len(available_tool_names) == len(simple_tools):
                # We have all requested tools from simple_loader, skip discovery
                logger.debug("Skipping discovery - all requested tools loaded from simple_loader")
                additional_count = 0
            else:
                logger.debug("Adding additional tool definitions from discovery")
                discovery = get_tool_discovery()
                discovery_definitions = discovery.get_tool_definitions_for_llm()
                
                additional_count = 0
                for defn in discovery_definitions:
                    tool_name = defn["function"]["name"]
                    
                    # Skip if we already have this tool name
                    if any(d["function"]["name"] == tool_name for d in definitions):
                        logger.debug(f"Skipping duplicate definition name: {tool_name}")
                        continue
                    
                    # Skip if this tool isn't actually loaded in our MCP
                    if tool_name not in available_tool_names:
                        logger.debug(f"Skipping unloaded tool definition: {tool_name}")
                        continue
                    
                    # Check if we can determine the class and if it's already covered
                    try:
                        # Try to find the tool definition to get its class
                        tool_def = discovery.get_tool_by_name(tool_name)
                        if tool_def:
                            module_parts = tool_def.class_path.rsplit('.', 1)
                            if len(module_parts) == 2:
                                module_name, class_name = module_parts
                                module = __import__(module_name, fromlist=[class_name])
                                tool_class = getattr(module, class_name)
                                
                                # Skip if we already have this class
                                if tool_class in loaded_classes:
                                    logger.debug(f"Skipping duplicate class in definitions: {tool_class.__name__}")
                                    continue
                                
                                loaded_classes.add(tool_class)
                    
                    except Exception:
                        # If we can't determine the class, just check by name
                        pass
                    
                    # Add this additional definition
                    definitions.append(defn)
                    additional_count += 1
                    logger.debug(f"Added additional definition: {tool_name}")
            
            logger.info(
                f"Generated {len(definitions)} unique tool definitions "
                f"({len(definitions) - additional_count} authoritative + {additional_count} additional)"
            )
            
            return definitions
            
        except Exception as e:
            logger.error(f"Enhanced tool definition generation failed: {e}")
            
            # FALLBACK: Use the original method
            logger.info("Using fallback tool definition generation")
            definitions = []
            
            # Get available tool classes for introspection
            try:
                tool_classes = get_all_tools()
            except Exception as e:
                logger.error(f"Failed to get tool classes: {e}")
                return definitions
            
            # Build definitions for each available tool
            for tool_name in self.get_available_tools():
                try:
                    # Find the tool class by name
                    tool_class = None
                    for class_name, cls in tool_classes.items():
                        if class_name == tool_name:
                            tool_class = cls
                            break
                    
                    if tool_class:
                        # Create instance for introspection
                        tool_instance = tool_class()
                        
                        # Get description (prefer short_description)
                        description = getattr(tool_instance, 'short_description', None)
                        if not description:
                            description = getattr(tool_instance, 'description', f"Tool: {tool_name}")
                            if isinstance(description, str) and '\n' in description:
                                description = description.split('\n')[0]  # First line only
                        
                        # Get parameters
                        parameters = getattr(tool_instance, 'parameters', {
                            "type": "object",
                            "properties": {},
                            "required": []
                        })
                        
                        # Create tool definition
                        definition = {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": description,
                                "parameters": parameters
                            }
                        }
                        
                        definitions.append(definition)
                    else:
                        logger.warning(f"Could not find tool class for {tool_name}")
                        
                except Exception as e:
                    logger.error(f"Error creating fallback definition for tool {tool_name}: {e}")
            
            return definitions

    def get_sandbox_info(self) -> Dict[str, Any]:
        """
        Get comprehensive sandbox information.
        
        Returns:
            Dictionary with sandbox configuration and status
        """
        info = {
            "sandbox_enabled": self.enhanced_sandbox_config.enabled,
            "sandbox_summary": self.enhanced_sandbox_config.get_summary(),
        }
        
        if self.enhanced_sandbox_config.enabled:
            available_tools = set(self._tools.keys())
            sandboxed_tools = self.enhanced_sandbox_config.get_sandboxed_tools(available_tools)
            local_tools = available_tools - sandboxed_tools
            
            info.update({
                "docker_image": self.enhanced_sandbox_config.docker_image,
                "tool_groups": self.enhanced_sandbox_config.tool_groups,
                "sandboxed_tools": sorted(list(sandboxed_tools)),
                "local_tools": sorted(list(local_tools)),
                "sandboxed_count": len(sandboxed_tools),
                "local_count": len(local_tools),
                "memory_limit": self.enhanced_sandbox_config.memory_limit,
                "cpu_limit": self.enhanced_sandbox_config.cpu_limit,
                "timeout": self.enhanced_sandbox_config.timeout,
                "network_enabled": self.enhanced_sandbox_config.network_enabled,
                "sandbox_executor_available": self.sandbox_executor is not None,
            })
        else:
            info.update({
                "docker_image": None,
                "tool_groups": None,
                "sandboxed_tools": [],
                "local_tools": sorted(list(self._tools.keys())),
                "sandboxed_count": 0,
                "local_count": len(self._tools),
                "sandbox_executor_available": False,
            })
        
        return info
    
    def print_sandbox_status(self) -> None:
        """Print a user-friendly sandbox status report."""
        info = self.get_sandbox_info()
        
        print("🔧 Enterprise-AI MCP Sandbox Status")
        print("=" * 50)
        print(f"📊 {info['sandbox_summary']}")
        print(f"🛠️  Total Tools: {len(self._tools)}")
        
        if info["sandbox_enabled"]:
            print(f"🐳 Sandboxed Tools ({info['sandboxed_count']}):")
            for tool in info["sandboxed_tools"]:
                print(f"   • {tool}")
            
            if info["local_tools"]:
                print(f"🏠 Local Tools ({info['local_count']}):")
                for tool in info["local_tools"][:5]:  # Show first 5
                    print(f"   • {tool}")
                if len(info["local_tools"]) > 5:
                    print(f"   ... and {len(info['local_tools']) - 5} more")
        else:
            print(f"🏠 All tools run locally (no sandbox)")
        
        print("=" * 50)
    
    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._failed_count = 0
    
    def get_session_intelligence(self) -> Dict[str, Any]:
        """
        Get intelligent session summary with actionable insights.
        
        This replaces raw logs with meaningful analysis and recommendations.
        """
        if not self.session_id:
            return {"error": "No active session"}
        
        # Get session summary (simplified)
        summary = {
            "session_id": self.session_id,
            "total_executions": self._execution_count,
            "failed_executions": self._failed_count,
            "success_rate": (self._execution_count - self._failed_count) / max(1, self._execution_count)
        }
        
        # Add MCP-specific intelligence
        intelligence = {
            "session_overview": summary,
            "source_citations": [],  # Simplified: no source tracking
            "research_quality": {"simplified": True},
            "efficiency_metrics": self._calculate_efficiency_metrics(summary),
            "sandbox_usage": self._analyze_sandbox_usage(summary),
            "recommendations": self._generate_recommendations(summary)
        }
        
        return intelligence
    
    def export_research_report(self, query: str = "MCP Session") -> str:
        """
        Export a complete research report with proper source citations.
        
        Perfect for compliance, auditing, and research documentation.
        """
        if not self.session_id:
            return json.dumps({"error": "No active session"})
        
        # Get research provenance (simplified)
        provenance = {"simplified": True, "query": query}
        
        # Format as a clean report
        report = {
            "research_session": {
                "query": query,
                "session_id": self.session_id,
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "executive_summary": {
                "sources_consulted": provenance.get("total_sources_consulted", 0),
                "high_quality_sources": len(provenance.get("high_quality_sources", [])),
                "tools_used": len(provenance.get("research_tools_used", [])),
                "total_research_time": f"{provenance.get('total_research_time', 0):.1f} seconds"
            },
            "source_analysis": {
                "citations": provenance.get("citations", []),
                "source_domains": provenance.get("source_domains", {}),
                "quality_distribution": self._analyze_source_quality(provenance.get("high_quality_sources", []))
            },
            "session_metrics": {
                "session_id": self.session_id,
                "total_executions": self._execution_count,
                "failed_executions": self._failed_count,
                "success_rate": (self._execution_count - self._failed_count) / max(1, self._execution_count)
            },
            "intelligence_summary": self.get_session_intelligence()
        }
        
        return json.dumps(report, indent=2, default=str)
    
    def print_session_summary(self) -> None:
        """Print a user-friendly session summary to console."""
        
        if not self.session_id:
            print("❌ No active MCP session")
            return
            
        # Get session summary (simplified)
        summary = {
            "session_id": self.session_id,
            "total_executions": self._execution_count,
            "failed_executions": self._failed_count,
            "success_rate": (self._execution_count - self._failed_count) / max(1, self._execution_count),
            "duration_minutes": 0,  # Simplified
            "total_execution_time": 0,  # Simplified
            "unique_sources": 0  # Simplified
        }
        
        print("🔧 Enterprise-AI MCP Session Summary")
        print("=" * 50)
        print(f"📊 Session: {summary.get('session_id', 'unknown')}")
        print(f"⏱️  Duration: {summary.get('duration_minutes', 0):.1f} minutes")
        print(f"🛠️  Tools Used: {len(summary.get('tools_used', {}))}")
        print(f"✅ Success Rate: {summary.get('success_rate', 0):.1%}")
        print(f"📄 Unique Sources: {summary.get('unique_sources', 0)}")
        
        # Show sources used (simplified - no source tracking)
        citations = []  # Simplified: no source tracking
        if citations:
            print(f"\n🔍 Sources Used (Proof of Research):")
            for i, citation in enumerate(citations[:10], 1):  # Show top 10
                print(f"   {i}. {citation}")
            
            if len(citations) > 10:
                print(f"   ... and {len(citations) - 10} more sources")
        
        # Show tool performance
        print(f"\n📈 Tool Performance:")
        for tool_name, stats in summary.get('tools_used', {}).items():
            success_rate = stats.get('successes', 0) / max(1, stats.get('executions', 1))
            avg_time = stats.get('total_time', 0) / max(1, stats.get('executions', 1))
            sources_used = stats.get('sources_used', 0)
            print(f"   • {tool_name}: {success_rate:.1%} success, {avg_time:.1f}s avg, {sources_used} sources")
        
        # Show recommendations
        intelligence = self.get_session_intelligence()
        recommendations = intelligence.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Recommendations:")
            for rec in recommendations:
                print(f"   • {rec}")
        
        print("=" * 50)
    
    def _assess_research_quality(self, summary: Dict) -> Dict[str, Any]:
        """Assess the quality of research conducted in this session."""
        
        research_tools = ["web_search", "deep_research", "browser"]
        research_stats = {
            tool: summary.get("tools_used", {}).get(tool, {})
            for tool in research_tools
            if tool in summary.get("tools_used", {})
        }
        
        if not research_stats:
            return {"quality_score": 0, "assessment": "No research conducted"}
        
        # Calculate quality based on source diversity and success rate
        total_sources = summary.get("unique_sources", 0)
        avg_success_rate = sum(
            stats.get("successes", 0) / max(1, stats.get("executions", 1))
            for stats in research_stats.values()
        ) / len(research_stats)
        
        quality_score = min(1.0, (total_sources * 0.3 + avg_success_rate * 0.7))
        
        if quality_score > 0.8:
            assessment = "High quality research with diverse sources"
        elif quality_score > 0.5:
            assessment = "Moderate quality research"
        else:
            assessment = "Limited research quality - consider more sources"
        
        return {
            "quality_score": quality_score,
            "assessment": assessment,
            "sources_found": total_sources,
            "research_success_rate": avg_success_rate,
            "research_tools_used": len(research_stats)
        }
    
    def _calculate_efficiency_metrics(self, summary: Dict) -> Dict[str, Any]:
        """Calculate efficiency metrics for the session."""
        
        total_time = summary.get("total_execution_time", 0)
        total_executions = summary.get("total_executions", 0)
        success_rate = summary.get("success_rate", 0)
        
        return {
            "avg_execution_time": total_time / max(1, total_executions),
            "success_rate": success_rate,
            "time_per_success": total_time / max(1, summary.get("successful_executions", 1)),
            "efficiency_rating": "high" if success_rate > 0.8 and total_time < 60 else "moderate",
            "total_tools_executed": total_executions
        }
    
    def _analyze_sandbox_usage(self, summary: Dict) -> Dict[str, Any]:
        """Analyze how sandbox was used in this session."""
        
        sandbox_info = self.get_sandbox_info()
        
        return {
            "sandbox_enabled": sandbox_info.get("sandbox_enabled", False),
            "sandboxed_tools_count": sandbox_info.get("sandboxed_count", 0),
            "local_tools_count": sandbox_info.get("local_count", 0),
            "sandbox_utilization": sandbox_info.get("sandboxed_count", 0) / max(1, len(self._tools)),
            "docker_image": sandbox_info.get("docker_image", "none")
        }
    
    def _generate_recommendations(self, summary: Dict) -> List[str]:
        """Generate actionable recommendations based on session analysis."""
        
        recommendations = []
        
        # Research quality recommendations
        if summary.get("unique_sources", 0) < 3:
            recommendations.append("💡 Consider using more diverse sources for better research coverage")
        
        # Efficiency recommendations
        if summary.get("success_rate", 0) < 0.7:
            recommendations.append("⚠️ High failure rate detected - check tool configurations and inputs")
        
        # Time recommendations
        avg_time = summary.get("total_execution_time", 0) / max(1, summary.get("total_executions", 1))
        if avg_time > 30:
            recommendations.append("⏱️ Tools taking longer than expected - consider timeout optimization")
        
        # Source diversity recommendations
        domains = summary.get("sources_by_domain", {})
        if len(domains) == 1 and list(domains.values())[0] > 3:
            recommendations.append("🌐 All sources from single domain - try diversifying source types")
        
        # Sandbox recommendations
        sandbox_info = self.get_sandbox_info()
        if not sandbox_info.get("sandbox_enabled") and summary.get("total_executions", 0) > 5:
            recommendations.append("🐳 Consider enabling sandbox for better security isolation")
        
        if not recommendations:
            recommendations.append("✅ Session performed well - no specific recommendations")
        
        return recommendations
    
    def _analyze_source_quality(self, high_quality_sources: List[Dict]) -> Dict[str, Any]:
        """Analyze the quality distribution of sources used."""
        
        if not high_quality_sources:
            return {"avg_quality": 0, "total_high_quality": 0}
        
        total_quality = sum(source.get("quality_score", 0) for source in high_quality_sources)
        avg_quality = total_quality / len(high_quality_sources)
        
        return {
            "avg_quality": avg_quality,
            "total_high_quality": len(high_quality_sources),
            "quality_range": f"{min(s.get('quality_score', 0) for s in high_quality_sources):.2f} - {max(s.get('quality_score', 0) for s in high_quality_sources):.2f}"
        }


# Factory function for easy creation
def create_simple_mcp(
    timeout: float = 30.0, 
    sandbox_config: Optional[Union[SandboxConfig, EnhancedSandboxConfig]] = None, 
    tools: Optional[List[str]] = None
) -> ToolMCP:
    """Create a ToolMCP instance with enhanced sandbox configuration."""
    return ToolMCP(timeout=timeout, sandbox_config=sandbox_config, tools=tools)


# Enhanced factory functions for common use cases
def create_local_mcp(timeout: float = 30.0, tools: Optional[List[str]] = None) -> ToolMCP:
    """
    Create MCP with local execution (no sandbox).
    
    Args:
        timeout: Tool execution timeout
        tools: Specific tools to load (None = all tools)
        
    Returns:
        ToolMCP configured for local execution
    """
    return create_simple_mcp(
        timeout=timeout,
        sandbox_config=create_local_config(),
        tools=tools
    )


def create_execution_sandbox_mcp(
    docker_image: str = "python:3.12-slim",
    timeout: float = 60.0,
    memory_limit: str = "512m",
    tools: Optional[List[str]] = None,
    validate_docker: bool = True
) -> ToolMCP:
    """
    Create MCP with sandbox for execution tools (bash, python, process).
    
    Args:
        docker_image: Docker image to use for sandbox
        timeout: Tool execution timeout  
        memory_limit: Memory limit for sandbox container
        tools: Specific tools to load (None = all tools)
        validate_docker: Whether to validate Docker setup
        
    Returns:
        ToolMCP configured with execution sandbox
        
    Example:
        mcp = create_execution_sandbox_mcp("python:3.11-slim", timeout=120)
    """
    from enterprise_ai.mcp.enhanced_sandbox import create_execution_sandbox
    
    sandbox_config = create_execution_sandbox(
        docker_image=docker_image,
        memory_limit=memory_limit,
        timeout=int(timeout),
        validate_docker=validate_docker
    )
    
    return create_simple_mcp(
        timeout=timeout,
        sandbox_config=sandbox_config,
        tools=tools
    )


def create_file_sandbox_mcp(
    docker_image: str = "python:3.12-slim",
    timeout: float = 30.0,
    memory_limit: str = "256m",
    tools: Optional[List[str]] = None,
    validate_docker: bool = True
) -> ToolMCP:
    """
    Create MCP with sandbox for file tools.
    
    Args:
        docker_image: Docker image to use for sandbox
        timeout: Tool execution timeout
        memory_limit: Memory limit for sandbox container
        tools: Specific tools to load (None = all tools)
        validate_docker: Whether to validate Docker setup
        
    Returns:
        ToolMCP configured with file sandbox
        
    Example:
        mcp = create_file_sandbox_mcp("ubuntu:22.04", memory_limit="1g")
    """
    from enterprise_ai.mcp.enhanced_sandbox import create_file_sandbox
    
    sandbox_config = create_file_sandbox(
        docker_image=docker_image,
        memory_limit=memory_limit,
        timeout=int(timeout),
        validate_docker=validate_docker
    )
    
    return create_simple_mcp(
        timeout=timeout,
        sandbox_config=sandbox_config,
        tools=tools
    )


def create_full_sandbox_mcp(
    docker_image: str = "ubuntu:22.04",
    timeout: float = 120.0,
    memory_limit: str = "1g",
    cpu_limit: float = 1.0,
    network_enabled: bool = False,
    tools: Optional[List[str]] = None,
    validate_docker: bool = True
) -> ToolMCP:
    """
    Create MCP with sandbox for all tools.
    
    Args:
        docker_image: Docker image to use for sandbox
        timeout: Tool execution timeout
        memory_limit: Memory limit for sandbox container
        cpu_limit: CPU limit for sandbox container
        network_enabled: Whether to enable network access in sandbox
        tools: Specific tools to load (None = all tools)
        validate_docker: Whether to validate Docker setup
        
    Returns:
        ToolMCP configured with full sandbox
        
    Example:
        mcp = create_full_sandbox_mcp(
            docker_image="ubuntu:22.04", 
            network_enabled=True,
            memory_limit="2g"
        )
    """
    from enterprise_ai.mcp.enhanced_sandbox import create_full_sandbox
    
    sandbox_config = create_full_sandbox(
        docker_image=docker_image,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        timeout=int(timeout),
        network_enabled=network_enabled,
        validate_docker=validate_docker
    )
    
    return create_simple_mcp(
        timeout=timeout,
        sandbox_config=sandbox_config,
        tools=tools
    )

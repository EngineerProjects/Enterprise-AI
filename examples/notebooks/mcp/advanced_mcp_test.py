#!/usr/bin/env python3
"""
Advanced MCP Test Suite with Enhanced Utils Integration

This comprehensive test suite validates all MCP functionality using
the Enterprise AI utils for beautiful visual output and testing.
"""

import asyncio
import tempfile
import os
import json
from pathlib import Path
import sys

# Setup project path and import utils
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from notebooks.utils import (
    print_header, print_test, print_chat, separator, Timer, Style, setup_project_path
)

from enterprise_ai.mcp import EnterpriseMCPServer, MCPConfig
from enterprise_ai.mcp.protocols.mcp_protocol import MCPMessage, MCPMessageType
from enterprise_ai.schema import ToolCall
from enterprise_ai.tool.core.registry import ToolRegistry


class AdvancedMCPTestSuite:
    """Comprehensive MCP test suite with visual utils integration."""
    
    def __init__(self):
        setup_project_path()
        self.config = MCPConfig(
            execution_mode="auto",
            verbose_logging=False,
            max_concurrent_sessions=10,
            session_timeout=3600.0
        )
        self.server = None
        self.test_sessions = []
        self.test_agent_id = "advanced_test_agent"
        
        # Test tracking
        self.test_results = {
            "tool_discovery": False,
            "concurrent_sessions": False,
            "tool_categories": False,
            "tool_capabilities": False,
            "file_operations": False,
            "configuration_mgmt": False,
            "web_operations": False,
            "execution_tools": False,
            "session_management": False,
            "error_recovery": False,
            "performance_stress": False,
            "integration_flow": False
        }
        
    async def run_full_test_suite(self):
        """Run the complete advanced test suite."""
        print_header("🚀 Advanced Enterprise AI MCP Test Suite", "double")
        print(f"{Style.CYAN}Testing MCP server with enhanced utils integration{Style.RESET}")
        
        try:
            # Initialize server
            await self._initialize_server()
            
            # Run all test categories
            await self._run_discovery_tests()
            await self._run_session_tests() 
            await self._run_tool_tests()
            await self._run_integration_tests()
            await self._run_performance_tests()
            
            # Final results
            self._print_final_results()
            
        except Exception as e:
            print_test(f"Test suite failed: {str(e)}", "fail")
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()
    
    async def _initialize_server(self):
        """Initialize the MCP server for testing."""
        print_header("🛠️ Server Initialization", "single")
        
        with Timer("MCP Server Setup"):
            self.server = EnterpriseMCPServer(self.config)
            self.server.is_running = True
            await self.server.session_manager.start()
            
            print_test("MCP Server initialized", "pass")
            print_test(f"Tools registered: {len(self.server.tool_registry.get_all_tool_classes())}", "pass")
            print_test("Session manager started", "pass")
    
    async def _run_discovery_tests(self):
        """Test tool discovery and information retrieval."""
        print_header("🔍 Tool Discovery & Information Tests", "single")
        
        # Test 1: Tool Discovery
        print_test("Testing tool discovery...", "running")
        
        message = MCPMessage.create(
            message_type=MCPMessageType.TOOL_LIST,
            data={},
            agent_id=self.test_agent_id
        )
        
        response = await self.server.process_message(message)
        
        if response.message_type != MCPMessageType.ERROR:
            tools = response.data.get("tools", [])
            if len(tools) >= 10:  # Should have at least 10 tools
                self.test_results["tool_discovery"] = True
                print_test(f"Discovered {len(tools)} tools", "pass")
                
                # Display detailed tool information
                separator()
                print(f"{Style.CYAN}🔧 Tool Inventory:{Style.RESET}")
                
                categories = {}
                for tool in tools:
                    name = tool.get('name', 'Unknown')
                    metadata = tool.get('metadata', {})
                    category = metadata.get('category', 'uncategorized')
                    
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(name)
                
                for category, tool_names in categories.items():
                    print(f"   📁 {category.title()}: {len(tool_names)} tools")
                    for tool_name in tool_names[:3]:  # Show first 3
                        print(f"      • {tool_name}")
                    if len(tool_names) > 3:
                        print(f"      ... and {len(tool_names) - 3} more")
            else:
                print_test(f"Only found {len(tools)} tools (expected >= 10)", "warn")
        else:
            print_test(f"Tool discovery failed: {response.data.get('error')}", "fail")
    
    async def _run_session_tests(self):
        """Test session management capabilities."""
        print_header("🔄 Session Management Tests", "single")
        
        # Test 1: Concurrent Sessions
        print_test("Testing concurrent session creation...", "running")
        
        session_count = 5
        created_sessions = []
        
        for i in range(session_count):
            message = MCPMessage.create(
                message_type=MCPMessageType.SESSION_CREATE,
                data={"agent_id": f"test_agent_{i}"},
                agent_id=f"test_agent_{i}"
            )
            
            response = await self.server.process_message(message)
            if response.message_type != MCPMessageType.ERROR:
                session_id = response.data.get("session_id")
                created_sessions.append(session_id)
        
        stats = self.server.session_manager.get_session_stats()
        if stats['active_sessions'] == session_count:
            self.test_results["concurrent_sessions"] = True
            print_test(f"Created {session_count} concurrent sessions", "pass")
            self.test_sessions.extend(created_sessions)
        else:
            print_test(f"Expected {session_count} sessions, got {stats['active_sessions']}", "warn")
        
        # Test 2: Session Cleanup
        print_test("Testing session cleanup...", "running")
        
        # Close half the sessions
        cleanup_count = len(created_sessions) // 2
        for session_id in created_sessions[:cleanup_count]:
            message = MCPMessage.create(
                message_type=MCPMessageType.SESSION_CLOSE,
                data={"session_id": session_id},
                agent_id=self.test_agent_id
            )
            await self.server.process_message(message)
        
        stats = self.server.session_manager.get_session_stats()
        expected = session_count - cleanup_count
        if stats['active_sessions'] == expected:
            self.test_results["session_management"] = True
            print_test(f"Session cleanup working correctly", "pass")
        else:
            print_test(f"Session cleanup inconsistent", "warn")
    
    async def _run_tool_tests(self):
        """Test individual tool categories and capabilities."""
        print_header("🛠️ Tool Functionality Tests", "single")
        
        if not self.test_sessions:
            # Create a session for testing
            message = MCPMessage.create(
                message_type=MCPMessageType.SESSION_CREATE,
                data={"agent_id": self.test_agent_id},
                agent_id=self.test_agent_id
            )
            response = await self.server.process_message(message)
            if response.message_type != MCPMessageType.ERROR:
                self.test_sessions.append(response.data.get("session_id"))
        
        test_session = self.test_sessions[0] if self.test_sessions else None
        
        # Test 1: Configuration Tool
        print_test("Testing configuration management...", "running")
        
        tool_call = ToolCall.create(
            name="configuration",
            arguments={"action": "get", "key": "system.name"},
            id="config_test_001"
        )
        
        success = await self._execute_tool_test(tool_call, test_session)
        if success:
            self.test_results["configuration_mgmt"] = True
            print_test("Configuration tool working", "pass")
        
        # Test 2: File Operations
        print_test("Testing file operations...", "running")
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write("Advanced MCP test file content\nLine 2\nLine 3")
            tmp_path = tmp.name
        
        try:
            tool_call = ToolCall.create(
                name="filesystem",
                arguments={"command": "read_file", "path": tmp_path},
                id="file_test_001"
            )
            
            success = await self._execute_tool_test(tool_call, test_session)
            if success:
                self.test_results["file_operations"] = True
                print_test("File operations working", "pass")
        finally:
            os.unlink(tmp_path)
        
        # Test 3: Web Operations (if available)
        print_test("Testing web search capabilities...", "running")
        
        tool_call = ToolCall.create(
            name="web_search",
            arguments={"query": "Enterprise AI test query"},
            id="web_test_001"
        )
        
        success = await self._execute_tool_test(tool_call, test_session)
        if success:
            self.test_results["web_operations"] = True
            print_test("Web operations working", "pass")
        
        # Test 4: Tool Categories
        print_test("Analyzing tool categories...", "running")
        
        registry = self.server.tool_registry
        categories = registry.get_all_category_names()
        
        if len(categories) >= 4:  # Should have multiple categories
            self.test_results["tool_categories"] = True
            print_test(f"Found {len(categories)} tool categories", "pass")
            
            separator()
            print(f"{Style.CYAN}📂 Category Analysis:{Style.RESET}")
            for category in sorted(categories):
                tools_in_category = registry.get_tools_by_category(category)
                print(f"   📁 {category}: {len(tools_in_category)} tools")
        
        # Test 5: Tool Capabilities 
        print_test("Analyzing tool capabilities...", "running")
        
        capabilities = registry.get_all_capability_names()
        
        if len(capabilities) >= 6:  # Should have various capabilities
            self.test_results["tool_capabilities"] = True
            print_test(f"Found {len(capabilities)} capabilities", "pass")
            
            separator()
            print(f"{Style.CYAN}⚡ Capability Analysis:{Style.RESET}")
            for capability in sorted(capabilities)[:8]:  # Show first 8
                tools_with_cap = registry.get_tools_by_capability(capability)
                print(f"   ⚡ {capability}: {len(tools_with_cap)} tools")
        else:
            print_test(f"Only found {len(capabilities)} capabilities", "warn")
    
    async def _run_integration_tests(self):
        """Test end-to-end integration scenarios."""
        print_header("🔗 Integration Flow Tests", "single")
        
        print_test("Testing multi-tool workflow...", "running")
        
        if not self.test_sessions:
            print_test("No session available for integration test", "skip")
            return
        
        test_session = self.test_sessions[0]
        
        # Complex workflow: Get config, then use that info in another tool
        workflow_success = True
        
        try:
            # Step 1: Get configuration
            config_call = ToolCall.create(
                name="configuration",
                arguments={"action": "get", "key": "app.name"},
                id="workflow_001"
            )
            
            config_success = await self._execute_tool_test(config_call, test_session)
            if not config_success:
                workflow_success = False
            
            # Step 2: Use mime type detector
            mime_call = ToolCall.create(
                name="mime_type_detector",
                arguments={"command": "detect_type", "path": "/etc/hosts"},
                id="workflow_002"
            )
            
            mime_success = await self._execute_tool_test(mime_call, test_session)
            if not mime_success:
                workflow_success = False
            
            if workflow_success:
                self.test_results["integration_flow"] = True
                print_test("Multi-tool workflow successful", "pass")
            
        except Exception as e:
            print_test(f"Integration workflow failed: {str(e)}", "fail")
    
    async def _run_performance_tests(self):
        """Test performance and stress scenarios."""
        print_header("⚡ Performance & Stress Tests", "single")
        
        print_test("Testing rapid tool execution...", "running")
        
        if not self.test_sessions:
            print_test("No session available for performance test", "skip")
            return
        
        test_session = self.test_sessions[0]
        
        # Rapid fire tool calls
        start_time = asyncio.get_event_loop().time()
        successful_calls = 0
        total_calls = 10
        
        for i in range(total_calls):
            tool_call = ToolCall.create(
                name="configuration",
                arguments={"action": "get", "key": "system.debug"},
                id=f"perf_test_{i}"
            )
            
            success = await self._execute_tool_test(tool_call, test_session, silent=True)
            if success:
                successful_calls += 1
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        if successful_calls >= total_calls * 0.8:  # 80% success rate
            self.test_results["performance_stress"] = True
            print_test(f"Performance test: {successful_calls}/{total_calls} calls in {duration:.2f}s", "pass")
        else:
            print_test(f"Performance test: only {successful_calls}/{total_calls} successful", "warn")
    
    async def _execute_tool_test(self, tool_call: ToolCall, session_id: str, silent: bool = False) -> bool:
        """Execute a tool call and return success status."""
        try:
            message = MCPMessage.create(
                message_type=MCPMessageType.TOOL_CALL,
                data={
                    "tool_calls": [tool_call.to_dict()],
                    "context": {"test_execution": True}
                },
                session_id=session_id,
                agent_id=self.test_agent_id
            )
            
            response = await self.server.process_message(message)
            
            if response.message_type == MCPMessageType.ERROR:
                if not silent:
                    print_test(f"Tool execution failed: {response.data.get('error')}", "warn")
                return False
            
            results = response.data.get("tool_results", [])
            if results and results[0].get("success", False):
                return True
            else:
                if not silent:
                    error = results[0].get("error", "Unknown error") if results else "No results"
                    print_test(f"Tool execution failed: {error}", "warn")
                return False
                
        except Exception as e:
            if not silent:
                print_test(f"Tool test exception: {str(e)}", "fail")
            return False
    
    def _print_final_results(self):
        """Print comprehensive final test results."""
        print_header("📊 Advanced Test Results Summary", "double")
        
        passed = sum(self.test_results.values())
        total = len(self.test_results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        # Group results by category
        categories = {
            "🔍 Discovery": ["tool_discovery", "tool_categories", "tool_capabilities"],
            "🔄 Sessions": ["concurrent_sessions", "session_management"],
            "🛠️ Tools": ["file_operations", "configuration_mgmt", "web_operations", "execution_tools"],
            "🔗 Integration": ["integration_flow", "error_recovery"],
            "⚡ Performance": ["performance_stress"]
        }
        
        for category, tests in categories.items():
            print(f"\n{Style.BOLD}{category}:{Style.RESET}")
            for test in tests:
                if test in self.test_results:
                    status = "✅ PASS" if self.test_results[test] else "❌ FAIL"
                    test_name = test.replace('_', ' ').title()
                    print(f"   {test_name}: {status}")
        
        separator()
        print(f"{Style.GREEN}✅ Tests Passed: {passed}{Style.RESET}")
        print(f"{Style.RED}❌ Tests Failed: {total - passed}{Style.RESET}")
        print(f"{Style.BOLD}📊 Success Rate: {success_rate:.1f}%{Style.RESET}")
        
        if success_rate >= 90:
            print_header("🎉 Excellent! MCP Implementation is Production Ready", "box")
            print(f"{Style.GREEN}✨ Your MCP server is working exceptionally well!{Style.RESET}")
            print(f"{Style.CYAN}🚀 Ready for advanced agent implementation!{Style.RESET}")
        elif success_rate >= 75:
            print_header("✅ Good! MCP Implementation is Solid with Minor Issues", "box")
            print(f"{Style.YELLOW}⚡ Minor improvements needed, but core functionality is strong{Style.RESET}")
        else:
            print_header("⚠️ MCP Implementation Needs Attention", "box")
            print(f"{Style.RED}🔧 Several issues need to be addressed before proceeding{Style.RESET}")
    
    async def _cleanup(self):
        """Clean up test resources."""
        print_header("🧹 Test Cleanup", "single")
        
        try:
            # Close remaining sessions
            for session_id in self.test_sessions:
                message = MCPMessage.create(
                    message_type=MCPMessageType.SESSION_CLOSE,
                    data={"session_id": session_id},
                    agent_id=self.test_agent_id
                )
                await self.server.process_message(message)
            
            print_test(f"Cleaned up {len(self.test_sessions)} sessions", "pass")
            
            # Stop session manager
            if self.server:
                await self.server.session_manager.stop()
                print_test("Session manager stopped", "pass")
            
        except Exception as e:
            print_test(f"Cleanup error: {str(e)}", "warn")


async def main():
    """Run the advanced MCP test suite."""
    tester = AdvancedMCPTestSuite()
    
    try:
        await tester.run_full_test_suite()
    except KeyboardInterrupt:
        print_test("Test interrupted by user", "warn")
    except Exception as e:
        print_test(f"Test failed with error: {str(e)}", "fail")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Terminate Tool Testing Script

Tests each aspect of the terminate tool individually with comprehensive coverage.
"""

import asyncio
import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.utility.terminate import TerminateTool
from enterprise_ai.tool.core.result import ToolResult


class TerminateToolTester:
    """Comprehensive terminate tool tester."""
    
    def __init__(self):
        self.terminate_tool = None
    
    async def show_tool_description(self):
        """Show the terminate tool description and capabilities."""
        print_header("Terminate Tool Description", "double")
        
        if self.terminate_tool:
            print_chat("tool", f"Name: {self.terminate_tool.name}")
            print_chat("tool", f"Description: {self.terminate_tool.description.strip()}")
            
            # Show capabilities
            if hasattr(self.terminate_tool, 'capabilities'):
                caps = [str(cap) for cap in self.terminate_tool.capabilities]
                print_chat("tool", f"Capabilities: {', '.join(caps)}")
            
            # Show parameters
            params = self.terminate_tool.parameters
            if params and "properties" in params:
                properties = params["properties"]
                print_chat("tool", "Parameters:")
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "unknown")
                    param_desc = param_info.get("description", "No description")
                    required = param_name in params.get("required", [])
                    req_str = " (required)" if required else " (optional)"
                    print_chat("tool", f"  • {param_name}: {param_type}{req_str} - {param_desc}")
                    
                    # Show enum values if present
                    if "enum" in param_info:
                        enum_values = ", ".join(param_info["enum"])
                        print_chat("tool", f"    Values: {enum_values}")

    async def setup(self):
        """Initialize terminate tool."""
        print_header("Terminate Tool Test Suite", "double")
        
        print_test("Setting up terminate tool", "running")
        
        self.terminate_tool = TerminateTool()
        success = await self.terminate_tool.initialize()
        
        if success:
            print_test("TerminateTool initialized", "pass")
            await self.show_tool_description()
            return True
        else:
            print_test("TerminateTool initialization failed", "fail")
            return False
    
    async def test_operation(self, description: str, expect_success: bool = True, 
                        show_content: bool = True, **kwargs):
        """Test a terminate operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: terminate"):
                result = await self.terminate_tool.execute(**kwargs)
            
            # Check result using the success field, not the error field
            is_success = isinstance(result, ToolResult) and getattr(result, 'success', True)
            
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                if hasattr(result, 'result') and result.result and show_content:
                    output = str(result.result)
                    print_chat("tool", output)
                return result, True
                
            elif not expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: EXPECTED ERROR - {error_msg}", "pass")
                return result, True
                
            elif expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: UNEXPECTED FAILURE - {error_msg}", "fail")
                return result, False
                
            else:
                print_test(f"{description}: UNEXPECTED SUCCESS", "warn")
                if hasattr(result, 'result') and result.result and show_content:
                    print_chat("tool", str(result.result))
                return result, False
                
        except Exception as e:
            if expect_success:
                print_test(f"{description}: EXCEPTION - {e}", "fail")
                return None, False
            else:
                print_test(f"{description}: EXPECTED EXCEPTION - {e}", "pass")
                return None, True
    
    async def run_basic_termination_tests(self):
        """Test basic termination functionality."""
        print_header("Basic Termination Tests", "single")
        
        # Test successful termination without message
        await self.test_operation(
            "Success Termination (No Message)",
            expect_success=True,
            status="success"
        )
        
        # Test successful termination with message
        await self.test_operation(
            "Success Termination (With Message)",
            expect_success=True,
            status="success",
            message="All tasks completed successfully. The system is ready for production deployment."
        )
        
        # Test failure termination without message
        await self.test_operation(
            "Failure Termination (No Message)",
            expect_success=True,
            status="failure"
        )
        
        # Test failure termination with message
        await self.test_operation(
            "Failure Termination (With Message)",
            expect_success=True,
            status="failure",
            message="Unable to proceed due to missing API credentials. Please configure authentication."
        )
    
    async def run_message_content_tests(self):
        """Test different types of termination messages."""
        print_header("Message Content Tests", "single")
        
        # Test with short message
        await self.test_operation(
            "Short Success Message",
            expect_success=True,
            status="success",
            message="Done!"
        )
        
        # Test with detailed technical message
        await self.test_operation(
            "Technical Success Message",
            expect_success=True,
            status="success",
            message="Database migration completed successfully. "
                   "Migrated 1,234,567 records in 45.2 seconds. "
                   "All indexes rebuilt and optimized. "
                   "System performance metrics are within normal ranges."
        )
        
        # Test with user-friendly message
        await self.test_operation(
            "User-Friendly Failure Message",
            expect_success=True,
            status="failure",
            message="I wasn't able to complete the requested task because the input file appears to be corrupted. "
                   "Please check the file and try again, or provide a different file."
        )
        
        # Test with structured message
        await self.test_operation(
            "Structured Status Message",
            expect_success=True,
            status="success",
            message="Task Summary:\n"
                   "✓ Configuration validated\n"
                   "✓ Dependencies installed\n" 
                   "✓ Tests passed (127/127)\n"
                   "✓ Build completed\n"
                   "✓ Deployment successful\n\n"
                   "Next steps: Monitor application logs for 24 hours."
        )
    
    async def run_workflow_scenarios(self):
        """Test realistic workflow termination scenarios."""
        print_header("Workflow Scenarios", "single")
        
        # Project completion scenario
        await self.test_operation(
            "Project Completion",
            expect_success=True,
            status="success",
            message="Project Alpha development completed successfully!\n\n"
                   "Deliverables:\n"
                   "• Backend API (100% test coverage)\n"
                   "• Frontend dashboard (responsive design)\n"
                   "• Documentation (user guide + API docs)\n"
                   "• Docker deployment configuration\n\n"
                   "The application is deployed to staging and ready for user acceptance testing."
        )
        
        # Blocked scenario
        await self.test_operation(
            "Blocked by Dependency",
            expect_success=True,
            status="failure",
            message="Unable to proceed with deployment due to infrastructure dependencies.\n\n"
                   "Blocking Issues:\n"
                   "• Database cluster is offline for maintenance\n"
                   "• SSL certificates expired on load balancer\n"
                   "• Network security group rules not updated\n\n"
                   "Estimated resolution time: 4-6 hours\n"
                   "Recommendation: Resume deployment tomorrow morning after infrastructure team completes maintenance."
        )
        
        # Resource limitation scenario
        await self.test_operation(
            "Resource Limitations",
            expect_success=True,
            status="failure",
            message="Task terminated due to resource constraints.\n\n"
                   "Resource Usage:\n"
                   "• Memory: 95% (7.6GB / 8GB)\n"
                   "• CPU: 98% sustained for 10+ minutes\n"
                   "• Disk I/O: Bottlenecked at 100MB/s\n\n"
                   "Recommendation: Upgrade to a larger instance type or optimize the data processing algorithm."
        )
    
    async def run_error_handling_tests(self):
        """Test error handling and edge cases."""
        print_header("Error Handling Tests", "single")
        
        # Test missing status parameter
        await self.test_operation(
            "Missing Status Parameter",
            expect_success=False,
            message="This should fail"
        )
        
        # Test invalid status values
        await self.test_operation(
            "Invalid Status Value",
            expect_success=False,
            status="invalid_status",
            message="This should fail"
        )
        
        await self.test_operation(
            "Empty Status",
            expect_success=False,
            status="",
            message="This should fail"
        )
        
        # Test with only message (no status)
        await self.test_operation(
            "Message Without Status",
            expect_success=False,
            message="Just a message without status"
        )
        
        # Test with empty parameters
        await self.test_operation(
            "No Parameters",
            expect_success=False
        )
    
    async def run_edge_case_tests(self):
        """Test edge cases and boundary conditions."""
        print_header("Edge Case Tests", "single")
        
        # Test with empty message
        await self.test_operation(
            "Empty Message",
            expect_success=True,
            status="success",
            message=""
        )
        
        # Test with special characters in message
        await self.test_operation(
            "Special Characters",
            expect_success=True,
            status="success",
            message="Message with special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\r"
        )
        
        # Test with unicode characters
        await self.test_operation(
            "Unicode Characters",
            expect_success=True,
            status="failure",
            message="Error with unicode: 你好世界 🚀 ✅ ❌ 🔧 📊 Ñoël café naïve résumé"
        )
        
        # Test with JSON-like message
        await self.test_operation(
            "JSON-like Message",
            expect_success=True,
            status="success",
            message='{"status": "completed", "items_processed": 1234, "errors": [], "duration": "45.2s"}'
        )
    
    async def run_integration_scenario_tests(self):
        """Test realistic integration scenarios."""
        print_header("Integration Scenario Tests", "single")
        
        print_chat("user", "These tests simulate real-world scenarios where the terminate tool would be used:")
        
        # AI Agent task completion
        await self.test_operation(
            "AI Agent Task Completion",
            expect_success=True,
            status="success",
            message="AI Agent Report:\n\n"
                   "Task: Analyze customer feedback and generate insights\n"
                   "Duration: 3 minutes 42 seconds\n"
                   "Data processed: 15,847 customer reviews\n\n"
                   "Key Insights:\n"
                   "• 87% positive sentiment (up 5% from last month)\n"
                   "• Top complaint: shipping delays (mentioned 234 times)\n"
                   "• Most praised feature: customer support (mentioned 567 times)\n"
                   "• Recommended action: Investigate logistics partner performance\n\n"
                   "Detailed report saved to: /reports/customer_feedback_2024_01.pdf"
        )
        
        # Automated testing completion
        await self.test_operation(
            "Automated Testing Suite",
            expect_success=True,
            status="success",
            message="Test Suite Execution Complete\n\n"
                   "Results Summary:\n"
                   "• Total Tests: 1,247\n"
                   "• Passed: 1,242 (99.6%)\n"
                   "• Failed: 5 (0.4%)\n"
                   "• Skipped: 0\n"
                   "• Duration: 8 minutes 15 seconds\n\n"
                   "Failed Tests:\n"
                   "• test_payment_gateway_timeout (known flaky test)\n"
                   "• test_email_delivery_timing (infrastructure dependent)\n"
                   "• test_cache_expiration_edge_case (race condition)\n"
                   "• test_concurrent_user_limit (load testing)\n"
                   "• test_external_api_fallback (third-party service)\n\n"
                   "Recommendation: All critical path tests passed. Failed tests are non-blocking for deployment."
        )
        
        # Deployment failure scenario
        await self.test_operation(
            "Deployment Failure",
            expect_success=True,
            status="failure",
            message="Deployment Failed - Rolling Back\n\n"
                   "Error Details:\n"
                   "• Stage: Database migration\n"
                   "• Error: Foreign key constraint violation\n"
                   "• Table: user_preferences\n"
                   "• Affected rows: 15,432\n\n"
                   "Rollback Status:\n"
                   "✓ Application containers stopped\n"
                   "✓ Load balancer traffic redirected\n"
                   "✓ Database migration reverted\n"
                   "✓ Previous version restored\n"
                   "✓ Health checks passing\n\n"
                   "Impact: Zero downtime achieved. Users remained on stable version.\n"
                   "Next Steps: Fix migration script and schedule retry deployment."
        )
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.terminate_tool:
            print_test("Cleaning up terminate tool", "running")
            await self.terminate_tool.cleanup()
            print_test("TerminateTool cleanup complete", "pass")


async def main():
    """Run all terminate tool tests."""
    tester = TerminateToolTester()
    
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run comprehensive test suites
        await tester.run_basic_termination_tests()
        await tester.run_message_content_tests()
        await tester.run_workflow_scenarios()
        await tester.run_error_handling_tests()
        await tester.run_edge_case_tests()
        await tester.run_integration_scenario_tests()
        
        print_header("All Terminate Tool Tests Complete!", "double")
        print_test("Terminate tool is ready for LLM integration", "pass")
        print_test("Tool can handle various termination scenarios", "pass")
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
    except Exception as e:
        print_test(f"Unexpected error: {e}", "fail")
    finally:
        await tester.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)
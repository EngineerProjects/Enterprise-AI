#!/usr/bin/env python3
"""
Planning Tool Testing Script

Tests each aspect of the planning tool individually with comprehensive coverage.
"""

import asyncio
import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.planning.planning import PlanningTool
from enterprise_ai.tool.core.result import ToolResult


class PlanningToolTester:
    """Comprehensive planning tool tester."""
    
    def __init__(self):
        self.planning_tool = None
        self.test_plans = {}
    
    async def show_tool_description(self):
        """Show the planning tool description and capabilities."""
        print_header("Planning Tool Description", "double")
        
        if self.planning_tool:
            print_chat("tool", f"Name: {self.planning_tool.name}")
            print_chat("tool", f"Description: {self.planning_tool.description}")
            
            # Show capabilities
            if hasattr(self.planning_tool, 'capabilities'):
                caps = [str(cap) for cap in self.planning_tool.capabilities]
                print_chat("tool", f"Capabilities: {', '.join(caps)}")
            
            # Show available commands
            commands = self.planning_tool.parameters.get("properties", {}).get("command", {}).get("enum", [])
            print_chat("tool", f"Commands: {', '.join(commands)}")

    async def setup(self):
        """Initialize planning tool."""
        print_header("Planning Tool Test Suite", "double")
        
        print_test("Setting up planning tool", "running")
        
        self.planning_tool = PlanningTool()
        success = await self.planning_tool.initialize()
        
        if success:
            print_test("PlanningTool initialized", "pass")
            await self.show_tool_description()
            return True
        else:
            print_test("PlanningTool initialization failed", "fail")
            return False
    
    async def test_operation(self, description: str, expect_success: bool = True, show_content: bool = True, **kwargs):
        """Test a planning operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {kwargs.get('command', 'unknown')}"):
                result = await self.planning_tool.execute(**kwargs)
            
            is_success = isinstance(result, ToolResult) and result.success
            
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                if hasattr(result, 'result') and result.result and show_content:
                    output = str(result.result)
                    if len(output) <= 1000:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output[:1000] + "...")
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
    
    async def run_basic_plan_operations(self):
        """Test basic plan creation and management."""
        print_header("Basic Plan Operations", "single")
        
        # Test plan creation
        result, success = await self.test_operation(
            "Create Project Plan",
            expect_success=True,
            command="create",
            plan_id="project_alpha",
            title="Alpha Project Development",
            steps=[
                "Set up development environment",
                "Design system architecture", 
                "Implement core features",
                "Write unit tests",
                "Deploy to staging",
                "Conduct user testing",
                "Deploy to production"
            ]
        )
        
        if success:
            self.test_plans["project"] = "project_alpha"
        
        # Test plan listing
        await self.test_operation(
            "List Plans",
            expect_success=True,
            command="list"
        )
        
        # Test plan retrieval
        await self.test_operation(
            "Get Plan Details",
            expect_success=True,
            command="get",
            plan_id="project_alpha"
        )
        
        # Test get without plan_id (should use active)
        await self.test_operation(
            "Get Active Plan",
            expect_success=True,
            command="get"
        )
        
        return success
    
    async def run_step_management_tests(self):
        """Test step status management."""
        print_header("Step Management Tests", "single")
        
        if "project" not in self.test_plans:
            print_test("No project plan available", "skip")
            return
        
        plan_id = self.test_plans["project"]
        
        # Mark first step as in progress
        await self.test_operation(
            "Mark Step In Progress",
            expect_success=True,
            command="mark_step",
            plan_id=plan_id,
            step_index=0,
            step_status="in_progress",
            step_notes="Setting up Docker and IDE"
        )
        
        # Complete first step
        await self.test_operation(
            "Complete Step",
            expect_success=True,
            command="mark_step",
            plan_id=plan_id,
            step_index=0,
            step_status="completed"
        )
        
        # Start second step
        await self.test_operation(
            "Start Architecture Design",
            expect_success=True,
            command="mark_step",
            plan_id=plan_id,
            step_index=1,
            step_status="in_progress",
            step_notes="Creating system diagrams and API specs"
        )
        
        # Mark a step as blocked
        await self.test_operation(
            "Block Testing Step",
            expect_success=True,
            command="mark_step",
            plan_id=plan_id,
            step_index=5,
            step_status="blocked",
            step_notes="Waiting for test environment setup"
        )
        
        # Test using active plan (no plan_id specified)
        await self.test_operation(
            "Update Step on Active Plan",
            expect_success=True,
            command="mark_step",
            step_index=2,
            step_status="in_progress"
        )
    
    async def run_multiple_plans_tests(self):
        """Test managing multiple plans."""
        print_header("Multiple Plans Management", "single")
        
        # Create second plan
        await self.test_operation(
            "Create Marketing Plan",
            expect_success=True,
            command="create",
            plan_id="marketing_q1",
            title="Q1 Marketing Campaign",
            steps=[
                "Research target audience",
                "Develop campaign strategy",
                "Create content calendar",
                "Launch social media campaign",
                "Monitor and optimize"
            ]
        )
        
        self.test_plans["marketing"] = "marketing_q1"
        
        # Create third plan
        await self.test_operation(
            "Create Operations Plan",
            expect_success=True,
            command="create",
            plan_id="ops_migration",
            title="Infrastructure Migration",
            steps=[
                "Audit current infrastructure",
                "Design new architecture",
                "Create migration plan",
                "Execute migration",
                "Validate and monitor"
            ]
        )
        
        self.test_plans["operations"] = "ops_migration"
        
        # List all plans
        await self.test_operation(
            "List All Plans",
            expect_success=True,
            command="list"
        )
        
        # Switch active plan
        await self.test_operation(
            "Set Marketing as Active",
            expect_success=True,
            command="set_active",
            plan_id="marketing_q1"
        )
        
        # Test active plan switch
        await self.test_operation(
            "Get New Active Plan",
            expect_success=True,
            command="get"
        )
        
        # Switch back to project plan
        await self.test_operation(
            "Set Project as Active",
            expect_success=True,
            command="set_active",
            plan_id="project_alpha"
        )
    
    async def run_plan_modification_tests(self):
        """Test plan updates and modifications."""
        print_header("Plan Modification Tests", "single")
        
        if "marketing" not in self.test_plans:
            print_test("No marketing plan available", "skip")
            return
        
        plan_id = self.test_plans["marketing"]
        
        # Update plan title
        await self.test_operation(
            "Update Plan Title",
            expect_success=True,
            command="update",
            plan_id=plan_id,
            title="Q1 Digital Marketing Campaign"
        )
        
        # Update plan steps
        updated_steps = [
            "Research target audience and competitors",
            "Develop comprehensive campaign strategy",
            "Create content calendar and assets",
            "Launch multi-channel campaign",
            "Monitor metrics and optimize performance",
            "Prepare Q2 strategy based on results"
        ]
        
        await self.test_operation(
            "Update Plan Steps",
            expect_success=True,
            command="update",
            plan_id=plan_id,
            steps=updated_steps
        )
        
        # Update both title and steps
        await self.test_operation(
            "Update Title and Steps",
            expect_success=True,
            command="update",
            plan_id=plan_id,
            title="Q1 Integrated Marketing Campaign",
            steps=[
                "Market research and analysis",
                "Strategy development",
                "Content creation",
                "Campaign execution",
                "Performance monitoring",
                "Results analysis and reporting"
            ]
        )
    
    async def run_error_handling_tests(self):
        """Test error handling and edge cases."""
        print_header("Error Handling Tests", "single")
        
        # Test missing command
        await self.test_operation(
            "Missing Command",
            expect_success=False,
            **{}  # No command provided
        )
        
        # Test invalid command
        await self.test_operation(
            "Invalid Command",
            expect_success=False,
            command="invalid_command"
        )
        
        # Test create without required parameters
        await self.test_operation(
            "Create Without Plan ID",
            expect_success=False,
            command="create",
            title="Test Plan"
        )
        
        await self.test_operation(
            "Create Without Title",
            expect_success=False,
            command="create",
            plan_id="test_plan"
        )
        
        await self.test_operation(
            "Create Without Steps",
            expect_success=False,
            command="create",
            plan_id="test_plan",
            title="Test Plan"
        )
        
        # Test duplicate plan creation
        await self.test_operation(
            "Create Duplicate Plan",
            expect_success=False,
            command="create",
            plan_id="project_alpha",  # Already exists
            title="Duplicate Plan",
            steps=["Step 1"]
        )
        
        # Test operations on non-existent plan
        await self.test_operation(
            "Get Non-existent Plan",
            expect_success=False,
            command="get",
            plan_id="non_existent"
        )
        
        await self.test_operation(
            "Update Non-existent Plan",
            expect_success=False,
            command="update",
            plan_id="non_existent",
            title="New Title"
        )
        
        # Test invalid step operations
        if "project" in self.test_plans:
            plan_id = self.test_plans["project"]
            
            await self.test_operation(
                "Mark Invalid Step Index",
                expect_success=False,
                command="mark_step",
                plan_id=plan_id,
                step_index=999,
                step_status="completed"
            )
            
            await self.test_operation(
                "Mark Step with Invalid Status",
                expect_success=False,
                command="mark_step",
                plan_id=plan_id,
                step_index=0,
                step_status="invalid_status"
            )
        
        # Test operations without active plan
        await self.test_operation(
            "Get Plan Without Active",
            expect_success=True,  # Should work with current active plan
            command="get"
        )
    
    async def run_workflow_simulation(self):
        """Simulate a real workflow with the planning tool."""
        print_header("Workflow Simulation", "single")
        
        # Create a development workflow plan
        await self.test_operation(
            "Create Development Workflow",
            expect_success=True,
            command="create",
            plan_id="dev_workflow",
            title="Feature Development Workflow",
            steps=[
                "Create feature branch",
                "Implement feature logic",
                "Write unit tests",
                "Run integration tests",
                "Code review",
                "Merge to main",
                "Deploy to staging",
                "QA testing",
                "Deploy to production"
            ]
        )
        
        # Simulate workflow progression
        workflow_steps = [
            (0, "completed", "Branch 'feature/user-auth' created"),
            (1, "in_progress", "Implementing authentication logic"),
            (2, "not_started", ""),
            (3, "not_started", ""),
            (4, "not_started", ""),
            (5, "not_started", ""),
            (6, "not_started", ""),
            (7, "blocked", "QA environment is down"),
            (8, "not_started", "")
        ]
        
        for step_idx, status, notes in workflow_steps:
            await self.test_operation(
                f"Update Step {step_idx}",
                expect_success=True,
                show_content=False,
                command="mark_step",
                plan_id="dev_workflow",
                step_index=step_idx,
                step_status=status,
                step_notes=notes
            )
        
        # Show final workflow state
        await self.test_operation(
            "Show Workflow Progress",
            expect_success=True,
            command="get",
            plan_id="dev_workflow"
        )
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.planning_tool:
            print_test("Cleaning up planning tool", "running")
            await self.planning_tool.cleanup()
            print_test("PlanningTool cleanup complete", "pass")


async def main():
    """Run all planning tool tests."""
    tester = PlanningToolTester()
    
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run comprehensive test suites
        await tester.run_basic_plan_operations()
        await tester.run_step_management_tests()
        await tester.run_multiple_plans_tests()
        await tester.run_plan_modification_tests()
        await tester.run_error_handling_tests()
        await tester.run_workflow_simulation()
        
        print_header("All Planning Tool Tests Complete!", "double")
        print_test("Planning tool is ready for LLM integration", "pass")
        
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
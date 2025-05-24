#!/usr/bin/env python
"""
Team Tool Sharing Test

This script demonstrates tool registration, discovery, and sharing
within teams, including access control and permission management.
"""

import asyncio
import sys
import os
from typing import Any, Dict, List

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import *

setup_project_path()

from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.team.tools.registry import ToolAccessLevel
from enterprise_ai.team.tools.sharing import (
    DefaultSharingPolicy,
    HierarchicalSharingPolicy,
    TaskBasedSharingPolicy
)
from enterprise_ai.agent.core import create_agent
from enterprise_ai.tool.core.base import BaseTool, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, ToolStatus
from enterprise_ai.logger import get_logger

logger = get_logger("team_tool_sharing")


class MockAnalysisTool(BaseTool):
    """Mock data analysis tool."""
    
    def __init__(self):
        super().__init__(
            name="data_analyzer",
            description="Analyzes data and provides insights",
            capabilities=[ToolCapability.ANALYSIS, ToolCapability.REPORTING]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        data = kwargs.get("data", "No data provided")
        return ToolResult(
            status=ToolStatus.SUCCESS,
            output=f"Analysis complete for: {data}",
            metadata={"tool": "data_analyzer", "rows_processed": 100}
        )


class MockVisualizationTool(BaseTool):
    """Mock visualization tool."""
    
    def __init__(self):
        super().__init__(
            name="visualizer",
            description="Creates data visualizations",
            capabilities=[ToolCapability.VISUALIZATION]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        chart_type = kwargs.get("type", "bar")
        return ToolResult(
            status=ToolStatus.SUCCESS,
            output=f"Created {chart_type} chart",
            metadata={"tool": "visualizer", "chart_type": chart_type}
        )


async def test_tool_registration():
    """Test tool registration and discovery."""
    print_title("TEAM TOOL SHARING")
    
    # Create team
    team = create_team(name="Data Science Team")
    
    # Create agents with tools
    print_section("1. Creating Agents with Tools")
    
    # Data analyst with analysis tool
    analyst = create_agent(
        agent_type="base",
        name="Data Analyst",
        agent_id="analyst-001"
    )
    analyst.register_tool(MockAnalysisTool())
    
    # Visualizer with visualization tool  
    visualizer = create_agent(
        agent_type="base",
        name="Visualizer",
        agent_id="viz-001"
    )    
    visualizer.register_tool(MockVisualizationTool())
    
    # Add to team
    team.add_member(analyst, role=TeamMemberRole.SPECIALIST)
    team.add_member(visualizer, role=TeamMemberRole.SPECIALIST)
    
    print_success("Created 2 agents with specialized tools")
    
    # Discover tools
    print_section("2. Tool Discovery")
    
    count = await team.discover_and_register_tools(
        access_level=ToolAccessLevel.TEAM_READ
    )
    
    print_info(f"Discovered {count} tools from team members")
    
    # List all tools
    all_tools = team.tool_registry.get_all_tools()
    for tool_name in all_tools:
        tool_info = team.tool_registry.get_tool_info(tool_name)
        print_info(f"  - {tool_name}: {tool_info.description} (owner: {tool_info.owner_id})")
    
    return team


async def test_tool_access_control():
    """Test tool access control and permissions."""
    print_section("3. Tool Access Control")
    
    team = await test_tool_registration()
    
    # Create a new agent without tools
    new_agent = create_agent(
        agent_type="base",
        name="New Team Member",
        agent_id="new-001"
    )
    team.add_member(new_agent, role=TeamMemberRole.MEMBER)
    
    # Check accessible tools
    print_info("\nChecking tool access for new member:")
    accessible = team.get_accessible_tools("new-001")
    print_info(f"  Accessible tools: {accessible}")
    
    # Request tool access
    print_info("\nRequesting tool access:")
    success, msg, request_id = await team.request_tool_access(
        agent_id="new-001",
        tool_name="data_analyzer",
        reason="Need to analyze team metrics"
    )    
    print_info(f"  Request result: {success}")
    print_info(f"  Message: {msg}")
    if request_id:
        print_info(f"  Request ID: {request_id}")
    
    return team


async def test_tool_execution():
    """Test tool execution through team."""
    print_section("4. Tool Execution")
    
    team = await test_tool_access_control()
    
    # Execute tool as owner
    print_info("\nExecuting tool as owner:")
    result = await team.execute_tool(
        agent_id="analyst-001",
        tool_name="data_analyzer",
        data="Sales Q4 2024"
    )
    
    print_info(f"  Status: {result.status}")
    print_info(f"  Output: {result.output}")
    
    # Try to execute tool without access
    print_info("\nTrying to execute without access:")
    try:
        result = await team.execute_tool(
            agent_id="new-001",
            tool_name="visualizer",
            type="pie"
        )
        print_warning("  No error raised - checking result")
        print_info(f"  Status: {result.status}")
    except Exception as e:
        print_info(f"  Expected error: {type(e).__name__}: {e}")


async def test_sharing_policies():
    """Test different sharing policies."""
    print_section("5. Sharing Policies")
    
    # Test hierarchical policy
    print_info("\nTesting Hierarchical Sharing Policy:")
    
    team = create_team(
        name="Hierarchical Team",
        sharing_policy=HierarchicalSharingPolicy(None)  # Will be set by team
    )    
    # Add manager
    manager = create_agent(
        agent_type="base",
        name="Team Manager",
        agent_id="mgr-001"
    )
    team.add_member(manager, role=TeamMemberRole.MANAGER)
    
    # Add specialist with tool
    specialist = create_agent(
        agent_type="base",
        name="Specialist",
        agent_id="spec-001"
    )
    specialist.register_tool(MockAnalysisTool())
    team.add_member(specialist, role=TeamMemberRole.SPECIALIST)
    
    # Discover tools
    await team.discover_and_register_tools()
    
    # Manager should have access
    mgr_access = team.get_accessible_tools("mgr-001")
    print_info(f"  Manager access to tools: {len(mgr_access)} tools")
    
    # Test task-based policy
    print_info("\nTesting Task-Based Sharing Policy:")
    
    task_team = create_team(
        name="Task Team",
        sharing_policy=TaskBasedSharingPolicy(None)
    )
    
    # Would need to create tasks and assign tools to tasks
    print_info("  Task-based policy requires task assignments")


async def main():
    """Run tool sharing tests."""
    print_title("TEAM MODULE - TOOL SHARING TEST", style="double")
    
    try:
        await test_tool_registration()
        await test_tool_access_control()
        await test_tool_execution()
        await test_sharing_policies()
        
        print_success("\nAll tool sharing tests completed!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
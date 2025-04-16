"""
Example usage of the Enterprise AI team management system.

This script demonstrates how to create, configure, and utilize teams
for collaborative AI agent tasks.
"""

import asyncio
import uuid
from typing import Dict, List, Optional

from enterprise_ai.agent.factory import create_agent, AgentBuilder
from enterprise_ai.agent.types import Task, TaskStatus
from enterprise_ai.team import (
    BaseTeam,
    HierarchicalTeam,
    TeamCoordinator,
    TeamFactory,
    get_team_factory,
    get_role_registry,
    get_team_registry,
)


async def create_and_use_development_team():
    """Demonstrate creating and using a development team."""
    print("\n=== Creating a Development Team ===\n")
    
    # Get the team factory
    factory = get_team_factory()
    
    # Create a development team
    team = factory.create_development_team(name="Software Development Team")
    
    print(f"Created team: {team.name} (ID: {team.id})")
    print(f"Manager: {team.manager.name}")
    
    print("\nTeam Members:")
    for agent_id, agent in team.members.items():
        role = team.get_member_role(agent_id)
        print(f"- {agent.name} (Role: {role})")
    
    # Create a coordinator for the team
    coordinator = TeamCoordinator(team)
    
    # Create a software development task
    coding_task = Task(
        id=str(uuid.uuid4()),
        description="Implement a user authentication module",
        status=TaskStatus.PENDING,
        metadata={
            "required_capability": "coding",
            "priority": "high",
            "language": "Python",
        }
    )
    
    # Submit the task
    coordinator.submit_task(coding_task)
    print(f"\nSubmitted task: {coding_task.description}")
    
    # Process pending tasks
    processed = coordinator.process_tasks()
    print(f"Processed {processed} tasks")
    
    # Check assignments
    active_tasks = coordinator.get_active_tasks()
    print("\nActive task assignments:")
    for task_id, agent_id in active_tasks.items():
        print(f"- Task {task_id} assigned to agent {agent_id}")
    
    # Simulate task completion
    print("\nSimulating task completion...")
    coordinator.update_task_status(
        coding_task.id,
        TaskStatus.COMPLETED,
        "developer",  # In reality, this would be the actual agent ID
        result_data={
            "code": "# User authentication module\nclass UserAuth:\n    ...",
            "tests_passed": True,
            "coverage": 92.5,
        }
    )
    
    # Collect results
    result = coordinator.collect_result(coding_task.id)
    if result:
        print(f"\nTask completed by: {result.agent_id}")
        print(f"Status: {result.status.name}")
        print("Result data:")
        for key, value in result.data.items():
            print(f"  {key}: {value}")
    
    print("\n=== Development Team Demo Complete ===")


async def create_hierarchical_organization():
    """Demonstrate creating a hierarchical organization with multiple teams."""
    print("\n=== Creating a Hierarchical Organization ===\n")
    
    # Get the team factory
    factory = get_team_factory()
    
    # Create an executive team
    executive = AgentBuilder().with_type("llm").with_role("manager", 
                            additional_context="Executive leadership").with_name("CEO").build()
    
    org = HierarchicalTeam(name="Enterprise Organization")
    org.manager = executive
    
    # Create department teams
    dev_team = factory.create_development_team(name="Engineering Department")
    research_team = factory.create_research_team(name="Research Department")
    analytics_team = factory.create_analytics_team(name="Analytics Department")
    
    # Add teams to the organization
    org.add_subteam(dev_team)
    org.add_subteam(research_team)
    org.add_subteam(analytics_team)
    
    # Get all teams in the registry
    team_registry = get_team_registry()
    team_registry.register_team(org, tags=["organization", "enterprise"])
    team_registry.register_team(dev_team, tags=["department", "engineering"])
    team_registry.register_team(research_team, tags=["department", "research"])
    team_registry.register_team(analytics_team, tags=["department", "analytics"])
    
    print(f"Created organization: {org.name} (ID: {org.id})")
    
    print("\nDepartments:")
    for team_id, team in org.subteams.items():
        print(f"- {team.name} (ID: {team.id})")
        print(f"  Manager: {team.manager.name}")
        print(f"  Members: {len(team.members)}")
    
    # Find teams by tag
    engineering_teams = team_registry.find_teams_by_tag("engineering")
    print(f"\nEngineering teams: {len(engineering_teams)}")
    for team in engineering_teams:
        print(f"- {team.name} (ID: {team.id})")
    
    # Find teams with data analysis capability
    analysis_teams = team_registry.find_teams_by_capability("data_analysis")
    print(f"\nTeams with data analysis capability: {len(analysis_teams)}")
    for team in analysis_teams:
        print(f"- {team.name} (ID: {team.id})")
    
    # Create a cross-functional project team
    project_manager = AgentBuilder().with_type("llm").with_role("manager", 
                                  additional_context="Project management").with_name("Project Manager").build()
    
    project_team = factory.create_cross_functional_team(
        ["development", "design", "research"],
        manager=project_manager,
        name="Product Launch Team"
    )
    
    # Add the project team to the organization
    org.add_subteam(project_team)
    team_registry.register_team(project_team, tags=["project", "cross-functional"])
    
    print(f"\nCreated project team: {project_team.name} (ID: {project_team.id})")
    print(f"Manager: {project_team.manager.name}")
    
    print("\nProject team members:")
    for agent_id, agent in project_team.members.items():
        role = project_team.get_member_role(agent_id)
        print(f"- {agent.name} (Role: {role})")
    
    # Get organization statistics
    print("\nOrganization Statistics:")
    print(f"- Departments: {len(org.subteams)}")
    print(f"- Total members: {len(org.get_all_members())}")
    
    print("\n=== Hierarchical Organization Demo Complete ===")


async def main():
    """Run the demo examples."""
    await create_and_use_development_team()
    await create_hierarchical_organization()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
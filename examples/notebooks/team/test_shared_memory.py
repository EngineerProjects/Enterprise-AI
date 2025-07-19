#!/usr/bin/env python3
"""
Enterprise AI: Shared Memory and Communication Test

This script tests information sharing between agents through shared memory
and basic communication mechanisms.
"""

import asyncio
import sys
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import (
    create_empty_team,
    create_agent_for_team
)
from enterprise_ai.schema import Message
from enterprise_ai.team.memory import SharedMemory
from enterprise_ai.team.communication import TeamMessage
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def shared_memory_test():
    """
    Test shared memory and communication between agents.
    """
    print("🧪 Enterprise AI Shared Memory and Communication Test")
    print("=" * 80)
    
    # Step 1: Create a shared memory instance with initial knowledge
    print("\n📚 Creating shared memory with initial knowledge...")
    
    shared_memory = SharedMemory()
    shared_memory.add_knowledge("project_name", "Healthcare AI Assistant")
    shared_memory.add_knowledge("deadline", "June 30, 2025")
    shared_memory.add_knowledge("key_requirements", [
        "HIPAA compliance",
        "Multi-language support",
        "Integration with EHR systems"
    ])
    
    # Step 2: Create agent roles
    print("\n📋 Creating agent roles...")
    
    planner_role = AgentRole(
        name="Project Planner",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Project Planning Specialist with expertise in breaking down complex projects into manageable tasks. Focus on creating well-structured project plans with clear milestones."
    )
    
    developer_role = AgentRole(
        name="Developer",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Development Specialist with expertise in software engineering. Focus on technical implementation details, architecture decisions, and coding requirements."
    )
    
    # Step 3: Create an empty team with the shared memory
    print("\n🏗️ Creating team with shared memory...")
    
    team = create_empty_team(
        name="CommunicationTeam",
        shared_memory=shared_memory,
        verbose=True
    )
    
    # Step 4: Create individual agents
    print("\n🤖 Creating individual agents...")
    
    planner = create_agent_for_team(
        name="planner",
        role=planner_role,
        reasoning_pattern="cot",
        verbose=True
    )
    
    # Reuse components for efficiency
    developer = create_agent_for_team(
        name="developer",
        role=developer_role,
        llm=planner.llm,
        mcp=planner.mcp,
        reasoning_pattern="swe",
        verbose=True
    )
    
    # Step 5: Add agents to the team
    team.add_agent("planner", planner)
    team.add_agent("developer", developer)
    
    print(f"✅ Team setup complete: {len(team.agents)} agents with shared memory")
    
    # Step 6: Have the planner create a project plan with knowledge from shared memory
    planner_task = """
    Create a project plan for our Healthcare AI Assistant project.
    Use the knowledge in shared memory about project requirements and deadline.
    The plan should include key milestones and technical considerations.
    """
    
    print("\n📝 Assigning task to planner...")
    planner_response = await team.delegate_task("planner", planner_task)
    
    print("✅ Planner completed the task")
    print("\n📊 Planner's Response (excerpt):")
    print("-" * 80)
    # Show a preview
    preview = planner_response[:300] + "..." if len(planner_response) > 300 else planner_response
    print(preview)
    print("-" * 80)
    
    # Step 7: Add the planner's response to shared knowledge
    shared_memory.add_knowledge("project_plan", planner_response)
    
    # Step 8: Now have the developer use the project plan
    developer_task = """
    Review the project plan in shared memory and provide technical implementation details.
    Focus on the architecture needed to meet the HIPAA compliance and EHR integration requirements.
    Outline the key components and technologies you would recommend.
    """
    
    print("\n📝 Assigning task to developer with access to planner's work...")
    developer_response = await team.delegate_task("developer", developer_task)
    
    print("✅ Developer completed the task")
    print("\n📊 Developer's Response (excerpt):")
    print("-" * 80)
    # Show a preview
    preview = developer_response[:300] + "..." if len(developer_response) > 300 else developer_response
    print(preview)
    print("-" * 80)
    
    # Step 9: Create a direct message from developer to planner
    print("\n📨 Testing direct message from developer to planner...")
    
    # Format a team message
    team_msg = TeamMessage(
        sender="developer",
        recipient="planner",
        content=f"""
        I've reviewed your project plan and have some technical concerns about the EHR integration timeline.
        Based on my analysis, we should allocate at least 3 more weeks for security testing.
        Can you adjust the timeline to account for this?
        """,
        msg_type="message"
    )
    
    formatted_message = team.communication.format_team_message(team_msg)
    
    # Send to planner
    planner_response_to_message = await team.delegate_task("planner", formatted_message)
    
    print("✅ Planner responded to the direct message")
    print("\n📊 Planner's Response to Message:")
    print("-" * 80)
    print(planner_response_to_message)
    print("-" * 80)
    
    # Step 10: Verify shared memory
    print("\n📚 Final Shared Memory Contents:")
    print(f"- Knowledge items: {len(shared_memory.knowledge_base)}")
    print(f"- Agent responses: {len(shared_memory.agent_responses)}")
    print(f"- Conversation messages: {len(shared_memory.get_messages())}")
    
    print("\n🏁 Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(shared_memory_test())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
"""
Enterprise AI Team - @Mention System Demo.

Demonstrates how agents use @mentions for direct communication.
"""

from enterprise_ai.team.communication.mentions import MentionParser
from enterprise_ai.team.communication.context import TeamContextBuilder
from enterprise_ai.schema.agent_profile import AgentProfile, AgentStatus

def demo_mention_parsing():
    """Demo the mention parsing functionality."""
    print("🎯 Enterprise AI @Mention System Demo")
    print("=" * 50)
    
    # Create mention parser
    parser = MentionParser()
    
    # Set up valid team members
    team_members = ["alice", "bob", "rosine", "ines", "clara"]
    parser.update_valid_agents(team_members)
    
    # Test different mention scenarios
    test_messages = [
        "@rosine, I need information about 2025 trends",
        "@ines can you check the market analysis data?",
        "@team the project we started this week will be abandoned",
        "I think @alice and @bob should collaborate on this API issue",
        "Regular message without mentions",
        "@rosine @ines please coordinate on the research findings"
    ]
    
    print("\n📝 Testing Message Parsing:")
    print("-" * 30)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. Input: '{message}'")
        
        # Parse the message
        parsed = parser.parse_message(message)
        
        print(f"   Has mentions: {parsed.has_mentions}")
        if parsed.has_mentions:
            print(f"   Mentioned agents: {parsed.mentioned_agents}")
            print(f"   Is broadcast: {parsed.is_broadcast}")
            
            # Validate mentions
            valid, invalid = parser.validate_mentions(parsed)
            if valid:
                print(f"   ✅ Valid mentions: {valid}")
            if invalid:
                print(f"   ❌ Invalid mentions: {invalid}")
    
    return parser

def demo_team_context():
    """Demo the team context building functionality."""
    print("\n\n🤝 Team Context Building Demo")
    print("=" * 50)
    
    # Create mock agents with profiles (simulating your real agent creation)
    class MockAgent:
        def __init__(self, name, profile):
            self.name = name
            self.profile = profile
    
    # Create team profiles
    agents = {
        "alice": MockAgent("alice", AgentProfile.create(
            name="alice",
            role_name="developer",
            role_description="Backend API specialist with Python and FastAPI expertise",
            available_tools=["web_search", "file_read", "code_execute"],
            initial_workload=0.3
        )),
        "rosine": MockAgent("rosine", AgentProfile.create(
            name="rosine", 
            role_name="researcher",
            role_description="Market research specialist focusing on technology trends",
            available_tools=["web_search", "data_analysis", "report_generate"],
            initial_workload=0.7
        )),
        "ines": MockAgent("ines", AgentProfile.create(
            name="ines",
            role_name="business_analyst", 
            role_description="Business analyst specializing in market analysis and strategy",
            available_tools=["data_analysis", "excel_processing", "chart_creation"],
            initial_workload=0.4
        ))
    }
    
    # Create context builder
    context_builder = TeamContextBuilder()
    
    # Generate team context for Alice
    print("\n📋 Team Context for Alice:")
    print("-" * 30)
    alice_context = context_builder.build_team_context("alice", agents)
    print(alice_context)
    
    # Show utility methods
    print("\n🔧 Utility Methods:")
    print("-" * 20)
    print(f"Available members: {context_builder.get_available_members(agents)}")
    print(f"Members with web_search: {context_builder.get_members_with_tool('web_search', agents)}")
    print(f"Research-related members: {context_builder.get_members_by_role_pattern('research', agents)}")

def demo_message_routing():
    """Demo message routing with mentions."""
    print("\n\n📬 Message Routing Demo")
    print("=" * 50)
    
    # Create parser and test routing
    parser = MentionParser()
    parser.update_valid_agents(["alice", "rosine", "ines", "clara"])
    
    # Test message with multiple mentions
    message = "@rosine I found some great 2025 trend data. @ines can you review the business implications?"
    
    print(f"📝 Message: '{message}'")
    print("\n🚀 Routing Results:")
    print("-" * 20)
    
    parsed = parser.parse_message(message)
    routed_messages = parser.create_routed_messages("clara", parsed)
    
    for i, msg in enumerate(routed_messages, 1):
        print(f"{i}. To: @{msg.recipient}")
        print(f"   Type: {msg.msg_type}")
        print(f"   Content: {msg.content}")
        print(f"   Metadata: {msg.metadata}")
        print()

if __name__ == "__main__":
    # Run all demos
    parser = demo_mention_parsing()
    demo_team_context()
    demo_message_routing()
    
    print("\n✅ @Mention System Successfully Implemented!")
    print("\nKey Features:")
    print("• Parse @agent_name for direct messages")
    print("• Parse @team for broadcasts")
    print("• Automatic team context in agent prompts")
    print("• Intelligent message routing")
    print("• Team member validation")
    print("• Capacity-aware team awareness")
    print("\nOptimal Usage:")
    print("• team.add_agent(alice_agent)  # No redundant name!")
    print("• team.refresh_team_context()  # After all agents added")
    print("• Agents automatically use @mentions in responses")

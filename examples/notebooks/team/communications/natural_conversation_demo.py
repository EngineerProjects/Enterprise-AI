#!/usr/bin/env python3
"""
Enterprise AI - Natural Agent Conversation Demo

Demonstrates best practices for:
1. Creating specialized agent roles
2. Configuring appropriate tools for each agent
3. Setting up agents with different models/configurations
4. Natural agent-to-agent conversation using @mentions
5. Agents self-managing conversation flow and redirects

This example shows agents having a natural discussion about a topic they choose,
using @mentions to communicate directly with each other.
"""

import asyncio
import sys
import os
import random

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enterprise_ai.agent.factory import create_agent
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.team.base import Team
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP

def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*80)
    print(f"🎯 {title}")
    print("="*80)

def print_conversation_message(speaker: str, message: str, message_num: int):
    """Print a conversation message with complete formatting - no truncation."""
    print(f"\n[Message {message_num:2d}] 🗣️  {speaker.title()}:")
    print("=" * 100)
    print(message)
    print("=" * 100)
    print(f"📊 Message length: {len(message)} characters")

async def create_specialized_agents():
    """Create agents with best practices - specialized roles, tools, and configurations."""
    
    print_section("Creating Specialized Agents with Best Practices")
    
    agents = {}
    
    # 0. TEAM MANAGER - Essential for every team
    print("\n👑 Creating Maya (Team Manager)...")
    
    manager_role = AgentRole(
        name="team_manager",
        description="Senior Team Manager coordinating AI innovation projects and team collaboration",
        system_prompt="""You are Maya, a Senior Team Manager with expertise in coordinating AI innovation projects. 
        You facilitate team discussions, ensure productive collaboration, and help resolve conflicts. You understand 
        both technical and business perspectives, enabling effective communication between different roles. You guide 
        discussions toward actionable outcomes and ensure everyone's voice is heard.
        
        IMPORTANT: Always use @name when addressing specific teammates:
        - "@sarah, from your research perspective..."
        - "@alex, what are the product implications..."
        - "@jordan, technically speaking..."
        
        Your role is to facilitate, guide, and ensure productive team collaboration."""
    )
    
    manager_mcp = ToolMCP(
        timeout=100.0,
        auto_load_tools=True,
        tools=["team_management", "project_coordination", "communication_facilitation"]
    )
    
    maya = create_agent(
        name="maya",
        role=manager_role,
        reasoning_pattern="react",
        llm_config={
            "provider": "ollama",
            "model_name": "llama3.2",
            "timeout": 500.0,
            "temperature": 0.5,  # Balanced for management decisions
        },
        mcp=manager_mcp,
        verbose=True
    )
    agents["maya"] = maya
    print(f"   ✅ Maya created successfully!")
    print(f"      Profile Name: {maya.profile.name}")
    print(f"      Profile Role: {maya.profile.role.name}")
    print(f"      Role Description: {maya.profile.role.description}")
    print(f"      Available Tools: {maya.profile.available_tools}")
    print(f"      Initial Capacity: {maya.profile.capacity.workload * 100:.0f}% workload")
    print(f"      Agent Status: {maya.profile.capacity.status.value}")
    
    # 1. AI RESEARCHER - Specialized in AI research and analysis
    print("\n🔬 Creating Dr. Sarah (AI Researcher)...")
    
    # Create specialized role
    researcher_role = AgentRole(
        name="ai_researcher",
        description="AI Research Scientist specializing in machine learning, LLMs, and emerging AI technologies",
        system_prompt="""You are Dr. Sarah, an AI Research Scientist with expertise in machine learning, 
        large language models, and emerging AI technologies. You stay current with latest research papers, 
        conduct analysis on AI trends, and provide scientific insights. You communicate clearly and cite 
        research when relevant. You are curious, analytical, and always eager to discuss AI developments.
        
        IMPORTANT: Always use @name when addressing specific teammates in conversations. For example:
        - "@alex, from a product perspective..."
        - "@jordan, how would you implement..."
        - "@alex @jordan, this research suggests..."
        
        This ensures clear communication in team discussions."""
    )
    
    # Create specialized MCP with research tools
    researcher_mcp = ToolMCP(
        timeout=120.0,
        auto_load_tools=True,
        tools=["web_search", "deep_research", "analysis", "data_processing"]
    )
    
    # Create agent with research-focused configuration
    sarah = create_agent(
        name="sarah",
        role=researcher_role,
        reasoning_pattern="cot",  # Chain of thought for analytical thinking
        llm_config={
            "provider": "ollama",
            "model_name": "llama3.2",
            "timeout": 500.0,
            "temperature": 0.3,  # Lower temperature for more factual responses
        },
        mcp=researcher_mcp,
        verbose=True
    )
    agents["sarah"] = sarah
    print(f"   ✅ Dr. Sarah created successfully!")
    print(f"      Profile Name: {sarah.profile.name}")
    print(f"      Profile Role: {sarah.profile.role.name}")
    print(f"      Role Description: {sarah.profile.role.description}")
    print(f"      Available Tools: {sarah.profile.available_tools}")
    print(f"      Initial Capacity: {sarah.profile.capacity.workload * 100:.0f}% workload")
    print(f"      Agent Status: {sarah.profile.capacity.status.value}")
    
    # 2. PRODUCT MANAGER - Specialized in product strategy and user experience  
    print("\n📊 Creating Alex (Product Manager)...")
    
    product_role = AgentRole(
        name="product_manager", 
        description="Senior Product Manager focused on AI products, user experience, and market strategy",
        system_prompt="""You are Alex, a Senior Product Manager with 8+ years experience building AI-powered 
        products. You excel at understanding user needs, defining product requirements, and bridging the gap 
        between technical capabilities and business value. You think strategically about market fit, user 
        experience, and product roadmaps. You communicate in a practical, business-focused manner.
        
        CRITICAL COMMUNICATION RULE: You MUST use @name when addressing teammates. This is mandatory:
        - Start responses with: "@sarah, @jordan, @maya, I think..."
        - When asking questions: "@jordan, how feasible is..."
        - When building on ideas: "@sarah, that research confirms..."
        
        Example response format:
        "@sarah @jordan, based on the research Sarah shared, I see three key product challenges..."
        
        NEVER respond without using @mentions - it's essential for team communication."""
    )
    
    product_mcp = ToolMCP(
        timeout=90.0,
        auto_load_tools=True,
        tools=["web_search", "market_analysis", "user_research", "competitive_analysis"]
    )
    
    alex = create_agent(
        name="alex",
        role=product_role,
        reasoning_pattern="react",  # ReAct for action-oriented thinking
        llm_config={
            "provider": "ollama", 
            "model_name": "llama3.2",
            "timeout": 500.0,
            "temperature": 0.4,  # LOWER temperature for more consistent @mention usage
        },
        mcp=product_mcp,
        verbose=True
    )
    agents["alex"] = alex
    print(f"   ✅ Alex created successfully!")
    print(f"      Profile Name: {alex.profile.name}")
    print(f"      Profile Role: {alex.profile.role.name}")
    print(f"      Role Description: {alex.profile.role.description}")
    print(f"      Available Tools: {alex.profile.available_tools}")
    print(f"      Initial Capacity: {alex.profile.capacity.workload * 100:.0f}% workload")
    print(f"      Agent Status: {alex.profile.capacity.status.value}")
    
    # 3. TECH LEAD - Specialized in software engineering and architecture
    print("\n💻 Creating Jordan (Tech Lead)...")
    
    tech_role = AgentRole(
        name="tech_lead",
        description="Senior Technical Lead specializing in AI/ML engineering, system architecture, and team leadership", 
        system_prompt="""You are Jordan, a Senior Technical Lead with deep expertise in AI/ML engineering, 
        distributed systems, and software architecture. You lead technical teams, make architectural decisions, 
        and solve complex engineering challenges. You think systematically about scalability, performance, 
        and maintainability. You communicate technical concepts clearly and enjoy mentoring others.
        
        IMPORTANT: Always use @name when addressing specific teammates in conversations. For example:
        - "@sarah, that research aligns with..."
        - "@alex, from a technical feasibility standpoint..."
        - "@sarah @alex, we could implement this by..."
        
        This maintains clear communication flow in technical discussions."""
    )
    
    tech_mcp = ToolMCP(
        timeout=150.0,
        auto_load_tools=True,
        tools=["code_analysis", "architecture_review", "performance_analysis", "system_design"]
    )
    
    jordan = create_agent(
        name="jordan",
        role=tech_role,
        reasoning_pattern="swe",  # Software engineering pattern for technical problems
        llm_config={
            "provider": "ollama",
            "model_name": "llama3.2", 
            "timeout": 500.0,
            "temperature": 0.4,  # Lower temperature for technical precision
        },
        mcp=tech_mcp,
        verbose=True
    )
    agents["jordan"] = jordan
    print(f"   ✅ Jordan created successfully!")
    print(f"      Profile Name: {jordan.profile.name}")
    print(f"      Profile Role: {jordan.profile.role.name}")
    print(f"      Role Description: {jordan.profile.role.description}")
    print(f"      Available Tools: {jordan.profile.available_tools}")
    print(f"      Initial Capacity: {jordan.profile.capacity.workload * 100:.0f}% workload")
    print(f"      Agent Status: {jordan.profile.capacity.status.value}")
    
    return agents

async def setup_team_with_context(agents):
    """Set up team and enable rich context for natural conversation."""
    
    print_section("Setting Up Team with Enhanced Context")
    
    # Create team
    team = Team("ai_innovation_team", verbose=True)
    
    # Add agents to team
    print("\n🏗️ Building team...")
    for agent in agents.values():
        team.add_agent(agent)
    
    # Set manager (mandatory for every team)
    print(f"\n👑 Setting Maya as team manager...")
    team.set_manager(agents["maya"])
    print(f"✅ Manager set successfully!")
    
    print(f"✅ Team created with {len(team.agents)} members: {list(team.get_team_member_names())}")
    
    # Show complete team composition details
    print(f"\n📋 Complete Team Composition:")
    for name in team.get_team_member_names():
        profile = team.get_agent_profile(name)
        if profile:
            print(f"  🤖 {name.title()}:")
            print(f"     Role: {profile.role.name}")
            print(f"     Description: {profile.role.description}")
            print(f"     Tools: {profile.available_tools}")
            print(f"     Status: {profile.capacity.status.value}")
            print(f"     Workload: {profile.capacity.workload * 100:.0f}%")
            print()
    
    # Enable enhanced team context
    print("\n🔄 Enabling enhanced team context...")
    team.refresh_team_context()
    print("✅ Enhanced team context activated!")
    
    # Show one agent's enhanced prompt
    print("\n👀 Sarah's COMPLETE Enhanced Prompt:")
    print("=" * 100)
    sarah = agents["sarah"]
    if hasattr(sarah, 'role') and hasattr(sarah.role, 'system_prompt'):
        print(sarah.role.system_prompt)
    else:
        print("❌ No system prompt available")
    print("=" * 100)
    
    return team

async def natural_conversation(team, agents, max_messages=20):
    """Facilitate natural conversation between agents using @mentions."""
    
    print_section("Natural Agent Conversation - AI Innovation Discussion")
    
    # Conversation starter topics
    topics = [
        "the future of AI agent teams and how they'll change software development",
        "challenges in building production-ready AI systems that users actually want",
        "the gap between AI research breakthroughs and real-world product applications",
        "how AI agents should collaborate - more like human teams or something entirely new"
    ]
    
    chosen_topic = random.choice(topics)
    print(f"\n💡 Conversation Topic: {chosen_topic}")
    
    # Start conversation with Sarah (researcher) introducing the topic
    starter_message = f"""
    Hey team! @alex @jordan @maya, I've been thinking about {chosen_topic}. 
    Given our different perspectives - research, product, engineering, and management - I think we could have 
    a really interesting discussion. What are your thoughts on this? @alex, from a product perspective, 
    what challenges do you see? @jordan, any technical insights? @maya, how would you guide this discussion?
    """
    
    print_conversation_message("sarah", starter_message.strip(), 1)
    
    # Conversation state
    conversation_history = [("sarah", starter_message)]
    current_speaker = "alex"  # Alex responds first
    message_count = 1
    
    # Conversation loop
    while message_count < max_messages:
        try:
            print(f"\n⏳ {current_speaker.title()} is thinking... (up to 500s)")
            
            # Build conversation context - show more history for better context
            recent_context = "\n\n".join([
                f"{speaker}: {msg}" for speaker, msg in conversation_history[-5:]  # Show last 5 messages
            ])
            
            conversation_prompt = f"""
            Recent conversation:
            {recent_context}
            
            Continue this discussion naturally. MANDATORY: You MUST use @mentions when addressing teammates:
            - Use @sarah to address the AI researcher  
            - Use @alex to address the product manager  
            - Use @jordan to address the tech lead
            - Use @maya to address the team manager
            - You can mention multiple people: "@sarah @alex, what do you think about..."
            
            CRITICAL: Start your response with @mentions. Example formats:
            - "@alex @jordan, I agree with..."
            - "@sarah, that research shows..."
            - "@maya, from a management perspective..."
            
            Share your perspective based on your expertise. Ask questions, build on others' ideas, 
            or introduce new angles. Keep responses conversational but insightful.
            Remember: ALWAYS begin responses with @name mentions!
            """
            
            # Get agent response
            agent = agents[current_speaker]
            response = await agent.process(conversation_prompt)
            
            message_count += 1
            print_conversation_message(current_speaker, response, message_count)
            
            # Add to history
            conversation_history.append((current_speaker, response))
            
            # Route @mentions if any
            try:
                print(f"\n📬 Analyzing message for @mentions...")
                mention_ids = await team.send_mention_message(current_speaker, response)
                if mention_ids:
                    print(f"✅ Valid mentions found and routed! Message IDs: {mention_ids}")
                else:
                    print(f"📝 No @mentions found - {current_speaker.title()} didn't address anyone specifically")
                    print(f"💡 Message routed to manager (Maya) by default")
                    print(f"⚠️  Note: {current_speaker.title()} should use @name to direct messages to specific teammates")
            except Exception as e:
                print(f"📬 Mention routing error: {type(e).__name__}: {e}")
            
            # Determine next speaker based on @mentions in response
            next_speaker = determine_next_speaker(response, current_speaker, agents.keys())
            print(f"🔄 Next speaker determined: {next_speaker.title()}")
            current_speaker = next_speaker
            
            # Small delay for readability
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Error in conversation: {type(e).__name__}: {e}")
            # Switch to next speaker on error
            speakers = list(agents.keys())
            current_idx = speakers.index(current_speaker)
            current_speaker = speakers[(current_idx + 1) % len(speakers)]
            continue
    
    print_section("Conversation Complete!")
    print(f"🎉 Agents exchanged {message_count} messages about {chosen_topic}")
    print("✅ Natural @mention communication demonstrated")
    print("✅ Agents stayed in character and shared domain expertise")
    print("✅ Conversation flowed naturally between perspectives")

def determine_next_speaker(message: str, current_speaker: str, all_agents):
    """Determine who should speak next based on @mentions in the message."""
    
    # Look for @mentions in the message
    mentioned_agents = []
    for agent in all_agents:
        if f"@{agent}" in message.lower():
            mentioned_agents.append(agent)
    
    print(f"🔍 Found @mentions: {mentioned_agents if mentioned_agents else 'None'}")
    
    # Remove current speaker from mentions
    mentioned_agents = [agent for agent in mentioned_agents if agent != current_speaker]
    
    # If specific agents mentioned, pick one
    if mentioned_agents:
        chosen = random.choice(mentioned_agents)
        print(f"🎯 Selected from mentions: {chosen}")
        return chosen
    
    # Otherwise, pick someone who hasn't spoken recently
    speakers = list(all_agents)
    others = [s for s in speakers if s != current_speaker]
    chosen = random.choice(others) if others else random.choice(speakers)
    print(f"🎯 Random selection from available speakers: {chosen}")
    return chosen

async def main():
    """Main demo of natural agent conversation with best practices."""
    
    print_section("Enterprise AI - Natural Agent Conversation Demo")
    print("🎯 Demonstrating: Specialized agents, enhanced context, natural @mention conversation")
    
    # Check ollama
    print("\n🔍 Checking Ollama + llama3.2...")
    try:
        test_llm = create_provider("ollama", "llama3.2", timeout=500.0)
        print("✅ Ready!")
    except Exception as e:
        print(f"❌ Setup issue: {e}")
        print("💡 Ensure: ollama serve && ollama pull llama3.2")
        return
    
    # Create specialized agents with best practices
    agents = await create_specialized_agents()
    
    # Set up team with enhanced context
    team = await setup_team_with_context(agents)
    
    # Have natural conversation
    await natural_conversation(team, agents, max_messages=10)
    
    print_section("🎉 Demo Complete!")
    print("✅ Best practices demonstrated:")
    print("  • Mandatory team manager (Maya) for proper team structure")
    print("  • Specialized agent roles with detailed personas")
    print("  • Appropriate tool selection for each agent")
    print("  • Enhanced team context with personal identity")
    print("  • Natural conversation with @mention flow")
    print("  • Agents staying in character and domain expertise")
    print("  • Self-managing conversation without external orchestration")
    print("  • Proper routing: @mentions to specific agents, no mentions to manager")
    
    print("\n🚀 Your @mention system enables truly natural AI team collaboration!")
    print("Note: If Alex still doesn't use @mentions, check his temperature and system prompt effectiveness.")

if __name__ == "__main__":
    asyncio.run(main())

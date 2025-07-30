"""
Enhanced Sandbox Usage Examples for Enterprise-AI MCP

This module demonstrates the new user-friendly sandbox system with tool groups,
Docker validation, and intuitive configuration.
"""

import asyncio
from typing import List

# Import the enhanced MCP functions
from enterprise_ai.mcp import (
    create_local_mcp,
    create_execution_sandbox_mcp,
    create_file_sandbox_mcp,
    create_full_sandbox_mcp,
    EnhancedSandboxConfig,
    create_execution_sandbox,
    create_custom_sandbox,
    TOOL_GROUPS,
)
from enterprise_ai.schema import ToolCall, Function


def example_1_default_local_execution():
    """
    Example 1: Default Local Execution
    
    By default, all tools run locally without Docker (as requested).
    """
    print("=== Example 1: Default Local Execution ===")
    
    # Default behavior: everything runs locally
    mcp = create_local_mcp()
    
    # Get sandbox information
    sandbox_info = mcp.get_sandbox_info()
    
    print(f"📊 Sandbox Status: {'Enabled' if sandbox_info['sandbox_enabled'] else 'Disabled'}")
    print(f"🛠️  Available Tools: {len(mcp.get_available_tools())}")
    print(f"🏠 Local Tools: {sandbox_info['local_count']}")
    print(f"🐳 Sandboxed Tools: {sandbox_info['sandboxed_count']}")
    
    # Print detailed status
    mcp.print_sandbox_status()
    
    print("✅ All tools will run locally on your system")


def example_2_execution_sandbox():
    """
    Example 2: Execution Tools Sandbox
    
    Shows how to sandbox only execution tools (bash, python, process)
    with automatic Docker validation.
    """
    print("\n=== Example 2: Execution Tools Sandbox ===")
    
    try:
        # Create MCP with execution sandbox (defaults to "execution" group if no group specified)
        mcp = create_execution_sandbox_mcp(
            docker_image="python:3.12-slim",  # Specify Docker image
            timeout=60,                       # Execution timeout
            memory_limit="512m",              # Container memory limit
            validate_docker=True              # Validate Docker is available
        )
        
        # Get sandbox information
        sandbox_info = mcp.get_sandbox_info()
        
        print(f"🐳 Docker Image: {sandbox_info['docker_image']}")
        print(f"📦 Tool Groups: {sandbox_info['tool_groups']}")
        print(f"⚡ Sandboxed Tools: {sandbox_info['sandboxed_tools']}")
        print(f"🏠 Local Tools: {len(sandbox_info['local_tools'])} tools")
        
        # Print detailed status
        mcp.print_sandbox_status()
        
        print("✅ Execution tools (bash, python, process) will run in Docker sandbox")
        print("🔒 File and network tools will run locally for better performance")
        
    except ValueError as e:
        print(f"❌ Sandbox creation failed: {e}")
        print("💡 Make sure Docker is installed and running")


def example_3_file_tools_sandbox():
    """
    Example 3: File Tools Sandbox
    
    Shows how to sandbox file tools while keeping execution tools local.
    """
    print("\n=== Example 3: File Tools Sandbox ===")
    
    try:
        # Create MCP with file tools sandbox
        mcp = create_file_sandbox_mcp(
            docker_image="python:3.12-slim",
            memory_limit="256m",  # Less memory for file operations
            timeout=30,           # Shorter timeout for file operations
            validate_docker=False  # Skip validation for this example
        )
        
        sandbox_info = mcp.get_sandbox_info()
        
        print(f"📁 Sandboxed file tools: {sandbox_info['sandboxed_tools']}")
        print(f"⚡ Local execution tools: Available for local execution")
        
        # Show which tools are in each group
        print(f"\n📦 Tool Group 'file' contains: {TOOL_GROUPS['file']}")
        print(f"📦 Tool Group 'execution' contains: {TOOL_GROUPS['execution']}")
        
        mcp.print_sandbox_status()
        
    except ValueError as e:
        print(f"❌ File sandbox creation failed: {e}")


def example_4_full_sandbox():
    """
    Example 4: Full Sandbox (All Tools)
    
    Shows how to sandbox ALL tools for maximum security.
    """
    print("\n=== Example 4: Full Sandbox (All Tools) ===")
    
    try:
        # Create MCP with full sandbox
        mcp = create_full_sandbox_mcp(
            docker_image="ubuntu:22.04",      # More complete OS
            memory_limit="1g",               # More memory for all tools
            cpu_limit=1.0,                   # Full CPU access
            timeout=120,                     # Longer timeout
            network_enabled=False,           # Disable network for security
            validate_docker=False           # Skip validation for example
        )
        
        sandbox_info = mcp.get_sandbox_info()
        
        print(f"🔐 Security Level: Maximum (all tools sandboxed)")
        print(f"🐳 Container: {sandbox_info['docker_image']}")
        print(f"💾 Resources: {sandbox_info['memory_limit']} RAM, {sandbox_info['cpu_limit']} CPU")
        print(f"🌐 Network: {'Enabled' if sandbox_info['network_enabled'] else 'Disabled'}")
        
        mcp.print_sandbox_status()
        
        print("🛡️  All tools run in isolated Docker container")
        print("🔒 Maximum security for untrusted code execution")
        
    except ValueError as e:
        print(f"❌ Full sandbox creation failed: {e}")


def example_5_custom_sandbox():
    """
    Example 5: Custom Sandbox Configuration
    
    Shows how to create custom sandbox configurations with specific tools.
    """
    print("\n=== Example 5: Custom Sandbox Configuration ===")
    
    try:
        # Create custom sandbox with specific tools
        custom_config = create_custom_sandbox(
            docker_image="python:3.11-alpine",  # Lightweight Python image
            specific_tools=["python_execute", "file_editor"],  # Only these tools
            exclude_tools=["bash"],              # Exclude bash even if specified
            memory_limit="128m",                # Minimal resources
            timeout=45,
            network_enabled=False,
            validate_docker=False
        )
        
        # Create MCP with custom config
        from enterprise_ai.mcp import create_simple_mcp
        mcp = create_simple_mcp(sandbox_config=custom_config)
        
        sandbox_info = mcp.get_sandbox_info()
        
        print(f"🎯 Custom Configuration:")
        print(f"   🐳 Image: {sandbox_info['docker_image']}")
        print(f"   🔧 Sandboxed: {sandbox_info['sandboxed_tools']}")
        print(f"   🏠 Local: {len(sandbox_info['local_tools'])} other tools")
        
        mcp.print_sandbox_status()
        
        print("✨ Custom sandbox with exactly the tools you specify")
        
    except ValueError as e:
        print(f"❌ Custom sandbox creation failed: {e}")


def example_6_configuration_comparison():
    """
    Example 6: Configuration Comparison
    
    Compare different sandbox configurations side by side.
    """
    print("\n=== Example 6: Configuration Comparison ===")
    
    configs = [
        ("Local (No Sandbox)", create_local_mcp()),
        ("Execution Sandbox", None),  # Will create if Docker available
        ("File Sandbox", None),       # Will create if Docker available
    ]
    
    print("📊 Configuration Comparison:")
    print("-" * 80)
    print(f"{'Configuration':<20} {'Sandbox':<8} {'Docker Image':<20} {'Sandboxed Tools':<15}")
    print("-" * 80)
    
    for config_name, mcp in configs:
        if mcp is None:
            # Try to create sandbox configs
            try:
                if "Execution" in config_name:
                    mcp = create_execution_sandbox_mcp(validate_docker=False)
                elif "File" in config_name:
                    mcp = create_file_sandbox_mcp(validate_docker=False)
            except:
                print(f"{config_name:<20} {'Failed':<8} {'N/A':<20} {'N/A':<15}")
                continue
        
        info = mcp.get_sandbox_info()
        sandbox_status = "Yes" if info["sandbox_enabled"] else "No"
        docker_image = info.get("docker_image", "None")[:18] if info.get("docker_image") else "None"
        sandboxed_count = info["sandboxed_count"]
        
        print(f"{config_name:<20} {sandbox_status:<8} {docker_image:<20} {sandboxed_count:<15}")
    
    print("-" * 80)


async def example_7_tool_execution_demo():
    """
    Example 7: Tool Execution Demo
    
    Demonstrates actual tool execution with sandbox routing.
    """
    print("\n=== Example 7: Tool Execution Demo ===")
    
    try:
        # Create execution sandbox MCP
        mcp = create_execution_sandbox_mcp(
            docker_image="python:3.12-slim",
            validate_docker=False  # Skip validation for demo
        )
        
        print("🧪 Demonstrating tool execution routing...")
        
        # Create sample tool calls
        tool_calls = [
            ToolCall(
                id="call_1",
                function=Function(
                    name="python_execute",  # This should run in sandbox
                    arguments={"code": "print('Hello from sandbox!')"}
                )
            ),
            ToolCall(
                id="call_2", 
                function=Function(
                    name="web_search",      # This should run locally
                    arguments={"query": "Python tutorial"}
                )
            )
        ]
        
        # Show routing information
        sandbox_info = mcp.get_sandbox_info()
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            is_sandboxed = tool_name in sandbox_info["sandboxed_tools"]
            location = "🐳 Docker Sandbox" if is_sandboxed else "🏠 Local System"
            print(f"   🔧 {tool_name} → {location}")
        
        print(f"\n📊 Routing Summary:")
        print(f"   🐳 Sandbox tools: {sandbox_info['sandboxed_count']}")
        print(f"   🏠 Local tools: {sandbox_info['local_count']}")
        
        # Note: Actual execution would require Docker setup
        print(f"\n💡 Note: Actual execution requires Docker to be running")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")


def example_8_docker_validation():
    """
    Example 8: Docker Validation
    
    Shows Docker validation features to prevent errors.
    """
    print("\n=== Example 8: Docker Validation ===")
    
    # Test Docker validation
    print("🔍 Testing Docker validation...")
    
    try:
        # Try to create sandbox with validation
        config = EnhancedSandboxConfig(
            enabled=True,
            docker_image="python:3.12-slim",
            tool_groups=["execution"],
            validate_docker=True  # This will check Docker
        )
        
        print("✅ Docker validation passed!")
        print(f"   🐳 Image '{config.docker_image}' is available")
        print("   🔧 Docker daemon is running")
        
    except ValueError as e:
        print(f"❌ Docker validation failed: {e}")
        print("💡 This is expected if Docker isn't installed/running")
        
        # Show how to disable validation
        print("\n🛠️  To skip validation, use validate_docker=False:")
        print("   config = create_execution_sandbox(..., validate_docker=False)")


async def main():
    """Run all enhanced sandbox examples."""
    print("🚀 Enhanced Enterprise-AI Sandbox System Examples")
    print("=" * 70)
    print("This demonstrates the new user-friendly sandbox configuration")
    print("that meets your requirements for intuitive Docker integration.")
    print("=" * 70)
    
    # Run all examples
    example_1_default_local_execution()
    example_2_execution_sandbox()
    example_3_file_tools_sandbox()
    example_4_full_sandbox()
    example_5_custom_sandbox()
    example_6_configuration_comparison()
    await example_7_tool_execution_demo()
    example_8_docker_validation()
    
    print(f"\n" + "=" * 70)
    print("✅ All Enhanced Sandbox Examples Completed!")
    print(f"\n🎯 Key Benefits of Enhanced Sandbox System:")
    print(f"   • 🏠 Default: All tools run locally (no Docker required)")
    print(f"   • 🐳 Optional: Easy sandbox with Docker image specification")
    print(f"   • 📦 Tool Groups: 'execution', 'file', 'network', 'all'")
    print(f"   • 🔍 Validation: Automatic Docker/image validation")
    print(f"   • 🛡️  Security: Granular control over which tools are sandboxed")
    print(f"   • 🚀 Performance: Only dangerous tools use sandbox by default")
    print(f"   • 💡 User-Friendly: Clear error messages and configuration help")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

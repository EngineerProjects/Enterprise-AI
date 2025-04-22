#!/usr/bin/env python
"""
Enterprise AI Prompt System Examples

This notebook demonstrates using the prompt management system for:
- Loading and formatting prompt templates
- Creating custom templates
- Using templates with various parameters
- Role-specific prompts
"""

import os
import sys
from pathlib import Path

# Import common utilities
from utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    separator
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.prompt import (
    PromptTemplate,
    PromptLibrary,
    get_prompt_library,
    get_prompt,
    format_prompt,
    create_composite_prompt,
    combine_prompts
)

def test_default_prompts():
    """Test loading and using the default prompts."""
    print_section("Testing Default Prompts")

    # Get the prompt library
    library = get_prompt_library()

    # List available prompts
    prompts = library.list_prompts()
    print_info(f"Available prompts: {len(prompts)}")
    for i, prompt_id in enumerate(prompts):
        print(f"{i+1}. {prompt_id}")

    # Try to load and format a role prompt
    developer_prompt = get_prompt("roles.developer")
    if developer_prompt:
        print_success("Successfully loaded developer role prompt")
        print_info("Developer prompt template:")
        print(developer_prompt)

        # Format the prompt with additional context
        formatted = format_prompt("roles.developer", additional_context="Focus on Python development")
        if formatted:
            print_info("\nFormatted developer prompt with additional context:")
            print(formatted)
        else:
            print_error("Failed to format developer prompt")
    else:
        print_error("Failed to load developer role prompt")

    # Try with manager role
    manager_prompt = get_prompt("roles.manager")
    if manager_prompt:
        print_success("Successfully loaded manager role prompt")
        formatted = format_prompt("roles.manager", additional_context="Managing a software development team")
        if formatted:
            print_info("\nFormatted manager prompt:")
            print(formatted)
    else:
        print_error("Failed to load manager role prompt")

def test_custom_prompts():
    """Test creating and using custom prompts."""
    print_section("Testing Custom Prompts")

    # Get the prompt library
    library = get_prompt_library()

    # Create a custom prompt template
    custom_template = """
You are an AI assistant specializing in $domain.

Your tasks include:
- $task1
- $task2
- $task3

Additional instructions: $additional_instructions
"""

    # Add the prompt to the library
    library.add_prompt(
        "custom.specialist",
        custom_template,
        metadata={"author": "User", "version": "1.0"}
    )

    # Format the custom prompt
    formatted = library.format_prompt(
        "custom.specialist",
        domain="data science",
        task1="Analyze datasets",
        task2="Build predictive models",
        task3="Visualize results",
        additional_instructions="Focus on interpretability"
    )

    if formatted:
        print_success("Successfully created and formatted custom prompt")
        print_info("Formatted custom prompt:")
        print(formatted)
    else:
        print_error("Failed to format custom prompt")

    # Create another custom prompt for a different domain
    custom_template2 = """
# $title

## Overview
$overview

## Requirements
$requirements

## Constraints
$constraints

## Timeline
$timeline
"""

    # Add the prompt to the library
    library.add_prompt(
        "custom.project",
        custom_template2,
        metadata={"author": "User", "version": "1.0", "type": "project_brief"}
    )

    # Format the custom prompt
    formatted2 = library.format_prompt(
        "custom.project",
        title="AI Assistant Project",
        overview="Develop an AI assistant for customer support",
        requirements="Must handle common customer queries and integrate with our CRM",
        constraints="Must comply with privacy regulations and work in real-time",
        timeline="Development to be completed within 3 months"
    )

    if formatted2:
        print_success("Successfully created and formatted project brief prompt")
        print_info("Formatted project brief:")
        print(formatted2)
    else:
        print_error("Failed to format project brief prompt")

def create_prompt_template_programmatically():
    """Create prompt templates programmatically."""
    print_section("Creating Prompt Templates Programmatically")

    # Create a simple template
    template = PromptTemplate(
        """
I want you to act as a $persona.

Your task is to $task.

Please follow these guidelines:
$guidelines

Remember to be $tone and $style in your approach.
""",
        metadata={"purpose": "Role playing", "category": "creative"}
    )

    # Format the template
    formatted = template.format(
        persona="historical detective",
        task="investigate a mysterious event from the past using only the clues provided",
        guidelines="- Use deductive reasoning\n- Consider the historical context\n- Look for patterns in the evidence",
        tone="analytical",
        style="thorough"
    )

    print_info("Prompt template created programmatically:")
    print(formatted)

    # Create a more complex template
    template2 = PromptTemplate(
        """
# $title

## Background
$background

## Current State
$current_state

## Desired Outcome
$desired_outcome

## Your Task
As an AI assistant, you need to $task.

## Constraints
$constraints

## Output Format
$output_format
""",
        metadata={"purpose": "Technical task", "category": "professional"}
    )

    # Format the template
    formatted2 = template2.format(
        title="Database Migration Plan",
        background="Our company has been using an outdated MySQL database system.",
        current_state="The system is slow and doesn't meet our scaling needs.",
        desired_outcome="A modern, scalable, and reliable database system.",
        task="create a step-by-step migration plan from MySQL to PostgreSQL",
        constraints="- Minimal downtime required\n- Must preserve all historical data\n- Security compliance must be maintained",
        output_format="Provide a detailed plan with timeline, resource requirements, risks, and mitigation strategies."
    )

    print_info("\nComplex prompt template created programmatically:")
    print(formatted2)

def test_composite_prompts():
    """Test combining role and system prompts."""
    print_section("Testing Composite Prompts")

    # Get the prompt library
    library = get_prompt_library()

    # Use the new combine_prompts function
    combined = combine_prompts(
        ["system.with_tools", "roles.developer"],
        tools_description="search: Search the web\ncode_exec: Execute code",
        additional_context="Focus on Python best practices."
    )

    if combined:
        print_success("Successfully combined system and role prompts")
        print_info("Combined prompt:")
        print(combined)
    else:
        print_error("Failed to combine prompts")

    # Use the new create_composite_prompt function
    composite = create_composite_prompt(
        "developer",
        "with_tools",
        tools_description="search: Search the web\ncode_exec: Execute code",
        additional_context="Focus on Python best practices."
    )

    if composite:
        print_success("Successfully created composite prompt")
        print_info("Composite prompt:")
        print(composite)
    else:
        print_error("Failed to create composite prompt")

def main():
    """Run all prompt examples."""
    print_title("Enterprise AI Prompt System Examples")

    # Test default prompts
    test_default_prompts()
    separator()

    # Test custom prompts
    test_custom_prompts()
    separator()

    # Create programmatic templates
    create_prompt_template_programmatically()
    separator()

    # Test composite prompts
    test_composite_prompts()
    separator()

    print_success("All prompt examples completed!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Test for CreateChatCompletion Tool via MCP

This script demonstrates how to use the CreateChatCompletion tool through the MCP system
to create structured formatted content with specific output types.
"""

import asyncio
import sys
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Import utilities for better formatting
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components directly to avoid circular imports
from enterprise_ai.tool.core.base import ToolConfig
from enterprise_ai.tool.content.chat_completion import CreateChatCompletion
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("chat_completion_test")

# Define some sample models to use with the tool
class PersonInfo(BaseModel):
    """Example model for structured person information."""
    name: str = Field(description="The person's full name")
    age: int = Field(description="The person's age in years")
    occupation: Optional[str] = Field(default=None, description="The person's job or profession")

class ProductReview(BaseModel):
    """Example model for structured product reviews."""
    product_name: str = Field(description="Name of the product")
    rating: float = Field(description="Rating from 1.0 to 5.0", ge=1.0, le=5.0)
    review_text: str = Field(description="Text of the review")
    pros: List[str] = Field(default_factory=list, description="List of positive aspects")
    cons: List[str] = Field(default_factory=list, description="List of negative aspects")


async def test_chat_completion_tool():
    """Test the CreateChatCompletion tool using the MCP system."""
    print_title("TESTING CREATE CHAT COMPLETION TOOL VIA MCP")

    # Create a test session
    session_id = "chat-completion-test"
    client = None

    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Test 1: Basic string response
        print_section("Test 1: Basic String Response")

        # Create and register the tool with string response type
        string_tool = CreateChatCompletion(
            name="chat_completion_string",
            description="Creates a formatted text response.",
            response_type=str
        )

        client.session.register_tool(string_tool)
        print_success("Registered chat completion tool with string response type")

        # Execute tool with a simple text response
        with Timer("Execution"):
            result = await client.execute_tool(
                string_tool.name,
                response="This is a simple text response from the chat completion tool."
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")

        separator()

        # Test 2: Integer response
        print_section("Test 2: Integer Response")

        # Create and register the tool with integer response type
        int_tool = CreateChatCompletion(
            name="chat_completion_int",
            description="Creates a numeric response.",
            response_type=int
        )

        client.session.register_tool(int_tool)
        print_success("Registered chat completion tool with integer response type")

        # Execute tool with a numeric response
        with Timer("Execution"):
            result = await client.execute_tool(
                int_tool.name,
                response="42"  # This should be converted to an integer
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
            print_info(f"Type: {type(eval(result.output))}")
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")

        separator()

        # Test 3: Pydantic model response - PersonInfo
        print_section("Test 3: Pydantic Model Response - PersonInfo")

        # Create and register the tool with PersonInfo response type
        person_tool = CreateChatCompletion(
            name="chat_completion_person",
            description="Creates a structured person info response.",
            response_type=PersonInfo
        )

        client.session.register_tool(person_tool)
        print_success("Registered chat completion tool with PersonInfo response type")

        # Execute tool with a structured person response
        with Timer("Execution"):
            result = await client.execute_tool(
                person_tool.name,
                name="Jane Doe",
                age=32,
                occupation="Software Engineer"
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
            # Try to parse as JSON to show structure
            try:
                print_info("Parsed as model:")
                # This is just for display, not actual parsing
                parsed = PersonInfo(
                    name="Jane Doe",
                    age=32,
                    occupation="Software Engineer"
                )
                print_info(json.dumps(parsed.model_dump(), indent=2))
            except Exception as e:
                print_warning(f"Couldn't parse output as PersonInfo: {e}")
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")

        separator()

        # Test 4: Pydantic model response - ProductReview
        print_section("Test 4: Pydantic Model Response - ProductReview")

        # Create and register the tool with ProductReview response type
        review_tool = CreateChatCompletion(
            name="chat_completion_review",
            description="Creates a structured product review response.",
            response_type=ProductReview
        )

        client.session.register_tool(review_tool)
        print_success("Registered chat completion tool with ProductReview response type")

        # Execute tool with a structured review response
        with Timer("Execution"):
            result = await client.execute_tool(
                review_tool.name,
                product_name="Smart Watch X1",
                rating=4.5,
                review_text="Great smartwatch with excellent battery life but occasional sync issues.",
                pros=["Long battery life", "Accurate fitness tracking", "Water resistant"],
                cons=["Occasional sync problems", "Limited app ecosystem"]
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
            # Try to parse as JSON to show structure
            try:
                print_info("Parsed as model:")
                # This is just for display, not actual parsing
                parsed = ProductReview(
                    product_name="Smart Watch X1",
                    rating=4.5,
                    review_text="Great smartwatch with excellent battery life but occasional sync issues.",
                    pros=["Long battery life", "Accurate fitness tracking", "Water resistant"],
                    cons=["Occasional sync problems", "Limited app ecosystem"]
                )
                print_info(json.dumps(parsed.model_dump(), indent=2))
            except Exception as e:
                print_warning(f"Couldn't parse output as ProductReview: {e}")
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")

        separator()

        # Test 5: List response
        print_section("Test 5: List Response")

        # Create and register the tool with list response type
        list_tool = CreateChatCompletion(
            name="chat_completion_list",
            description="Creates a list response.",
            response_type=List[str]
        )

        client.session.register_tool(list_tool)
        print_success("Registered chat completion tool with List[str] response type")

        # Execute tool with a list response
        with Timer("Execution"):
            result = await client.execute_tool(
                list_tool.name,
                response='["Item 1", "Item 2", "Item 3"]'  # This should be interpreted as a list
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")

        separator()

        # Test 6: Error handling - Invalid type conversion
        print_section("Test 6: Error Handling - Invalid Type Conversion")

        # Try to convert a non-numeric string to an integer
        with Timer("Execution"):
            result = await client.execute_tool(
                int_tool.name,
                response="not a number"  # This should cause a conversion error
            )

        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_warning(f"Error (expected): {result.error}")

        print_success("All tests completed successfully!")

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        if client:
            await client.close()
            print_info("Session closed and resources cleaned up")
        separator()


if __name__ == "__main__":
    asyncio.run(test_chat_completion_tool())

#!/usr/bin/env python
"""
Enterprise AI Chat Completion Examples

This script demonstrates structured data formats that can be used with the 
CreateChatCompletion tool:
- Basic text responses
- Structured responses with Pydantic models
- Different output formats (string, list, dictionary)
- Error handling with data validation
"""

import sys
import asyncio
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# Import common utilities
from notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    AsyncTimer,
    run_async
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.tool.core.result import ToolResult


# Define Pydantic models for structured outputs
class ProductReview(BaseModel):
    """Model for a product review."""
    product_name: str = Field(..., description="Name of the product being reviewed")
    rating: int = Field(..., description="Rating from 1-5 stars", ge=1, le=5)
    pros: List[str] = Field(..., description="List of positive aspects")
    cons: List[str] = Field(..., description="List of negative aspects")
    summary: str = Field(..., description="Short summary of the review")
    
    def __str__(self) -> str:
        """String representation of the product review."""
        return (f"Product Review: {self.product_name} - {self.rating}★\n"
                f"Pros: {', '.join(self.pros)}\n"
                f"Cons: {', '.join(self.cons)}\n"
                f"Summary: {self.summary}")


class RecipeSummary(BaseModel):
    """Model for a recipe summary."""
    title: str = Field(..., description="Title of the recipe")
    cooking_time: str = Field(..., description="Total cooking time (e.g., '30 minutes')")
    difficulty: str = Field(..., description="Difficulty level (e.g., 'Easy', 'Medium', 'Hard')")
    ingredients: List[str] = Field(..., description="List of main ingredients")
    steps: List[str] = Field(..., description="List of main preparation steps")
    
    def __str__(self) -> str:
        """String representation of the recipe summary."""
        return (f"Recipe: {self.title}\n"
                f"Time: {self.cooking_time} | Difficulty: {self.difficulty}\n"
                f"Ingredients: {', '.join(self.ingredients)}\n"
                f"Steps:\n" + "\n".join(f"  {i+1}. {step}" for i, step in enumerate(self.steps)))


async def basic_completion_example() -> None:
    """Example of basic text completion."""
    print_section("Basic Text Completion")
    
    try:
        # Create a simple response directly
        print_info("Generating a simple text response...")
        response_text = "This is a simple text response generated directly."
        
        print(response_text)
        
        # Note about tool usage
        print_info("\nNote: The CreateChatCompletion tool needs to be used by LLMs rather than directly.")
        print("It defines a schema for the LLM to follow when generating responses,")
        print("but doesn't actually generate the responses itself.")
        print("It would typically be used in agent workflows where the LLM creates structured outputs.")
        
    except Exception as e:
        print_error(f"Error in basic completion example: {e}")


async def structured_completion_example() -> None:
    """Example of structured completion with Pydantic models."""
    print_section("Structured Completion with Pydantic Models")
    
    try:
        # Product review example
        print_info("Demonstrating a structured product review format...")
        
        # Example of data that would be generated
        review_data = {
            "product_name": "Wireless Noise-Cancelling Headphones",
            "rating": 4,
            "pros": [
                "Excellent sound quality", 
                "Comfortable for long periods", 
                "Good battery life"
            ],
            "cons": [
                "Slightly expensive", 
                "Case is bulky"
            ],
            "summary": "A high-quality pair of headphones with great features, though a bit pricey."
        }
        
        # Create an instance of the model directly
        review = ProductReview(**review_data)
        print(review)
        
        # Recipe summary example
        print_info("\nDemonstrating a structured recipe summary format...")
        
        recipe_data = {
            "title": "Easy Veggie Pasta",
            "cooking_time": "25 minutes",
            "difficulty": "Easy",
            "ingredients": [
                "Pasta", "Bell peppers", "Zucchini", "Cherry tomatoes", 
                "Olive oil", "Garlic", "Basil", "Parmesan cheese"
            ],
            "steps": [
                "Boil pasta according to package instructions",
                "Chop vegetables into bite-sized pieces",
                "Sauté garlic in olive oil until fragrant",
                "Add vegetables and cook until tender",
                "Drain pasta and combine with vegetables",
                "Top with fresh basil and grated parmesan"
            ]
        }
        
        recipe = RecipeSummary(**recipe_data)
        print(recipe)
                
    except Exception as e:
        print_error(f"Error in structured completion example: {e}")


async def different_types_example() -> None:
    """Example of completions with different return types."""
    print_section("Examples of Different Data Types")
    
    try:
        # List response example
        print_info("Example of a list response format:")
        list_example = ["First item", "Second item", "Third item", "Fourth item"]
        print(list_example)
        
        # Dictionary response example
        print_info("\nExample of a dictionary response format:")
        dict_example = {
            "name": "John Smith",
            "age": 32,
            "occupation": "Software Engineer",
            "skills": ["Python", "JavaScript", "Docker"],
            "contact": {
                "email": "john.smith@example.com",
                "phone": "123-456-7890"
            }
        }
        print(dict_example)
        
        # Integer response example
        print_info("\nExample of an integer response:")
        int_example = 42
        print(int_example)
        
        # Note about CreateChatCompletion usage
        print_info("\nNote on CreateChatCompletion:")
        print("The CreateChatCompletion tool can specify these data types as expected outputs")
        print("when used by LLMs in agent workflows, ensuring structured responses.")
                
    except Exception as e:
        print_error(f"Error in different types example: {e}")


async def error_handling_example() -> None:
    """Example of error handling with structured data validation."""
    print_section("Error Handling in Structured Data")
    
    try:
        # Missing required fields example
        print_info("Example of error when required fields are missing:")
        incomplete_data = {
            "product_name": "Smart Watch",
            "rating": 5,
            # Missing pros, cons, and summary
        }
        
        try:
            # Try to create a ProductReview with missing fields
            review = ProductReview(**incomplete_data)
            print(review)
        except Exception as e:
            print_error(f"Validation error (expected): {e}")
        
        # Type conversion error example
        print_info("\nExample of error when field types are incorrect:")
        invalid_data = {
            "product_name": "Gaming Laptop",
            "rating": "five stars",  # Should be an integer
            "pros": "Fast performance, beautiful display",  # Should be a list
            "cons": ["Expensive"],
            "summary": "A great gaming laptop with impressive specifications."
        }
        
        try:
            # Try to create a ProductReview with invalid types
            review = ProductReview(**invalid_data)
            print(review)
        except Exception as e:
            print_error(f"Validation error (expected): {e}")
        
        # Note about validation in CreateChatCompletion
        print_info("\nNote about validation:")
        print("The CreateChatCompletion tool would enforce these validation rules")
        print("when processing responses from LLMs, ensuring data quality.")
                
    except Exception as e:
        print_error(f"Error in error handling example: {e}")


async def run_examples() -> None:
    """Run all chat completion examples."""
    try:
        # Introduction to the purpose of the tool
        print_info("The CreateChatCompletion tool defines structured formats for LLM responses.")
        print_info("This script demonstrates the type of data structures it can enforce.")
        print_info("In actual usage, the tool would be invoked by an LLM, not directly.")
        separator()
        
        await basic_completion_example()
        separator()

        await structured_completion_example()
        separator()

        await different_types_example()
        separator()

        await error_handling_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for chat completion examples."""
    print_title("Enterprise AI Chat Completion Format Examples")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All examples completed successfully!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
#!/usr/bin/env python
"""
Enterprise AI File Editor Examples

This notebook demonstrates working with the File Editor:
- Viewing files and directories in a sandbox environment
- Creating new files
- String replacement (exact matches)
- Regex pattern replacement with capture groups
- Line-based operations (insert, delete, replace)
- Character position editing
- Undo functionality
"""

import os
import sys
import asyncio
import tempfile
import uuid
from typing import Dict, Optional, Any

# Import common utilities
from examples.notebooks.utils import (
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
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.file import FileEditor


async def view_example() -> None:
    """Example of viewing files and directories."""
    print_section("Viewing Files and Directories")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    print_info("Initializing the sandbox environment...")
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_view_{unique_id}.txt"

    test_content = "Line 1: This is a test file for viewing\n"
    test_content += "Line 2: It contains multiple lines\n"
    test_content += "Line 3: This line will be shown\n"
    test_content += "Line 4: Along with other lines\n"
    test_content += "Line 5: To demonstrate the view command\n"

    # Write directly using sandbox client (bypassing the FileEditor validation)
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the entire file
        print_info("\nViewing the entire file:")
        async with AsyncTimer("Viewing file"):
            result = await editor.execute(
                command="view",
                path=test_file
            )

        if isinstance(result, CLIResult):
            print(result.output)
        else:
            print_error(f"Unexpected result type: {type(result)}")

        # View a specific range of lines
        print_info("\nViewing a specific range of lines (2-4):")
        async with AsyncTimer("Viewing line range"):
            result = await editor.execute(
                command="view",
                path=test_file,
                view_range=[2, 4]  # Show lines 2-4
            )

        if isinstance(result, CLIResult):
            print(result.output)
        else:
            print_error(f"Unexpected result type: {type(result)}")

        # View a directory
        print_info("\nViewing directory /tmp:")
        async with AsyncTimer("Viewing directory"):
            result = await editor.execute(
                command="view",
                path="/tmp"
            )

        if isinstance(result, CLIResult):
            print(result.output.split("\n")[:10])  # Show first 10 lines to avoid cluttering output
            print("... (output truncated)")
        else:
            print_error(f"Unexpected result type: {type(result)}")

    except Exception as e:
        print_error(f"Error in view example: {e}")


async def str_replace_example() -> None:
    """Example of exact string replacement."""
    print_section("String Replacement")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_replace_{unique_id}.txt"

    # Modified content to ensure REPLACE_ME appears exactly once
    test_content = "This is a test file for string replacement.\n"
    test_content += "It contains the text that will be replaced.\n"
    test_content += "The string REPLACE_ME should be unique in the file.\n"
    test_content += "This way we can target it specifically.\n"

    # Write directly using sandbox client
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the original file
        print_info("\nOriginal file content:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

        # Perform string replacement
        print_info("\nReplacing 'REPLACE_ME' with 'NEW_VALUE'...")
        async with AsyncTimer("String replacement"):
            result = await editor.execute(
                command="str_replace",
                path=test_file,
                old_str="REPLACE_ME",
                new_str="NEW_VALUE",
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)

            # View the modified file
            print_info("\nVerifying the changes:")
            result = await editor.execute(
                command="view",
                path=test_file
            )

            if isinstance(result, CLIResult):
                print(result.output)
        else:
            print_error(f"Replacement failed: {result}")

    except Exception as e:
        print_error(f"Error in string replacement example: {e}")


async def regex_replace_example() -> None:
    """Example of regex pattern replacement."""
    print_section("Regex Pattern Replacement")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_regex_{unique_id}.txt"

    test_content = "Date: 2023-01-15 - User: john_doe - Status: active\n"
    test_content += "Date: 2023-02-20 - User: jane_smith - Status: pending\n"
    test_content += "Date: 2023-03-10 - User: bob_jones - Status: inactive\n"
    test_content += "Date: 2023-04-05 - User: alice_wonder - Status: active\n"

    # Write directly using sandbox client
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the original file
        print_info("\nOriginal file content:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

        # Perform regex replacement to reformat dates
        print_info("\nReformatting dates from YYYY-MM-DD to MM/DD/YYYY...")
        async with AsyncTimer("Regex replacement"):
            result = await editor.execute(
                command="regex_replace",
                path=test_file,
                regex_params={
                    "pattern": r"Date: (\d{4})-(\d{2})-(\d{2})",
                    "replacement": r"Date: \2/\3/\1",  # MM/DD/YYYY format
                    "count": 0,  # Replace all occurrences
                    "flags": ""   # No special flags needed
                },
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)

            # Perform another regex replacement to anonymize usernames
            print_info("\nAnonymizing usernames...")
            result = await editor.execute(
                command="regex_replace",
                path=test_file,
                regex_params={
                    "pattern": r"User: (\w+)_(\w+)",
                    "replacement": r"User: [REDACTED]",
                    "count": 0,  # Replace all occurrences
                    "flags": "i"  # Case-insensitive matching
                },
                make_backup=True
            )

            if isinstance(result, CLIResult):
                print(result.output)

                # View the modified file
                print_info("\nVerifying all changes:")
                result = await editor.execute(
                    command="view",
                    path=test_file
                )

                if isinstance(result, CLIResult):
                    print(result.output)
            else:
                print_error(f"Username anonymization failed: {result}")
        else:
            print_error(f"Date reformatting failed: {result}")

    except Exception as e:
        print_error(f"Error in regex replacement example: {e}")


async def line_edit_example() -> None:
    """Example of line-based editing operations."""
    print_section("Line Editing")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_line_edit_{unique_id}.txt"

    test_content = "Line 1: Introduction to line editing\n"
    test_content += "Line 2: This line will be kept\n"
    test_content += "Line 3: We'll delete this line\n"
    test_content += "Line 4: Another line to keep\n"
    test_content += "Line 5: TODO: Replace this line\n"
    test_content += "Line 6: Final line of the file\n"

    # Write directly using sandbox client
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the original file
        print_info("\nOriginal file content:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

        # Delete a specific line
        print_info("\nDeleting line 3...")
        async with AsyncTimer("Line deletion"):
            result = await editor.execute(
                command="line_edit",
                path=test_file,
                line_params={
                    "operation": "delete",
                    "line_number": 3,
                    "count": 1
                },
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)
        else:
            print_error(f"Line deletion failed: {result}")

        # Replace a line matching a pattern
        print_info("\nReplacing line containing 'TODO'...")
        async with AsyncTimer("Pattern-based replacement"):
            result = await editor.execute(
                command="line_edit",
                path=test_file,
                line_params={
                    "operation": "replace",
                    "pattern": "TODO",
                    "content": "Line 5: DONE: This line has been replaced",
                    "count": 1
                },
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)
        else:
            print_error(f"Pattern replacement failed: {result}")

        # Insert a line before a specific line
        print_info("\nInserting new line before the final line...")
        async with AsyncTimer("Line insertion"):
            result = await editor.execute(
                command="line_edit",
                path=test_file,
                line_params={
                    "operation": "insert",
                    "line_number": 5,  # Position is now different after previous edits
                    "content": "NEW LINE: This was inserted before the final line",
                    "count": 1
                },
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)

            # View the final result
            print_info("\nVerifying all line edits:")
            result = await editor.execute(
                command="view",
                path=test_file
            )

            if isinstance(result, CLIResult):
                print(result.output)
        else:
            print_error(f"Line insertion failed: {result}")

    except Exception as e:
        print_error(f"Error in line editing example: {e}")


async def insert_example() -> None:
    """Example of inserting content at lines or character positions."""
    print_section("Content Insertion")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_insert_{unique_id}.txt"

    test_content = "This is a test file for insertion operations.\n"
    test_content += "We will insert content at specific line numbers.\n"
    test_content += "And also insert content at specific character positions.\n"

    # Write directly using sandbox client
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the original file
        print_info("\nOriginal file content:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

        # Insert at a specific line
        print_info("\nInserting content at line 2...")
        async with AsyncTimer("Line insertion"):
            result = await editor.execute(
                command="insert",
                path=test_file,
                insert_line=2,  # After line 2
                new_str="-- INSERTED LINE --\nThis line was inserted after line 2.\n",
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)
        else:
            print_error(f"Line insertion failed: {result}")

        # Find a specific character position to insert at
        original_content = await sandbox.read_file(test_file)
        position = original_content.find("specific character")

        if position != -1:
            # Insert at character position
            print_info(f"\nInserting content at character position {position}...")
            async with AsyncTimer("Character position insertion"):
                result = await editor.execute(
                    command="insert_at",
                    path=test_file,
                    position=position,
                    new_str="[EXACT] ",
                    make_backup=True
                )

            if isinstance(result, CLIResult):
                print(result.output)
            else:
                print_error(f"Character insertion failed: {result}")
        else:
            print_error("Could not find the target insertion point in the file")

        # View the final result
        print_info("\nVerifying all insertions:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

    except Exception as e:
        print_error(f"Error in insertion example: {e}")


async def undo_example() -> None:
    """Example of undoing edits."""
    print_section("Undo Functionality")

    # Create the editor
    editor = FileEditor()

    # Initialize the sandbox
    sandbox = await editor._get_sandbox_client()

    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_undo_{unique_id}.txt"

    test_content = "This is the original content of the file.\n"
    test_content += "We will make changes and then undo them.\n"
    test_content += "The undo operation will restore this text.\n"

    # Write directly using sandbox client
    print_info(f"Creating a test file at {test_file}")
    await sandbox.write_file(test_file, test_content)

    try:
        # View the original file
        print_info("\nOriginal file content:")
        result = await editor.execute(
            command="view",
            path=test_file
        )

        if isinstance(result, CLIResult):
            print(result.output)

        # Make a change to the file
        print_info("\nMaking a change to the file...")
        async with AsyncTimer("String replacement"):
            result = await editor.execute(
                command="str_replace",
                path=test_file,
                old_str="original content",
                new_str="MODIFIED content",
                make_backup=True
            )

        if isinstance(result, CLIResult):
            print(result.output)

            # View the modified file
            print_info("\nModified file content:")
            result = await editor.execute(
                command="view",
                path=test_file
            )

            if isinstance(result, CLIResult):
                print(result.output)

                # Undo the change
                print_info("\nUndoing the change...")
                async with AsyncTimer("Undo operation"):
                    result = await editor.execute(
                        command="undo_edit",
                        path=test_file
                    )

                if isinstance(result, CLIResult):
                    print(result.output)

                    # Verify the file has been restored
                    print_info("\nVerifying the file has been restored:")
                    result = await editor.execute(
                        command="view",
                        path=test_file
                    )

                    if isinstance(result, CLIResult):
                        print(result.output)
                else:
                    print_error(f"Undo operation failed: {result}")
            else:
                print_error("Failed to view modified file")
        else:
            print_error(f"String replacement failed: {result}")

    except Exception as e:
        print_error(f"Error in undo example: {e}")


async def run_examples() -> None:
    """Run all file editor examples."""
    try:
        # View example
        await view_example()
        separator()

        # String replacement example
        await str_replace_example()
        separator()

        # Regex replacement example
        await regex_replace_example()
        separator()

        # Line editing example
        await line_edit_example()
        separator()

        # Insert example
        await insert_example()
        separator()

        # Undo example
        await undo_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for file editor examples."""
    print_title("Enterprise AI File Editor Examples")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All file editor examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

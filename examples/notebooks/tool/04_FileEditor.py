#!/usr/bin/env python
"""
Test for FileEditor Tool via MCP

This script tests the FileEditor tool using only FileEditor commands.
"""

import asyncio
import os
from typing import Any

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

# Import core components
from enterprise_ai.tool.file.editor import FileEditor
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

logger = get_logger("file_editor_test")

async def test_file_editor():
    """Test the FileEditor tool using the MCP system."""
    print_title("TESTING FILE EDITOR TOOL VIA MCP")

    # Create a test session
    session_id = "file-editor-test"
    client = None

    # Test file in a subdirectory to verify auto-creation
    test_dir_path = "/workspace/test_dir"
    test_file_path = f"{test_dir_path}/test_file.txt"
    test_content = "This is a test file.\nLine 2 with some content."

    try:
        # Create client
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create file editor tool
        print_section("Tool Creation and Configuration")
        file_editor = FileEditor(
            name="file_editor",
            description="Tool for reading, writing, and modifying files."
        )
        client.session.register_tool(file_editor)
        print_success(f"Created and registered FileEditor tool with configuration")

        # Test 1: Check initial workspace state
        print_section("Test 1: Check Initial Workspace State")
        with Timer("Execution"):
            result = await client.execute_tool(
                file_editor.name,
                command="view",
                path="/workspace"
            )

        if hasattr(result, 'error') and result.error:
            print_error(f"Error: {result.error}")
        else:
            print_success(f"Initial workspace state:")
            print_info(result.output)

        # Test 2: Create initial file
        print_section("Test 2: Create Initial File")

        # First create a simple file directly (helps create the parent dir too)
        with Timer("Execution"):
            create_result = await client.execute_tool(
                file_editor.name,
                command="insert_at",  # Using insert_at which can create files
                path=test_file_path,
                position=0,  # Insert at beginning
                new_str=test_content  # Initial content
            )

        if hasattr(create_result, 'error') and create_result.error:
            print_error(f"Error: {create_result.error}")
        else:
            print_success(f"File creation result:")
            print_info(create_result.output)

        # Test 3: View directory structure
        print_section("Test 3: View Directory Structure")
        with Timer("Execution"):
            dir_result = await client.execute_tool(
                file_editor.name,
                command="view",
                path=test_dir_path
            )

        if hasattr(dir_result, 'error') and dir_result.error:
            print_error(f"Error: {dir_result.error}")
        else:
            print_success(f"Directory listing:")
            print_info(dir_result.output)

        # Test 4: View file content
        print_section("Test 4: View File Content")
        with Timer("Execution"):
            view_result = await client.execute_tool(
                file_editor.name,
                command="view",
                path=test_file_path
            )

        if hasattr(view_result, 'error') and view_result.error:
            print_error(f"Error: {view_result.error}")
        else:
            print_success(f"File content:")
            print_info(view_result.output)

        # Test 5: String replacement
        print_section("Test 5: String Replacement")
        with Timer("Execution"):
            str_result = await client.execute_tool(
                file_editor.name,
                command="str_replace",
                path=test_file_path,
                old_str="test file",
                new_str="modified file",
                make_backup=True
            )

        if hasattr(str_result, 'error') and str_result.error:
            print_error(f"Error: {str_result.error}")
        else:
            print_success(f"String replacement result:")
            print_info(str_result.output)

        # Test 6: Create Python file
        print_section("Test 6: Create Python File")
        python_code = """#!/usr/bin/env python
'''A simple Hello World program'''

def greet(name="World"):
    '''Return a greeting message'''
    return f"Hello, {name}!"

# Main program
if __name__ == "__main__":
    print(greet())
    print(greet("FileEditor Test"))
"""
        python_file = f"{test_dir_path}/hello.py"

        with Timer("Execution"):
            create_py_result = await client.execute_tool(
                file_editor.name,
                command="insert_at",  # Using insert_at which can create files
                path=python_file,
                position=0,
                new_str=python_code
            )

        if hasattr(create_py_result, 'error') and create_py_result.error:
            print_error(f"Error: {create_py_result.error}")
        else:
            print_success(f"Python file creation result:")
            print_info(create_py_result.output)

        # Test 7: View Python file
        print_section("Test 7: View Python File")
        with Timer("Execution"):
            view_py_result = await client.execute_tool(
                file_editor.name,
                command="view",
                path=python_file
            )

        if hasattr(view_py_result, 'error') and view_py_result.error:
            print_error(f"Error: {view_py_result.error}")
        else:
            print_success(f"Python file content:")
            print_info(view_py_result.output)

        # Test 8: Regex replacement in Python file
        print_section("Test 8: Regex Replacement in Python File")
        regex_params = {
            "pattern": r'def greet\(name="([^"]*)"\):',
            "replacement": r'def greet(name="Friend"):',
            "count": 0,
            "flags": "i"
        }

        with Timer("Execution"):
            regex_result = await client.execute_tool(
                file_editor.name,
                command="regex_replace",
                path=python_file,
                regex_params=regex_params
            )

        if hasattr(regex_result, 'error') and regex_result.error:
            print_error(f"Error: {regex_result.error}")
        else:
            print_success(f"Regex replacement result:")
            print_info(regex_result.output)

        # Test 9: Add lines to text file
        print_section("Test 9: Add New Lines to Text File")

        # First, check how many lines we have
        with Timer("Execution"):
            # Add new line at end
            append_result = await client.execute_tool(
                file_editor.name,
                command="insert_at",
                path=test_file_path,
                position=50,  # Very large position to append at end
                new_str="\nThis is a new line added at the end."
            )

        if hasattr(append_result, 'error') and append_result.error:
            print_error(f"Error: {append_result.error}")
        else:
            print_success(f"Line addition result:")
            print_info(append_result.output)

        # Test 10: Final view to verify changes
        print_section("Test 10: Final State Verification")
        with Timer("Execution"):
            final_result = await client.execute_tool(
                file_editor.name,
                command="view",
                path=test_dir_path
            )

        if hasattr(final_result, 'error') and final_result.error:
            print_error(f"Error: {final_result.error}")
        else:
            print_success(f"Final directory listing:")
            print_info(final_result.output)

            # View final file content
            view_final = await client.execute_tool(
                file_editor.name,
                command="view",
                path=test_file_path
            )

            print_success(f"Final file content:")
            print_info(view_final.output)

        print_success("All tests completed successfully!")

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up MCP resources
        if client:
            await client.close()
            print_info("Session closed and resources cleaned up")

        separator()


if __name__ == "__main__":
    asyncio.run(test_file_editor())

#!/usr/bin/env python3
"""
File Editor Tool Testing Script

Tests each aspect of the file editor tool individually with configurable LLM support.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.file.editor import FileEditor
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class FileEditorTester:
    """Comprehensive file editor tool tester with LLM configuration support."""
    
    def __init__(self):
        self.file_editor = None
        self.test_dir = None
        self.test_files = {}
    
    async def show_current_config(self):
        """Show current configuration."""
        print_header("Current Configuration", "single")
        
        # LLM Configuration
        provider = get_config("llm.default_provider", "not configured")
        model = get_config("llm.default_model", "not configured")
        print_test(f"LLM Provider: {provider}", "pass")
        print_test(f"LLM Model: {model}", "pass")
        
        # File Editor Configuration
        print_test(f"Test Directory: {self.test_dir}", "pass" if self.test_dir else "warn")

    async def show_tool_description(self):
        """Show the file editor tool description and capabilities."""
        print_header("FileEditor Tool Description", "double")
        
        if self.file_editor:
            print_chat("tool", f"Tool Name: {self.file_editor.name}")
            print_chat("tool", f"Description: {self.file_editor.description.strip()}")
            
            # Show capabilities
            if hasattr(self.file_editor, 'capabilities'):
                caps = [str(cap) for cap in self.file_editor.capabilities]
                print_chat("tool", f"Capabilities: {', '.join(caps)}")
            
            # Show parameters
            print_chat("tool", "Available Commands:")
            commands = self.file_editor.parameters.get("properties", {}).get("command", {}).get("enum", [])
            for cmd in commands:
                print_chat("tool", f"  • {cmd}")

    async def setup(self, llm_provider=None, llm_model=None):
        """Initialize file editor tool with optional LLM configuration."""
        print_header("FileEditor Tool Test Suite", "double")
        
        # Create temporary test directory
        self.test_dir = tempfile.mkdtemp(prefix="file_editor_test_")
        print_test(f"Created test directory: {self.test_dir}", "pass")
        
        # Show current config
        await self.show_current_config()
        
        print_test("Setting up file editor tool", "running")
        
        # Create file editor
        kwargs = {}
        if llm_provider:
            kwargs['llm_provider'] = llm_provider
            print_test(f"Using LLM Provider Override: {llm_provider}", "pass")
        if llm_model:
            kwargs['llm_model'] = llm_model
            print_test(f"Using LLM Model Override: {llm_model}", "pass")
        
        self.file_editor = FileEditor(**kwargs)
        success = await self.file_editor.initialize()
        
        if success:
            print_test("FileEditor tool initialized", "pass")
            await self.show_tool_description()
            return True
        else:
            print_test("FileEditor tool initialization failed", "fail")
            return False
    
    async def test_operation(self, description: str, expect_success: bool = True, show_content: bool = True, **kwargs):
        """Test a single file editor operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {kwargs.get('command', 'unknown')}"):
                result = await self.file_editor.execute(**kwargs)
            
            is_success = isinstance(result, ToolResult) and result.success
            
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                
                # Show result content
                if hasattr(result, 'result') and result.result and show_content:
                    output = str(result.result)
                    if len(output) <= 1000:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output[:1000] + "...")
                
                return result, True
            elif not expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: EXPECTED ERROR - {error_msg}", "pass")
                if hasattr(result, 'result') and result.result and show_content:
                    print_chat("tool", f"Result: {result.result}")
                return result, True
            elif expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: UNEXPECTED FAILURE - {error_msg}", "fail")
                if hasattr(result, 'result') and result.result:
                    print_chat("tool", f"Result: {result.result}")
                return result, False
            else:  # not expect_success and is_success
                print_test(f"{description}: UNEXPECTED SUCCESS (expected failure)", "warn")
                if hasattr(result, 'result') and result.result and show_content:
                    output = str(result.result)
                    if len(output) <= 1000:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output[:1000] + "...")
                return result, False
                
        except Exception as e:
            if expect_success:
                print_test(f"{description}: EXCEPTION - {e}", "fail")
                return None, False
            else:
                print_test(f"{description}: EXPECTED EXCEPTION - {e}", "pass")
                return None, True
    
    def _get_test_file_path(self, filename: str) -> str:
        """Get full path for test file."""
        return os.path.join(self.test_dir, filename)
    
    async def run_basic_file_operations(self):
        """Test basic file operations."""
        print_header("Basic File Operations", "single")
        
        # Test file creation
        test_file = self._get_test_file_path("test.txt")
        result, success = await self.test_operation(
            "Create File",
            expect_success=True,
            command="create",
            path=test_file,
            file_text="Hello, World!\nThis is a test file.\nLine 3 content."
        )
        
        if not success:
            print_test("File creation failed, cannot continue basic tests", "fail")
            return False
        
        self.test_files["basic"] = test_file
        
        # Test file viewing
        await self.test_operation(
            "View File",
            expect_success=True,
            command="view",
            path=test_file
        )
        
        # Test view with range
        await self.test_operation(
            "View File Range",
            expect_success=True,
            command="view",
            path=test_file,
            view_range=[1, 2]
        )
        
        # Test directory viewing
        await self.test_operation(
            "View Directory",
            expect_success=True,
            command="view",
            path=self.test_dir
        )
        
        return True
    
    async def run_string_replacement_tests(self):
        """Test string replacement functionality."""
        print_header("String Replacement Tests", "single")
        
        if "basic" not in self.test_files:
            print_test("No basic test file available", "skip")
            return
        
        test_file = self.test_files["basic"]
        
        # Test exact string replacement
        await self.test_operation(
            "String Replace",
            expect_success=True,
            command="str_replace",
            path=test_file,
            old_str="Hello, World!",
            new_str="Hello, FileEditor!"
        )
        
        # Test string replacement with empty string
        await self.test_operation(
            "String Replace with Empty",
            expect_success=True,
            command="str_replace",
            path=test_file,
            old_str="This is a test file.",
            new_str=""
        )
        
        # Test non-existent string (should fail)
        await self.test_operation(
            "String Replace Non-existent",
            expect_success=False,  # This should fail
            command="str_replace",
            path=test_file,
            old_str="This string does not exist",
            new_str="replacement"
        )
    
    async def run_regex_replacement_tests(self):
        """Test regex replacement functionality."""
        print_header("Regex Replacement Tests", "single")
        
        # Create a new file for regex tests
        regex_test_file = self._get_test_file_path("regex_test.txt")
        await self.test_operation(
            "Create Regex Test File",
            expect_success=True,
            command="create",
            path=regex_test_file,
            file_text="Email: john@example.com\nEmail: jane@test.org\nPhone: 123-456-7890\nDate: 2024-01-15"
        )
        
        self.test_files["regex"] = regex_test_file
        
        # Test regex replacement
        await self.test_operation(
            "Regex Replace Emails",
            expect_success=True,
            command="regex_replace",
            path=regex_test_file,
            regex_params={
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                "replacement": "[EMAIL_REDACTED]",
                "count": 0,
                "flags": ""
            }
        )
        
        # Test regex with groups
        await self.test_operation(
            "Regex Replace with Groups",
            expect_success=True,
            command="regex_replace",
            path=regex_test_file,
            regex_params={
                "pattern": r"Phone: (\d{3})-(\d{3})-(\d{4})",
                "replacement": "Phone: (\\1) \\2-\\3",
                "count": 0,
                "flags": ""
            }
        )
    
    async def run_line_editing_tests(self):
        """Test line-based editing operations."""
        print_header("Line Editing Tests", "single")
        
        # Create a new file for line editing
        line_test_file = self._get_test_file_path("line_test.txt")
        await self.test_operation(
            "Create Line Test File",
            expect_success=True,
            command="create",
            path=line_test_file,
            file_text="Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        )
        
        self.test_files["line"] = line_test_file
        
        # Test line insertion
        await self.test_operation(
            "Line Insert",
            expect_success=True,
            command="line_edit",
            path=line_test_file,
            line_params={
                "operation": "insert",
                "line_number": 3,
                "content": "Inserted Line"
            }
        )
        
        # Test line replacement
        await self.test_operation(
            "Line Replace",
            expect_success=True,
            command="line_edit",
            path=line_test_file,
            line_params={
                "operation": "replace",
                "line_number": 1,
                "content": "Modified Line 1"
            }
        )
        
        # Test line deletion
        await self.test_operation(
            "Line Delete",
            expect_success=True,
            command="line_edit",
            path=line_test_file,
            line_params={
                "operation": "delete",
                "line_number": 2,
                "count": 1
            }
        )
        
        # Test pattern-based editing
        await self.test_operation(
            "Pattern-based Insert",
            expect_success=True,
            command="line_edit",
            path=line_test_file,
            line_params={
                "operation": "insert",
                "pattern": "Line 4",
                "after_match": True,
                "content": "After Line 4"
            }
        )
    
    async def run_insertion_tests(self):
        """Test insertion operations."""
        print_header("Insertion Tests", "single")
        
        # Create a new file for insertion tests
        insert_test_file = self._get_test_file_path("insert_test.txt")
        await self.test_operation(
            "Create Insert Test File",
            expect_success=True,
            command="create",
            path=insert_test_file,
            file_text="First line\nSecond line\nThird line"
        )
        
        self.test_files["insert"] = insert_test_file
        
        # Test line insertion
        await self.test_operation(
            "Insert at Line",
            expect_success=True,
            command="insert",
            path=insert_test_file,
            insert_line=2,
            new_str="Inserted at line 2"
        )
        
        # Test character position insertion
        await self.test_operation(
            "Insert at Position",
            expect_success=True,
            command="insert_at",
            path=insert_test_file,
            position=5,
            new_str="[INSERTED]"
        )
    
    async def run_undo_tests(self):
        """Test undo functionality."""
        print_header("Undo Tests", "single")
        
        if "basic" not in self.test_files:
            print_test("No basic test file available for undo tests", "skip")
            return
        
        test_file = self.test_files["basic"]
        
        # Make a change
        await self.test_operation(
            "Make Change for Undo Test",
            expect_success=True,
            command="str_replace",
            path=test_file,
            old_str="Line 3 content.",
            new_str="Modified content for undo test."
        )
        
        # Test undo
        await self.test_operation(
            "Undo Last Edit",
            expect_success=True,
            command="undo_edit",
            path=test_file
        )
        
        # View file to confirm undo
        await self.test_operation(
            "View File After Undo",
            expect_success=True,
            command="view",
            path=test_file
        )
    
    async def run_error_handling_tests(self):
        """Test error handling and edge cases."""
        print_header("Error Handling Tests", "single")
        
        non_existent = self._get_test_file_path("non_existent.txt")
        
        # Test operations on non-existent file (should fail)
        await self.test_operation(
            "View Non-existent File",
            expect_success=False,  # Should fail
            command="view",
            path=non_existent
        )
        
        # Test create on existing file (should fail)
        if "basic" in self.test_files:
            await self.test_operation(
                "Create Existing File",
                expect_success=False,  # Should fail
                command="create",
                path=self.test_files["basic"],
                file_text="This should fail"
            )
        
        # Test invalid regex (should fail)
        if "regex" in self.test_files:
            await self.test_operation(
                "Invalid Regex Pattern",
                expect_success=False,  # Should fail
                command="regex_replace",
                path=self.test_files["regex"],
                regex_params={
                    "pattern": "[invalid regex",
                    "replacement": "test",
                    "count": 0,
                    "flags": ""
                }
            )
        
        # Test invalid line number (should fail)
        if "line" in self.test_files:
            await self.test_operation(
                "Invalid Line Number",
                expect_success=False,  # Should fail
                command="line_edit",
                path=self.test_files["line"],
                line_params={
                    "operation": "replace",
                    "line_number": 999,
                    "content": "This should fail"
                }
            )
        
        # Test undo on file with no history (should fail)
        empty_file = self._get_test_file_path("empty_for_undo.txt")
        await self.test_operation(
            "Create Empty File for Undo Test",
            expect_success=True,
            command="create",
            path=empty_file,
            file_text="Empty file content"
        )
        
        await self.test_operation(
            "Undo with No History",
            expect_success=False,  # Should fail
            command="undo_edit",
            path=empty_file
        )
    
    async def run_llm_integration_tests(self):
        """Test LLM integration with real editing scenarios."""
        print_header("LLM Integration Tests", "single")
        
        # Create a code file for LLM to edit
        code_file = self._get_test_file_path("sample_code.py")
        initial_code = '''def hello_world():
    print("Hello, World!")

def add_numbers(a, b):
    return a + b

if __name__ == "__main__":
    hello_world()
    result = add_numbers(2, 3)
    print(f"Result: {result}")
'''
        
        await self.test_operation(
            "Create Code File for LLM Test",
            expect_success=True,
            command="create",
            path=code_file,
            file_text=initial_code
        )
        
        self.test_files["code"] = code_file
        
        print_chat("user", f"I have created a Python file at {code_file}. Now you can use the file_editor tool to:")
        print_chat("user", "1. View the current code")
        print_chat("user", "2. Add a new function to multiply two numbers")
        print_chat("user", "3. Update the main section to test the new function")
        print_chat("user", "4. Add proper docstrings to all functions")
        
        # Note: In a real LLM integration test, the LLM would receive these instructions
        # and use the file_editor tool to make the changes
        
        print_test("LLM Integration setup complete", "pass")
        print_test("File ready for LLM editing at: " + code_file, "pass")
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.file_editor:
            print_test("Cleaning up file editor", "running")
            await self.file_editor.cleanup()
            print_test("FileEditor cleanup complete", "pass")
        
        if self.test_dir and os.path.exists(self.test_dir):
            print_test("Removing test directory", "running")
            shutil.rmtree(self.test_dir)
            print_test("Test directory removed", "pass")


async def main():
    """Run all file editor tests with comprehensive coverage."""
    tester = FileEditorTester()
    
    # Setup with default configuration
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run core test suites
        await tester.run_basic_file_operations()
        await tester.run_string_replacement_tests()
        await tester.run_regex_replacement_tests()
        await tester.run_line_editing_tests()
        await tester.run_insertion_tests()
        await tester.run_undo_tests()
        await tester.run_error_handling_tests()
        await tester.run_llm_integration_tests()
        
        print_header("All FileEditor Tests Complete!", "double")
        print_test("You can now test the file_editor tool with your LLM", "pass")
        print_test(f"Test files available in: {tester.test_dir}", "pass")
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
    except Exception as e:
        print_test(f"Unexpected error: {e}", "fail")
    finally:
        await tester.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)
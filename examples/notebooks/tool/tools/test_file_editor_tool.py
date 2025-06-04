#!/usr/bin/env python3
"""
Comprehensive File Editor Tool Testing Script

Tests each aspect of the file editor individually with detailed validation.
This script tests all FileEditor capabilities systematically:
- String replacement (exact and fuzzy matching)
- Regex replacement with various patterns
- Line-based operations (insert, delete, replace)
- Character position insertion
- Undo functionality
- Backup creation and cleanup
- Error handling and edge cases
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Setup project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from examples.notebooks.utils import (
    print_header, print_test, print_chat, Timer, run_async, separator
)
from enterprise_ai.tool.file.editor import FileEditor
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.base import ToolConfig
from enterprise_ai.tool.constants import ExecutionMode, SandboxMode


class FileEditorTester:
    """Comprehensive file editor tester with all feature validation."""
    
    def __init__(self, use_sandbox: bool = False):
        self.editor = None
        self.test_dir = None
        self.test_files: Dict[str, str] = {}
        self.use_sandbox = use_sandbox
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
    
    async def setup(self):
        """Initialize the file editor and test environment."""
        print_header("File Editor Tool Comprehensive Test Suite", "double")
        
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="file_editor_test_"))
        print_test(f"Test directory: {self.test_dir}", "pass")
        
        # Initialize FileEditor with configuration
        config = ToolConfig(
            timeout=30.0,
            max_retries=2,
            sandbox_enabled=self.use_sandbox,
            execution_mode=ExecutionMode.AUTO,
            sandbox_mode=SandboxMode.NONE if not self.use_sandbox else SandboxMode.UNIFIED,
            verbose_logging=True
        )
        
        print_test("Creating FileEditor instance", "running")
        self.editor = FileEditor(config=config)
        
        # Show tool description
        print_header("Tool Description", "single")
        print_chat("tool", self.editor.description)
        
        # Initialize the tool
        print_test("Initializing FileEditor", "running")
        success = await self.editor.initialize()
        
        if success:
            print_test("FileEditor initialized successfully", "pass")
            print_test(f"Mode: {'Sandbox' if self.use_sandbox else 'Local'}", "pass")
            return True
        else:
            print_test("FileEditor initialization failed", "fail")
            return False
    
    def create_test_file(self, name: str, content: str) -> str:
        """Create a test file with given content."""
        file_path = str(self.test_dir / name)
        Path(file_path).write_text(content, encoding='utf-8')
        self.test_files[name] = file_path
        return file_path
    
    def read_test_file(self, path: str) -> str:
        """Read test file content."""
        return Path(path).read_text(encoding='utf-8')
    
    async def run_test(self, test_name: str, command: str, path: str, 
                      expected_success: bool = True, **kwargs) -> tuple[ToolResult, bool]:
        """Run a single test and validate results."""
        self.test_count += 1
        print_test(f"Test #{self.test_count}: {test_name}", "running")
        
        try:
            with Timer(f"Execution time"):
                result = await self.editor.execute(command=command, path=path, **kwargs)
            
            success = isinstance(result, ToolResult) and result.success
            
            if success == expected_success:
                self.pass_count += 1
                print_test(f"✓ {test_name}", "pass")
                
                # Show result if it's a string and not too long
                if hasattr(result, 'result') and isinstance(result.result, str):
                    output = result.result
                    if len(output) <= 300:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output[:300] + "...")
                
                return result, True
            else:
                self.fail_count += 1
                expected_str = "SUCCESS" if expected_success else "FAILURE"
                actual_str = "SUCCESS" if success else "FAILURE"
                print_test(f"✗ {test_name}: Expected {expected_str}, got {actual_str}", "fail")
                
                if hasattr(result, 'error') and result.error:
                    print_chat("tool", f"Error: {result.error}")
                
                return result, False
                
        except Exception as e:
            self.fail_count += 1
            print_test(f"✗ {test_name}: Exception - {e}", "fail")
            return None, False
    
    async def test_basic_string_replacement(self):
        """Test basic string replacement functionality."""
        print_header("String Replacement Tests", "single")
        
        # Create test file
        content = """Hello World!
This is a test file.
We will replace some text here.
Hello World again!"""
        
        test_file = self.create_test_file("test_str_replace.txt", content)
        
        # Test 1: Simple replacement
        await self.run_test(
            "Simple string replacement",
            "str_replace",
            test_file,
            old_str="Hello World!",
            new_str="Hi Universe!",
            expected_replacements=1
        )
        
        # Verify the change
        new_content = self.read_test_file(test_file)
        if "Hi Universe!" in new_content and new_content.count("Hello World") == 1:
            print_test("✓ Content correctly modified", "pass")
        else:
            print_test("✗ Content not correctly modified", "fail")
        
        # Test 2: Multiple replacements
        await self.run_test(
            "Multiple string replacements",
            "str_replace",
            test_file,
            old_str="test",
            new_str="sample",
            expected_replacements=1
        )
        
        # Test 3: Non-existent string (should fail)
        await self.run_test(
            "Non-existent string replacement",
            "str_replace",
            test_file,
            old_str="xyz123",
            new_str="replacement",
            expected_success=False
        )
        
        # Test 4: Empty replacement
        await self.run_test(
            "Empty string replacement",
            "str_replace",
            test_file,
            old_str="again!",
            new_str="",
            expected_replacements=1
        )
    
    async def test_regex_replacement(self):
        """Test regex replacement functionality."""
        print_header("Regex Replacement Tests", "single")
        
        content = """Contact: john@example.com
Phone: (555) 123-4567
Email: jane@company.org
Phone: (555) 987-6543"""
        
        test_file = self.create_test_file("test_regex.txt", content)
        
        # Test 1: Email pattern replacement
        await self.run_test(
            "Email regex replacement",
            "regex_replace",
            test_file,
            regex_params={
                "pattern": r"(\w+)@(\w+\.\w+)",
                "replacement": r"\1[AT]\2",
                "count": 0,  # Replace all
                "flags": ""
            }
        )
        
        # Test 2: Phone number formatting
        await self.run_test(
            "Phone number regex replacement",
            "regex_replace",
            test_file,
            regex_params={
                "pattern": r"\((\d{3})\)\s*(\d{3})-(\d{4})",
                "replacement": r"\1.\2.\3",
                "count": 0,
                "flags": ""
            }
        )
        
        # Test 3: Case-insensitive replacement
        await self.run_test(
            "Case-insensitive regex replacement",
            "regex_replace",
            test_file,
            regex_params={
                "pattern": r"phone",
                "replacement": "Tel",
                "count": 0,
                "flags": "i"
            }
        )
        
        # Test 4: Invalid regex (should fail)
        await self.run_test(
            "Invalid regex pattern",
            "regex_replace",
            test_file,
            regex_params={
                "pattern": r"[invalid regex",
                "replacement": "replacement",
                "count": 0,
                "flags": ""
            },
            expected_success=False
        )
    
    async def test_line_operations(self):
        """Test line-based operations."""
        print_header("Line Operations Tests", "single")
        
        content = """Line 1
Line 2
Line 3
Line 4
Line 5"""
        
        test_file = self.create_test_file("test_lines.txt", content)
        
        # Test 1: Insert at specific line
        await self.run_test(
            "Insert at line number",
            "line_edit",
            test_file,
            line_params={
                "operation": "insert",
                "line_number": 3,
                "content": "Inserted Line"
            }
        )
        
        # Test 2: Delete line by number
        await self.run_test(
            "Delete line by number",
            "line_edit",
            test_file,
            line_params={
                "operation": "delete",
                "line_number": 2,
                "count": 1
            }
        )
        
        # Test 3: Replace line by pattern
        await self.run_test(
            "Replace line by pattern",
            "line_edit",
            test_file,
            line_params={
                "operation": "replace",
                "pattern": "Line 4",
                "content": "Modified Line 4",
                "count": 1
            }
        )
        
        # Test 4: Insert after pattern match
        await self.run_test(
            "Insert after pattern match",
            "line_edit",
            test_file,
            line_params={
                "operation": "insert",
                "pattern": "Line 5",
                "content": "Line after 5",
                "after_match": True
            }
        )
        
        # Test 5: Invalid line number (should fail)
        await self.run_test(
            "Invalid line number",
            "line_edit",
            test_file,
            line_params={
                "operation": "delete",
                "line_number": 100
            },
            expected_success=False
        )
    
    async def test_insertion_operations(self):
        """Test various insertion operations."""
        print_header("Insertion Operations Tests", "single")
        
        content = "ABC\nDEF\nGHI"
        test_file = self.create_test_file("test_insert.txt", content)
        
        # Test 1: Insert at line
        await self.run_test(
            "Insert at line",
            "insert",
            test_file,
            insert_line=2,
            new_str="New Line"
        )
        
        # Test 2: Insert at character position
        await self.run_test(
            "Insert at character position",
            "insert_at",
            test_file,
            position=4,
            new_str="XYZ"
        )
        
        # Test 3: Insert at end of file (FIXED - use actual line count + 1)
        current_content = self.read_test_file(test_file)
        line_count = len(current_content.splitlines())
        await self.run_test(
            "Insert at end of file",
            "insert",
            test_file,
            insert_line=line_count + 1,  # Use actual line count + 1
            new_str="End Line"
        )
        
        # Test 4: Insert at beginning
        await self.run_test(
            "Insert at beginning",
            "insert_at",
            test_file,
            position=0,
            new_str="START:"
        )
    
    async def test_undo_functionality(self):
        """Test undo functionality."""
        print_header("Undo Functionality Tests", "single")
        
        original_content = "Original content\nLine 2\nLine 3"
        test_file = self.create_test_file("test_undo.txt", original_content)
        
        # Make a change
        await self.run_test(
            "Make change to enable undo",
            "str_replace",
            test_file,
            old_str="Original content",
            new_str="Modified content"
        )
        
        # Verify change
        modified_content = self.read_test_file(test_file)
        if "Modified content" in modified_content:
            print_test("✓ Content successfully modified", "pass")
        else:
            print_test("✗ Content modification failed", "fail")
        
        # Test undo
        await self.run_test(
            "Undo last edit",
            "undo_edit",
            test_file
        )
        
        # Verify undo
        restored_content = self.read_test_file(test_file)
        if restored_content == original_content:
            print_test("✓ Undo successfully restored original content", "pass")
        else:
            print_test("✗ Undo failed to restore content", "fail")
        
        # Test undo on file with no history (should fail)
        new_file = self.create_test_file("no_history.txt", "content")
        await self.run_test(
            "Undo with no history",
            "undo_edit",
            new_file,
            expected_success=False
        )
    
    async def test_file_creation(self):
        """Test automatic file creation."""
        print_header("File Creation Tests", "single")
        
        # Test creating new file (FIXED - use insert instead of str_replace with empty string)
        new_file_path = str(self.test_dir / "new_file.txt")
        
        await self.run_test(
            "Create new file with content",
            "insert",
            new_file_path,
            insert_line=1,
            new_str="New file content",
            create_if_missing=True
        )
        
        # Verify file was created
        if Path(new_file_path).exists():
            content = self.read_test_file(new_file_path)
            print_test(f"✓ File created with content: {content[:50]}...", "pass")
        else:
            print_test("✗ File was not created", "fail")
        
        # Test operation on non-existent file without create flag (should fail)
        missing_file_path = str(self.test_dir / "missing.txt")
        await self.run_test(
            "Operation on missing file (no create flag)",
            "str_replace",
            missing_file_path,
            old_str="test",
            new_str="replacement",
            create_if_missing=False,
            expected_success=False
        )
    
    async def test_backup_functionality(self):
        """Test backup creation and management."""
        print_header("Backup Functionality Tests", "single")
        
        content = "Important content\nDo not lose this!"
        test_file = self.create_test_file("test_backup.txt", content)
        
        # Test with backup enabled
        await self.run_test(
            "Edit with backup enabled",
            "str_replace",
            test_file,
            old_str="Important",
            new_str="Critical",
            make_backup=True
        )
        
        # Check if backup was created
        backup_files = list(self.test_dir.glob("test_backup.txt.bak.*"))
        if backup_files:
            print_test(f"✓ Backup created: {backup_files[0].name}", "pass")
            
            # Verify backup content
            backup_content = self.read_test_file(str(backup_files[0]))
            if backup_content == content:
                print_test("✓ Backup contains original content", "pass")
            else:
                print_test("✗ Backup content incorrect", "fail")
        else:
            print_test("✗ No backup file created", "fail")
        
        # Test with backup disabled
        await self.run_test(
            "Edit with backup disabled",
            "str_replace",
            test_file,
            old_str="Critical",
            new_str="Essential",
            make_backup=False
        )
    
    async def test_fuzzy_matching(self):
        """Test fuzzy matching functionality."""
        print_header("Fuzzy Matching Tests", "single")
        
        content = "Hello World!\nThis is a test file.\nGoodbye World!"
        test_file = self.create_test_file("test_fuzzy.txt", content)
        
        # Test with exact match disabled, fuzzy enabled (should fail gracefully)
        await self.run_test(
            "Fuzzy matching with similar text",
            "str_replace",
            test_file,
            old_str="Helo World!",  # Typo
            new_str="Hi Universe!",
            enable_fuzzy_matching=True,
            fuzzy_threshold=0.8,
            expected_success=False  # Should fail but provide fuzzy analysis
        )
        
        # Test with fuzzy matching disabled
        await self.run_test(
            "No fuzzy matching",
            "str_replace",
            test_file,
            old_str="Helo World!",  # Typo
            new_str="Hi Universe!",
            enable_fuzzy_matching=False,
            expected_success=False
        )
    
    async def test_edge_cases(self):
        """Test edge cases and error conditions."""
        print_header("Edge Cases and Error Handling Tests", "single")
        
        # Test 1: Empty file operations
        empty_file = self.create_test_file("empty.txt", "")
        
        await self.run_test(
            "Insert into empty file",
            "insert",
            empty_file,
            insert_line=1,
            new_str="First line"
        )
        
        # Test 2: Very large line numbers (FIXED - test with realistic but invalid numbers)
        current_content = self.read_test_file(empty_file)
        line_count = len(current_content.splitlines())
        await self.run_test(
            "Insert at very large line number",
            "insert",
            empty_file,
            insert_line=line_count + 100,  # Use a more reasonable but still invalid number
            new_str="Last line",
            expected_success=False  # Expect this to fail gracefully
        )
        
        # Test 3: Binary file handling (should handle gracefully)
        binary_content = b'\x00\x01\x02\x03\xFF\xFE\xFD'
        binary_file = str(self.test_dir / "binary.bin")
        Path(binary_file).write_bytes(binary_content)
        
        await self.run_test(
            "Operation on binary file",
            "str_replace",
            binary_file,
            old_str="test",
            new_str="replacement",
            expected_success=False  # Should handle gracefully
        )
        
        # Test 4: Directory instead of file (should fail)
        await self.run_test(
            "Operation on directory",
            "str_replace",
            str(self.test_dir),
            old_str="test",
            new_str="replacement",
            expected_success=False
        )
        
        # Test 5: Invalid command
        test_file = self.create_test_file("test_invalid.txt", "content")
        try:
            result = await self.editor.execute(command="invalid_command", path=test_file)
            if not result.success:
                print_test("✓ Invalid command properly rejected", "pass")
            else:
                print_test("✗ Invalid command not rejected", "fail")
        except Exception:
            print_test("✓ Invalid command raised exception as expected", "pass")

    
    async def test_line_ending_handling(self):
        """Test different line ending handling."""
        print_header("Line Ending Handling Tests", "single")
        
        # Test Unix line endings
        unix_content = "Line 1\nLine 2\nLine 3\n"
        unix_file = self.create_test_file("unix_endings.txt", unix_content)
        
        await self.run_test(
            "Unix line endings",
            "str_replace",
            unix_file,
            old_str="Line 2",
            new_str="Modified Line 2"
        )
        
        # Test Windows line endings (FIXED - avoid newline parameter compatibility issue)
        windows_content = "Line 1\r\nLine 2\r\nLine 3\r\n"
        windows_file = str(self.test_dir / "windows_endings.txt")
        
        # Use binary mode to ensure exact line endings
        with open(windows_file, 'wb') as f:
            f.write(windows_content.encode('utf-8'))
        
        await self.run_test(
            "Windows line endings",
            "str_replace",
            windows_file,
            old_str="Line 2",
            new_str="Modified Line 2"
        )
        
        # Verify line endings are preserved (FIXED - use binary mode)
        try:
            with open(windows_file, 'rb') as f:
                modified_bytes = f.read()
            modified_content = modified_bytes.decode('utf-8')
            
            if '\r\n' in modified_content:
                print_test("✓ Windows line endings preserved", "pass")
            else:
                print_test("✗ Windows line endings not preserved", "fail")
        except Exception as e:
            print_test(f"⚠️ Could not verify line endings: {e}", "warn")
    
    def print_summary(self):
        """Print test summary."""
        print_header("Test Summary", "double")
        
        print_test(f"Total Tests: {self.test_count}", "pass")
        print_test(f"Passed: {self.pass_count}", "pass")
        print_test(f"Failed: {self.fail_count}", "fail" if self.fail_count > 0 else "pass")
        
        success_rate = (self.pass_count / max(1, self.test_count)) * 100
        print_test(f"Success Rate: {success_rate:.1f}%", 
                  "pass" if success_rate >= 90 else "warn" if success_rate >= 70 else "fail")
        
        if self.fail_count == 0:
            print_chat("system", "🎉 All tests passed! FileEditor is working perfectly.")
        elif success_rate >= 90:
            print_chat("system", "✅ Most tests passed. Minor issues detected.")
        else:
            print_chat("system", "⚠️ Some tests failed. Please review the implementation.")
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.editor:
            print_test("Cleaning up FileEditor", "running")
            await self.editor.cleanup()
            print_test("FileEditor cleanup complete", "pass")
        
        if self.test_dir and self.test_dir.exists():
            print_test(f"Removing test directory: {self.test_dir}", "running")
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print_test("Test directory cleanup complete", "pass")


async def main():
    """Run comprehensive file editor tests."""
    # Option to test both local and sandbox modes
    test_sandbox = False  # Set to True to also test sandbox mode
    
    for mode_name, use_sandbox in [("Local Mode", False)] + ([("Sandbox Mode", True)] if test_sandbox else []):
        print_header(f"Testing in {mode_name}", "double")
        
        tester = FileEditorTester(use_sandbox=use_sandbox)
        
        try:
            # Setup
            if not await tester.setup():
                print_test("Setup failed, skipping this mode", "fail")
                continue
            
            # Run all test suites
            await tester.test_basic_string_replacement()
            await tester.test_regex_replacement()
            await tester.test_line_operations()
            await tester.test_insertion_operations()
            await tester.test_undo_functionality()
            await tester.test_file_creation()
            await tester.test_backup_functionality()
            await tester.test_fuzzy_matching()
            await tester.test_edge_cases()
            await tester.test_line_ending_handling()
            
            # Print summary for this mode
            tester.print_summary()
            
        except KeyboardInterrupt:
            print_test("Tests interrupted by user", "warn")
            break
        except Exception as e:
            print_test(f"Unexpected error in {mode_name}: {e}", "fail")
        finally:
            await tester.cleanup()
        
        separator("═", 80)
    
    print_header("All File Editor Tests Complete!", "double")
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)
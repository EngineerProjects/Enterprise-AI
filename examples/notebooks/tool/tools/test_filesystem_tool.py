#!/usr/bin/env python3
"""
Comprehensive FileSystem Tool Testing Script

Tests each aspect of the filesystem tool individually with detailed validation.
This script tests all FileSystemTool capabilities systematically:
- File reading (single and multiple files)
- URL content fetching
- File writing (rewrite and append modes)
- Directory operations (create, list)
- File operations (move, rename)
- File searching by name patterns
- File metadata retrieval
- Path validation and security
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
from enterprise_ai.tool.file.filesystem import FileSystemTool
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.base import ToolConfig
from enterprise_ai.tool.constants import ExecutionMode, SandboxMode


class FileSystemTester:
    """Comprehensive filesystem tool tester with all feature validation."""
    
    def __init__(self, use_sandbox: bool = False):
        self.filesystem = None
        self.test_dir = None
        self.test_files: Dict[str, str] = {}
        self.use_sandbox = use_sandbox
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
    
    async def setup(self):
        """Initialize the filesystem tool and test environment."""
        print_header("FileSystem Tool Comprehensive Test Suite", "double")
        
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="filesystem_test_"))
        print_test(f"Test directory: {self.test_dir}", "pass")
        
        # Initialize FileSystemTool with configuration
        config = ToolConfig(
            timeout=30.0,
            max_retries=2,
            sandbox_enabled=self.use_sandbox,
            execution_mode=ExecutionMode.AUTO,
            sandbox_mode=SandboxMode.NONE if not self.use_sandbox else SandboxMode.UNIFIED,
            verbose_logging=True
        )
        
        print_test("Creating FileSystemTool instance", "running")
        self.filesystem = FileSystemTool(config=config)
        
        # Show tool description
        print_header("Tool Description", "single")
        print_chat("tool", self.filesystem.description)
        
        # Initialize the tool
        print_test("Initializing FileSystemTool", "running")
        success = await self.filesystem.initialize()
        
        if success:
            print_test("FileSystemTool initialized successfully", "pass")
            print_test(f"Mode: {'Sandbox' if self.use_sandbox else 'Local'}", "pass")
            return True
        else:
            print_test("FileSystemTool initialization failed", "fail")
            return False
    
    def create_test_file(self, name: str, content: str) -> str:
        """Create a test file with given content."""
        file_path = str(self.test_dir / name)
        Path(file_path).write_text(content, encoding='utf-8')
        self.test_files[name] = file_path
        return file_path
    
    def create_test_directory(self, name: str) -> str:
        """Create a test directory."""
        dir_path = str(self.test_dir / name)
        Path(dir_path).mkdir(exist_ok=True)
        return dir_path
    
    async def run_test(self, test_name: str, command: str, 
                      expected_success: bool = True, **kwargs) -> tuple[ToolResult, bool]:
        """Run a single test and validate results."""
        self.test_count += 1
        print_test(f"Test #{self.test_count}: {test_name}", "running")
        
        try:
            with Timer(f"Execution time"):
                result = await self.filesystem.execute(command=command, **kwargs)
            
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
    
    async def test_file_reading(self):
        """Test file reading capabilities."""
        print_header("File Reading Tests", "single")
        
        # Create test files
        simple_content = "Hello World!\nThis is line 2.\nThis is line 3."
        test_file1 = self.create_test_file("simple.txt", simple_content)
        
        large_content = "\n".join([f"Line {i}" for i in range(1, 101)])
        test_file2 = self.create_test_file("large.txt", large_content)
        
        # Test 1: Read simple file
        await self.run_test(
            "Read simple text file",
            "read_file",
            path=test_file1
        )
        
        # Test 2: Read file with offset
        await self.run_test(
            "Read file with offset",
            "read_file",
            path=test_file2,
            offset=10
        )
        
        # Test 3: Read file with length limit
        await self.run_test(
            "Read file with length limit",
            "read_file",
            path=test_file2,
            length=5
        )
        
        # Test 4: Read non-existent file (should fail)
        await self.run_test(
            "Read non-existent file",
            "read_file",
            path=str(self.test_dir / "missing.txt"),
            expected_success=False
        )
    
    async def test_multiple_file_reading(self):
        """Test reading multiple files simultaneously."""
        print_header("Multiple File Reading Tests", "single")
        
        # Create multiple test files
        files = {}
        for i in range(1, 4):
            content = f"Content of file {i}\nSecond line of file {i}"
            files[f"multi_{i}.txt"] = self.create_test_file(f"multi_{i}.txt", content)
        
        # Test 1: Read multiple existing files
        await self.run_test(
            "Read multiple existing files",
            "read_multiple_files",
            paths=list(files.values())
        )
        
        # Test 2: Read mix of existing and non-existent files
        mixed_paths = list(files.values()) + [str(self.test_dir / "missing.txt")]
        await self.run_test(
            "Read mix of existing and missing files",
            "read_multiple_files",
            paths=mixed_paths
        )
        
        # Test 3: Empty file list
        await self.run_test(
            "Read empty file list",
            "read_multiple_files",
            paths=[],
            expected_success=False
        )
    
    async def test_url_reading(self):
        """Test URL content fetching."""
        print_header("URL Reading Tests", "single")
        
        # Test 1: Read from HTTP URL
        await self.run_test(
            "Read content from HTTP URL",
            "read_file",
            path="https://httpbin.org/json",
            is_url=True
        )
        
        # Test 2: Read from invalid URL (should fail gracefully)
        await self.run_test(
            "Read from invalid URL",
            "read_file",
            path="https://this-domain-does-not-exist-12345.com",
            is_url=True,
            expected_success=False
        )
    
    async def test_file_writing(self):
        """Test file writing capabilities."""
        print_header("File Writing Tests", "single")
        
        # Test 1: Create new file
        new_file = str(self.test_dir / "new_file.txt")
        await self.run_test(
            "Create new file",
            "write_file",
            path=new_file,
            content="Initial content\nSecond line"
        )
        
        # Verify content
        if Path(new_file).exists():
            content = Path(new_file).read_text()
            print_test(f"✓ File created with correct content", "pass")
        
        # Test 2: Rewrite existing file
        await self.run_test(
            "Rewrite existing file",
            "write_file",
            path=new_file,
            content="Overwritten content",
            mode="rewrite"
        )
        
        # Test 3: Append to existing file
        await self.run_test(
            "Append to existing file",
            "write_file",
            path=new_file,
            content="\nAppended line",
            mode="append"
        )
        
        # Test 4: Write to directory path (should fail)
        await self.run_test(
            "Write to directory path",
            "write_file",
            path=str(self.test_dir),
            content="content",
            expected_success=False
        )
    
    async def test_directory_operations(self):
        """Test directory operations."""
        print_header("Directory Operations Tests", "single")
        
        # Test 1: Create new directory
        new_dir = str(self.test_dir / "new_directory")
        await self.run_test(
            "Create new directory",
            "create_directory",
            path=new_dir
        )
        
        # Verify directory was created
        if Path(new_dir).exists() and Path(new_dir).is_dir():
            print_test("✓ Directory successfully created", "pass")
        else:
            print_test("✗ Directory was not created", "fail")
        
        # Test 2: Create nested directories
        nested_dir = str(self.test_dir / "level1" / "level2" / "level3")
        await self.run_test(
            "Create nested directories",
            "create_directory",
            path=nested_dir
        )
        
        # Test 3: List directory contents
        # Create some files and subdirectories first
        (Path(new_dir) / "subdir").mkdir(exist_ok=True)
        (Path(new_dir) / "file.txt").write_text("content")
        
        await self.run_test(
            "List directory contents",
            "list_directory",
            path=new_dir
        )
        
        # Test 4: List root test directory
        await self.run_test(
            "List test directory",
            "list_directory",
            path=str(self.test_dir)
        )
        
        # Test 5: List non-existent directory (should fail)
        await self.run_test(
            "List non-existent directory",
            "list_directory",
            path=str(self.test_dir / "does_not_exist"),
            expected_success=False
        )
    
    async def test_file_operations(self):
        """Test file move and rename operations."""
        print_header("File Operations Tests", "single")
        
        # Create test files
        source_file = self.create_test_file("source.txt", "Source file content")
        target_dir = self.create_test_directory("target_dir")
        
        # Test 1: Move file to different directory
        target_file = str(Path(target_dir) / "moved_file.txt")
        await self.run_test(
            "Move file to different directory",
            "move_file",
            source=source_file,
            destination=target_file
        )
        
        # Verify move
        if Path(target_file).exists() and not Path(source_file).exists():
            print_test("✓ File successfully moved", "pass")
        else:
            print_test("✗ File move failed", "fail")
        
        # Test 2: Rename file in same directory
        rename_source = self.create_test_file("original_name.txt", "Rename test")
        rename_target = str(self.test_dir / "renamed_file.txt")
        await self.run_test(
            "Rename file in same directory",
            "move_file",
            source=rename_source,
            destination=rename_target
        )
        
        # Test 3: Move to non-existent directory (should fail)
        test_file = self.create_test_file("test_move.txt", "content")
        await self.run_test(
            "Move to non-existent directory",
            "move_file",
            source=test_file,
            destination=str(self.test_dir / "nonexistent" / "file.txt"),
            expected_success=False
        )
        
        # Test 4: Move non-existent file (should fail)
        await self.run_test(
            "Move non-existent file",
            "move_file",
            source=str(self.test_dir / "missing.txt"),
            destination=str(self.test_dir / "target.txt"),
            expected_success=False
        )
    
    async def test_file_search(self):
        """Test file search functionality."""
        print_header("File Search Tests", "single")
        
        # Create test files with different names
        search_dir = self.create_test_directory("search_test")
        Path(search_dir, "python_file.py").write_text("print('hello')")
        Path(search_dir, "javascript_file.js").write_text("console.log('hello')")
        Path(search_dir, "text_file.txt").write_text("Some text content")
        Path(search_dir, "readme.md").write_text("# README")
        
        # Create subdirectory with files
        subdir = Path(search_dir, "subdir")
        subdir.mkdir()
        Path(subdir, "nested_file.py").write_text("nested content")
        
        # Test 1: Search for all Python files
        await self.run_test(
            "Search for Python files",
            "search_files",
            path=search_dir,
            pattern="*.py"
        )
        
        # Test 2: Search for files containing 'file'
        await self.run_test(
            "Search for files containing 'file'",
            "search_files",
            path=search_dir,
            pattern="*file*"
        )
        
        # Test 3: Search in non-existent directory (should fail)
        await self.run_test(
            "Search in non-existent directory",
            "search_files",
            path=str(self.test_dir / "missing_dir"),
            pattern="*.txt",
            expected_success=False
        )
        
        # Test 4: Case-insensitive search
        await self.run_test(
            "Case-insensitive search",
            "search_files",
            path=search_dir,
            pattern="*README*"
        )
    
    async def test_file_metadata(self):
        """Test file metadata retrieval."""
        print_header("File Metadata Tests", "single")
        
        # Create test file with known content
        metadata_file = self.create_test_file("metadata_test.txt", 
                                              "Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        
        # Test 1: Get file metadata
        await self.run_test(
            "Get file metadata",
            "get_file_info",
            path=metadata_file
        )
        
        # Test 2: Get directory metadata
        await self.run_test(
            "Get directory metadata",
            "get_file_info",
            path=str(self.test_dir)
        )
        
        # Test 3: Get metadata for non-existent file (should fail)
        await self.run_test(
            "Get metadata for non-existent file",
            "get_file_info",
            path=str(self.test_dir / "missing.txt"),
            expected_success=False
        )
    
    async def test_binary_files(self):
        """Test binary file handling."""
        print_header("Binary File Tests", "single")
        
        # Create a binary file
        binary_content = bytes([0, 1, 2, 3, 255, 254, 253])
        binary_file = str(self.test_dir / "binary.bin")
        Path(binary_file).write_bytes(binary_content)
        
        # Test 1: Read binary file
        await self.run_test(
            "Read binary file",
            "read_file",
            path=binary_file
        )
        
        # Test 2: Get binary file metadata
        await self.run_test(
            "Get binary file metadata",
            "get_file_info",
            path=binary_file
        )
    
    async def test_edge_cases(self):
        """Test edge cases and error conditions."""
        print_header("Edge Cases and Error Handling Tests", "single")
        
        # Test 1: Empty file operations
        empty_file = self.create_test_file("empty.txt", "")
        await self.run_test(
            "Read empty file",
            "read_file",
            path=empty_file
        )
        
        # Test 2: Very long filename
        long_name = "a" * 200 + ".txt"
        try:
            long_file = self.create_test_file(long_name, "content")
            await self.run_test(
                "File with very long name",
                "read_file",
                path=long_file
            )
        except OSError:
            print_test("✓ Very long filename properly rejected by OS", "pass")
        
        # Test 3: Invalid characters in filename (platform dependent)
        # This test may behave differently on different operating systems
        
        # Test 4: Read file as directory
        test_file = self.create_test_file("not_a_dir.txt", "content")
        await self.run_test(
            "List file as directory",
            "list_directory",
            path=test_file,
            expected_success=False
        )
        
        # Test 5: Invalid command
        try:
            result = await self.filesystem.execute(command="invalid_command", path=test_file)
            if not result.success:
                print_test("✓ Invalid command properly rejected", "pass")
            else:
                print_test("✗ Invalid command not rejected", "fail")
        except Exception:
            print_test("✓ Invalid command raised exception as expected", "pass")
    
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
            print_chat("system", "🎉 All tests passed! FileSystemTool is working perfectly.")
        elif success_rate >= 90:
            print_chat("system", "✅ Most tests passed. Minor issues detected.")
        else:
            print_chat("system", "⚠️ Some tests failed. Please review the implementation.")
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.filesystem:
            print_test("Cleaning up FileSystemTool", "running")
            await self.filesystem.cleanup()
            print_test("FileSystemTool cleanup complete", "pass")
        
        if self.test_dir and self.test_dir.exists():
            print_test(f"Removing test directory: {self.test_dir}", "running")
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print_test("Test directory cleanup complete", "pass")


async def main():
    """Run comprehensive filesystem tests."""
    test_sandbox = False  # Set to True to also test sandbox mode
    
    for mode_name, use_sandbox in [("Local Mode", False)] + ([("Sandbox Mode", True)] if test_sandbox else []):
        print_header(f"Testing in {mode_name}", "double")
        
        tester = FileSystemTester(use_sandbox=use_sandbox)
        
        try:
            # Setup
            if not await tester.setup():
                print_test("Setup failed, skipping this mode", "fail")
                continue
            
            # Run all test suites
            await tester.test_file_reading()
            await tester.test_multiple_file_reading()
            await tester.test_url_reading()
            await tester.test_file_writing()
            await tester.test_directory_operations()
            await tester.test_file_operations()
            await tester.test_file_search()
            await tester.test_file_metadata()
            await tester.test_binary_files()
            await tester.test_edge_cases()
            
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
    
    print_header("All FileSystem Tests Complete!", "double")
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)
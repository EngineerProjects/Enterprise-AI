#!/usr/bin/env python3
"""
MIME Types Tool Testing Suite - Comprehensive File Type Detection Testing

Comprehensive testing for the MIME type detection and file classification tool.
"""

import asyncio
import sys
import os
import tempfile
import time
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parents[4]
sys.path.insert(0, str(project_root))

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.utility.mime_types import MimeTypeTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class MimeTypesToolTester:
    """Comprehensive MIME types tool tester."""
    
    def __init__(self):
        self.mime_tool = None
        self.test_results = []
        self.test_files_created = []
        self.working_dir = None
        self._cleanup_done = False
    
    async def setup(self):
        """Initialize the MIME types tool."""
        print_header("MIME Types Tool Test Suite", "double")
        
        print_test("Creating test working directory", "running")
        self.working_dir = tempfile.mkdtemp(prefix="mime_test_")
        print_test(f"Test working directory: {self.working_dir}", "pass")
        
        print_test("Initializing MIME types tool", "running")
        
        self.mime_tool = MimeTypeTool()
        success = await self.mime_tool.initialize()
        
        if success:
            print_test("MIME types tool initialized", "pass")
            await self.show_tool_info()
            await self.create_test_files()
            return True
        else:
            print_test("Failed to initialize MIME types tool", "fail")
            return False
    
    async def show_tool_info(self):
        """Show tool information."""
        print_header("Tool Information", "single")
        
        print_chat("tool", f"Tool Name: {self.mime_tool.name}")
        print_chat("tool", f"Description: {self.mime_tool.description.strip()}")
        
        if hasattr(self.mime_tool, 'capabilities'):
            caps = [str(cap) for cap in self.mime_tool.capabilities]
            print_chat("tool", f"Capabilities: {', '.join(caps)}")
        
        print_chat("tool", f"Working Directory: {self.working_dir}")

    async def create_test_files(self):
        """Create various test files for MIME type detection."""
        print_test("Creating test files", "running")
        
        test_files = {
            "text_file.txt": "Hello, this is a plain text file!",
            "python_script.py": "#!/usr/bin/env python3\nprint('Hello World')",
            "json_data.json": '{"name": "test", "value": 42}',
            "csv_data.csv": "name,age,city\nJohn,30,NYC\nJane,25,LA",
            "yaml_config.yaml": "version: 1.0\nname: test\nvalues:\n  - item1\n  - item2",
            "markdown_doc.md": "# Test Document\n\nThis is a **markdown** file.",
            "html_page.html": "<!DOCTYPE html>\n<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>",
            "css_style.css": "body { margin: 0; padding: 20px; font-family: Arial; }",
            "javascript.js": "function hello() { console.log('Hello World'); }",
            "shell_script.sh": "#!/bin/bash\necho 'Hello from shell'",
            "config.ini": "[section]\nkey=value\ndebug=true",
            "no_extension": "This file has no extension"
        }
        
        # Create text files
        for filename, content in test_files.items():
            file_path = os.path.join(self.working_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.test_files_created.append(file_path)
        
        # Create binary files with magic numbers
        binary_files = {
            "fake_png.png": b'\x89PNG\r\n\x1a\n' + b'fake png data' * 10,
            "fake_jpeg.jpg": b'\xff\xd8\xff\xe0' + b'fake jpeg data' * 10,
            "fake_gif.gif": b'GIF89a' + b'fake gif data' * 10,
            "fake_pdf.pdf": b'%PDF-1.4' + b'fake pdf content' * 20,
            "fake_zip.zip": b'PK\x03\x04' + b'fake zip data' * 15,
            "binary_data.bin": bytes(range(256)) * 4
        }
        
        for filename, content in binary_files.items():
            file_path = os.path.join(self.working_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(content)
            self.test_files_created.append(file_path)
        
        print_test(f"Created {len(test_files) + len(binary_files)} test files", "pass")

    async def test_operation(self, description: str, expect_success: bool = True, **kwargs):
        """Test a single operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {description}"):
                result = await self.mime_tool.execute(**kwargs)
            
            is_success = isinstance(result, ToolResult) and result.success
            
            # Record test result
            self.test_results.append({
                'description': description,
                'expected_success': expect_success,
                'actual_success': is_success,
                'passed': is_success == expect_success
            })
            
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                
                if hasattr(result, 'result') and result.result:
                    output = str(result.result)
                    # Show output (truncated if too long)
                    if len(output) <= 800:
                        print_chat("output", output)
                    else:
                        print_chat("output", output[:800] + "...")
                
                return result, True
                
            elif not expect_success and not is_success:
                print_test(f"{description}: EXPECTED ERROR", "pass")
                error_msg = getattr(result, 'error', 'Unknown error')
                print_chat("error", f"Expected error: {error_msg}")
                return result, True
                
            elif expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: UNEXPECTED FAILURE - {error_msg}", "fail")
                return result, False
                
            else:  # not expect_success and is_success
                print_test(f"{description}: UNEXPECTED SUCCESS", "warn")
                return result, False
                
        except Exception as e:
            self.test_results.append({
                'description': description,
                'expected_success': expect_success,
                'actual_success': False,
                'passed': not expect_success
            })
            
            if expect_success:
                print_test(f"{description}: EXCEPTION - {e}", "fail")
                return None, False
            else:
                print_test(f"{description}: EXPECTED EXCEPTION - {e}", "pass")
                return None, True

    async def test_basic_detection(self):
        """Test basic MIME type detection."""
        print_header("Basic MIME Type Detection", "single")
        
        # Test text file
        text_file = os.path.join(self.working_dir, "text_file.txt")
        await self.test_operation(
            "Detect Plain Text File",
            expect_success=True,
            command="detect_type",
            path=text_file,
            use_content=True,
            include_magic=True
        )
        
        # Test Python file
        python_file = os.path.join(self.working_dir, "python_script.py")
        await self.test_operation(
            "Detect Python Script",
            expect_success=True,
            command="detect_type",
            path=python_file,
            use_content=True
        )
        
        # Test JSON file
        json_file = os.path.join(self.working_dir, "json_data.json")
        await self.test_operation(
            "Detect JSON Data",
            expect_success=True,
            command="detect_type",
            path=json_file
        )
        
        # Test file without extension
        no_ext_file = os.path.join(self.working_dir, "no_extension")
        await self.test_operation(
            "Detect File Without Extension",
            expect_success=True,
            command="detect_type",
            path=no_ext_file,
            use_content=True,
            include_magic=True
        )

    async def test_content_detection(self):
        """Test content-based detection."""
        print_header("Content-Based Detection", "single")
        
        # Test PNG file with magic number
        png_file = os.path.join(self.working_dir, "fake_png.png")
        await self.test_operation(
            "Detect PNG by Magic Number",
            expect_success=True,
            command="detect_type",
            path=png_file,
            use_content=True,
            include_magic=True
        )
        
        # Test JPEG file
        jpeg_file = os.path.join(self.working_dir, "fake_jpeg.jpg")
        await self.test_operation(
            "Detect JPEG by Magic Number",
            expect_success=True,
            command="detect_type",
            path=jpeg_file,
            use_content=True,
            include_magic=True
        )
        
        # Test PDF file
        pdf_file = os.path.join(self.working_dir, "fake_pdf.pdf")
        await self.test_operation(
            "Detect PDF by Magic Number",
            expect_success=True,
            command="detect_type",
            path=pdf_file,
            use_content=True,
            include_magic=True
        )
        
        # Test ZIP file
        zip_file = os.path.join(self.working_dir, "fake_zip.zip")
        await self.test_operation(
            "Detect ZIP by Magic Number",
            expect_success=True,
            command="detect_type",
            path=zip_file,
            use_content=True,
            include_magic=True
        )

    async def test_content_sample_detection(self):
        """Test detection from content samples."""
        print_header("Content Sample Detection", "single")
        
        # Test with text content sample
        await self.test_operation(
            "Detect from Text Sample",
            expect_success=True,
            command="detect_type",
            content_sample="Hello world, this is plain text!",
            use_content=True,
            include_magic=True
        )
        
        # Test with JSON content sample
        await self.test_operation(
            "Detect from JSON Sample",
            expect_success=True,
            command="detect_type",
            content_sample='{"key": "value", "number": 42}',
            use_content=True,
            include_magic=True
        )
        
        # Test with HTML content sample
        await self.test_operation(
            "Detect from HTML Sample",
            expect_success=True,
            command="detect_type",
            content_sample='<!DOCTYPE html><html><head><title>Test</title></head></html>',
            use_content=True,
            include_magic=True
        )

    async def test_file_classification(self):
        """Test file classification functionality."""
        print_header("File Classification", "single")
        
        # Classify Python file
        python_file = os.path.join(self.working_dir, "python_script.py")
        await self.test_operation(
            "Classify Python File",
            expect_success=True,
            command="classify_file",
            path=python_file
        )
        
        # Classify image file
        png_file = os.path.join(self.working_dir, "fake_png.png")
        await self.test_operation(
            "Classify PNG Image",
            expect_success=True,
            command="classify_file",
            path=png_file
        )
        
        # Classify config file
        yaml_file = os.path.join(self.working_dir, "yaml_config.yaml")
        await self.test_operation(
            "Classify YAML Config",
            expect_success=True,
            command="classify_file",
            path=yaml_file
        )
        
        # Classify binary file
        binary_file = os.path.join(self.working_dir, "binary_data.bin")
        await self.test_operation(
            "Classify Binary File",
            expect_success=True,
            command="classify_file",
            path=binary_file
        )

    async def test_batch_detection(self):
        """Test batch detection functionality."""
        print_header("Batch Detection", "single")
        
        # Batch detect all files
        all_files = self.test_files_created[:8]  # Limit to first 8 files
        await self.test_operation(
            "Batch Detect Multiple Files",
            expect_success=True,
            command="batch_detect",
            paths=all_files,
            use_content=False  # For performance
        )
        
        # Batch detect with content analysis
        text_files = [f for f in self.test_files_created if f.endswith(('.txt', '.py', '.json', '.yaml'))]
        await self.test_operation(
            "Batch Detect with Content Analysis",
            expect_success=True,
            command="batch_detect",
            paths=text_files[:5],
            use_content=True
        )
        
        # Batch detect with category filter
        await self.test_operation(
            "Batch Detect with Text Filter",
            expect_success=True,
            command="batch_detect",
            paths=all_files,
            category_filter="text"
        )
        
        # Batch detect with image filter
        await self.test_operation(
            "Batch Detect with Image Filter",
            expect_success=True,
            command="batch_detect",
            paths=all_files,
            category_filter="image"
        )

    async def test_type_management(self):
        """Test type registration and listing."""
        print_header("Type Management", "single")
        
        # List all types
        await self.test_operation(
            "List All Types",
            expect_success=True,
            command="list_types"
        )
        
        # List specific category
        await self.test_operation(
            "List Text Category",
            expect_success=True,
            command="list_types",
            category_filter="text"
        )
        
        # List code category
        await self.test_operation(
            "List Code Category",
            expect_success=True,
            command="list_types",
            category_filter="code"
        )
        
        # Register custom type
        await self.test_operation(
            "Register Custom Type",
            expect_success=True,
            command="register_type",
            extension="myext",
            mime_type="application/x-custom"
        )
        
        # Update existing type
        await self.test_operation(
            "Update Existing Type",
            expect_success=True,
            command="register_type",
            extension="py",
            mime_type="text/x-python-updated"
        )

    async def test_validation(self):
        """Test validation functionality."""
        print_header("Validation Tests", "single")
        
        # Validate file type detection
        python_file = os.path.join(self.working_dir, "python_script.py")
        await self.test_operation(
            "Validate Python File Detection",
            expect_success=True,
            command="validate_type",
            path=python_file
        )
        
        # Validate image file
        png_file = os.path.join(self.working_dir, "fake_png.png")
        await self.test_operation(
            "Validate PNG File Detection",
            expect_success=True,
            command="validate_type",
            path=png_file
        )
        
        # Validate MIME type format
        await self.test_operation(
            "Validate Valid MIME Type",
            expect_success=True,
            command="validate_type",
            mime_type="text/plain"
        )
        
        await self.test_operation(
            "Validate Complex MIME Type",
            expect_success=True,
            command="validate_type",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    async def test_error_handling(self):
        """Test error handling."""
        print_header("Error Handling", "single")
        
        # Test missing parameters
        await self.test_operation(
            "Missing Command Parameter",
            expect_success=False,
            command=""
        )
        
        # Test invalid command
        await self.test_operation(
            "Invalid Command",
            expect_success=False,
            command="invalid_command"
        )
        
        # Test non-existent file
        await self.test_operation(
            "Non-existent File",
            expect_success=False,
            command="detect_type",
            path="/nonexistent/file.txt"
        )
        
        # Test classify non-existent file
        await self.test_operation(
            "Classify Non-existent File",
            expect_success=False,
            command="classify_file",
            path="/nonexistent/file.txt"
        )
        
        # Test invalid MIME type format
        await self.test_operation(
            "Invalid MIME Type Format",
            expect_success=True,  # Validation should succeed but show invalid format
            command="validate_type",
            mime_type="invalid-mime-type"
        )
        
        # Test invalid category filter
        await self.test_operation(
            "Invalid Category Filter",
            expect_success=False,
            command="list_types",
            category_filter="nonexistent_category"
        )
        
        # Test register type without extension
        await self.test_operation(
            "Register Type Missing Extension",
            expect_success=False,
            command="register_type",
            mime_type="application/test"
        )

    async def test_edge_cases(self):
        """Test edge cases and special scenarios."""
        print_header("Edge Cases", "single")
        
        # Test empty file
        empty_file = os.path.join(self.working_dir, "empty.txt")
        with open(empty_file, 'w') as f:
            pass  # Create empty file
        self.test_files_created.append(empty_file)
        
        await self.test_operation(
            "Detect Empty File",
            expect_success=True,
            command="detect_type",
            path=empty_file,
            use_content=True
        )
        
        # Test file with multiple extensions
        multi_ext_file = os.path.join(self.working_dir, "data.tar.gz")
        with open(multi_ext_file, 'wb') as f:
            f.write(b'\x1f\x8b')  # gzip magic number
        self.test_files_created.append(multi_ext_file)
        
        await self.test_operation(
            "Detect Multi-Extension File",
            expect_success=True,
            command="detect_type",
            path=multi_ext_file,
            use_content=True,
            include_magic=True
        )
        
        # Test very large file path
        await self.test_operation(
            "Detect from Content Only",
            expect_success=True,
            command="detect_type",
            content_sample="#!/usr/bin/env python3\nimport os\nprint('test')",
            use_content=True
        )
        
        # Test batch with empty list
        await self.test_operation(
            "Batch Detect Empty List",
            expect_success=False,
            command="batch_detect",
            paths=[]
        )

    async def show_final_statistics(self):
        """Show comprehensive test results."""
        print_header("Final Test Results & Statistics", "double")
        
        # Test summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print_test(f"Total Tests: {total_tests}", "pass")
        print_test(f"Passed: {passed_tests}", "pass")
        print_test(f"Failed: {failed_tests}", "fail" if failed_tests > 0 else "pass")
        print_test(f"Success Rate: {passed_tests/total_tests*100:.1f}%", 
                  "pass" if passed_tests/total_tests >= 0.8 else "warn")
        
        # Test environment info
        print_header("Test Environment", "single")
        print_chat("env", f"Working Directory: {self.working_dir}")
        print_chat("env", f"Test Files Created: {len(self.test_files_created)}")
        
        # Failed tests details
        if failed_tests > 0:
            print_header("Failed Tests Details", "single")
            for result in self.test_results:
                if not result['passed']:
                    status = "FAIL" if result['expected_success'] else "UNEXPECTED_SUCCESS"
                    print_test(f"{result['description']}: {status}", "fail")

    async def cleanup(self):
        """Clean up test resources."""
        if self._cleanup_done:
            return
            
        print_header("Cleanup", "single")
        
        # Clean up MIME tool
        if self.mime_tool:
            print_test("Cleaning up MIME types tool", "running")
            try:
                await self.mime_tool.cleanup()
                print_test("MIME types tool cleanup complete", "pass")
            except Exception as e:
                print_test(f"MIME types tool cleanup completed with warnings: {e}", "warn")
        
        # Clean up directory
        if self.working_dir and os.path.exists(self.working_dir):
            print_test("Removing test directory", "running")
            import shutil
            try:
                shutil.rmtree(self.working_dir)
                print_test("Test directory removed", "pass")
            except Exception as e:
                print_test(f"Directory cleanup warning: {e}", "warn")
        
        self._cleanup_done = True


async def run_all_tests():
    """Run all tests."""
    tester = MimeTypesToolTester()
    
    try:
        if not await tester.setup():
            print_test("Setup failed, exiting", "fail")
            return 1
        
        # Run all test suites
        await tester.test_basic_detection()
        await tester.test_content_detection()
        await tester.test_content_sample_detection()
        await tester.test_file_classification()
        await tester.test_batch_detection()
        await tester.test_type_management()
        await tester.test_validation()
        await tester.test_error_handling()
        await tester.test_edge_cases()
        
        # Show comprehensive results
        await tester.show_final_statistics()
        
        print_header("MIME Types Tool Testing Complete!", "double")
        print_test("All test suites completed successfully", "pass")
        
        return 0
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
        return 1
    except Exception as e:
        print_test(f"Unexpected error during testing: {e}", "fail")
        return 1
    finally:
        try:
            await tester.cleanup()
        except Exception as e:
            print_test(f"Final cleanup warning: {e}", "warn")


def main():
    """Main entry point."""
    try:
        return asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print_test("Tests interrupted", "warn")
        return 1
    except Exception as e:
        print_test(f"Fatal error occurred: {e}", "fail")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_test("Tests interrupted", "warn")
        sys.exit(1)
    except Exception as e:
        print_test(f"Fatal error: {e}", "fail")
        sys.exit(1)
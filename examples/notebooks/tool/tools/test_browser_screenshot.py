#!/usr/bin/env python3
"""
Enhanced Browser Tool Testing Script with Screenshot Support

Tests browser functionality and saves screenshots for visual validation.
"""

import asyncio
import sys
import os
import base64
from pathlib import Path
from datetime import datetime


from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.browser.browser import BrowserUseTool
from enterprise_ai.tool.core.result import ToolResult


class EnhancedBrowserTester:
    """Enhanced browser tool tester with screenshot support."""
    
    def __init__(self):
        self.browser = None
        self.screenshot_dir = Path("browser_test_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_count = 0
    
    def save_screenshot(self, result: ToolResult, action_name: str) -> str:
        """Save screenshot from result if available."""
        if hasattr(result, 'base64_image') and result.base64_image:
            self.screenshot_count += 1
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{self.screenshot_count:02d}_{action_name}_{timestamp}.jpg"
            filepath = self.screenshot_dir / filename
            
            try:
                # Decode and save the image
                image_data = base64.b64decode(result.base64_image)
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                
                print_test(f"📸 Screenshot saved: {filename}", "pass")
                return str(filepath)
            except Exception as e:
                print_test(f"📸 Screenshot save failed: {e}", "fail")
                return ""
        return ""
    
    async def setup(self):
        """Initialize browser tool."""
        print_header("Enhanced Browser Tool Test Suite", "double")
        print_test("Setting up browser tool", "running")
        
        self.browser = BrowserUseTool()
        success = await self.browser.initialize()
        
        if success:
            print_test("Browser tool initialized", "pass")
            return True
        else:
            print_test("Browser tool initialization failed", "fail")
            return False
    
    async def test_action_with_screenshot(self, action_name: str, save_screenshot: bool = False, **kwargs):
        """Test a single browser action and optionally save screenshot."""
        print_test(f"Testing: {action_name}", "running")
        
        try:
            with Timer(f"Action: {action_name}"):
                result = await self.browser.execute(action=action_name, **kwargs)
            
            if isinstance(result, ToolResult) and result.success:
                print_test(f"{action_name}: SUCCESS", "pass")
                
                # Save screenshot if requested and available
                if save_screenshot:
                    screenshot_path = self.save_screenshot(result, action_name)
                
                # Show result if not too long
                if hasattr(result, 'result') and result.result:
                    output = str(result.result)
                    if len(output) > 300:
                        output = output[:300] + "..."
                    print_chat("tool", output)
                
                return result, True
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{action_name}: FAILED - {error_msg}", "fail")
                return result, False
                
        except Exception as e:
            print_test(f"{action_name}: EXCEPTION - {e}", "fail")
            return None, False
    
    async def run_screenshot_tests(self):
        """Test screenshot capture functionality specifically."""
        print_header("Screenshot Capture Tests", "single")
        
        # Navigate to visually interesting pages and capture screenshots
        test_pages = [
            ("https://httpbin.org/", "httpbin_homepage"),
            ("https://example.com", "example_com"),
            ("https://www.python.org/", "python_homepage"),
        ]
        
        for url, page_name in test_pages:
            await self.test_action_with_screenshot("go_to_url", url=url)
            result, success = await self.test_action_with_screenshot(
                "get_current_state", 
                save_screenshot=True
            )
            
            if success and result:
                if hasattr(result, 'base64_image') and result.base64_image:
                    img_size = len(result.base64_image)
                    print_test(f"📸 Screenshot captured: {img_size} chars base64", "pass")
                else:
                    print_test("📸 No screenshot in result", "warn")
    
    async def run_interaction_with_screenshots(self):
        """Test interactions and capture state changes."""
        print_header("Interaction Tests with Screenshots", "single")
        
        # Navigate to a form page
        await self.test_action_with_screenshot("go_to_url", url="https://httpbin.org/forms/post")
        await self.test_action_with_screenshot("get_current_state", save_screenshot=True)
        
        # Test scrolling and capture state
        await self.test_action_with_screenshot("scroll_down", scroll_amount=200)
        await self.test_action_with_screenshot("get_current_state", save_screenshot=True)
        
        await self.test_action_with_screenshot("scroll_up", scroll_amount=200)
        await self.test_action_with_screenshot("get_current_state", save_screenshot=True)
    
    async def test_content_extraction_fixed(self):
        """Test content extraction with better error handling."""
        print_header("Content Extraction Tests (Fixed)", "single")
        
        await self.test_action_with_screenshot("go_to_url", url="https://example.com")
        
        print_test("Testing content extraction (may fail due to LLM config)", "running")
        
        # Test extraction but handle the LLM error gracefully
        try:
            result, success = await self.test_action_with_screenshot(
                "extract_content", 
                goal="Get the main content and purpose of this website"
            )
            
            if success:
                print_test("Content extraction worked!", "pass")
            else:
                print_test("Content extraction failed (expected due to LLM config)", "warn")
                
        except Exception as e:
            print_test(f"Content extraction error (expected): {e}", "warn")
    
    async def show_screenshot_summary(self):
        """Show summary of captured screenshots."""
        print_header("Screenshot Summary", "single")
        
        screenshots = list(self.screenshot_dir.glob("*.jpg"))
        print_test(f"Total screenshots captured: {len(screenshots)}", "pass")
        
        if screenshots:
            print_test("Screenshots saved in:", "pass")
            for screenshot in sorted(screenshots):
                size_kb = screenshot.stat().st_size / 1024
                print_chat("tool", f"  📸 {screenshot.name} ({size_kb:.1f}KB)")
        
        if screenshots:
            print_test(f"Open screenshots folder: {self.screenshot_dir.absolute()}", "pass")
    
    async def cleanup(self):
        """Clean up browser resources."""
        print_header("Cleanup", "single")
        
        if self.browser:
            print_test("Cleaning up browser", "running")
            await self.browser.cleanup()
            print_test("Browser cleanup complete", "pass")


async def main():
    """Run all enhanced browser tests."""
    tester = EnhancedBrowserTester()
    
    # Setup
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run test suites with screenshot capture
        await tester.run_screenshot_tests()
        await tester.run_interaction_with_screenshots()
        await tester.test_content_extraction_fixed()
        
        # Show screenshot summary
        await tester.show_screenshot_summary()
        
        print_header("All Enhanced Tests Complete!", "double")
        
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
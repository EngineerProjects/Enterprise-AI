#!/usr/bin/env python3
"""
Simple Browser Usage Test - Visual Browser Operations  
====================================================

Quick validation test to verify browser tool works with:
✅ VISIBLE browser (non-headless) so you can see operations
✅ Real navigation and screenshot capture
✅ Simple logging to logs/ folder

Under 150 lines - just validates browser functionality works.
"""

import asyncio
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def setup_simple_logging():
    """Setup simple .log file logging (optional)."""
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Simple log file setup
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / "browser_test.log"),
            logging.StreamHandler()  # Also show in console
        ]
    )
    return logging.getLogger("browser_test")

async def simple_browser_usage_test():
    """Simple browser usage test with VISIBLE browser."""
    
    print("🌐 Simple Browser Usage Test")
    print("=" * 35)
    print("📝 Browser will be VISIBLE so you can see operations!")
    
    # Optional logging
    logger = setup_simple_logging()
    logger.info("Starting browser test")
    
    try:
        # Try Firefox first (more reliable for testing)
        print("\n🔧 Testing Firefox browser...")
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        
        # VISIBLE browser configuration
        firefox_options = FirefoxOptions()
        # NOTE: NO --headless flag = browser will be visible!
        
        print("   🦊 Opening Firefox browser (you should see it)...")
        driver = webdriver.Firefox(options=firefox_options)
        
        browser_type = "Firefox"
        
    except Exception as firefox_error:
        print(f"   ⚠️  Firefox failed: {firefox_error}")
        
        # Fallback to Chrome with better configuration
        print("\n🔧 Trying Chrome browser...")
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1200,800")
        
        print("   🚀 Opening Chrome browser (you should see it)...")
        driver = webdriver.Chrome(options=chrome_options)
        browser_type = "Chrome"
        
        # Test navigation - you'll see this happen!
        print(f"   🌐 Navigating to test page with {browser_type}...")
        driver.get("https://httpbin.org/html")
        
        # Wait so you can see the page
        print("   ⏱️  Waiting 3 seconds (observe the browser)...")
        await asyncio.sleep(3)
        
        # Get page info
        title = driver.title
        current_url = driver.current_url
        print(f"   📄 Page title: {title}")
        print(f"   🔗 Current URL: {current_url}")
        
        # Take screenshot  
        print("   📸 Taking screenshot...")
        screenshot_path = Path(__file__).parent / "logs" / "browser_screenshot.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"   💾 Screenshot saved: {screenshot_path.name}")
        
        # Get some page text
        body_text = driver.find_element("tag name", "body").text
        print(f"   📝 Page text length: {len(body_text)} characters")
        
        # Close browser
        print("   🔒 Closing browser...")
        driver.quit()
        
        logger.info("Browser test completed successfully")
        print("\n✅ Browser functionality working!")
        return True
        
    except ImportError:
        print("❌ Selenium not available")
        return False
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        logger.error(f"Browser test failed: {e}")
        return False

async def test_original_browser_tool():
    """Quick test of original browser tool if available."""
    print("\n🔍 Testing original Enterprise-AI browser tool...")
    
    try:
        from enterprise_ai.tool.browser.browser import BrowserUseTool
        
        # Configure for VISIBLE browser
        browser_tool = BrowserUseTool()
        
        # Try to initialize
        init_ok = await browser_tool.initialize()
        print(f"   {'✅' if init_ok else '❌'} Original browser tool: {'Working' if init_ok else 'Not available'}")
        
        if init_ok:
            # Quick navigation test
            result = await browser_tool.execute(action="go_to_url", url="https://httpbin.org/html")
            print(f"   {'✅' if result.success else '❌'} Navigation test")
            
            # Cleanup
            await browser_tool.cleanup()
        
        return init_ok
        
    except ImportError as e:
        print(f"   ⚠️  Original browser tool not available: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Original browser tool error: {e}")
        return False

async def main():
    """Main test function."""
    
    # Test 1: Simple browser with Selenium (visible)
    selenium_works = await simple_browser_usage_test()
    
    # Test 2: Original browser tool
    original_works = await test_original_browser_tool()
    
    # Summary
    print(f"\n🎯 SUMMARY")
    print(f"=" * 15)
    print(f"🔧 Selenium browser: {'✅ Working' if selenium_works else '❌ Failed'}")
    print(f"🌐 Original browser tool: {'✅ Working' if original_works else '❌ Not available'}")
    
    if selenium_works or original_works:
        print(f"\n🎉 Browser functionality is available!")
        print(f"📁 Check logs/ folder for browser_test.log and screenshot")
        return 0
    else:
        print(f"\n⚠️  No browser functionality available")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

"""
Comprehensive test for browser tool content extraction capabilities.
"""

import asyncio
import sys
import os

# Add project root
project_root = "/home/amiche/Projects/AI/Enterprise-AI"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def test_browser_tool():
    """Test browser tool content extraction capabilities."""
    print("🔷 TESTING BROWSER TOOL CONTENT EXTRACTION")
    print("=" * 60)
    
    try:
        from enterprise_ai.tool.browser.browser import BrowserUseTool
        
        # Initialize browser tool
        browser_tool = BrowserUseTool()
        await browser_tool.initialize()
        print("✅ Browser tool initialized")
        
        # Test 1: Basic Navigation
        print("\n📊 TEST 1: BASIC NAVIGATION")
        print("-" * 40)
        
        result = await browser_tool.execute(action="go_to_url", url="https://httpbin.org/html")
        if result.success:
            print("✅ Navigation successful")
        else:
            print(f"❌ Navigation failed: {result.result}")
            return
        
        # Test 2: Get Current Page State  
        print("\n📊 TEST 2: PAGE STATE EXTRACTION")
        print("-" * 40)
        
        state_result = await browser_tool.execute(action="get_current_state")
        if state_result.success:
            print("✅ Page state retrieved")
            print(f"   State data length: {len(state_result.result)} characters")
        else:
            print(f"❌ Page state failed: {state_result.result}")
        
        # Test 3: Basic Page Content
        print("\n📊 TEST 3: BASIC PAGE CONTENT")
        print("-" * 40)
        
        try:
            # Test the internal _get_page_content method
            page_content = await browser_tool._get_page_content()
            if page_content:
                print(f"✅ Basic content extraction: {len(page_content)} characters")
                print(f"   Content preview: {page_content[:200]}...")
            else:
                print("❌ No content extracted")
        except Exception as e:
            print(f"❌ Basic content extraction error: {e}")
        
        # Test 4: LLM-Guided Content Extraction
        print("\n📊 TEST 4: LLM-GUIDED EXTRACTION")
        print("-" * 40)
        
        try:
            extraction_result = await browser_tool.execute(
                action="extract_content",
                goal="Extract the main heading and any paragraph text from this page"
            )
            
            if extraction_result.success:
                print("✅ LLM-guided extraction successful")
                print(f"   Extracted data: {extraction_result.result[:300]}...")
            else:
                print(f"❌ LLM-guided extraction failed: {extraction_result.result}")
        except Exception as e:
            print(f"❌ LLM-guided extraction error: {e}")
        
        # Test 5: Navigate to Different Page Type
        print("\n📊 TEST 5: COMPLEX PAGE NAVIGATION")
        print("-" * 40)
        
        result2 = await browser_tool.execute(action="go_to_url", url="https://python.org")
        if result2.success:
            print("✅ Navigation to Python.org successful")
            
            # Test content extraction on a real website
            try:
                extraction_result2 = await browser_tool.execute(
                    action="extract_content", 
                    goal="Find information about Python downloads and latest version"
                )
                
                if extraction_result2.success:
                    print("✅ Real website extraction successful")
                    print(f"   Extracted data: {extraction_result2.result[:200]}...")
                else:
                    print(f"❌ Real website extraction failed: {extraction_result2.result}")
            except Exception as e:
                print(f"❌ Real website extraction error: {e}")
        else:
            print(f"❌ Navigation to Python.org failed: {result2.result}")
        
        # Test 6: Performance Test
        print("\n📊 TEST 6: PERFORMANCE TEST")
        print("-" * 40)
        
        import time
        start_time = time.time()
        
        try:
            perf_result = await browser_tool.execute(
                action="extract_content",
                goal="Extract the main navigation menu items"
            )
            
            extraction_time = time.time() - start_time
            print(f"✅ Performance test: {extraction_time:.2f}s")
            
            if perf_result.success:
                print("✅ Performance extraction successful")
            else:
                print(f"❌ Performance extraction failed: {perf_result.result}")
                
        except Exception as e:
            print(f"❌ Performance test error: {e}")
        
        # Cleanup
        print("\n🧹 CLEANUP")
        print("-" * 40)
        
        try:
            await browser_tool.cleanup()
            print("✅ Browser tool cleanup successful")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
        
    except Exception as e:
        print(f"❌ Browser tool test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎯 BROWSER TOOL TEST COMPLETE")


async def test_browser_vs_research_extraction():
    """Compare browser tool vs research tool extraction on same URL."""
    print("\n" + "=" * 60)
    print("🔷 BROWSER vs RESEARCH EXTRACTION COMPARISON")
    print("=" * 60)
    
    test_url = "https://httpbin.org/html"
    
    # Test Browser Tool Extraction
    print("📊 BROWSER TOOL EXTRACTION:")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.browser.browser import BrowserUseTool
        
        browser_tool = BrowserUseTool()
        await browser_tool.initialize()
        
        await browser_tool.execute(action="go_to_url", url=test_url)
        browser_content = await browser_tool._get_page_content()
        
        browser_result = await browser_tool.execute(
            action="extract_content",
            goal="Extract all text content from this page"
        )
        
        print(f"✅ Browser basic content: {len(browser_content)} chars")
        print(f"✅ Browser LLM extraction: {'SUCCESS' if browser_result.success else 'FAILED'}")
        
        await browser_tool.cleanup()
        
    except Exception as e:
        print(f"❌ Browser tool error: {e}")
    
    # Test Research Tool Extraction
    print("\n📊 RESEARCH TOOL EXTRACTION:")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.content_extractor import EnterpriseContentExtractor
        
        research_extractor = EnterpriseContentExtractor(timeout=15)
        research_result = await research_extractor.extract(test_url)
        
        if research_result.success:
            print(f"✅ Research extraction: {research_result.char_count} chars via {research_result.method}")
        else:
            print(f"❌ Research extraction failed: {research_result.error}")
        
    except Exception as e:
        print(f"❌ Research tool error: {e}")
    
    print("\n🎯 COMPARISON COMPLETE")


if __name__ == "__main__":
    asyncio.run(test_browser_tool())
    asyncio.run(test_browser_vs_research_extraction())

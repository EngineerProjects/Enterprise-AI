"""
Test the integrated content extraction in research tools.
"""

import asyncio
import sys
import os

# Add project root
project_root = "/home/amiche/Projects/AI/Enterprise-AI"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def test_integration():
    """Test the integrated content extraction in research tools."""
    print("🔷 TESTING RESEARCH TOOLS INTEGRATION")
    print("=" * 60)
    
    # Test 1: Web Search Tool with optimized extraction
    print("📊 TEST 1: WEB SEARCH TOOL")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.web_search import WebSearch
        
        search_tool = WebSearch()
        await search_tool.initialize()
        print("✅ WebSearch tool initialized")
        
        # Test with content fetching enabled
        response = await search_tool.execute(
            query="artificial intelligence news",
            num_results=2,
            fetch_content=True
        )
        
        print(f"✅ Search completed: {len(response.results)} results")
        
        # Check if results have content
        content_count = 0
        for result in response.results:
            if hasattr(result, 'raw_content') and result.raw_content:
                content_count += 1
                print(f"   Content extracted: {len(result.raw_content)} chars from {result.url}")
        
        print(f"✅ Content extraction: {content_count}/{len(response.results)} results have content")
        
    except Exception as e:
        print(f"❌ WebSearch test error: {e}")
    
    print()
    
    # Test 2: Deep Research Tool with enhanced extraction
    print("📊 TEST 2: DEEP RESEARCH TOOL")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.deep_research import DeepResearch
        
        research_tool = DeepResearch()
        await research_tool.initialize()
        print("✅ DeepResearch tool initialized")
        
        # Test with a focused query
        summary = await research_tool.execute(
            query="latest AI breakthroughs",
            max_depth=1,  # Limit depth for testing
            max_results=2
        )
        
        print(f"✅ Research completed: {len(summary.insights)} insights found")
        
        # Check insights quality
        for i, insight in enumerate(summary.insights, 1):
            print(f"   Insight {i}: {insight.content[:100]}... (relevance: {insight.relevance_score})")
        
        print(f"✅ Research summary generated with {len(summary.insights)} insights")
        
    except Exception as e:
        print(f"❌ DeepResearch test error: {e}")
    
    print()
    
    # Test 3: Content fetcher directly
    print("📊 TEST 3: DIRECT CONTENT FETCHER")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.web_search import WebContentFetcher
        
        fetcher = WebContentFetcher()
        print("✅ WebContentFetcher created")
        
        # Test content extraction
        content = await fetcher.fetch_content("https://httpbin.org/html")
        if content:
            print(f"✅ Direct extraction: {len(content)} characters")
        else:
            print("❌ Direct extraction failed")
            
    except Exception as e:
        print(f"❌ Direct fetcher test error: {e}")
    
    print()
    print("🎯 INTEGRATION TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(test_integration())

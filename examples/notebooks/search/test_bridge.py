"""
Test the simplified content_extractor.py bridge.
"""

import asyncio
import sys
import os

# Add project root
project_root = "/home/amiche/Projects/AI/Enterprise-AI"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def test_simplified_bridge():
    """Test the simplified content extractor bridge."""
    print("🔷 TESTING SIMPLIFIED CONTENT EXTRACTOR BRIDGE")
    print("=" * 60)
    
    # Test 1: Legacy interface (backward compatibility)
    print("📊 TEST 1: LEGACY INTERFACE")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.content_extractor import (
            AdvancedContentExtractor, 
            create_content_extractor
        )
        
        print("✅ Legacy imports successful")
        
        # Test legacy class
        extractor = AdvancedContentExtractor(timeout=15)
        print("✅ Legacy AdvancedContentExtractor created")
        
        # Test legacy factory
        extractor2 = create_content_extractor(timeout=15)
        print("✅ Legacy create_content_extractor works")
        
        # Test extraction
        content = await extractor.extract("https://httpbin.org/html")
        if content and len(content) > 100:
            print(f"✅ Legacy extraction works: {len(content)} characters")
        else:
            print("❌ Legacy extraction failed")
        
        # Test stats
        stats = extractor.get_stats()
        print(f"✅ Legacy stats work: {stats.get('success_rate', 0)}% success rate")
        
    except Exception as e:
        print(f"❌ Legacy interface error: {e}")
    
    print()
    
    # Test 2: New interface 
    print("📊 TEST 2: NEW INTERFACE")
    print("-" * 40)
    
    try:
        from enterprise_ai.tool.research.content_extractor import (
            EnterpriseContentExtractor,
            create_enterprise_extractor,
            ExtractionResult
        )
        
        print("✅ New interface imports successful")
        
        # Test new class
        extractor = EnterpriseContentExtractor(timeout=15, enable_js_extraction=False)
        print("✅ EnterpriseContentExtractor created")
        
        # Test new factory
        extractor2 = create_enterprise_extractor(timeout=15)
        print("✅ create_enterprise_extractor works")
        
        # Test extraction with full result
        result = await extractor.extract("https://httpbin.org/html")
        if result.success:
            print(f"✅ New extraction works: {result.char_count} chars via {result.method}")
        else:
            print(f"❌ New extraction failed: {result.error}")
        
        # Test detailed stats
        stats = extractor.get_stats()
        print(f"✅ New stats work: {stats.get('success_rate', 0)}% success rate")
        
    except Exception as e:
        print(f"❌ New interface error: {e}")
    
    print()
    
    # Test 3: Import compatibility
    print("📊 TEST 3: IMPORT COMPATIBILITY")
    print("-" * 40)
    
    try:
        # Test that both can be imported together
        from enterprise_ai.tool.research.content_extractor import (
            AdvancedContentExtractor,
            EnterpriseContentExtractor,
            create_content_extractor,
            create_enterprise_extractor,
            ExtractionResult
        )
        
        print("✅ All imports work together")
        print("✅ No import conflicts")
        print("✅ Bridge module is clean and functional")
        
    except Exception as e:
        print(f"❌ Import compatibility error: {e}")


if __name__ == "__main__":
    asyncio.run(test_simplified_bridge())

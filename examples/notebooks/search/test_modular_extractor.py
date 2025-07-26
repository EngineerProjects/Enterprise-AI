"""
Test the optimized modular content extraction system.
"""

import asyncio
import sys
import os
import time

# Add project root
project_root = "/home/amiche/Projects/AI/Enterprise-AI"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


async def test_modular_system():
    """Test the new modular extraction system."""
    print("🔷 TESTING OPTIMIZED MODULAR EXTRACTION SYSTEM")
    print("=" * 60)
    
    try:
        # Test new modular system
        from enterprise_ai.tool.research.extraction import (
            create_enterprise_extractor,
            get_available_methods
        )
        
        print("✅ Modular extraction system imported successfully")
        
        # Show available methods
        available = get_available_methods()
        print(f"📊 Available methods: {available}")
        
        # Create extractor
        extractor = create_enterprise_extractor(
            timeout=20,
            enable_js_extraction=False  # Disable slow methods for testing
        )
        
        print(f"✅ Extractor created with methods: {extractor.get_available_methods()}")
        
    except ImportError as e:
        print(f"❌ Could not import modular system: {e}")
        return
    
    # Test URLs
    test_urls = [
        "https://httpbin.org/html",
        "https://python.org",
        "https://example.com"
    ]
    
    print("\n📊 EXTRACTION TESTS:")
    print("-" * 60)
    
    for i, url in enumerate(test_urls, 1):
        print(f"[{i}/{len(test_urls)}] Testing: {url}")
        
        try:
            start_time = time.time()
            result = await extractor.extract(url)
            extraction_time = time.time() - start_time
            
            if result.success:
                print(f"✅ SUCCESS: {result.char_count:,} chars via {result.method} ({extraction_time:.2f}s)")
            else:
                print(f"❌ FAILED: {result.error}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        print()
    
    # Test legacy compatibility
    print("🔄 TESTING LEGACY COMPATIBILITY:")
    print("-" * 60)
    
    try:
        from enterprise_ai.tool.research.content_extractor import AdvancedContentExtractor
        
        legacy_extractor = AdvancedContentExtractor(timeout=15)
        print("✅ Legacy AdvancedContentExtractor created")
        
        # Test legacy interface
        content = await legacy_extractor.extract("https://httpbin.org/html")
        if content:
            print(f"✅ Legacy interface works: {len(content)} characters")
        else:
            print("❌ Legacy interface failed")
            
    except Exception as e:
        print(f"❌ Legacy compatibility error: {e}")
    
    # Show final stats
    try:
        stats = extractor.get_stats()
        print("\n📈 FINAL STATISTICS:")
        print(f"Success Rate: {stats.get('success_rate', 0)}%")
        print(f"Total Attempts: {stats.get('total_attempts', 0)}")
        
        method_breakdown = stats.get('method_breakdown', {})
        for method, data in method_breakdown.items():
            if isinstance(data, dict) and data.get('attempts', 0) > 0:
                print(f"{method}: {data.get('successes', 0)}/{data.get('attempts', 0)} ({data.get('success_rate', 0)}%)")
                
    except Exception as e:
        print(f"Could not get final stats: {e}")


if __name__ == "__main__":
    asyncio.run(test_modular_system())

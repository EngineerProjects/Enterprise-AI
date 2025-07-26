import asyncio
import sys
import os

# Add your project root
project_root = "/home/amiche/Projects/AI/Enterprise-AI"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

MIN_PREVIEW_LENGTH = 2000

def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"🔷 {title}")
    print("=" * 60 + "\n")

def preview_content(content: str):
    if not content:
        print("❌ No content extracted.")
        return

    trimmed = content.strip()
    length = len(trimmed)

    print(f"✅ Extracted {length} characters")
    print("\n📄 PREVIEW:")
    if length >= MIN_PREVIEW_LENGTH:
        print(trimmed[:length])
    else:
        print(trimmed)
        print("\n⚠️ Content below 2,000 characters. Consider using Playwright or increasing timeout.")

async def test_urls():
    """Run tests on predefined URLs with the AdvancedContentExtractor."""
    print_section("INITIALIZING CONTENT EXTRACTOR TESTS")

    try:
        from enterprise_ai.tool.research.content_extractor import AdvancedContentExtractor
        extractor = AdvancedContentExtractor(timeout=20)
        print("✅ AdvancedContentExtractor loaded (timeout=20s)\n")
    except ImportError as e:
        print(f"❌ Failed to import extractor: {e}")
        return

    urls = [
        "https://httpbin.org/html",
        "https://example.com",
        "https://python.org",
        "https://moonshotai.github.io/Kimi-K2/",
        "https://en.wikipedia.org/wiki/History_of_mathematics",
        "https://www.artificialintelligence-news.com/news/sam-altman-ai-cause-job-losses-national-security-threats/"
    ]

    results = []

    for index, url in enumerate(urls, start=1):
        print_section(f"TEST {index}: {url}")
        try:
            content = await extractor.extract(url)
            preview_content(content)
            results.append((url, True, len(content)))
        except Exception as e:
            print(f"❌ Extraction error: {e}")
            results.append((url, False, 0))

    print_section("TEST SUMMARY")
    successes = sum(1 for _, success, _ in results if success)
    for url, success, length in results:
        status = "✅ Success" if success else "❌ Failed"
        print(f"{status}: {url} → {length} characters")

    stats = extractor.get_stats()
    print_section("METHOD BREAKDOWN")
    print(f"Total Attempts: {stats['total_attempts']}")
    print(f"Success Rate: {stats['success_rate']}%")
    for method, count in stats['method_breakdown'].items():
        print(f"  - {method}: {count}")

async def main():
    await test_urls()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted.")
    except Exception as e:
        print(f"\n❌ Fatal test error: {e}")

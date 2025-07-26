"""
Playwright extraction method - optimized for JavaScript-heavy sites.
"""

import asyncio
from typing import List

from .base import BrowserMethod, ExtractionResult
from ..validation import is_valid_content


class PlaywrightMethod(BrowserMethod):
    """Playwright method optimized for JavaScript sites with better performance."""
    
    @property
    def dependencies(self) -> List[str]:
        """Required dependencies."""
        return ["playwright"]
    
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content using Playwright with performance optimizations."""
        if not self.is_available():
            return self.create_result(url, error="Playwright not installed")
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                # Launch browser with optimized settings for speed
                browser = await p.chromium.launch(
                    headless=True,
                    args=self.get_browser_args() + [
                        '--disable-images',           # Faster loading
                        '--disable-javascript-harmony-shipping',
                        '--disable-background-networking',
                        '--disable-background-sync',
                        '--disable-default-apps',
                        '--disable-sync',
                    ]
                )
                
                try:
                    # Create optimized context
                    context = await browser.new_context(
                        user_agent=self.get_user_agent(),
                        viewport={'width': 1366, 'height': 768},
                        ignore_https_errors=True,
                        java_script_enabled=True,
                        locale='en-US'
                    )
                    
                    # Block unnecessary resources for faster loading
                    await context.route("**/*", self._handle_route)
                    
                    page = await context.new_page()
                    
                    # Navigate with optimized timeout
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",  # Faster than networkidle
                        timeout=self.timeout * 1000
                    )
                    
                    # Wait briefly for dynamic content
                    await asyncio.sleep(1)
                    
                    # Remove noise elements efficiently
                    await page.evaluate("""
                        () => {
                            const removeSelectors = [
                                'nav', 'header', 'footer', 'aside', '.sidebar',
                                '.ad', '.ads', '.advertisement', '.banner',
                                '.popup', '.modal', '.overlay', '.cookie',
                                '.social', '.share', '.comment-form',
                                'script', 'style', 'noscript'
                            ];
                            
                            removeSelectors.forEach(selector => {
                                document.querySelectorAll(selector).forEach(el => {
                                    try { el.remove(); } catch(e) {}
                                });
                            });
                        }
                    """)
                    
                    # Extract content with smart selection
                    content = await page.evaluate("""
                        () => {
                            const contentSelectors = [
                                'main', '[role="main"]', '.main-content', '#main-content',
                                'article', '.article', '.post', '.entry-content',
                                '.content', '#content', '.text', '.body',
                                '.story', '.article-body', '.post-content'
                            ];
                            
                            let bestContent = '';
                            let maxScore = 0;
                            
                            // Score each potential content area
                            contentSelectors.forEach(selector => {
                                const elements = document.querySelectorAll(selector);
                                elements.forEach(el => {
                                    const text = el.innerText || '';
                                    const wordCount = text.split(/\s+/).length;
                                    const hasStructure = (text.match(/[.!?]/g) || []).length > 3;
                                    
                                    // Score based on length and structure
                                    const score = wordCount + (hasStructure ? 100 : 0);
                                    
                                    if (score > maxScore && text.length > 200) {
                                        maxScore = score;
                                        bestContent = text;
                                    }
                                });
                            });
                            
                            // Fallback to body if no content area found
                            if (!bestContent || bestContent.length < 200) {
                                bestContent = document.body.innerText || '';
                            }
                            
                            return bestContent.trim();
                        }
                    """)
                    
                    if content and is_valid_content(content):
                        return self.create_result(url, content=content)
                    
                    return self.create_result(url, error="Content validation failed")
                    
                finally:
                    await browser.close()
                    
        except asyncio.TimeoutError:
            return self.create_result(url, error=f"Timeout after {self.timeout}s")
        except Exception as e:
            return self.create_result(url, error=f"Playwright error: {str(e)}")
    
    async def _handle_route(self, route):
        """Handle route to block unnecessary resources."""
        resource_type = route.request.resource_type
        
        # Block images, stylesheets, and other non-essential resources for speed
        if resource_type in ['image', 'stylesheet', 'font', 'media']:
            await route.abort()
        else:
            await route.continue_()

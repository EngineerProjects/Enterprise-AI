"""
Selenium extraction method - for complex JavaScript sites (optional, slow).
"""

import asyncio
from typing import List

from .base import BrowserMethod, ExtractionResult
from ..validation import is_valid_content


class SeleniumMethod(BrowserMethod):
    """
    Selenium method for complex JavaScript sites.
    
    WARNING: This method is slow (40-120s per extraction) and should only be used
    as a last resort when other methods fail. Consider using Playwright instead.
    """
    
    @property
    def dependencies(self) -> List[str]:
        """Required dependencies."""
        return ["selenium"]
    
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content using Selenium (slow but thorough)."""
        if not self.is_available():
            return self.create_result(url, error="Selenium not installed")
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException
            
            # Configure Chrome options for headless operation
            options = Options()
            for arg in self.get_browser_args():
                options.add_argument(arg)
            
            # Additional speed optimizations
            options.add_argument('--disable-images')
            options.add_argument('--disable-javascript-harmony-shipping')
            options.add_argument('--disable-background-networking')
            options.add_argument(f'--user-agent={self.get_user_agent()}')
            
            # Reduce memory usage
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=4096')
            
            driver = webdriver.Chrome(options=options)
            
            try:
                # Set reduced timeout for faster failure
                driver.set_page_load_timeout(min(self.timeout, 30))
                driver.implicitly_wait(10)
                
                # Navigate to page
                driver.get(url)
                
                # Wait for basic content to load
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except TimeoutException:
                    return self.create_result(url, error="Page load timeout")
                
                # Brief wait for JavaScript content
                await asyncio.sleep(2)
                
                # Try to find main content efficiently
                content_selectors = [
                    'main', '[role="main"]', '.main-content', '#main-content',
                    'article', '.article', '.post', '.entry-content',
                    '.content', '#content', '.text', '.body'
                ]
                
                best_content = ""
                max_length = 0
                
                for selector in content_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text
                            if text and len(text) > max_length:
                                max_length = len(text)
                                best_content = text
                    except:
                        continue
                    
                    # Early exit if we found good content
                    if max_length > 1000:
                        break
                
                # Fallback to body if no specific content area found
                if not best_content or len(best_content) < 200:
                    try:
                        body = driver.find_element(By.TAG_NAME, "body")
                        best_content = body.text
                    except:
                        pass
                
                if best_content and is_valid_content(best_content):
                    return self.create_result(url, content=best_content)
                
                return self.create_result(url, error="Content validation failed")
                
            finally:
                try:
                    driver.quit()
                except:
                    pass  # Ignore cleanup errors
                    
        except Exception as e:
            return self.create_result(url, error=f"Selenium error: {str(e)}")

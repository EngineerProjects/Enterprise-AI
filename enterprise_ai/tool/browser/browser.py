"""Browser automation tool for Enterprise AI."""

import asyncio
import base64
import json
from typing import Any, Dict, List, Optional, Set, Union

from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from enterprise_ai.config import get_config
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.tool.research.web_search import WebSearch

logger = get_optimized_logger("tool.browser.browser_use")


def llm_prompt(goal: str, content: str, max_content_length: int) -> str:
    """Create a prompt for content extraction."""
    truncated_content = content[:max_content_length] if len(content) > max_content_length else content
    return f"""\
Your task is to extract the content of the page. You will be given a page and a goal, and you should extract all relevant information around this goal from the page. If the goal is vague, summarize the page. Respond in json format.

Extraction goal: {goal}

Page content:
{truncated_content}

Please extract the relevant information and format it as JSON with the following structure:
{{
  "extracted_content": {{
    "text": "The main content extracted from the page",
    "metadata": {{
      "source": "Description of the source",
      "relevance": "How the content relates to the goal"
    }}
  }}
}}
"""


def _get_llm_completion(messages, model_name=None, provider_name=None, **kwargs):
    """Lazy import and execute LLM completion with configurable model."""
    try:
        from enterprise_ai.llm import complete, CompletionOptions
        from enterprise_ai.config import get_config
        
        # Use provided model/provider or fall back to config defaults
        provider = provider_name or get_config("llm.default_provider", "ollama")
        model = model_name or get_config("llm.default_model", "llama3.2")

        timeout = kwargs.get('timeout') or get_config("llm.timeout", 120.0)
        
        # Log what we're using for debugging
        logger.debug("Using LLM provider: %s, model: %s", provider, model)
        
        return complete(
            messages=messages,
            provider_name=provider,
            model_name=model,
            options=CompletionOptions(
                temperature=kwargs.get('temperature', 0.1),
                max_tokens=kwargs.get('max_tokens', 2000),
                timeout=timeout
            )
        )
    except ImportError as e:
        logger.error("Failed to import LLM completion: %s", e)
        raise ToolError("LLM completion not available for content extraction")
    except Exception as e:
        logger.error("LLM completion failed: %s", e)
        # Return a fallback response instead of crashing
        class FallbackResponse:
            def __init__(self, content):
                self.content = content
        
        return FallbackResponse('{"extracted_content": {"text": "Content extraction temporarily unavailable", "metadata": {"source": "fallback", "relevance": "extraction failed"}}}')


@register_tool(category="browser", capabilities=["network_access", "web_automation"])
class BrowserUseTool(BaseTool):
    """
    Browser automation tool that enables web interaction and content extraction.

    Key capabilities:
    * Navigate to websites and perform web searches
    * Interact with web elements (click, input text, select from dropdowns)
    * Extract content and analyze webpage information
    * Manage multiple browser tabs
    * Scroll and navigate through pages

    Use this tool when:
    * You need to navigate and interact with web content
    * You need to fill forms or click buttons on websites
    * You need to extract information from dynamic web pages
    * You need to perform a sequence of actions on a website

    Notes:
    * Maintains state between calls, keeping the browser session alive
    * Supports numbered element references shown in browser state
    * Can handle timeout situations and page loading
    """

    name: str = "browser_use"
    description: str = """
    Browser automation tool that provides interactive web capabilities.

    * Purpose: Control a browser to navigate, interact with, and extract data from websites
    * Usage: Navigate to URLs, click elements, fill forms, extract content, and analyze web pages
    * Features: Web navigation, element interaction, content extraction, tab management, scrolling
    * Returns: The result of each browser action, including success/failure and relevant data

    The tool maintains state across calls, keeping the browser session alive until explicitly closed.
    When interacting with elements, refer to them by the numbered indices shown in the current browser state.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "go_to_url",
                    "click_element",
                    "input_text",
                    "scroll_down",
                    "scroll_up",
                    "scroll_to_text",
                    "send_keys",
                    "get_dropdown_options",
                    "select_dropdown_option",
                    "go_back",
                    "refresh",
                    "web_search",
                    "wait",
                    "extract_content",
                    "switch_tab",
                    "open_tab",
                    "close_tab",
                    "get_current_state",
                ],
                "description": "The browser action to perform",
            },
            "url": {
                "type": "string",
                "description": "URL for 'go_to_url' or 'open_tab' actions",
            },
            "index": {
                "type": "integer",
                "description": "Element index for 'click_element', 'input_text', 'get_dropdown_options', or 'select_dropdown_option' actions",
            },
            "text": {
                "type": "string",
                "description": "Text for 'input_text', 'scroll_to_text', or 'select_dropdown_option' actions",
            },
            "scroll_amount": {
                "type": "integer",
                "description": "Pixels to scroll (positive for down, negative for up) for 'scroll_down' or 'scroll_up' actions",
                "default": 500,
            },
            "tab_id": {
                "type": "integer",
                "description": "Tab ID for 'switch_tab' action",
            },
            "query": {
                "type": "string",
                "description": "Search query for 'web_search' action",
            },
            "goal": {
                "type": "string",
                "description": "Extraction goal for 'extract_content' action",
            },
            "keys": {
                "type": "string",
                "description": "Keys to send for 'send_keys' action",
            },
            "seconds": {
                "type": "integer",
                "description": "Seconds to wait for 'wait' action",
                "default": 3,
            },
        },
        "required": ["action"],
    }

    # Define capabilities
    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.BROWSER_CONTROL,
        ToolCapability.NETWORK_ACCESS,
    }

    # Tool requires initialization
    requires_initialization: bool = True

    # LLM Configuration fields (NEW)
    llm_provider: Optional[str] = Field(default=None, description="LLM provider for content extraction")
    llm_model: Optional[str] = Field(default=None, description="LLM model for content extraction")

    # Tool fields
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock, exclude=True)
    browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    context: Optional[BrowserContext] = Field(default=None, exclude=True)
    dom_service: Optional[DomService] = Field(default=None, exclude=True)
    web_search_tool: Optional["WebSearch"] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the browser automation tool with configurable LLM.
        
        Args:
            llm_provider: LLM provider to use for content extraction (e.g., "ollama", "openai")
            llm_model: Model name to use for content extraction (e.g., "llama3.2:3b", "gpt-4")
        """
        model_fields = self.__class__.model_fields

        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            config=config or ToolConfig(
                timeout=60.0, 
                max_retries=3, 
                cache_results=False, 
                sandbox_enabled=True
            ),
            llm_provider=llm_provider,  # Now this will work
            llm_model=llm_model,        # Now this will work
            **kwargs,
        )
        
        # Initialize tool fields that can't be set in super().__init__
        self.lock = asyncio.Lock()
        self.browser = None
        self.context = None
        self.dom_service = None
        self.web_search_tool = None

        logger.debug("BrowserUseTool initialized")

    @field_validator("parameters", mode="before")
    def validate_parameters(cls, v: dict, info: ValidationInfo) -> dict:
        """Validate parameters."""
        if not v:
            raise ValueError("Parameters cannot be empty")
        return v

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize the browser and any required resources.
        """
        try:
            # Initialize web search tool lazily when needed
            return True
        except Exception as e:
            logger.error("Browser initialization error: %s", e)
            return False

    async def _ensure_browser_initialized(self) -> BrowserContext:
        """
        Ensure browser and context are initialized.
        """
        if self.browser is None:
            logger.info("Initializing browser")

            # Get configuration from config system
            headless = get_config("browser_config.headless", False)
            disable_security = get_config("browser_config.disable_security", True)
            extra_args = get_config("browser_config.extra_chromium_args", [])

            # Build browser configuration
            browser_config_kwargs: Dict[str, Any] = {
                "headless": headless,
                "disable_security": disable_security,
            }

            # Add extra args if provided
            if extra_args:
                browser_config_kwargs["extra_chromium_args"] = extra_args

            try:
                self.browser = BrowserUseBrowser(BrowserConfig(**browser_config_kwargs))
                logger.debug("Browser instance created successfully")
            except Exception as e:
                logger.error("Browser creation failed: %s", e)
                raise ToolError(f"Failed to create browser: {str(e)}")

        if self.context is None:
            logger.info("Creating browser context")
            try:
                context_config = BrowserContextConfig()
                self.context = await self.browser.new_context(context_config)
                self.dom_service = DomService(await self.context.get_current_page())
                logger.debug("Browser context created successfully")
            except Exception as e:
                logger.error("Browser context creation failed: %s", e)
                raise ToolError(f"Failed to create browser context: {str(e)}")

        return self.context

    async def _get_page_content(self) -> str:
        """Get current page content."""
        if not self.context:
            return ""
        
        page = await self.context.get_current_page()
        try:
            import markdownify
            content = markdownify.markdownify(await page.content())
        except ImportError:
            # Fallback to plain text if markdownify is not available
            content = await page.inner_text('body')
        
        return content

    async def _extract_content(self, goal: str, max_content_length: int = 4000) -> str:
        """Extract content from current page using configured LLM."""
        try:
            content = await self._get_page_content()
            if not content:
                return "No content could be extracted from the page."

            prompt = llm_prompt(goal, content, max_content_length)
            messages = [Message.user_message(prompt)]
            
            # Use instance-specific LLM configuration
            response = _get_llm_completion(
                messages=messages,
                model_name=self.llm_model,
                provider_name=self.llm_provider,
                temperature=0.1,
                max_tokens=2000
            )
            
            if hasattr(response, 'content') and response.content:
                try:
                    extracted_data = json.loads(response.content)
                    return json.dumps(extracted_data, indent=2)
                except json.JSONDecodeError:
                    return response.content
            
            return "No content extracted."
            
        except Exception as e:
            logger.error("Content extraction failed: %s", e)
            return f"Content extraction failed: {str(e)}"

    async def _ensure_web_search_tool(self):
        """Ensure web search tool is initialized."""
        if self.web_search_tool is None:
            try:
                from enterprise_ai.tool.research.web_search import WebSearch
                self.web_search_tool = WebSearch()
                logger.debug("WebSearch tool initialized")
            except ImportError:
                logger.error("WebSearch tool not available")
                raise ToolError("WebSearch tool not available")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute a specified browser action.
        """
        # Apply configured timeout and retries
        execution_timeout = self.config.timeout
        retry_count = 0
        max_retries = self.config.max_retries or 0

        # Extract parameters
        action = kwargs.get("action")
        if not action:
            return ToolResult.create_error("Action parameter is required", tool_name=self.name)

        # Extract other parameters
        url = kwargs.get("url")
        index = kwargs.get("index")
        text = kwargs.get("text")
        scroll_amount = kwargs.get("scroll_amount", 500)
        tab_id = kwargs.get("tab_id")
        query = kwargs.get("query")
        goal = kwargs.get("goal")
        keys = kwargs.get("keys")
        seconds = kwargs.get("seconds", 3)

        # Execution with retries
        while retry_count <= max_retries:
            try:
                async with self.lock:
                    # Ensure browser is initialized
                    context = await self._ensure_browser_initialized()

                    # Execute the appropriate action
                    if action == "go_to_url":
                        if not url:
                            return ToolResult.create_error("URL is required for 'go_to_url' action", tool_name=self.name)

                        logger.debug("Navigating to URL: %s", url)
                        page = await context.get_current_page()
                        page_timeout = execution_timeout * 1000 if execution_timeout else 60000

                        try:
                            await page.goto(url, timeout=page_timeout)
                            await page.wait_for_load_state()
                            logger.info("Successfully navigated to: %s", url)
                            return ToolResult.create_success(f"Navigated to {url}", tool_name=self.name)
                        except Exception as e:
                            logger.error("Navigation error: %s", e)
                            return ToolResult.create_error(f"Failed to navigate to {url}: {str(e)}", tool_name=self.name)

                    elif action == "go_back":
                        logger.debug("Navigating back")
                        await context.go_back()
                        return ToolResult.create_success("Navigated back", tool_name=self.name)

                    elif action == "refresh":
                        logger.debug("Refreshing page")
                        await context.refresh_page()
                        return ToolResult.create_success("Refreshed current page", tool_name=self.name)

                    elif action == "web_search":
                        if not query:
                            return ToolResult.create_error("Query is required for 'web_search' action", tool_name=self.name)

                        logger.debug("Performing web search for: %s", query)

                        # Initialize web search tool if not already done
                        await self._ensure_web_search_tool()

                        # Execute the web search
                        search_response = await self.web_search_tool.execute(
                            query=query, fetch_content=True, num_results=5
                        )

                        # Navigate to the first search result if available
                        if hasattr(search_response, "result") and search_response.result:
                            results = search_response.result.get("results", [])
                            if results:
                                first_result = results[0]
                                url_to_navigate = first_result.get("url")

                                if url_to_navigate:
                                    page = await context.get_current_page()
                                    await page.goto(url_to_navigate)
                                    await page.wait_for_load_state()
                                    logger.info("Navigated to search result: %s", url_to_navigate)

                                    # Return the search results and navigation info
                                    return ToolResult.create_success(
                                        {
                                            "search_results": results,
                                            "navigated_to": url_to_navigate
                                        },
                                        tool_name=self.name
                                    )
                        
                        return ToolResult.create_error("No search results found", tool_name=self.name)

                    elif action == "click_element":
                        if index is None:
                            return ToolResult.create_error("Index is required for 'click_element' action", tool_name=self.name)

                        logger.debug("Clicking element at index: %s", index)
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult.create_error(f"Element with index {index} not found", tool_name=self.name)

                        download_path = await context._click_element_node(element)
                        result_msg = f"Clicked element at index {index}"
                        if download_path:
                            result_msg += f" - Downloaded file to {download_path}"

                        logger.info(result_msg)
                        return ToolResult.create_success(result_msg, tool_name=self.name)

                    elif action == "input_text":
                        if index is None or not text:
                            return ToolResult.create_error("Index and text are required for 'input_text' action", tool_name=self.name)

                        logger.debug("Inputting text at element index %s: %s", index, text)
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult.create_error(f"Element with index {index} not found", tool_name=self.name)

                        await context._input_text_element_node(element, text)
                        logger.info("Text input successful at index %s", index)
                        return ToolResult.create_success(f"Input '{text}' into element at index {index}", tool_name=self.name)

                    elif action in ["scroll_down", "scroll_up"]:
                        direction = 1 if action == "scroll_down" else -1
                        amount = scroll_amount if scroll_amount is not None else context.config.browser_window_size["height"]

                        logger.debug("Scrolling %s by %s pixels", 'down' if direction > 0 else 'up', amount)
                        await context.execute_javascript(f"window.scrollBy(0, {direction * amount});")

                        result_msg = f"Scrolled {'down' if direction > 0 else 'up'} by {amount} pixels"
                        logger.info(result_msg)
                        return ToolResult.create_success(result_msg, tool_name=self.name)

                    elif action == "scroll_to_text":
                        if not text:
                            return ToolResult.create_error("Text is required for 'scroll_to_text' action", tool_name=self.name)

                        logger.debug("Scrolling to text: '%s'", text)
                        page = await context.get_current_page()
                        try:
                            locator = page.get_by_text(text, exact=False)
                            await locator.scroll_into_view_if_needed()
                            logger.info("Successfully scrolled to text: '%s'", text)
                            return ToolResult.create_success(f"Scrolled to text: '{text}'", tool_name=self.name)
                        except Exception as e:
                            logger.error("Failed to scroll to text: %s", e)
                            return ToolResult.create_error(f"Failed to scroll to text: {str(e)}", tool_name=self.name)

                    elif action == "send_keys":
                        if not keys:
                            return ToolResult.create_error("Keys are required for 'send_keys' action", tool_name=self.name)

                        logger.debug("Sending keys: %s", keys)
                        page = await context.get_current_page()
                        await page.keyboard.press(keys)

                        logger.info("Successfully sent keys: %s", keys)
                        return ToolResult.create_success(f"Sent keys: {keys}", tool_name=self.name)

                    elif action == "get_dropdown_options":
                        if index is None:
                            return ToolResult.create_error("Index is required for 'get_dropdown_options' action", tool_name=self.name)

                        logger.debug("Getting dropdown options for element at index %s", index)
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult.create_error(f"Element with index {index} not found", tool_name=self.name)

                        page = await context.get_current_page()
                        options = await page.evaluate(
                            """
                            (xpath) => {
                                const select = document.evaluate(xpath, document, null,
                                    XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                                if (!select) return null;
                                return Array.from(select.options).map(opt => ({
                                    text: opt.text,
                                    value: opt.value,
                                    index: opt.index
                                }));
                            }
                        """,
                            element.xpath,
                        )

                        logger.info("Retrieved %s dropdown options", len(options) if options else 0)
                        return ToolResult.create_success(f"Dropdown options: {options}", tool_name=self.name)

                    elif action == "select_dropdown_option":
                        if index is None or not text:
                            return ToolResult.create_error("Index and text are required for 'select_dropdown_option' action", tool_name=self.name)

                        logger.debug("Selecting option '%s' from dropdown at index %s", text, index)
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult.create_error(f"Element with index {index} not found", tool_name=self.name)

                        page = await context.get_current_page()
                        await page.select_option(element.xpath, label=text)

                        result_msg = f"Selected option '{text}' from dropdown at index {index}"
                        logger.info(result_msg)
                        return ToolResult.create_success(result_msg, tool_name=self.name)

                    elif action == "extract_content":
                        if not goal:
                            return ToolResult.create_error("Goal is required for 'extract_content' action", tool_name=self.name)

                        logger.debug("Extracting content with goal: %s", goal)
                        
                        # FIXED: Use the correct method name
                        extracted_data = await self._extract_content(goal, max_content_length=4000)
                        
                        logger.info("Content extraction successful")
                        return ToolResult.create_success(extracted_data, tool_name=self.name)

                    elif action == "switch_tab":
                        if tab_id is None:
                            return ToolResult.create_error("Tab ID is required for 'switch_tab' action", tool_name=self.name)

                        logger.debug("Switching to tab: %s", tab_id)
                        await context.switch_to_tab(tab_id)
                        page = await context.get_current_page()
                        await page.wait_for_load_state()

                        logger.info("Switched to tab %s", tab_id)
                        return ToolResult.create_success(f"Switched to tab {tab_id}", tool_name=self.name)

                    elif action == "open_tab":
                        if not url:
                            return ToolResult.create_error("URL is required for 'open_tab' action", tool_name=self.name)

                        logger.debug("Opening new tab with URL: %s", url)
                        await context.create_new_tab(url)

                        logger.info("Opened new tab with URL: %s", url)
                        return ToolResult.create_success(f"Opened new tab with {url}", tool_name=self.name)

                    elif action == "close_tab":
                        logger.debug("Closing current tab")
                        await context.close_current_tab()

                        logger.info("Closed current tab")
                        return ToolResult.create_success("Closed current tab", tool_name=self.name)

                    elif action == "wait":
                        seconds_to_wait = seconds if seconds is not None else 3
                        logger.debug("Waiting for %s seconds", seconds_to_wait)
                        await asyncio.sleep(seconds_to_wait)

                        logger.info("Waited for %s seconds", seconds_to_wait)
                        return ToolResult.create_success(f"Waited for {seconds_to_wait} seconds", tool_name=self.name)

                    elif action == "get_current_state":
                        return await self.get_current_state()

                    else:
                        logger.warning("Unknown action: %s", action)
                        return ToolResult.create_error(f"Unknown action: {action}", tool_name=self.name)

            except ToolError as e:
                # If it's an explicit tool error, don't retry
                logger.error("Tool error in action '%s': %s", action, str(e))
                return ToolResult.create_error(str(e), tool_name=self.name)

            except Exception as e:
                retry_count += 1
                logger.warning("Error in browser action '%s' (attempt %s/%s): %s", action, retry_count, max_retries + 1, str(e))

                # If we've hit max retries, return the error
                if retry_count > max_retries:
                    logger.error("Max retries reached for action '%s': %s", action, str(e))
                    return ToolResult.create_error(
                        f"Browser action '{action}' failed after {max_retries} retries: {str(e)}",
                        tool_name=self.name
                    )

                # Wait before retrying (exponential backoff)
                backoff_time = 2 ** (retry_count - 1)
                await asyncio.sleep(backoff_time)

        # This should never be reached due to the while loop logic
        return ToolResult.create_error(f"Unexpected end of execution for action '{action}'", tool_name=self.name)

    async def get_current_state(self) -> ToolResult:
        """
        Get the current browser state as a ToolResult.
        """
        try:
            # Ensure browser is initialized
            ctx = self.context
            if not ctx:
                ctx = await self._ensure_browser_initialized()

            # Get state with required parameter
            state = await ctx.get_state(cache_clickable_elements_hashes=True)

            # Create viewport info
            viewport_height = 0
            if hasattr(state, "viewport_info") and state.viewport_info:
                viewport_height = state.viewport_info.height
            elif hasattr(ctx, "config") and hasattr(ctx.config, "browser_window_size"):
                viewport_height = ctx.config.browser_window_size.get("height", 0)

            # Take screenshot
            page = await ctx.get_current_page()
            await page.bring_to_front()
            await page.wait_for_load_state()

            screenshot = await page.screenshot(
                full_page=True, 
                animations="disabled", 
                type="jpeg", 
                quality=75
            )
            screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

            # Get scroll info
            pixels_above = getattr(state, "pixels_above", 0) or 0
            pixels_below = getattr(state, "pixels_below", 0) or 0

            # Build state info
            state_info = {
                "url": state.url,
                "title": state.title,
                "tabs": [tab.dict() for tab in state.tabs] if hasattr(state, 'tabs') else [],
                "help": "[0], [1], [2], etc., represent clickable indices corresponding to the elements listed. Clicking on these indices will navigate to or interact with the respective content behind them.",
                "interactive_elements": (
                    state.element_tree.clickable_elements_to_string() 
                    if state.element_tree else "No interactive elements found"
                ),
                "scroll_info": {
                    "pixels_above": pixels_above,
                    "pixels_below": pixels_below,
                    "total_height": pixels_above + pixels_below + viewport_height,
                },
                "viewport_height": viewport_height,
            }

            logger.info("Retrieved current browser state")
            
            # Create result with both text output and image
            result = ToolResult.create_success(
                json.dumps(state_info, indent=2, ensure_ascii=False),
                tool_name=self.name
            )
            result.base64_image = screenshot_b64
            
            return result
            
        except Exception as e:
            logger.error("Failed to get browser state: %s", e)
            return ToolResult.create_error(f"Failed to get browser state: {str(e)}", tool_name=self.name)

    async def cleanup(self) -> None:
        """
        Clean up browser resources.
        """
        logger.info("Cleaning up browser resources")

        async with self.lock:
            if self.context is not None:
                try:
                    await self.context.close()
                    logger.debug("Browser context closed")
                except Exception as e:
                    logger.warning("Error closing browser context: %s", e)
                finally:
                    self.context = None
                    self.dom_service = None

            if self.browser is not None:
                try:
                    await self.browser.close()
                    logger.debug("Browser closed")
                except Exception as e:
                    logger.warning("Error closing browser: %s", e)
                finally:
                    self.browser = None

        logger.info("Browser cleanup completed")

    def __del__(self) -> None:
        """Ensure cleanup when object is destroyed."""
        if (
            hasattr(self, "browser") and self.browser is not None
            or hasattr(self, "context") and self.context is not None
        ):
            try:
                # Try to run cleanup in the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in a running loop, schedule cleanup
                    loop.create_task(self.cleanup())
                else:
                    # If no loop is running, run cleanup synchronously
                    loop.run_until_complete(self.cleanup())
            except RuntimeError:
                # If we can't access the event loop, create a new one
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(self.cleanup())
                    loop.close()
                except Exception as e:
                    logger.warning("Could not cleanup browser in destructor: %s", e)
"""Browser automation tool for Enterprise AI."""

import asyncio
import base64
import json
from typing import Any, Dict, List, Optional, Set, TypeVar, Union, cast

from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from enterprise_ai.config import get_config
from enterprise_ai.llm.simple import LLM
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.tool.research.web_search import WebSearch


logger = get_logger("tool.browser.browser_use")


def llm_prompt(goal: str, content: List[str], max_content_length: int) -> str:
    return f"""\
Your task is to extract the content of the page. You will be given a page and a goal, and you should extract all relevant information around this goal from the page. If the goal is vague, summarize the page. Respond in json format.
Extraction goal: {goal}

Page content:
{content[:max_content_length]}
"""


@register_tool(category="browser")
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
                    "web_search",
                    "wait",
                    "extract_content",
                    "switch_tab",
                    "open_tab",
                    "close_tab",
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
            },
        },
        "required": ["action"],
        "dependencies": {
            "go_to_url": ["url"],
            "click_element": ["index"],
            "input_text": ["index", "text"],
            "switch_tab": ["tab_id"],
            "open_tab": ["url"],
            "scroll_down": ["scroll_amount"],
            "scroll_up": ["scroll_amount"],
            "scroll_to_text": ["text"],
            "send_keys": ["keys"],
            "get_dropdown_options": ["index"],
            "select_dropdown_option": ["index", "text"],
            "go_back": [],
            "web_search": ["query"],
            "wait": ["seconds"],
            "extract_content": ["goal"],
        },
    }

    # Define capabilities
    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.BROWSER_CONTROL,
        ToolCapability.NETWORK_ACCESS,
    }

    # Tool requires initialization
    requires_initialization: bool = True

    # Tool fields
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    context: Optional[BrowserContext] = Field(default=None, exclude=True)
    dom_service: Optional[DomService] = Field(default=None, exclude=True)
    web_search_tool: Optional[WebSearch] = Field(default=None, exclude=True)
    llm: Optional[LLM] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the browser automation tool with standard parameters.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            name=name or self.name,
            description=description or self.description,
            parameters=parameters or self.parameters,
        )

        # Store tool configuration
        self.config = config or ToolConfig(
            timeout=60.0, max_retries=3, cache_results=False, sandbox_enabled=True
        )

        # Create a lock for synchronization
        self.lock = asyncio.Lock()

        # Initialize web search tool
        self.web_search_tool = WebSearch()

        # LLM will be initialized lazily
        self.llm = None

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

        Args:
            **kwargs: Additional initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Initialize LLM
            if self.llm is None:
                try:
                    self.llm = LLM()
                except Exception as e:
                    logger.error(f"Failed to initialize LLM: {e}")
                    # Continue even without LLM, just with reduced functionality

            # Browser will be initialized lazily when needed
            return True
        except Exception as e:
            logger.error(f"Browser initialization error: {e}")
            return False

    async def _ensure_browser_initialized(self) -> BrowserContext:
        """
        Ensure browser and context are initialized.

        Returns:
            The initialized browser context

        Raises:
            ToolError: If browser initialization fails
        """
        if self.browser is None:
            logger.info("Initializing browser")

            # Get configuration from config system
            headless = get_config("browser_config.headless", False)
            disable_security = get_config("browser_config.disable_security", True)
            extra_args = get_config("browser_config.extra_chromium_args", [])

            # Apply timeout from ToolConfig
            timeout_config = self.config.timeout

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
                logger.error(f"Browser creation failed: {e}")
                raise ToolError(f"Failed to create browser: {str(e)}")

        if self.context is None:
            logger.info("Creating browser context")
            try:
                context_config = BrowserContextConfig()
                self.context = await self.browser.new_context(context_config)
                self.dom_service = DomService(await self.context.get_current_page())
                logger.debug("Browser context created successfully")
            except Exception as e:
                logger.error(f"Browser context creation failed: {e}")
                raise ToolError(f"Failed to create browser context: {str(e)}")

        return self.context

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute a specified browser action.

        Args:
            **kwargs: Keyword arguments including:
                action: The browser action to perform
                url: URL for navigation or new tab
                index: Element index for click or input actions
                text: Text for input action or search query
                scroll_amount: Pixels to scroll for scroll action
                tab_id: Tab ID for switch_tab action
                query: Search query for web search
                goal: Extraction goal for content extraction
                keys: Keys to send for keyboard actions
                seconds: Seconds to wait

        Returns:
            ToolResult with the action's output or error
        """
        # Apply configured timeout
        execution_timeout = self.config.timeout
        retry_count = 0
        max_retries = self.config.max_retries

        # Extract parameters from kwargs
        action = kwargs.get("action")
        if not action:
            return ToolResult(error="Action parameter is required")

        # Extract other parameters
        url = kwargs.get("url")
        index = kwargs.get("index")
        text = kwargs.get("text")
        scroll_amount = kwargs.get("scroll_amount")
        tab_id = kwargs.get("tab_id")
        query = kwargs.get("query")
        goal = kwargs.get("goal")
        keys = kwargs.get("keys")
        seconds = kwargs.get("seconds")

        # Log the action being performed
        logger.info(f"Executing browser action: {action}")

        # Execution with retries if configured
        while retry_count <= max_retries:
            try:
                async with self.lock:
                    # Make sure browser is initialized
                    context = await self._ensure_browser_initialized()

                    # Get max content length from config
                    max_content_length = get_config("browser_config.max_content_length", 2000)

                    # Execute the appropriate action based on the action parameter

                    # Navigation actions
                    if action == "go_to_url":
                        if not url:
                            return ToolResult(error="URL is required for 'go_to_url' action")

                        logger.debug(f"Navigating to URL: {url}")
                        page = await context.get_current_page()

                        # Use timeout from config
                        page_timeout = (
                            execution_timeout * 1000 if execution_timeout else 60000
                        )  # Convert to ms

                        try:
                            await page.goto(url, timeout=page_timeout)
                            await page.wait_for_load_state()
                            logger.info(f"Successfully navigated to: {url}")
                            return ToolResult(output=f"Navigated to {url}")
                        except Exception as e:
                            logger.error(f"Navigation error: {e}")
                            return ToolResult(error=f"Failed to navigate to {url}: {str(e)}")

                    elif action == "go_back":
                        logger.debug("Navigating back")
                        await context.go_back()
                        return ToolResult(output="Navigated back")

                    elif action == "refresh":
                        logger.debug("Refreshing page")
                        await context.refresh_page()
                        return ToolResult(output="Refreshed current page")

                    elif action == "web_search":
                        if not query:
                            return ToolResult(error="Query is required for 'web_search' action")

                        logger.debug(f"Performing web search for: {query}")

                        # Initialize web search tool if not already done
                        if self.web_search_tool is None:
                            self.web_search_tool = WebSearch()

                        # Execute the web search and return results directly
                        search_response = await self.web_search_tool.execute(
                            query=query, fetch_content=True, num_results=1
                        )

                        # Navigate to the first search result
                        if hasattr(search_response, "results") and search_response.results:
                            first_search_result = search_response.results[0]
                            url_to_navigate = first_search_result.url

                            page = await context.get_current_page()
                            await page.goto(url_to_navigate)
                            await page.wait_for_load_state()
                            logger.info(f"Navigated to search result: {url_to_navigate}")

                        return search_response

                    # Element interaction actions
                    elif action == "click_element":
                        if index is None:
                            return ToolResult(error="Index is required for 'click_element' action")

                        logger.debug(f"Clicking element at index: {index}")
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult(error=f"Element with index {index} not found")

                        download_path = await context._click_element_node(element)
                        output = f"Clicked element at index {index}"
                        if download_path:
                            output += f" - Downloaded file to {download_path}"

                        logger.info(output)
                        return ToolResult(output=output)

                    elif action == "input_text":
                        if index is None or not text:
                            return ToolResult(
                                error="Index and text are required for 'input_text' action"
                            )

                        logger.debug(f"Inputting text at element index {index}: {text}")
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult(error=f"Element with index {index} not found")

                        await context._input_text_element_node(element, text)
                        logger.info(f"Text input successful at index {index}")
                        return ToolResult(output=f"Input '{text}' into element at index {index}")

                    elif action == "scroll_down" or action == "scroll_up":
                        direction = 1 if action == "scroll_down" else -1
                        amount = (
                            scroll_amount
                            if scroll_amount is not None
                            else context.config.browser_window_size["height"]
                        )

                        logger.debug(
                            f"Scrolling {'down' if direction > 0 else 'up'} by {amount} pixels"
                        )
                        await context.execute_javascript(
                            f"window.scrollBy(0, {direction * amount});"
                        )

                        logger.info(
                            f"Scrolled {'down' if direction > 0 else 'up'} by {amount} pixels"
                        )
                        return ToolResult(
                            output=f"Scrolled {'down' if direction > 0 else 'up'} by {amount} pixels"
                        )

                    elif action == "scroll_to_text":
                        if not text:
                            return ToolResult(error="Text is required for 'scroll_to_text' action")

                        logger.debug(f"Scrolling to text: '{text}'")
                        page = await context.get_current_page()
                        try:
                            locator = page.get_by_text(text, exact=False)
                            await locator.scroll_into_view_if_needed()
                            logger.info(f"Successfully scrolled to text: '{text}'")
                            return ToolResult(output=f"Scrolled to text: '{text}'")
                        except Exception as e:
                            logger.error(f"Failed to scroll to text: {e}")
                            return ToolResult(error=f"Failed to scroll to text: {str(e)}")

                    elif action == "send_keys":
                        if not keys:
                            return ToolResult(error="Keys are required for 'send_keys' action")

                        logger.debug(f"Sending keys: {keys}")
                        page = await context.get_current_page()
                        await page.keyboard.press(keys)

                        logger.info(f"Successfully sent keys: {keys}")
                        return ToolResult(output=f"Sent keys: {keys}")

                    elif action == "get_dropdown_options":
                        if index is None:
                            return ToolResult(
                                error="Index is required for 'get_dropdown_options' action"
                            )

                        logger.debug(f"Getting dropdown options for element at index {index}")
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult(error=f"Element with index {index} not found")

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

                        logger.info(f"Retrieved {len(options) if options else 0} dropdown options")
                        return ToolResult(output=f"Dropdown options: {options}")

                    elif action == "select_dropdown_option":
                        if index is None or not text:
                            return ToolResult(
                                error="Index and text are required for 'select_dropdown_option' action"
                            )

                        logger.debug(f"Selecting option '{text}' from dropdown at index {index}")
                        element = await context.get_dom_element_by_index(index)
                        if not element:
                            return ToolResult(error=f"Element with index {index} not found")

                        page = await context.get_current_page()
                        await page.select_option(element.xpath, label=text)

                        logger.info(f"Selected option '{text}' from dropdown at index {index}")
                        return ToolResult(
                            output=f"Selected option '{text}' from dropdown at index {index}"
                        )

                    # Content extraction actions
                    elif action == "extract_content":
                        if not goal:
                            return ToolResult(error="Goal is required for 'extract_content' action")

                        logger.debug(f"Extracting content with goal: {goal}")
                        page = await context.get_current_page()
                        import markdownify

                        content = markdownify.markdownify(await page.content())

                        # Prepare prompt for LLM
                        prompt = llm_prompt(goal, content, max_content_length)

                        # Initialize LLM if needed
                        if not self.llm:
                            try:
                                self.llm = LLM()
                                logger.debug("LLM initialized for content extraction")
                            except Exception as e:
                                logger.error(f"Failed to initialize LLM: {e}")
                                return ToolResult(
                                    error="LLM service unavailable for content extraction"
                                )

                        # Define extraction function schema
                        extraction_function = {
                            "type": "function",
                            "function": {
                                "name": "extract_content",
                                "description": "Extract specific information from a webpage based on a goal",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "extracted_content": {
                                            "type": "object",
                                            "description": "The content extracted from the page according to the goal",
                                            "properties": {
                                                "text": {
                                                    "type": "string",
                                                    "description": "Text content extracted from the page",
                                                },
                                                "metadata": {
                                                    "type": "object",
                                                    "description": "Additional metadata about the extracted content",
                                                    "properties": {
                                                        "source": {
                                                            "type": "string",
                                                            "description": "Source of the extracted content",
                                                        }
                                                    },
                                                },
                                            },
                                        }
                                    },
                                    "required": ["extracted_content"],
                                },
                            },
                        }

                        # Use LLM to extract content
                        try:
                            messages = [{"role": "user", "content": prompt}]
                            response = await self.llm.acomplete(
                                messages=messages,
                                functions=[extraction_function],
                                function_call={"name": "extract_content"},
                            )

                            if (
                                hasattr(response, "function_call")
                                and response.function_call
                                and response.function_call.get("name") == "extract_content"
                            ):
                                args = json.loads(response.function_call["arguments"])
                                extracted_content = args.get("extracted_content", {})
                                logger.info("Content extraction successful")
                                return ToolResult(
                                    output=f"Extracted from page:\n{extracted_content}\n"
                                )

                            logger.warning("No content extracted")
                            return ToolResult(output="No content was extracted from the page.")
                        except Exception as e:
                            logger.error(f"Error during content extraction: {e}")
                            return ToolResult(error=f"Content extraction failed: {str(e)}")

                    # Tab management actions
                    elif action == "switch_tab":
                        if tab_id is None:
                            return ToolResult(error="Tab ID is required for 'switch_tab' action")

                        logger.debug(f"Switching to tab: {tab_id}")
                        await context.switch_to_tab(tab_id)
                        page = await context.get_current_page()
                        await page.wait_for_load_state()

                        logger.info(f"Switched to tab {tab_id}")
                        return ToolResult(output=f"Switched to tab {tab_id}")

                    elif action == "open_tab":
                        if not url:
                            return ToolResult(error="URL is required for 'open_tab' action")

                        logger.debug(f"Opening new tab with URL: {url}")
                        await context.create_new_tab(url)

                        logger.info(f"Opened new tab with URL: {url}")
                        return ToolResult(output=f"Opened new tab with {url}")

                    elif action == "close_tab":
                        logger.debug("Closing current tab")
                        await context.close_current_tab()

                        logger.info("Closed current tab")
                        return ToolResult(output="Closed current tab")

                    # Utility actions
                    elif action == "wait":
                        seconds_to_wait = seconds if seconds is not None else 3
                        logger.debug(f"Waiting for {seconds_to_wait} seconds")
                        await asyncio.sleep(seconds_to_wait)

                        logger.info(f"Waited for {seconds_to_wait} seconds")
                        return ToolResult(output=f"Waited for {seconds_to_wait} seconds")

                    else:
                        logger.warning(f"Unknown action: {action}")
                        return ToolResult(error=f"Unknown action: {action}")

            except ToolError as e:
                # If it's an explicit tool error, don't retry
                logger.error(f"Tool error in action '{action}': {str(e)}")
                return ToolResult(error=str(e))

            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"Error in browser action '{action}' (attempt {retry_count}/{max_retries + 1}): {str(e)}"
                )

                # If we've hit max retries, return the error
                if retry_count > max_retries:
                    logger.error(f"Max retries reached for action '{action}': {str(e)}")
                    return ToolResult(
                        error=f"Browser action '{action}' failed after {max_retries} retries: {str(e)}"
                    )

                # Wait before retrying (exponential backoff)
                backoff_time = 2 ** (retry_count - 1)  # 1, 2, 4, 8...
                await asyncio.sleep(backoff_time)

    async def get_current_state(self) -> ToolResult:
        """
        Get the current browser state as a ToolResult.

        Returns:
            ToolResult containing the browser state and screenshot
        """
        try:
            # Ensure browser is initialized
            ctx = self.context
            if not ctx:
                ctx = await self._ensure_browser_initialized()

            state = await ctx.get_state()

            # Create a viewport_info dictionary
            viewport_height = 0
            if hasattr(state, "viewport_info") and state.viewport_info:
                viewport_height = state.viewport_info.height
            elif hasattr(ctx, "config") and hasattr(ctx.config, "browser_window_size"):
                viewport_height = ctx.config.browser_window_size.get("height", 0)

            # Take a screenshot for the state
            page = await ctx.get_current_page()

            await page.bring_to_front()
            await page.wait_for_load_state()

            # Use lower quality for screenshot to reduce size
            screenshot = await page.screenshot(
                full_page=True, animations="disabled", type="jpeg", quality=75
            )

            screenshot = base64.b64encode(screenshot).decode("utf-8")

            # Build the state info with all required fields
            state_info = {
                "url": state.url,
                "title": state.title,
                "tabs": [tab.dict() for tab in state.tabs],
                "help": "[0], [1], [2], etc., represent clickable indices corresponding to the elements listed. Clicking on these indices will navigate to or interact with the respective content behind them.",
                "interactive_elements": (
                    state.element_tree.clickable_elements_to_string() if state.element_tree else ""
                ),
                "scroll_info": {
                    "pixels_above": getattr(state, "pixels_above", 0),
                    "pixels_below": getattr(state, "pixels_below", 0),
                    "total_height": getattr(state, "pixels_above", 0)
                    + getattr(state, "pixels_below", 0)
                    + viewport_height,
                },
                "viewport_height": viewport_height,
            }

            logger.info("Retrieved current browser state")
            return ToolResult(
                output=json.dumps(state_info, indent=4, ensure_ascii=False),
                base64_image=screenshot,
            )
        except Exception as e:
            logger.error(f"Failed to get browser state: {e}")
            return ToolResult(error=f"Failed to get browser state: {str(e)}")

    async def cleanup(self) -> None:
        """
        Clean up browser resources.

        This method closes the browser context and browser instance.
        """
        logger.info("Cleaning up browser resources")

        async with self.lock:
            if self.context is not None:
                try:
                    await self.context.close()
                    logger.debug("Browser context closed")
                except Exception as e:
                    logger.warning(f"Error closing browser context: {e}")
                finally:
                    self.context = None
                    self.dom_service = None

            if self.browser is not None:
                try:
                    await self.browser.close()
                    logger.debug("Browser closed")
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                finally:
                    self.browser = None

        logger.info("Browser cleanup completed")

    def __del__(self) -> None:
        """Ensure cleanup when object is destroyed."""
        if self.browser is not None or self.context is not None:
            try:
                asyncio.run(self.cleanup())
            except RuntimeError:
                # If already in an event loop, create a new one
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.cleanup())
                loop.close()

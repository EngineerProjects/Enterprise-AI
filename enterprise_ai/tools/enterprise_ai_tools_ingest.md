# Prompt for AI Assistance with Tool System Restructuring

```
I'm working on an Enterprise AI framework and need help restructuring my tool system to make it more modular and independently extensible. Here's what I want to accomplish:

## Current Situation
I have a collection of tools in my `tool/` directory that are currently in a flat structure. Each tool is a separate file implementing a `BaseTool` class. I'll share my current code with you, including key files like `base.py`, `tool_collection.py`, and some example tool implementations.

## Desired Structure
I want to reorganize into a more modular structure:

tool/
├── __init__.py               # Main exports
├── core/                     # Core infrastructure
│   ├── __init__.py
│   ├── base.py               # BaseTool and interfaces
│   ├── collection.py         # Tool collections
│   ├── registry.py           # Tool registration system (new)
│   └── result.py             # ToolResult classes
├── execution/                # Code and bash execution tools with maybe any other execution tools
├── planning/                 # Planning tools
├── content/                  # Content generation tools
├── file/                     # File management tools
├── research/                 # Research tools
└── browser/                  # Browser automation

## Key Requirements
1. I want tools to be completely independent - adding a new tool shouldn't require changes to any other code
2. The system should use a registry pattern where tools auto-register themselves
3. Tools should be discoverable through a central registry
4. The `tool/core` components should provide a stable interface for agent systems to interact with tools
5. Each tool category should have its own directory for organization

## Specific Help Needed
1. How to split the existing base.py into appropriate core components
2. Implementation of the registry system for auto-discovery
3. Example of how to refactor existing tools to work with this new structure
4. Required changes to __init__.py files to maintain proper exports
5. Any design patterns I should follow to ensure tools remain independent

Please help me refactor my code to implement this structure while maintaining functionality. I'll share my current code in the next message.
```


# Project Summary
Repository: /home/amiche/PROJECTS/Enterprise-AI/enterprise_ai
Branch: main
Files analyzed: 47
Estimated tokens: 53.1k
Analysis time: 0.00 seconds 

# Directory Structure

```
├── tool
│   ├── search
│   │   ├── __init__.py
│   │   ├── baidu_search.py
│   │   ├── base.py
│   │   ├── bing_search.py
│   │   ├── duckduckgo_search.py
│   │   └── google_search.py
│   ├── __init__.py
│   ├── base.py
│   ├── bash.py
│   ├── browser_use_tool.py
│   ├── create_chat_completion.py
│   ├── deep_research.py
│   ├── planning.py
│   ├── python_execute.py
│   ├── str_replace_editor.py
│   ├── terminate.py
│   ├── tool_collection.py
│   └── web_search.py
```

# Files Content


## tool/search/__init__.py

```py
"""Search engine implementations."""

from enterprise_ai.tool.search.baidu_search import BaiduSearchEngine
from enterprise_ai.tool.search.base import SearchItem, WebSearchEngine
from enterprise_ai.tool.search.bing_search import BingSearchEngine
from enterprise_ai.tool.search.duckduckgo_search import DuckDuckGoSearchEngine
from enterprise_ai.tool.search.google_search import GoogleSearchEngine


__all__ = [
    "WebSearchEngine",
    "SearchItem",
    "BaiduSearchEngine",
    "DuckDuckGoSearchEngine",
    "GoogleSearchEngine",
    "BingSearchEngine",
]

```

## tool/search/baidu_search.py

```py
"""Baidu search engine implementation."""

from typing import List

from baidusearch.baidusearch import search

from enterprise_ai.tool.search.base import SearchItem, WebSearchEngine


class BaiduSearchEngine(WebSearchEngine):
    """Implementation of Baidu search engine."""

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Baidu search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return

        Returns:
            List of search results formatted according to SearchItem model
        """
        raw_results = search(query, num_results=num_results)

        # Convert raw results to SearchItem format
        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, str):
                # If it's just a URL
                results.append(
                    SearchItem(title=f"Baidu Result {i + 1}", url=item, description=None)
                )
            elif isinstance(item, dict):
                # If it's a dictionary with details
                results.append(
                    SearchItem(
                        title=item.get("title", f"Baidu Result {i + 1}"),
                        url=item.get("url", ""),
                        description=item.get("abstract", None),
                    )
                )
            else:
                # Try to get attributes directly
                try:
                    results.append(
                        SearchItem(
                            title=getattr(item, "title", f"Baidu Result {i + 1}"),
                            url=getattr(item, "url", ""),
                            description=getattr(item, "abstract", None),
                        )
                    )
                except Exception:
                    # Fallback to a basic result
                    results.append(
                        SearchItem(title=f"Baidu Result {i + 1}", url=str(item), description=None)
                    )

        return results

```

## tool/search/base.py

```py
"""Base class definitions for search engines."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    """Represents a single search result item"""

    title: str = Field(description="The title of the search result")
    url: str = Field(description="The URL of the search result")
    description: Optional[str] = Field(
        default=None, description="A description or snippet of the search result"
    )

    def __str__(self) -> str:
        """String representation of a search result item."""
        return f"{self.title} - {self.url}"


class WebSearchEngine(BaseModel):
    """Base class for web search engines."""

    class Config:
        arbitrary_types_allowed = True

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Perform a web search and return a list of search items.

        Args:
            query (str): The search query to submit to the search engine.
            num_results (int, optional): The number of search results to return. Default is 10.
            args: Additional arguments.
            kwargs: Additional keyword arguments.

        Returns:
            List[SearchItem]: A list of SearchItem objects matching the search query.
        """
        raise NotImplementedError("Subclasses must implement perform_search method")

```

## tool/search/bing_search.py

```py
"""Bing search engine implementation."""

from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from enterprise_ai.logger import get_logger
from enterprise_ai.tool.search.base import SearchItem, WebSearchEngine


logger = get_logger("tool.search.bing")

ABSTRACT_MAX_LENGTH = 300

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/49.0.2623.108 Chrome/49.0.2623.108 Safari/537.36",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": USER_AGENTS[0],
    "Referer": "https://www.bing.com/",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

BING_HOST_URL = "https://www.bing.com"
BING_SEARCH_URL = "https://www.bing.com/search?q="


class BingSearchEngine(WebSearchEngine):
    """Implementation of Bing search engine."""

    session: Optional[requests.Session] = None

    def __init__(self, **data):
        """Initialize the BingSearch tool with a requests session."""
        super().__init__(**data)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _search_sync(self, query: str, num_results: int = 10) -> List[SearchItem]:
        """
        Synchronous Bing search implementation to retrieve search results.

        Args:
            query: The search query to submit to Bing
            num_results: Maximum number of results to return (default: 10)

        Returns:
            List of search items with title, URL, and description
        """
        if not query:
            return []

        list_result = []
        first = 1
        next_url = BING_SEARCH_URL + query

        while len(list_result) < num_results:
            data, next_url = self._parse_html(next_url, rank_start=len(list_result), first=first)
            if data:
                list_result.extend(data)
            if not next_url:
                break
            first += 10

        return list_result[:num_results]

    def _parse_html(
        self, url: str, rank_start: int = 0, first: int = 1
    ) -> Tuple[List[SearchItem], str]:
        """
        Parse Bing search result HTML to extract search results and the next page URL.

        Args:
            url: The URL to parse
            rank_start: Starting rank for search results
            first: First result number

        Returns:
            Tuple of (List of SearchItem objects, next page URL or None)
        """
        try:
            res = self.session.get(url=url)
            res.encoding = "utf-8"
            root = BeautifulSoup(res.text, "lxml")

            list_data = []
            ol_results = root.find("ol", id="b_results")
            if not ol_results:
                return [], None

            for li in ol_results.find_all("li", class_="b_algo"):
                title = ""
                url = ""
                abstract = ""
                try:
                    h2 = li.find("h2")
                    if h2:
                        title = h2.text.strip()
                        url = h2.a["href"].strip()

                    p = li.find("p")
                    if p:
                        abstract = p.text.strip()

                    if ABSTRACT_MAX_LENGTH and len(abstract) > ABSTRACT_MAX_LENGTH:
                        abstract = abstract[:ABSTRACT_MAX_LENGTH]

                    rank_start += 1

                    # Create a SearchItem object
                    list_data.append(
                        SearchItem(
                            title=title or f"Bing Result {rank_start}",
                            url=url,
                            description=abstract,
                        )
                    )
                except Exception:
                    continue

            next_btn = root.find("a", title="Next page")
            if not next_btn:
                return list_data, None

            next_url = BING_HOST_URL + next_btn["href"]
            return list_data, next_url
        except Exception as e:
            logger.warning(f"Error parsing HTML: {e}")
            return [], None

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Bing search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return

        Returns:
            List of search results formatted according to SearchItem model
        """
        return self._search_sync(query, num_results=num_results)

```

## tool/search/duckduckgo_search.py

```py
"""DuckDuckGo search engine implementation."""

from typing import List

from duckduckgo_search import DDGS

from enterprise_ai.tool.search.base import SearchItem, WebSearchEngine


class DuckDuckGoSearchEngine(WebSearchEngine):
    """Implementation of DuckDuckGo search engine."""

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        DuckDuckGo search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return

        Returns:
            List of search results formatted according to SearchItem model
        """
        raw_results = DDGS().text(query, max_results=num_results)

        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, str):
                # If it's just a URL
                results.append(
                    SearchItem(title=f"DuckDuckGo Result {i + 1}", url=item, description=None)
                )
            elif isinstance(item, dict):
                # Extract data from the dictionary
                results.append(
                    SearchItem(
                        title=item.get("title", f"DuckDuckGo Result {i + 1}"),
                        url=item.get("href", ""),
                        description=item.get("body", None),
                    )
                )
            else:
                # Try to extract attributes directly
                try:
                    results.append(
                        SearchItem(
                            title=getattr(item, "title", f"DuckDuckGo Result {i + 1}"),
                            url=getattr(item, "href", ""),
                            description=getattr(item, "body", None),
                        )
                    )
                except Exception:
                    # Fallback
                    results.append(
                        SearchItem(
                            title=f"DuckDuckGo Result {i + 1}",
                            url=str(item),
                            description=None,
                        )
                    )

        return results

```

## tool/search/google_search.py

```py
"""Google search engine implementation."""

from typing import List

from googlesearch import search

from enterprise_ai.tool.search.base import SearchItem, WebSearchEngine


class GoogleSearchEngine(WebSearchEngine):
    """Implementation of Google search engine."""

    def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        Google search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return

        Returns:
            List of search results formatted according to SearchItem model
        """
        raw_results = search(query, num_results=num_results, advanced=True)

        results = []
        for i, item in enumerate(raw_results):
            if isinstance(item, str):
                # If it's just a URL
                results.append(SearchItem(title=f"Google Result {i + 1}", url=item, description=""))
            else:
                results.append(
                    SearchItem(title=item.title, url=item.url, description=item.description)
                )

        return results

```

## tool/__init__.py

```py
"""
Tool system for Enterprise AI.

This module provides a collection of tools for various tasks.
"""

from enterprise_ai.tool.base import BaseTool, ToolResult, ToolError, CLIResult, ToolFailure
from enterprise_ai.tool.bash import Bash
from enterprise_ai.tool.browser_use_tool import BrowserUseTool
from enterprise_ai.tool.create_chat_completion import CreateChatCompletion
from enterprise_ai.tool.deep_research import DeepResearch
from enterprise_ai.tool.planning import PlanningTool
from enterprise_ai.tool.python_execute import PythonExecute
from enterprise_ai.tool.str_replace_editor import StrReplaceEditor
from enterprise_ai.tool.terminate import Terminate
from enterprise_ai.tool.tool_collection import ToolCollection
from enterprise_ai.tool.web_search import WebSearch

__all__ = [
    # Base classes
    "BaseTool",
    "ToolResult",
    "CLIResult",
    "ToolFailure",
    "ToolError",
    "ToolCollection",
    # Tool implementations
    "Bash",
    "BrowserUseTool",
    "CreateChatCompletion",
    "DeepResearch",
    "PlanningTool",
    "PythonExecute",
    "StrReplaceEditor",
    "Terminate",
    "WebSearch",
]

```

## tool/base.py

```py
"""
Base tool definitions for Enterprise AI.

This module defines the abstract base classes for all tools in the framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from enterprise_ai.exceptions import EnterpriseAIError


class ToolError(EnterpriseAIError):
    """Error raised by tools during execution."""

    def __init__(self, message: str = "Tool execution error") -> None:
        self.message = message
        super().__init__(self.message)


class BaseTool(ABC, BaseModel):
    """Base class for all tools in Enterprise AI."""

    name: str
    description: str
    parameters: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        pass

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    output: Any = Field(default=None)
    error: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        return f"Error: {self.error}" if self.error else str(self.output)

    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        return type(self)(**{**self.dict(), **kwargs})


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""

    pass


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""

    pass

```

## tool/bash.py

```py
"""Bash command execution tool."""

import asyncio
import os
from typing import Optional

from enterprise_ai.tool.base import BaseTool, CLIResult, ToolError


_BASH_DESCRIPTION = """Execute a bash command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
* Interactive: If a bash command returns exit code `-1`, this means the process is not yet finished. The assistant must then send a second call to terminal with an empty `command` (which will retrieve any additional logs), or it can send additional text (set `command` to the text) to STDIN of the running process, or it can send command=`ctrl+c` to interrupt the process.
* Timeout: If a command execution result says "Command timed out. Sending SIGINT to the process", the assistant should retry running the command in the background.
"""


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False

    async def start(self):
        """Start the bash shell."""
        if self._started:
            return

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            preexec_fn=os.setsid,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str) -> CLIResult:
        """Execute a command in the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        self._process.stdin.write(command.encode() + f"; echo '{self._sentinel}'\n".encode())
        await self._process.stdin.drain()

        # read output from the process, until the sentinel is found
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    # if we read directly from stdout/stderr, it will wait forever for
                    # EOF. use the StreamReader buffer directly instead.
                    output = self._process.stdout._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
                    if self._sentinel in output:
                        # strip the sentinel and break
                        output = output[: output.index(self._sentinel)]
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]

        error = self._process.stderr._buffer.decode()  # pyright: ignore[reportAttributeAccessIssue]
        if error.endswith("\n"):
            error = error[:-1]

        # clear the buffers so that the next output can be read correctly
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        return CLIResult(output=output, error=error)


class Bash(BaseTool):
    """A tool for executing bash commands"""

    name: str = "bash"
    description: str = _BASH_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
            "restart": {
                "type": "boolean",
                "description": "Whether to restart the bash session.",
                "default": False,
            },
        },
        "required": ["command"],
    }

    _session: Optional[_BashSession] = None

    async def execute(
        self, command: str | None = None, restart: bool = False, **kwargs
    ) -> CLIResult:
        """Execute a bash command."""
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start()

            return CLIResult(system="Bash session has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("No command provided.")

```

## tool/browser_use_tool.py

```py
"""Browser automation tool for Enterprise AI."""

import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional, TypeVar, Union, cast

from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from enterprise_ai.config import get_config
from enterprise_ai.llm import LLM
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.base import BaseTool, ToolResult
from enterprise_ai.tool.web_search import WebSearch


logger = get_logger("tool.browser_use")

_BROWSER_DESCRIPTION = """\
A powerful browser automation tool that allows interaction with web pages through various actions.
* This tool provides commands for controlling a browser session, navigating web pages, and extracting information
* It maintains state across calls, keeping the browser session alive until explicitly closed
* Use this when you need to browse websites, fill forms, click buttons, extract content, or perform web searches
* Each action requires specific parameters as defined in the tool's dependencies

Key capabilities include:
* Navigation: Go to specific URLs, go back, search the web, or refresh pages
* Interaction: Click elements, input text, select from dropdowns, send keyboard commands
* Scrolling: Scroll up/down by pixel amount or scroll to specific text
* Content extraction: Extract and analyze content from web pages based on specific goals
* Tab management: Switch between tabs, open new tabs, or close tabs

Note: When using element indices, refer to the numbered elements shown in the current browser state.
"""

Context = TypeVar("Context")


class BrowserUseTool(BaseTool):
    """Browser automation tool using browser_use package."""

    name: str = "browser_use"
    description: str = _BROWSER_DESCRIPTION
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

    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    context: Optional[BrowserContext] = Field(default=None, exclude=True)
    dom_service: Optional[DomService] = Field(default=None, exclude=True)
    web_search_tool: WebSearch = Field(default_factory=WebSearch, exclude=True)
    llm: Optional[LLM] = Field(default_factory=LLM)

    @field_validator("parameters", mode="before")
    def validate_parameters(cls, v: dict, info: ValidationInfo) -> dict:
        """Validate parameters."""
        if not v:
            raise ValueError("Parameters cannot be empty")
        return v

    async def _ensure_browser_initialized(self) -> BrowserContext:
        """Ensure browser and context are initialized."""
        if self.browser is None:
            browser_config_kwargs = {"headless": False, "disable_security": True}

            # Get additional configuration from config
            headless = get_config("browser_config.headless", False)
            disable_security = get_config("browser_config.disable_security", True)
            extra_args = get_config("browser_config.extra_chromium_args", [])

            browser_config_kwargs.update(
                {
                    "headless": headless,
                    "disable_security": disable_security,
                }
            )

            if extra_args:
                browser_config_kwargs["extra_chromium_args"] = extra_args

            self.browser = BrowserUseBrowser(BrowserConfig(**browser_config_kwargs))

        if self.context is None:
            context_config = BrowserContextConfig()
            self.context = await self.browser.new_context(context_config)
            self.dom_service = DomService(await self.context.get_current_page())

        return self.context

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        index: Optional[int] = None,
        text: Optional[str] = None,
        scroll_amount: Optional[int] = None,
        tab_id: Optional[int] = None,
        query: Optional[str] = None,
        goal: Optional[str] = None,
        keys: Optional[str] = None,
        seconds: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute a specified browser action.

        Args:
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
            **kwargs: Additional arguments

        Returns:
            ToolResult with the action's output or error
        """
        async with self.lock:
            try:
                context = await self._ensure_browser_initialized()

                # Get max content length from config
                max_content_length = get_config("browser_config.max_content_length", 2000)

                # Navigation actions
                if action == "go_to_url":
                    if not url:
                        return ToolResult(error="URL is required for 'go_to_url' action")
                    page = await context.get_current_page()
                    await page.goto(url)
                    await page.wait_for_load_state()
                    return ToolResult(output=f"Navigated to {url}")

                elif action == "go_back":
                    await context.go_back()
                    return ToolResult(output="Navigated back")

                elif action == "refresh":
                    await context.refresh_page()
                    return ToolResult(output="Refreshed current page")

                elif action == "web_search":
                    if not query:
                        return ToolResult(error="Query is required for 'web_search' action")
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

                    return search_response

                # Element interaction actions
                elif action == "click_element":
                    if index is None:
                        return ToolResult(error="Index is required for 'click_element' action")
                    element = await context.get_dom_element_by_index(index)
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    download_path = await context._click_element_node(element)
                    output = f"Clicked element at index {index}"
                    if download_path:
                        output += f" - Downloaded file to {download_path}"
                    return ToolResult(output=output)

                elif action == "input_text":
                    if index is None or not text:
                        return ToolResult(
                            error="Index and text are required for 'input_text' action"
                        )
                    element = await context.get_dom_element_by_index(index)
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    await context._input_text_element_node(element, text)
                    return ToolResult(output=f"Input '{text}' into element at index {index}")

                elif action == "scroll_down" or action == "scroll_up":
                    direction = 1 if action == "scroll_down" else -1
                    amount = (
                        scroll_amount
                        if scroll_amount is not None
                        else context.config.browser_window_size["height"]
                    )
                    await context.execute_javascript(f"window.scrollBy(0, {direction * amount});")
                    return ToolResult(
                        output=f"Scrolled {'down' if direction > 0 else 'up'} by {amount} pixels"
                    )

                elif action == "scroll_to_text":
                    if not text:
                        return ToolResult(error="Text is required for 'scroll_to_text' action")
                    page = await context.get_current_page()
                    try:
                        locator = page.get_by_text(text, exact=False)
                        await locator.scroll_into_view_if_needed()
                        return ToolResult(output=f"Scrolled to text: '{text}'")
                    except Exception as e:
                        return ToolResult(error=f"Failed to scroll to text: {str(e)}")

                elif action == "send_keys":
                    if not keys:
                        return ToolResult(error="Keys are required for 'send_keys' action")
                    page = await context.get_current_page()
                    await page.keyboard.press(keys)
                    return ToolResult(output=f"Sent keys: {keys}")

                elif action == "get_dropdown_options":
                    if index is None:
                        return ToolResult(
                            error="Index is required for 'get_dropdown_options' action"
                        )
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
                    return ToolResult(output=f"Dropdown options: {options}")

                elif action == "select_dropdown_option":
                    if index is None or not text:
                        return ToolResult(
                            error="Index and text are required for 'select_dropdown_option' action"
                        )
                    element = await context.get_dom_element_by_index(index)
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    page = await context.get_current_page()
                    await page.select_option(element.xpath, label=text)
                    return ToolResult(
                        output=f"Selected option '{text}' from dropdown at index {index}"
                    )

                # Content extraction actions
                elif action == "extract_content":
                    if not goal:
                        return ToolResult(error="Goal is required for 'extract_content' action")

                    page = await context.get_current_page()
                    import markdownify

                    content = markdownify.markdownify(await page.content())

                    prompt = f"""\
Your task is to extract the content of the page. You will be given a page and a goal, and you should extract all relevant information around this goal from the page. If the goal is vague, summarize the page. Respond in json format.
Extraction goal: {goal}

Page content:
{content[:max_content_length]}
"""
                    messages = [{"role": "user", "content": prompt}]

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

                    # Use LLM to extract content with required function calling
                    response = await self.llm.complete(
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
                        return ToolResult(output=f"Extracted from page:\n{extracted_content}\n")

                    return ToolResult(output="No content was extracted from the page.")

                # Tab management actions
                elif action == "switch_tab":
                    if tab_id is None:
                        return ToolResult(error="Tab ID is required for 'switch_tab' action")
                    await context.switch_to_tab(tab_id)
                    page = await context.get_current_page()
                    await page.wait_for_load_state()
                    return ToolResult(output=f"Switched to tab {tab_id}")

                elif action == "open_tab":
                    if not url:
                        return ToolResult(error="URL is required for 'open_tab' action")
                    await context.create_new_tab(url)
                    return ToolResult(output=f"Opened new tab with {url}")

                elif action == "close_tab":
                    await context.close_current_tab()
                    return ToolResult(output="Closed current tab")

                # Utility actions
                elif action == "wait":
                    seconds_to_wait = seconds if seconds is not None else 3
                    await asyncio.sleep(seconds_to_wait)
                    return ToolResult(output=f"Waited for {seconds_to_wait} seconds")

                else:
                    return ToolResult(error=f"Unknown action: {action}")

            except Exception as e:
                return ToolResult(error=f"Browser action '{action}' failed: {str(e)}")

    async def get_current_state(self) -> ToolResult:
        """
        Get the current browser state as a ToolResult.
        """
        try:
            # Ensure browser is initialized
            ctx = self.context
            if not ctx:
                ctx = await self._ensure_browser_initialized()

            state = await ctx.get_state()

            # Create a viewport_info dictionary if it doesn't exist
            viewport_height = 0
            if hasattr(state, "viewport_info") and state.viewport_info:
                viewport_height = state.viewport_info.height
            elif hasattr(ctx, "config") and hasattr(ctx.config, "browser_window_size"):
                viewport_height = ctx.config.browser_window_size.get("height", 0)

            # Take a screenshot for the state
            page = await ctx.get_current_page()

            await page.bring_to_front()
            await page.wait_for_load_state()

            screenshot = await page.screenshot(
                full_page=True, animations="disabled", type="jpeg", quality=100
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

            return ToolResult(
                output=json.dumps(state_info, indent=4, ensure_ascii=False),
                base64_image=screenshot,
            )
        except Exception as e:
            return ToolResult(error=f"Failed to get browser state: {str(e)}")

    async def cleanup(self):
        """Clean up browser resources."""
        async with self.lock:
            if self.context is not None:
                await self.context.close()
                self.context = None
                self.dom_service = None
            if self.browser is not None:
                await self.browser.close()
                self.browser = None

    def __del__(self):
        """Ensure cleanup when object is destroyed."""
        if self.browser is not None or self.context is not None:
            try:
                asyncio.run(self.cleanup())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.cleanup())
                loop.close()

```

## tool/create_chat_completion.py

```py
"""Chat completion tool for Enterprise AI."""

from typing import Any, List, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field

from enterprise_ai.tool.base import BaseTool, ToolResult


class CreateChatCompletion(BaseTool):
    """Tool for creating structured chat completions with specific formats."""

    name: str = "create_chat_completion"
    description: str = "Creates a structured completion with specified output formatting."

    # Type mapping for JSON schema
    type_mapping: dict = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }
    response_type: Optional[Type] = None
    required: List[str] = Field(default_factory=lambda: ["response"])

    def __init__(self, response_type: Optional[Type] = str):
        """Initialize with a specific response type."""
        super().__init__()
        self.response_type = response_type
        self.parameters = self._build_parameters()

    def _build_parameters(self) -> dict:
        """Build parameters schema based on response type."""
        if self.response_type is str:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "The response text that should be delivered to the user.",
                    },
                },
                "required": self.required,
            }

        if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
            schema = self.response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema["properties"],
                "required": schema.get("required", self.required),
            }

        return self._create_type_schema(self.response_type)

    def _create_type_schema(self, type_hint: Type) -> dict:
        """Create a JSON schema for the given type."""
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        # Handle primitive types
        if origin is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": self.type_mapping.get(type_hint, "string"),
                        "description": f"Response of type {type_hint.__name__}",
                    }
                },
                "required": self.required,
            }

        # Handle List type
        if origin is list:
            item_type = args[0] if args else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "array",
                        "items": self._get_type_info(item_type),
                    }
                },
                "required": self.required,
            }

        # Handle Dict type
        if origin is dict:
            value_type = args[1] if len(args) > 1 else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "object",
                        "additionalProperties": self._get_type_info(value_type),
                    }
                },
                "required": self.required,
            }

        # Handle Union type
        if origin is Union:
            return self._create_union_schema(args)

        return self._build_parameters()

    def _get_type_info(self, type_hint: Type) -> dict:
        """Get type information for a single type."""
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            return type_hint.model_json_schema()

        return {
            "type": self.type_mapping.get(type_hint, "string"),
            "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
        }

    def _create_union_schema(self, types: tuple) -> dict:
        """Create schema for Union types."""
        return {
            "type": "object",
            "properties": {"response": {"anyOf": [self._get_type_info(t) for t in types]}},
            "required": self.required,
        }

    async def execute(self, required: list | None = None, **kwargs) -> ToolResult:
        """Execute the chat completion with type conversion.

        Args:
            required: List of required field names or None
            **kwargs: Response data

        Returns:
            Converted response based on response_type
        """
        required = required or self.required

        # Handle case when required is a list
        if isinstance(required, list) and len(required) > 0:
            if len(required) == 1:
                required_field = required[0]
                result = kwargs.get(required_field, "")
            else:
                # Return multiple fields as a dictionary
                result = {field: kwargs.get(field, "") for field in required}
        else:
            required_field = "response"
            result = kwargs.get(required_field, "")

        # Type conversion logic
        if self.response_type is str:
            return ToolResult(output=result)

        if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
            converted = self.response_type(**kwargs)
            return ToolResult(output=str(converted))

        if get_origin(self.response_type) in (list, dict):
            return ToolResult(output=str(result))  # Convert to string for output

        try:
            converted = self.response_type(result)
            return ToolResult(output=str(converted))
        except (ValueError, TypeError):
            return ToolResult(output=str(result))

```

## tool/deep_research.py

```py
"""Deep research tool for Enterprise AI."""

import asyncio
import json
import re
import time
from typing import List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.llm import LLM
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.base import BaseTool, ToolError, ToolResult
from enterprise_ai.tool.web_search import SearchResult, WebSearch


logger = get_logger("tool.deep_research")

# Prompts for LLM interactions
OPTIMIZE_QUERY_PROMPT = """
You are a research assistant helping to optimize a search query for web research.
Your task is to reformulate the given query to be more effective for web searches.
Make it specific, use relevant keywords, and ensure it's clear and concise.

Original query: {query}

Provide only the optimized query text without any explanation or additional formatting.
"""

EXTRACT_INSIGHTS_PROMPT = """
Analyze the following content and extract key insights related to the research query.
For each insight, assess its relevance to the query on a scale of 0.0 to 1.0.

Research query: {query}
Content to analyze:
{content}

Extract up to 3 most important insights from this content. For each insight:
1. Provide the insight content
2. Provide relevance score (0.0-1.0)
"""

GENERATE_FOLLOW_UPS_PROMPT = """
Based on the insights discovered so far, generate follow-up research queries to explore gaps or related areas.
These should help deepen our understanding of the topic.

Original query: {original_query}
Current query: {current_query}
Key insights so far:
{insights}

Generate up to 3 specific follow-up queries that would help address gaps in our current knowledge.
Each query should be concise and focused on a specific aspect of the research topic.
"""

# Constants for insight parsing
DEFAULT_RELEVANCE_SCORE = 1.0
FALLBACK_RELEVANCE_SCORE = 0.7
FALLBACK_CONTENT_LIMIT = 500
# Pattern to detect start of an insight (number., -, *, •) and capture content
INSIGHT_MARKER_PATTERN = re.compile(r"^\s*(?:\d+\.|-|\*|•)\s*(.*)")
# Pattern to detect relevance score, capturing the number (case-insensitive)
RELEVANCE_SCORE_PATTERN = re.compile(r"relevance.*?:.*?(\d\.?\d*)", re.IGNORECASE)


class ResearchInsight(BaseModel):
    """A single insight discovered during research."""

    model_config = ConfigDict(frozen=True)  # Make insights immutable

    content: str = Field(description="The insight content")
    source_url: str = Field(description="URL where this insight was found")
    source_title: Optional[str] = Field(default=None, description="Title of the source")
    relevance_score: float = Field(
        default=1.0, description="Relevance score (0.0-1.0)", ge=0.0, le=1.0
    )

    def __str__(self) -> str:
        """Format insight as string with source attribution."""
        source = self.source_title or self.source_url
        return f"{self.content} [Source: {source}]"


class ResearchContext(BaseModel):
    """Research context for tracking research progress."""

    query: str = Field(description="The original research query")
    insights: List[ResearchInsight] = Field(
        default_factory=list, description="Key insights discovered"
    )
    follow_up_queries: List[str] = Field(
        default_factory=list, description="Generated follow-up queries"
    )
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    current_depth: int = Field(default=0, description="Current depth of research exploration", ge=0)
    max_depth: int = Field(default=2, description="Maximum depth of research to reach", ge=1)


class ResearchSummary(ToolResult):
    """Comprehensive summary of deep research results."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str = Field(description="The original research query")
    insights: List[ResearchInsight] = Field(
        default_factory=list, description="Key insights discovered"
    )
    visited_urls: Set[str] = Field(default_factory=set, description="URLs visited during research")
    depth_reached: int = Field(default=0, description="Maximum depth of research reached", ge=0)

    @model_validator(mode="after")
    def populate_output(self) -> "ResearchSummary":
        """Populate the output field after validation."""
        # Group and sort insights by relevance
        grouped_insights = {
            "Key Findings": [i for i in self.insights if i.relevance_score >= 0.8],
            "Additional Information": [i for i in self.insights if 0.5 <= i.relevance_score < 0.8],
            "Supplementary Information": [i for i in self.insights if i.relevance_score < 0.5],
        }

        sections = [
            f"# Research: {self.query}\n",
            f"**Sources**: {len(self.visited_urls)} | **Depth**: {self.depth_reached + 1}\n",
        ]

        for section_title, insights in grouped_insights.items():
            if insights:
                sections.append(f"## {section_title}")
                for i, insight in enumerate(insights, 1):
                    sections.extend(
                        [
                            insight.content,
                            f"> Source: [{insight.source_title or 'Link'}]({insight.source_url})\n",
                        ]
                    )

        # Assign the formatted string to the 'output' field inherited from ToolResult
        self.output = "\n".join(sections)
        return self


class DeepResearch(BaseTool):
    """Advanced research tool that explores a topic through iterative web searches."""

    name: str = "deep_research"
    description: str = """
    Performs comprehensive research on a topic through multi-level web searches
    and content analysis. Returns a structured summary of findings with source
    attribution and relevance ratings.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question or topic to investigate.",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum depth of iterative research (1-5). Default is 2.",
                "default": 2,
            },
            "results_per_search": {
                "type": "integer",
                "description": "Number of search results to analyze per search (1-20). Default is 5.",
                "default": 5,
            },
            "max_insights": {
                "type": "integer",
                "description": "Maximum number of insights to return. Default is 20.",
                "default": 20,
            },
            "time_limit_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds. Default is 120.",
                "default": 120,
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        super().__init__()
        self.search_tool = WebSearch()
        self.llm = LLM()

    async def execute(
        self,
        query: str,
        max_depth: int = 2,
        results_per_search: int = 5,
        max_insights: int = 20,
        time_limit_seconds: int = 120,
    ) -> ResearchSummary:
        """Execute deep research on the given query."""
        # Normalize parameters
        max_depth = max(1, min(max_depth, 5))
        results_per_search = max(1, min(results_per_search, 20))

        # Initialize research context and set deadline
        context = ResearchContext(query=query, max_depth=max_depth)
        deadline = time.time() + time_limit_seconds

        try:
            # Initiate research process with optimized query
            optimized_query = await self._generate_optimized_query(query)
            await self._research_graph(
                context=context,
                query=optimized_query,
                results_count=results_per_search,
                deadline=deadline,
            )
        except ToolError as e:
            logger.error(f"Research error: {str(e)}")
        except EnterpriseAIError as e:
            logger.error(f"Research error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during research: {str(e)}")

        # Prepare final summary
        return ResearchSummary(
            query=query,
            insights=sorted(context.insights, key=lambda x: x.relevance_score, reverse=True)[
                :max_insights
            ],
            visited_urls=context.visited_urls,
            depth_reached=context.current_depth,
        )

    async def _generate_optimized_query(self, query: str) -> str:
        """Generate an optimized search query using LLM."""
        try:
            prompt = OPTIMIZE_QUERY_PROMPT.format(query=query)

            # Prepare the request for the LLM
            messages = [{"role": "user", "content": prompt}]

            # Get a response from the LLM
            response = await self.llm.complete(messages=messages)

            # Extract the optimized query from the response
            optimized_query = (
                response.content.strip() if response and hasattr(response, "content") else ""
            )

            if not optimized_query:
                logger.warning("Generated empty optimized query, using original")
                return query

            logger.info(f"Optimized query: '{optimized_query}'")
            return optimized_query
        except Exception as e:
            logger.warning(f"Failed to optimize query: {str(e)}")
            return query  # Fall back to original query on error

    async def _research_graph(
        self,
        context: ResearchContext,
        query: str,
        results_count: int,
        deadline: float,
    ) -> None:
        """Run a complete research cycle (search, analyze, generate follow-ups)."""
        # Check termination conditions
        if time.time() >= deadline or context.current_depth >= context.max_depth:
            return

        # Log current research step
        logger.info(f"Research cycle at depth {context.current_depth + 1}")

        # 1. Web search
        search_results = await self._search_web(query, results_count)
        if not search_results:
            return

        # 2. Extract insights
        new_insights = await self._extract_insights(
            context, search_results, context.query, deadline
        )
        if not new_insights:
            return

        # 3. Generate follow-up queries
        follow_up_queries = await self._generate_follow_ups(new_insights, query, context.query)
        context.follow_up_queries.extend(follow_up_queries)

        # Update depth and proceed to next level
        context.current_depth += 1

        # 4. Continue research with follow-up queries
        if follow_up_queries and context.current_depth < context.max_depth:
            tasks = []  # Create a list to hold the tasks
            for follow_up in follow_up_queries[:2]:  # Limit branching factor
                if time.time() >= deadline:
                    break

                # Create a coroutine for the recursive research call
                task = self._research_graph(
                    context=context,
                    query=follow_up,
                    results_count=max(1, results_count - 1),  # Reduce result count
                    deadline=deadline,
                )
                tasks.append(task)  # Add the task to the list

            # Run all the created tasks concurrently
            if tasks:
                await asyncio.gather(*tasks)

    async def _search_web(self, query: str, results_count: int) -> List[SearchResult]:
        """Perform web search for the given query."""
        search_response = await self.search_tool.execute(
            query=query, num_results=results_count, fetch_content=True
        )
        return getattr(search_response, "results", [])

    async def _extract_insights(
        self,
        context: ResearchContext,
        results: List[SearchResult],
        original_query: str,
        deadline: float,
    ) -> List[ResearchInsight]:
        """Extract insights from search results."""
        all_insights = []

        for rst in results:
            # Skip if URL already visited or time exceeded
            if rst.url in context.visited_urls or time.time() >= deadline:
                continue

            context.visited_urls.add(rst.url)

            # Skip if no content available
            if not rst.raw_content:
                continue

            # Extract insights using LLM
            insights = await self._analyze_content(
                content=rst.raw_content[:10000],  # Limit content size
                url=rst.url,
                title=rst.title,
                query=original_query,
            )

            all_insights.extend(insights)
            context.insights.extend(insights)

            # Log discovered insights
            logger.info(f"Extracted {len(insights)} insights from {rst.url}")

        return all_insights

    async def _generate_follow_ups(
        self, insights: List[ResearchInsight], current_query: str, original_query: str
    ) -> List[str]:
        """Generate follow-up queries based on insights."""
        if not insights:
            return []

        # Format insights for the prompt
        insights_text = "\n".join([f"- {insight.content}" for insight in insights[:5]])

        # Create prompt for generating follow-up queries
        prompt = GENERATE_FOLLOW_UPS_PROMPT.format(
            original_query=original_query,
            current_query=current_query,
            insights=insights_text,
        )

        # Get follow-up queries from LLM
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.complete(messages=messages)
            content = response.content if hasattr(response, "content") else ""

            # Extract queries from response
            queries = []
            for line in content.strip().split("\n"):
                # Look for numbered lines, bulleted lines, or similar formatting
                if re.match(r"^\s*(\d+\.|\*|-|\•)\s+", line):
                    query_text = re.sub(r"^\s*(\d+\.|\*|-|\•)\s+", "", line).strip()
                    if query_text and len(query_text) > 10:  # Avoid too short queries
                        queries.append(query_text)

            # Ensure we don't return more than 3 queries
            return queries[:3]
        except Exception as e:
            logger.error(f"Error generating follow-up queries: {str(e)}")
            return []

    async def _analyze_content(
        self, content: str, url: str, title: str, query: str
    ) -> List[ResearchInsight]:
        """Extract insights from content based on relevance to query."""
        prompt = EXTRACT_INSIGHTS_PROMPT.format(
            query=query,
            content=content[:5000],  # Limit content size
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.complete(messages=messages)
            insights = []

            if response and hasattr(response, "content"):
                # Parse insights from the response text
                current_insight = {"content": "", "relevance_score": DEFAULT_RELEVANCE_SCORE}
                for line in response.content.strip().split("\n"):
                    # Check for new insight marker
                    if match := INSIGHT_MARKER_PATTERN.match(line):
                        # If we have a previous insight, add it
                        if current_insight["content"]:
                            insights.append(
                                ResearchInsight(
                                    content=current_insight["content"].strip(),
                                    source_url=url,
                                    source_title=title,
                                    relevance_score=current_insight["relevance_score"],
                                )
                            )
                            current_insight = {
                                "content": "",
                                "relevance_score": DEFAULT_RELEVANCE_SCORE,
                            }

                        # Start new insight
                        current_insight["content"] = match.group(1)
                    elif "relevance" in line.lower() and (
                        score_match := RELEVANCE_SCORE_PATTERN.search(line)
                    ):
                        # Extract relevance score
                        try:
                            score = float(score_match.group(1))
                            if 0 <= score <= 1:
                                current_insight["relevance_score"] = score
                        except ValueError:
                            pass
                    elif current_insight["content"]:
                        # Continue current insight
                        current_insight["content"] += " " + line.strip()

                # Add the last insight if any
                if current_insight["content"]:
                    insights.append(
                        ResearchInsight(
                            content=current_insight["content"].strip(),
                            source_url=url,
                            source_title=title,
                            relevance_score=current_insight["relevance_score"],
                        )
                    )

            # If no insights found, use fallback approach
            if not insights:
                logger.warning(
                    f"Could not parse insights from LLM response for {url}. Using fallback."
                )
                insights.append(
                    ResearchInsight(
                        content=f"Information found about {title or url}."[:FALLBACK_CONTENT_LIMIT],
                        source_url=url,
                        source_title=title,
                        relevance_score=FALLBACK_RELEVANCE_SCORE,
                    )
                )

            return insights
        except Exception as e:
            logger.error(f"Error analyzing content from {url}: {str(e)}")
            # Return fallback insight on error
            return [
                ResearchInsight(
                    content=f"Information related to the query was found at {title or url}."[
                        :FALLBACK_CONTENT_LIMIT
                    ],
                    source_url=url,
                    source_title=title,
                    relevance_score=FALLBACK_RELEVANCE_SCORE,
                )
            ]

```

## tool/planning.py

```py
"""Planning tool for Enterprise AI."""

from typing import Dict, List, Literal, Optional

from enterprise_ai.tool.base import BaseTool, ToolError, ToolResult


_PLANNING_TOOL_DESCRIPTION = """
A planning tool that allows the agent to create and manage plans for solving complex tasks.
The tool provides functionality for creating plans, updating plan steps, and tracking progress.
"""


class PlanningTool(BaseTool):
    """
    A planning tool that allows the agent to create and manage plans for solving complex tasks.
    The tool provides functionality for creating plans, updating plan steps, and tracking progress.
    """

    name: str = "planning"
    description: str = _PLANNING_TOOL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The command to execute. Available commands: create, update, list, get, set_active, mark_step, delete.",
                "enum": [
                    "create",
                    "update",
                    "list",
                    "get",
                    "set_active",
                    "mark_step",
                    "delete",
                ],
                "type": "string",
            },
            "plan_id": {
                "description": "Unique identifier for the plan. Required for create, update, set_active, and delete commands. Optional for get and mark_step (uses active plan if not specified).",
                "type": "string",
            },
            "title": {
                "description": "Title for the plan. Required for create command, optional for update command.",
                "type": "string",
            },
            "steps": {
                "description": "List of plan steps. Required for create command, optional for update command.",
                "type": "array",
                "items": {"type": "string"},
            },
            "step_index": {
                "description": "Index of the step to update (0-based). Required for mark_step command.",
                "type": "integer",
            },
            "step_status": {
                "description": "Status to set for a step. Used with mark_step command.",
                "enum": ["not_started", "in_progress", "completed", "blocked"],
                "type": "string",
            },
            "step_notes": {
                "description": "Additional notes for a step. Optional for mark_step command.",
                "type": "string",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    plans: dict = {}  # Dictionary to store plans by plan_id
    _current_plan_id: Optional[str] = None  # Track the current active plan

    async def execute(
        self,
        *,
        command: Literal["create", "update", "list", "get", "set_active", "mark_step", "delete"],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[Literal["not_started", "in_progress", "completed", "blocked"]] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute the planning tool with the given command and parameters.

        Parameters:
        - command: The operation to perform
        - plan_id: Unique identifier for the plan
        - title: Title for the plan (used with create command)
        - steps: List of steps for the plan (used with create command)
        - step_index: Index of the step to update (used with mark_step command)
        - step_status: Status to set for a step (used with mark_step command)
        - step_notes: Additional notes for a step (used with mark_step command)
        """

        if command == "create":
            return self._create_plan(plan_id, title, steps)
        elif command == "update":
            return self._update_plan(plan_id, title, steps)
        elif command == "list":
            return self._list_plans()
        elif command == "get":
            return self._get_plan(plan_id)
        elif command == "set_active":
            return self._set_active_plan(plan_id)
        elif command == "mark_step":
            return self._mark_step(plan_id, step_index, step_status, step_notes)
        elif command == "delete":
            return self._delete_plan(plan_id)
        else:
            raise ToolError(
                f"Unrecognized command: {command}. Allowed commands are: create, update, list, get, set_active, mark_step, delete"
            )

    def _create_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """Create a new plan with the given ID, title, and steps."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: create")

        if plan_id in self.plans:
            raise ToolError(
                f"A plan with ID '{plan_id}' already exists. Use 'update' to modify existing plans."
            )

        if not title:
            raise ToolError("Parameter `title` is required for command: create")

        if (
            not steps
            or not isinstance(steps, list)
            or not all(isinstance(step, str) for step in steps)
        ):
            raise ToolError(
                "Parameter `steps` must be a non-empty list of strings for command: create"
            )

        # Create a new plan with initialized step statuses
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
        }

        self.plans[plan_id] = plan
        self._current_plan_id = plan_id  # Set as active plan

        return ToolResult(
            output=f"Plan created successfully with ID: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _update_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """Update an existing plan with new title or steps."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: update")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]

        if title:
            plan["title"] = title

        if steps:
            if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
                raise ToolError("Parameter `steps` must be a list of strings for command: update")

            # Preserve existing step statuses for unchanged steps
            old_steps = plan["steps"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]

            # Create new step statuses and notes
            new_statuses = []
            new_notes = []

            for i, step in enumerate(steps):
                # If the step exists at the same position in old steps, preserve status and notes
                if i < len(old_steps) and step == old_steps[i]:
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")

            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        return ToolResult(
            output=f"Plan updated successfully: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _list_plans(self) -> ToolResult:
        """List all available plans."""
        if not self.plans:
            return ToolResult(output="No plans available. Create a plan with the 'create' command.")

        output = "Available plans:\n"
        for plan_id, plan in self.plans.items():
            current_marker = " (active)" if plan_id == self._current_plan_id else ""
            completed = sum(1 for status in plan["step_statuses"] if status == "completed")
            total = len(plan["steps"])
            progress = f"{completed}/{total} steps completed"
            output += f"• {plan_id}{current_marker}: {plan['title']} - {progress}\n"

        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Get details of a specific plan."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError("No active plan. Please specify a plan_id or set an active plan.")
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]
        return ToolResult(output=self._format_plan(plan))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Set a plan as the active plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: set_active")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        self._current_plan_id = plan_id
        return ToolResult(
            output=f"Plan '{plan_id}' is now the active plan.\n\n{self._format_plan(self.plans[plan_id])}"
        )

    def _mark_step(
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """Mark a step with a specific status and optional notes."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError("No active plan. Please specify a plan_id or set an active plan.")
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        if step_index is None:
            raise ToolError("Parameter `step_index` is required for command: mark_step")

        plan = self.plans[plan_id]

        if step_index < 0 or step_index >= len(plan["steps"]):
            raise ToolError(
                f"Invalid step_index: {step_index}. Valid indices range from 0 to {len(plan['steps']) - 1}."
            )

        if step_status and step_status not in [
            "not_started",
            "in_progress",
            "completed",
            "blocked",
        ]:
            raise ToolError(
                f"Invalid step_status: {step_status}. Valid statuses are: not_started, in_progress, completed, blocked"
            )

        if step_status:
            plan["step_statuses"][step_index] = step_status

        if step_notes:
            plan["step_notes"][step_index] = step_notes

        return ToolResult(
            output=f"Step {step_index} updated in plan '{plan_id}'.\n\n{self._format_plan(plan)}"
        )

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Delete a plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: delete")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        del self.plans[plan_id]

        # If the deleted plan was the active plan, clear the active plan
        if self._current_plan_id == plan_id:
            self._current_plan_id = None

        return ToolResult(output=f"Plan '{plan_id}' has been deleted.")

    def _format_plan(self, plan: Dict) -> str:
        """Format a plan for display."""
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"

        # Calculate progress statistics
        total_steps = len(plan["steps"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(1 for status in plan["step_statuses"] if status == "in_progress")
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        not_started = sum(1 for status in plan["step_statuses"] if status == "not_started")

        output += f"Progress: {completed}/{total_steps} steps completed "
        if total_steps > 0:
            percentage = (completed / total_steps) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"

        output += f"Status: {completed} completed, {in_progress} in progress, {blocked} blocked, {not_started} not started\n\n"
        output += "Steps:\n"

        # Add each step with its status and notes
        for i, (step, status, notes) in enumerate(
            zip(plan["steps"], plan["step_statuses"], plan["step_notes"])
        ):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(status, "[ ]")

            output += f"{i}. {status_symbol} {step}\n"
            if notes:
                output += f"   Notes: {notes}\n"

        return output

```

## tool/python_execute.py

```py
"""Python code execution tool."""

import multiprocessing
import sys
from io import StringIO
from typing import Dict

from enterprise_ai.tool.base import BaseTool, ToolResult


class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results."
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds.",
                "default": 5,
            },
        },
        "required": ["code"],
    }

    def _run_code(self, code: str, result_dict: dict, safe_globals: dict) -> None:
        """Execute Python code in a separate process with output capturing."""
        original_stdout = sys.stdout
        try:
            output_buffer = StringIO()
            sys.stdout = output_buffer
            exec(code, safe_globals, safe_globals)
            result_dict["output"] = output_buffer.getvalue()
            result_dict["success"] = True
        except Exception as e:
            result_dict["output"] = str(e)
            result_dict["success"] = False
        finally:
            sys.stdout = original_stdout

    async def execute(
        self,
        code: str,
        timeout: int = 5,
    ) -> ToolResult:
        """
        Executes the provided Python code with a timeout.

        Args:
            code: The Python code to execute.
            timeout: Execution timeout in seconds.

        Returns:
            ToolResult containing execution output or error message.
        """
        with multiprocessing.Manager() as manager:
            result = manager.dict({"output": "", "success": False})

            # Create a safe globals dictionary
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": __builtins__}
            else:
                safe_globals = {"__builtins__": __builtins__.__dict__.copy()}

            # Execute in a separate process for isolation
            proc = multiprocessing.Process(target=self._run_code, args=(code, result, safe_globals))
            proc.start()
            proc.join(timeout)

            # Handle timeout
            if proc.is_alive():
                proc.terminate()
                proc.join(1)
                return ToolResult(error=f"Execution timeout after {timeout} seconds")

            # Return successful result
            if result["success"]:
                return ToolResult(output=result["output"])
            else:
                # Return error result
                return ToolResult(error=f"Execution error: {result['output']}")

```

## tool/str_replace_editor.py

```py
"""File and directory manipulation tool with sandbox support."""

from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, List, Literal, Optional, get_args

from enterprise_ai.config import get_config
from enterprise_ai.tool.base import BaseTool, CLIResult, ToolError, ToolResult
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client

# Type for command literals
Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
    "undo_edit",
]

# Constants
SNIPPET_LINES: int = 4
MAX_RESPONSE_LEN: int = 16000
TRUNCATED_MESSAGE: str = (
    "<response clipped><NOTE>To save on context only part of this file has been shown to you. "
    "You should retry this tool after you have searched inside the file with `grep -n` "
    "in order to find the line numbers of what you are looking for.</NOTE>"
)

# Tool description
_STR_REPLACE_EDITOR_DESCRIPTION = """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`
"""


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE


class StrReplaceEditor(BaseTool):
    """A tool for viewing, creating, and editing files with sandbox support."""

    name: str = "str_replace_editor"
    description: str = _STR_REPLACE_EDITOR_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.",
                "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                "type": "string",
            },
            "path": {
                "description": "Absolute path to file or directory.",
                "type": "string",
            },
            "file_text": {
                "description": "Required parameter of `create` command, with the content of the file to be created.",
                "type": "string",
            },
            "old_str": {
                "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                "type": "string",
            },
            "new_str": {
                "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                "type": "string",
            },
            "insert_line": {
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                "type": "integer",
            },
            "view_range": {
                "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                "items": {"type": "integer"},
                "type": "array",
            },
        },
        "required": ["command", "path"],
    }
    _file_history: DefaultDict[str, List[str]] = defaultdict(list)
    _sandbox_client: Optional[BaseSandboxClient] = None

    def __init__(self):
        super().__init__()
        self._sandbox_client = None

    async def _get_sandbox_client(self) -> BaseSandboxClient:
        """Get or create a sandbox client."""
        if self._sandbox_client is None:
            self._sandbox_client = create_sandbox_client()
            await self._sandbox_client.create()
        return self._sandbox_client

    async def execute(
        self,
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a file operation command."""
        # Get the sandbox client
        sandbox = await self._get_sandbox_client()

        # Validate path and command combination
        await self.validate_path(command, path, sandbox)

        # Execute the appropriate command
        if command == "view":
            result = await self.view(path, view_range, sandbox)
        elif command == "create":
            if file_text is None:
                raise ToolError("Parameter `file_text` is required for command: create")
            await sandbox.write_file(path, file_text)
            self._file_history[path].append(file_text)
            result = ToolResult(output=f"File created successfully at: {path}")
        elif command == "str_replace":
            if old_str is None:
                raise ToolError("Parameter `old_str` is required for command: str_replace")
            result = await self.str_replace(path, old_str, new_str, sandbox)
        elif command == "insert":
            if insert_line is None:
                raise ToolError("Parameter `insert_line` is required for command: insert")
            if new_str is None:
                raise ToolError("Parameter `new_str` is required for command: insert")
            result = await self.insert(path, insert_line, new_str, sandbox)
        elif command == "undo_edit":
            result = await self.undo_edit(path, sandbox)
        else:
            # This should be caught by type checking, but we include it for safety
            raise ToolError(
                f"Unrecognized command {command}. The allowed commands are: {', '.join(get_args(Command))}"
            )

        return result

    async def validate_path(self, command: str, path: str, sandbox: BaseSandboxClient) -> None:
        """Validate path and command combination."""
        path_obj = Path(path)

        # Check if path is absolute
        if not path_obj.is_absolute():
            raise ToolError(f"The path {path} is not an absolute path")

        # Check if path exists (except for create command)
        if command != "create":
            try:
                # Check if path exists by running a command in the sandbox
                exit_code, stdout, stderr = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )
                if "not exists" in stdout:
                    raise ToolError(f"The path {path} does not exist. Please provide a valid path.")

                # Check if path is a directory
                exit_code, stdout, stderr = await sandbox.run_command(
                    f"test -d {path} && echo 'directory' || echo 'file'"
                )
                is_dir = "directory" in stdout

                if is_dir and command != "view":
                    raise ToolError(
                        f"The path {path} is a directory and only the `view` command can be used on directories"
                    )
            except Exception as e:
                if not isinstance(e, ToolError):
                    raise ToolError(f"Error validating path: {str(e)}")
                raise

        # Check if file exists for create command
        elif command == "create":
            try:
                exit_code, stdout, stderr = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )
                if "exists" in stdout:
                    raise ToolError(
                        f"File already exists at: {path}. Cannot overwrite files using command `create`."
                    )
            except Exception as e:
                if not isinstance(e, ToolError):
                    raise ToolError(f"Error checking file existence: {str(e)}")
                raise

    async def view(
        self,
        path: str,
        view_range: Optional[List[int]] = None,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Display file or directory content."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Determine if path is a directory
        exit_code, stdout, stderr = await sandbox.run_command(
            f"test -d {path} && echo 'directory' || echo 'file'"
        )
        is_dir = "directory" in stdout

        if is_dir:
            # Directory handling
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            return await self._view_directory(path, sandbox)
        else:
            # File handling
            return await self._view_file(path, sandbox, view_range)

    @staticmethod
    async def _view_directory(path: str, sandbox: BaseSandboxClient) -> CLIResult:
        """Display directory contents."""
        find_cmd = f"find {path} -maxdepth 2 -not -path '*/\\.*'"

        # Execute command using the sandbox
        exit_code, stdout, stderr = await sandbox.run_command(find_cmd)

        if not stderr:
            stdout = (
                f"Here's the files and directories up to 2 levels deep in {path}, "
                f"excluding hidden items:\n{stdout}\n"
            )

        return CLIResult(output=stdout, error=stderr)

    async def _view_file(
        self,
        path: str,
        sandbox: BaseSandboxClient,
        view_range: Optional[List[int]] = None,
    ) -> CLIResult:
        """Display file content, optionally within a specified line range."""
        # Read file content
        file_content = await sandbox.read_file(path)
        init_line = 1

        # Apply view range if specified
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError("Invalid `view_range`. It should be a list of two integers.")

            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range

            # Validate view range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be "
                    f"within the range of lines of the file: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be "
                    f"smaller than the number of lines in the file: `{n_lines_file}`"
                )
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be "
                    f"larger or equal than its first `{init_line}`"
                )

            # Apply range
            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        # Format and return result
        return CLIResult(output=self._make_output(file_content, str(path), init_line=init_line))

    async def str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Replace a unique string in a file with a new string."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content and expand tabs
        file_content = await sandbox.read_file(path)
        file_content = file_content.expandtabs()
        old_str = old_str.expandtabs()
        new_str = new_str.expandtabs() if new_str is not None else ""

        # Check if old_str is unique in the file
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ToolError(
                f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
            )
        elif occurrences > 1:
            # Find line numbers of occurrences
            file_content_lines = file_content.split("\n")
            lines = []
            for idx, line in enumerate(file_content_lines):
                if old_str in line:
                    lines.append(idx + 1)
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str `{old_str}` "
                f"in lines {lines}. Please ensure it is unique"
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str, new_str)

        # Write the new content to the file
        await sandbox.write_file(path, new_file_content)

        # Save the original content to history
        self._file_history[path].append(file_content)

        # Create a snippet of the edited section
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # Prepare the success message
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(snippet, f"a snippet of {path}", start_line + 1)
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

        return CLIResult(output=success_msg)

    async def insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Insert text at a specific line in a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read and prepare content
        file_text = await sandbox.read_file(path)
        file_text = file_text.expandtabs()
        new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        # Validate insert_line
        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within "
                f"the range of lines of the file: {[0, n_lines_file]}"
            )

        # Perform insertion
        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line] + new_str_lines + file_text_lines[insert_line:]
        )

        # Create a snippet for preview
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        # Join lines and write to file
        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        await sandbox.write_file(path, new_file_text)
        self._file_history[path].append(file_text)

        # Prepare success message
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(
            snippet,
            "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."

        return CLIResult(output=success_msg)

    async def undo_edit(self, path: str, sandbox: Optional[BaseSandboxClient] = None) -> CLIResult:
        """Revert the last edit made to a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        await sandbox.write_file(path, old_text)

        return CLIResult(
            output=f"Last edit to {path} undone successfully. {self._make_output(old_text, str(path))}"
        )

    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        """Format file content for display with line numbers."""
        file_content = maybe_truncate(file_content)
        if expand_tabs:
            file_content = file_content.expandtabs()

        # Add line numbers to each line
        file_content = "\n".join(
            [f"{i + init_line:6}\t{line}" for i, line in enumerate(file_content.split("\n"))]
        )

        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n" + file_content + "\n"
        )

```

## tool/terminate.py

```py
"""Terminate tool for Enterprise AI."""

from enterprise_ai.tool.base import BaseTool, ToolResult


_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
When you have finished all the tasks, call this tool to end the work."""


class Terminate(BaseTool):
    """Tool to signal the end of a conversation or task."""

    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            },
            "message": {
                "type": "string",
                "description": "Optional message explaining the termination reason.",
            },
        },
        "required": ["status"],
    }

    async def execute(self, status: str, message: str = None) -> ToolResult:
        """
        Terminate the current execution.

        Args:
            status: The status of termination ('success' or 'failure')
            message: Optional explanation message

        Returns:
            ToolResult with termination status
        """
        response = f"The interaction has been completed with status: {status}"
        if message:
            response += f"\nMessage: {message}"

        return ToolResult(output=response)

```

## tool/tool_collection.py

```py
"""Collection classes for managing multiple tools."""

from typing import Any, Dict, List, Tuple

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.tool.base import BaseTool, ToolFailure, ToolResult, ToolError


class ToolCollection:
    """A collection of defined tools."""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def __iter__(self):
        return iter(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        """Convert all tools to function call format."""
        return [tool.to_param() for tool in self.tools]

    async def execute(self, *, name: str, tool_input: Dict[str, Any] = None) -> ToolResult:
        """Execute a specific tool by name with provided input."""
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            result = await tool(**(tool_input or {}))
            return result
        except ToolError as e:
            return ToolFailure(error=e.message)
        except EnterpriseAIError as e:
            return ToolFailure(error=str(e))
        except Exception as e:
            return ToolFailure(error=f"Unexpected error: {str(e)}")

    async def execute_all(self) -> List[ToolResult]:
        """Execute all tools in the collection sequentially."""
        results = []
        for tool in self.tools:
            try:
                result = await tool()
                results.append(result)
            except ToolError as e:
                results.append(ToolFailure(error=e.message))
            except Exception as e:
                results.append(ToolFailure(error=f"Error: {str(e)}"))
        return results

    def get_tool(self, name: str) -> BaseTool:
        """Get a tool by name."""
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool):
        """Add a single tool to the collection."""
        self.tools = (*self.tools, tool)
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool):
        """Add multiple tools to the collection."""
        for tool in tools:
            self.add_tool(tool)
        return self

```

## tool/web_search.py

```py
"""Web search tool for Enterprise AI."""

import asyncio
import base64
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, model_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.base import BaseTool, ToolResult
from enterprise_ai.tool.search import (
    BaiduSearchEngine,
    BingSearchEngine,
    DuckDuckGoSearchEngine,
    GoogleSearchEngine,
    SearchItem,
    WebSearchEngine,
)

logger = get_logger("tool.web_search")


class SearchResult(BaseModel):
    """Represents a single search result returned by a search engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    position: int = Field(description="Position in search results")
    url: str = Field(description="URL of the search result")
    title: str = Field(default="", description="Title of the search result")
    description: str = Field(default="", description="Description or snippet of the search result")
    source: str = Field(description="The search engine that provided this result")
    raw_content: Optional[str] = Field(
        default=None, description="Raw content from the search result page if available"
    )

    def __str__(self) -> str:
        """String representation of a search result."""
        return f"{self.title} ({self.url})"


class SearchMetadata(BaseModel):
    """Metadata about the search operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_results: int = Field(description="Total number of results found")
    language: str = Field(description="Language code used for the search")
    country: str = Field(description="Country code used for the search")


class SearchResponse(ToolResult):
    """Structured response from the web search tool, inheriting ToolResult."""

    query: str = Field(description="The search query that was executed")
    results: List[SearchResult] = Field(default_factory=list, description="List of search results")
    metadata: Optional[SearchMetadata] = Field(
        default=None, description="Metadata about the search"
    )

    @model_validator(mode="after")
    def populate_output(self) -> "SearchResponse":
        """Populate output or error fields based on search results."""
        if self.error:
            return self

        result_text = [f"Search results for '{self.query}':"]

        for i, result in enumerate(self.results, 1):
            # Add title with position number
            title = result.title.strip() or "No title"
            result_text.append(f"\n{i}. {title}")

            # Add URL with proper indentation
            result_text.append(f"   URL: {result.url}")

            # Add description if available
            if result.description.strip():
                result_text.append(f"   Description: {result.description}")

            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content[:1000].replace("\n", " ").strip()
                if len(result.raw_content) > 1000:
                    content_preview += "..."
                result_text.append(f"   Content: {content_preview}")

        # Add metadata at the bottom if available
        if self.metadata:
            result_text.extend(
                [
                    "\nMetadata:",
                    f"- Total results: {self.metadata.total_results}",
                    f"- Language: {self.metadata.language}",
                    f"- Country: {self.metadata.country}",
                ]
            )

        self.output = "\n".join(result_text)
        return self


class WebContentFetcher:
    """Utility class for fetching web content."""

    @staticmethod
    async def fetch_content(url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch and extract the main content from a webpage.

        Args:
            url: The URL to fetch content from
            timeout: Request timeout in seconds

        Returns:
            Extracted text content or None if fetching fails
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Use asyncio to run requests in a thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.get(url, headers=headers, timeout=timeout)
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch content from {url}: HTTP {response.status_code}")
                return None

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()

            # Get text content
            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace and limit size (100KB max)
            text = " ".join(text.split())
            return text[:10000] if text else None

        except Exception as e:
            logger.warning(f"Error fetching content from {url}: {e}")
            return None


class WebSearch(BaseTool):
    """Search the web for information using various search engines."""

    name: str = "web_search"
    description: str = """Search the web for real-time information about any topic.
    This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
    If the primary search engine fails, it automatically falls back to alternative engines."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to the search engine.",
            },
            "num_results": {
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 5.",
                "default": 5,
            },
            "lang": {
                "type": "string",
                "description": "(optional) Language code for search results (default: en).",
                "default": "en",
            },
            "country": {
                "type": "string",
                "description": "(optional) Country code for search results (default: us).",
                "default": "us",
            },
            "fetch_content": {
                "type": "boolean",
                "description": "(optional) Whether to fetch full content from result pages. Default is false.",
                "default": False,
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        super().__init__()
        # Initialize search engines
        self._search_engine = {
            "google": GoogleSearchEngine(),
            "baidu": BaiduSearchEngine(),
            "duckduckgo": DuckDuckGoSearchEngine(),
            "bing": BingSearchEngine(),
        }
        self.content_fetcher = WebContentFetcher()

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        lang: Optional[str] = None,
        country: Optional[str] = None,
        fetch_content: bool = False,
    ) -> SearchResponse:
        """
        Execute a Web search and return detailed search results.

        Args:
            query: The search query to submit to the search engine
            num_results: The number of search results to return (default: 5)
            lang: Language code for search results (default from config)
            country: Country code for search results (default from config)
            fetch_content: Whether to fetch content from result pages (default: False)

        Returns:
            A structured response containing search results and metadata
        """
        # Get settings from config
        retry_delay = get_config("search.retry_delay", 60)
        max_retries = get_config("search.max_retries", 3)

        # Use config values for lang and country if not specified
        if lang is None:
            lang = get_config("search.lang", "en")

        if country is None:
            country = get_config("search.country", "us")

        search_params = {"lang": lang, "country": country}

        # Try searching with retries when all engines fail
        for retry_count in range(max_retries + 1):
            results = await self._try_all_engines(query, num_results, search_params)

            if results:
                # Fetch content if requested
                if fetch_content:
                    results = await self._fetch_content_for_results(results)

                # Return a successful structured response
                return SearchResponse(
                    query=query,
                    results=results,
                    metadata=SearchMetadata(
                        total_results=len(results),
                        language=lang,
                        country=country,
                    ),
                )

            if retry_count < max_retries:
                # All engines failed, wait and retry
                logger.warning(
                    f"All search engines failed. Waiting {retry_delay} seconds before retry {retry_count + 1}/{max_retries}..."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"All search engines failed after {max_retries} retries. Giving up.")

        # Return an error response
        return SearchResponse(
            query=query,
            error="All search engines failed to return results after multiple retries.",
            results=[],
        )

    async def _try_all_engines(
        self, query: str, num_results: int, search_params: Dict[str, str]
    ) -> List[SearchResult]:
        """Try all search engines in the configured order."""
        engine_order = self._get_engine_order()
        failed_engines = []

        for engine_name in engine_order:
            engine = self._search_engine[engine_name]
            logger.info(f"🔎 Attempting search with {engine_name.capitalize()}...")
            search_items = await self._perform_search_with_engine(
                engine, query, num_results, search_params
            )

            if not search_items:
                failed_engines.append(engine_name)
                continue

            if failed_engines:
                logger.info(
                    f"Search successful with {engine_name.capitalize()} after trying: {', '.join(failed_engines)}"
                )

            # Transform search items into structured results
            return [
                SearchResult(
                    position=i + 1,
                    url=item.url,
                    title=item.title or f"Result {i + 1}",  # Ensure we always have a title
                    description=item.description or "",
                    source=engine_name,
                )
                for i, item in enumerate(search_items)
            ]

        if failed_engines:
            logger.error(f"All search engines failed: {', '.join(failed_engines)}")
        return []

    async def _fetch_content_for_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Fetch and add web content to search results."""
        if not results:
            return []

        # Create tasks for each result
        tasks = [self._fetch_single_result_content(result) for result in results]

        # Execute all fetch operations concurrently
        fetched_results = await asyncio.gather(*tasks)
        return list(fetched_results)

    async def _fetch_single_result_content(self, result: SearchResult) -> SearchResult:
        """Fetch content for a single search result."""
        if result.url:
            content = await self.content_fetcher.fetch_content(result.url)
            if content:
                # Create a new result with content added
                return SearchResult(
                    position=result.position,
                    url=result.url,
                    title=result.title,
                    description=result.description,
                    source=result.source,
                    raw_content=content,
                )
        return result

    def _get_engine_order(self) -> List[str]:
        """Determines the order in which to try search engines."""
        preferred = get_config("search.engine", "google").lower()
        fallbacks = get_config("search.fallback_engines", [])

        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]

        # Start with preferred engine, then fallbacks, then remaining engines
        engine_order = [preferred] if preferred in self._search_engine else []
        engine_order.extend(
            [fb for fb in fallbacks if fb in self._search_engine and fb not in engine_order]
        )
        engine_order.extend([e for e in self._search_engine if e not in engine_order])

        return engine_order

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, str],
    ) -> List[SearchItem]:
        """Execute search with the given engine and parameters."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: list(
                engine.perform_search(
                    query,
                    num_results=num_results,
                    lang=search_params.get("lang"),
                    country=search_params.get("country"),
                )
            ),
        )

```
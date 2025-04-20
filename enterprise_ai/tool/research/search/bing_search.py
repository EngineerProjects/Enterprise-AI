"""Bing search engine implementation."""

from typing import Any, Dict, List, Optional, Tuple, cast

import requests  # type: ignore
from bs4 import BeautifulSoup, Tag  # type: ignore

from enterprise_ai.logger import get_logger
from enterprise_ai.tool.research.search.base import SearchItem, WebSearchEngine


logger = get_logger("tool.research.search.bing")

ABSTRACT_MAX_LENGTH = 300

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/49.0.2623.108 Chrome/49.0.2623.108 Safari/537.36",
]

HEADERS: Dict[str, str] = {
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

    def __init__(self, **data: Any) -> None:
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

        list_result: List[SearchItem] = []
        first = 1
        current_url = BING_SEARCH_URL + query

        while len(list_result) < num_results and current_url:
            data, next_url = self._parse_html(current_url, rank_start=len(list_result), first=first)
            if data:
                list_result.extend(data)

            if not next_url:
                break

            current_url = next_url
            first += 10

        return list_result[:num_results]

    def _parse_html(
        self, url: str, rank_start: int = 0, first: int = 1
    ) -> Tuple[List[SearchItem], Optional[str]]:
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
            if not self.session:
                logger.error("Session not initialized")
                return [], None

            res = self.session.get(url=url)
            res.encoding = "utf-8"
            root = BeautifulSoup(res.text, "lxml")

            list_data: List[SearchItem] = []

            # Find results container
            ol_results = root.find("ol", {"id": "b_results"})
            if not ol_results:
                return [], None

            # Find all result items
            for li in ol_results.find_all("li", {"class": "b_algo"}):  # type: ignore
                title = ""
                url_text = ""
                abstract = ""
                try:
                    # Extract title and URL
                    h2 = li.find("h2")
                    if h2:
                        title = self._safe_get_text(h2)
                        a_tag = h2.find("a")
                        if a_tag:
                            # Use safe attribute access
                            href = self._safe_get_attribute(a_tag, "href")
                            if href:
                                url_text = href

                    # Extract description
                    p = li.find("p")
                    if p:
                        abstract = self._safe_get_text(p)

                    # Truncate description if needed
                    if ABSTRACT_MAX_LENGTH and len(abstract) > ABSTRACT_MAX_LENGTH:
                        abstract = abstract[:ABSTRACT_MAX_LENGTH]

                    rank_start += 1

                    # Create a SearchItem object
                    list_data.append(
                        SearchItem(
                            title=title or f"Bing Result {rank_start}",
                            url=url_text,
                            description=abstract,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue

            # Find next page button
            next_btn = root.find("a", {"title": "Next page"})
            if not next_btn:
                return list_data, None

            # Safely get next page URL
            href = self._safe_get_attribute(next_btn, "href")
            if href:
                next_url = BING_HOST_URL + href
                return list_data, next_url

            return list_data, None

        except Exception as e:
            logger.warning(f"Error parsing HTML: {e}")
            return [], None

    def _safe_get_text(self, element: Any) -> str:
        """Safely extract text from a BeautifulSoup element."""
        try:
            if hasattr(element, "text"):
                text = element.text
                if isinstance(text, str):
                    return text.strip()
            return ""
        except Exception:
            return ""

    def _safe_get_attribute(self, element: Any, attr: str) -> str:
        """Safely get an attribute from a BeautifulSoup element."""
        try:
            # First check if it's a Tag (which has .get method)
            if isinstance(element, Tag):
                attr_value = element.get(attr)
                if attr_value and isinstance(attr_value, str):
                    return cast(str, attr_value).strip()

            # Fallback: try direct attribute access if .get isn't available
            elif hasattr(element, attr):
                attr_value = getattr(element, attr)
                if attr_value and isinstance(attr_value, str):
                    return cast(str, attr_value).strip()
            return ""
        except Exception:
            return ""

    def perform_search(
        self, query: str, num_results: int = 10, *args: Any, **kwargs: Any
    ) -> List[SearchItem]:
        """
        Bing search engine.

        Args:
            query: The search query
            num_results: Maximum number of results to return
            args: Additional positional arguments
            kwargs: Additional keyword arguments

        Returns:
            List of search results formatted according to SearchItem model
        """
        return self._search_sync(query, num_results=num_results)

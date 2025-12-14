"""Firecrawl client for news fetching via MCP or API."""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class FirecrawlClient:
    """
    Client for Firecrawl integration.

    Uses Firecrawl API to search and scrape news content.
    """

    def __init__(self) -> None:
        """Initialize Firecrawl client with API configuration."""
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.base_url = "https://api.firecrawl.dev/v1"
        self.timeout = 30.0

    async def search_news(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for news using Firecrawl's search capability.

        Uses web search with news-focused query to find actual news articles.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of search result dictionaries with title, url, description
        """
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Keep query focused - "news 2024 2025" already in category queries
            news_query = query

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json={
                        "query": news_query,
                        "limit": limit,
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("data", [])
                logger.info(f"Firecrawl search returned {len(results)} results for query: {query}")
                return results

        except httpx.TimeoutException:
            logger.warning(f"Firecrawl search timeout for query: {query}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Firecrawl search HTTP error: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Firecrawl search failed: {e}")
            return []

    async def scrape_url(
        self,
        url: str,
    ) -> Dict[str, Any]:
        """
        Scrape a specific URL to get content.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with scraped content
        """
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/scrape",
                    headers=headers,
                    json={
                        "url": url,
                        "formats": ["markdown", "links"],
                        "onlyMainContent": True,
                    },
                )
                response.raise_for_status()
                data = response.json()

                logger.info(f"Successfully scraped URL: {url}")
                return data.get("data", {})

        except httpx.TimeoutException:
            logger.warning(f"Firecrawl scrape timeout for URL: {url}")
            return {}
        except httpx.HTTPStatusError as e:
            logger.error(f"Firecrawl scrape HTTP error for {url}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Firecrawl scrape failed for {url}: {e}")
            return {}

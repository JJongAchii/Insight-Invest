"""Google News RSS client for fetching news without API limits."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


class GoogleNewsClient:
    """
    Client for fetching news from Google News RSS feeds.

    Benefits over Firecrawl:
    - No API key required
    - No rate limits
    - Always returns recent news
    - Free and unlimited
    """

    def __init__(self) -> None:
        """Initialize Google News client."""
        self.base_url = "https://news.google.com/rss"
        self.timeout = 15.0

    async def fetch_recent_news(
        self,
        limit: int = 10,
        language: str = "en",
        country: str = "US",
    ) -> List[Dict[str, Any]]:
        """
        Fetch most recent top news stories.

        Args:
            limit: Maximum number of articles
            language: Language code (en, ko, etc.)
            country: Country code (US, KR, etc.)

        Returns:
            List of news article dictionaries
        """
        # Google News top stories RSS
        url = f"{self.base_url}?hl={language}-{country}&gl={country}&ceid={country}:{language}"
        return await self._fetch_rss(url, limit)

    async def fetch_topic_news(
        self,
        query: str,
        limit: int = 5,
        language: str = "en",
        country: str = "US",
    ) -> List[Dict[str, Any]]:
        """
        Fetch news for a specific topic/query.

        Args:
            query: Search query for news topic
            limit: Maximum number of articles
            language: Language code
            country: Country code

        Returns:
            List of news article dictionaries
        """
        # Google News search RSS
        encoded_query = quote(query)
        url = f"{self.base_url}/search?q={encoded_query}&hl={language}-{country}&gl={country}&ceid={country}:{language}"
        return await self._fetch_rss(url, limit)

    async def _fetch_rss(self, url: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch and parse RSS feed.

        Args:
            url: RSS feed URL
            limit: Maximum number of items

        Returns:
            List of parsed news items
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_content = response.text

            # Parse RSS XML
            articles = self._parse_rss_xml(xml_content, limit)
            logger.info(f"Google News RSS returned {len(articles)} articles")
            return articles

        except httpx.TimeoutException:
            logger.warning(f"Google News RSS timeout for URL: {url}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Google News RSS HTTP error: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Google News RSS failed: {e}")
            return []

    def _parse_rss_xml(self, xml_content: str, limit: int) -> List[Dict[str, Any]]:
        """
        Parse RSS XML content into article dictionaries.

        Uses regex parsing to avoid external XML library dependency.
        """
        articles = []

        # Extract all <item> blocks
        item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL)
        items = item_pattern.findall(xml_content)

        for item_xml in items[:limit]:
            article = self._parse_item(item_xml)
            if article:
                articles.append(article)

        return articles

    def _parse_item(self, item_xml: str) -> Optional[Dict[str, Any]]:
        """Parse a single RSS item into article dictionary."""
        try:
            title = self._extract_tag(item_xml, "title")
            link = self._extract_tag(item_xml, "link")
            pub_date = self._extract_tag(item_xml, "pubDate")
            source = self._extract_source(item_xml)

            if not title or not link:
                return None

            # Google News RSS descriptions contain HTML lists of related articles
            # which aren't useful as summaries, so we don't use them
            return {
                "title": title,
                "url": link,
                "source": source or "Google News",
                "published_at": self._parse_pub_date(pub_date),
                "description": None,
            }
        except Exception as e:
            logger.warning(f"Failed to parse RSS item: {e}")
            return None

    @staticmethod
    def _extract_tag(xml: str, tag: str) -> Optional[str]:
        """Extract content from XML tag."""
        # Handle CDATA
        cdata_pattern = re.compile(rf"<{tag}[^>]*><!\[CDATA\[(.*?)\]\]></{tag}>", re.DOTALL)
        match = cdata_pattern.search(xml)
        if match:
            return match.group(1).strip()

        # Handle regular tags
        pattern = re.compile(rf"<{tag}[^>]*>(.*?)</{tag}>", re.DOTALL)
        match = pattern.search(xml)
        if match:
            return match.group(1).strip()

        return None

    @staticmethod
    def _extract_source(xml: str) -> Optional[str]:
        """Extract source from Google News RSS item."""
        # Google News uses <source> tag
        pattern = re.compile(r"<source[^>]*>(.*?)</source>", re.DOTALL)
        match = pattern.search(xml)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags and entities from text."""
        if not text:
            return ""

        # Remove CDATA markers
        clean = re.sub(r"<!\[CDATA\[", "", text)
        clean = re.sub(r"\]\]>", "", clean)

        # Remove all HTML tags (including self-closing and with attributes)
        clean = re.sub(r"<[^>]*>", " ", clean)

        # Decode common HTML entities
        html_entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&apos;": "'",
            "&#x27;": "'",
            "&mdash;": "—",
            "&ndash;": "–",
            "&hellip;": "...",
            "&rsquo;": "'",
            "&lsquo;": "'",
            "&rdquo;": '"',
            "&ldquo;": '"',
            "&#8217;": "'",
            "&#8220;": '"',
            "&#8221;": '"',
        }
        for entity, char in html_entities.items():
            clean = clean.replace(entity, char)

        # Handle numeric HTML entities (&#123; or &#x7B;)
        clean = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), clean)
        clean = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), clean)

        # Remove any remaining HTML-like patterns
        clean = re.sub(r"&\w+;", "", clean)

        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean)

        return clean.strip()

    @staticmethod
    def _parse_pub_date(date_str: Optional[str]) -> Optional[str]:
        """Parse RSS pubDate format to ISO format."""
        if not date_str:
            return None

        try:
            # RSS date format: "Sat, 14 Dec 2024 10:30:00 GMT"
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.isoformat()
        except ValueError:
            try:
                # Try without timezone
                dt = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
                return dt.isoformat()
            except ValueError:
                return None

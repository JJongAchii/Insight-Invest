"""News service for fetching news from Google News RSS."""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import CATEGORY_LIMITS, CATEGORY_QUERIES, DOMAIN_TO_SOURCE, NewsCategory, NewsRegion
from .google_news_client import GoogleNewsClient

logger = logging.getLogger(__name__)


class NewsArticle:
    """Data class representing a news article."""

    def __init__(
        self,
        id: str,
        title: str,
        url: str,
        source: str,
        category: str,
        region: str,
        summary: Optional[str] = None,
        published_at: Optional[datetime] = None,
        image_url: Optional[str] = None,
        sentiment: Optional[str] = None,
    ) -> None:
        self.id = id
        self.title = title
        self.summary = summary
        self.url = url
        self.source = source
        self.published_at = published_at
        self.category = category
        self.region = region
        self.image_url = image_url
        self.sentiment = sentiment

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "category": self.category,
            "region": self.region,
            "image_url": self.image_url,
            "sentiment": self.sentiment,
        }


class NewsService:
    """
    Service for fetching news from Google News RSS.

    Uses Google News RSS feeds which are:
    - Free with no API limits
    - Always returns recent news
    - No API key required
    """

    # Region to Google News country/language mapping
    REGION_CONFIG = {
        NewsRegion.US: ("en", "US"),
        NewsRegion.ASIA: ("en", "US"),  # Use US feed for English Asia news
        NewsRegion.EUROPE: ("en", "GB"),  # UK for Europe English news
        NewsRegion.GLOBAL: ("en", "US"),
        NewsRegion.ALL: ("en", "US"),
    }

    def __init__(self) -> None:
        """Initialize news service with Google News client."""
        self.google_news = GoogleNewsClient()

    async def fetch_news(
        self,
        category: NewsCategory = NewsCategory.TOPNEWS,
        region: NewsRegion = NewsRegion.ALL,
        search_query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[NewsArticle]:
        """
        Fetch news from Google News RSS.

        Args:
            category: News category (recent shows top stories, others search by topic)
            region: Geographic region for news
            search_query: Optional custom search query
            limit: Maximum articles (defaults to category limit)

        Returns:
            List of NewsArticle sorted by published_at (newest first)
        """
        # Get default limit for category if not specified
        if limit is None:
            limit = CATEGORY_LIMITS.get(category, 5)

        # Get region config
        language, country = self.REGION_CONFIG.get(region, ("en", "US"))

        all_articles: List[NewsArticle] = []

        try:
            # Custom search query takes priority
            if search_query:
                results = await self.google_news.fetch_topic_news(
                    query=search_query,
                    limit=limit,
                    language=language,
                    country=country,
                )
            # TOPNEWS category: use top stories feed
            elif category == NewsCategory.TOPNEWS:
                results = await self.google_news.fetch_recent_news(
                    limit=limit,
                    language=language,
                    country=country,
                )
            # Other categories: search by topic
            else:
                query = CATEGORY_QUERIES.get(category)
                if query:
                    results = await self.google_news.fetch_topic_news(
                        query=query,
                        limit=limit,
                        language=language,
                        country=country,
                    )
                else:
                    results = []

            # Convert to NewsArticle objects
            for result in results:
                article = self._parse_result(result, category, region)
                if article:
                    all_articles.append(article)

            logger.info(f"Fetched {len(all_articles)} articles for {category.value}")

        except Exception as e:
            logger.error(f"Failed to fetch news: {e}", exc_info=True)

        # Sort by published_at (newest first)
        all_articles.sort(
            key=lambda x: (x.published_at or datetime.min),
            reverse=True,
        )

        return all_articles[:limit]

    def _parse_result(
        self,
        result: Dict[str, Any],
        category: NewsCategory,
        region: NewsRegion,
    ) -> Optional[NewsArticle]:
        """Parse Google News RSS result into NewsArticle."""
        try:
            url = result.get("url", "")
            title = result.get("title", "")

            if not url or not title:
                return None

            # Parse published date
            published_at = None
            pub_date_str = result.get("published_at")
            if pub_date_str:
                try:
                    published_at = datetime.fromisoformat(pub_date_str)
                except ValueError:
                    pass

            return NewsArticle(
                id=self._generate_id(url),
                title=title,
                summary=result.get("description"),
                url=url,
                source=result.get("source", self._extract_source_from_url(url)),
                published_at=published_at,
                category=category.value,
                region=region.value if region != NewsRegion.ALL else "global",
                image_url=None,  # Google News RSS doesn't provide images
                sentiment=None,
            )
        except Exception as e:
            logger.warning(f"Failed to parse result: {e}")
            return None

    @staticmethod
    def _generate_id(url: str) -> str:
        """Generate unique ID from URL using MD5 hash."""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    @staticmethod
    def _extract_source_from_url(url: str) -> str:
        """Extract source name from URL domain."""
        url_lower = url.lower()
        for domain, name in DOMAIN_TO_SOURCE.items():
            if domain in url_lower:
                return name
        return "News"

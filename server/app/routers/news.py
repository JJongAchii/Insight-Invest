"""News API router for fetching financial news from various sources."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
from app import schemas
from datastore import storage
from module.news.service import NewsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["News"])

# Simple in-memory cache with TTL
_cache: Dict[str, Tuple[List[dict], datetime]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cache_key(category: str, region: str, search_query: Optional[str]) -> str:
    """Generate cache key from parameters."""
    return f"{category}:{region}:{search_query or ''}"


def _is_cache_valid(timestamp: datetime) -> bool:
    """Check if cache entry is still valid."""
    return datetime.now() - timestamp < timedelta(seconds=CACHE_TTL_SECONDS)


@router.get("", response_model=schemas.NewsResponse)
async def get_news(
    category: schemas.NewsCategory = Query(
        default=schemas.NewsCategory.TOPNEWS, description="News category filter"
    ),
    region: schemas.NewsRegion = Query(default=schemas.NewsRegion.ALL, description="Region filter"),
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=50,
        description="Number of articles (default: 10 for recent, 5 for others)",
    ),
    search_query: Optional[str] = Query(default=None, description="Optional keyword search"),
) -> schemas.NewsResponse:
    """
    Fetch news articles from various sources.

    Results are cached for 5 minutes to improve performance and reduce API calls.

    Args:
        category: Filter by news category (market, economy, stocks, crypto, etc.)
        region: Filter by region (us, kr, global)
        limit: Maximum number of articles to return (1-50)
        search_query: Optional keyword to search for

    Returns:
        NewsResponse with list of articles and metadata
    """
    cache_key = _get_cache_key(category.value, region.value, search_query)

    # Check cache
    if cache_key in _cache:
        cached_data, timestamp = _cache[cache_key]
        if _is_cache_valid(timestamp):
            logger.info(f"Cache hit for key: {cache_key}")
            articles = [schemas.NewsArticle(**a) for a in cached_data[:limit]]
            return schemas.NewsResponse(
                articles=articles,
                total_count=len(cached_data),
                cached=True,
                fetched_at=timestamp,
            )

    # Cache miss - fetch from sources
    logger.info(f"Cache miss for key: {cache_key}, fetching from sources")

    try:
        news_service = NewsService()

        # Map schema enums to module enums
        from module.news.config import NewsCategory as ModuleNewsCategory
        from module.news.config import NewsRegion as ModuleNewsRegion

        module_category = ModuleNewsCategory(category.value)
        module_region = ModuleNewsRegion(region.value)

        articles = await news_service.fetch_news(
            category=module_category,
            region=module_region,
            search_query=search_query,
            limit=limit,  # Let service handle default limits (10 for topnews, 5 for others)
        )

        # Convert to dict for caching
        articles_dict = [a.to_dict() for a in articles]

        # Update cache
        fetch_time = datetime.now()
        _cache[cache_key] = (articles_dict, fetch_time)

        # Convert to response model
        response_articles = [schemas.NewsArticle(**a) for a in articles_dict]

        return schemas.NewsResponse(
            articles=response_articles,
            total_count=len(articles_dict),
            cached=False,
            fetched_at=fetch_time,
        )
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Failed to fetch news: {str(e)}")


@router.get("/sources", response_model=Dict[str, List[schemas.NewsSource]])
async def get_news_sources() -> Dict[str, List[schemas.NewsSource]]:
    """Get list of available news sources."""
    sources = [
        schemas.NewsSource(id="bloomberg", name="Bloomberg", region="global"),
        schemas.NewsSource(id="reuters", name="Reuters", region="global"),
        schemas.NewsSource(id="cnbc", name="CNBC", region="us"),
        schemas.NewsSource(id="yahoo_finance", name="Yahoo Finance", region="global"),
        schemas.NewsSource(id="google_news", name="Google News", region="global"),
        schemas.NewsSource(id="wsj", name="Wall Street Journal", region="us"),
        schemas.NewsSource(id="ft", name="Financial Times", region="global"),
    ]
    return {"sources": sources}


@router.delete("/cache")
async def clear_cache() -> Dict[str, str]:
    """
    Clear news cache (admin endpoint).

    Returns:
        Message confirming cache was cleared
    """
    global _cache
    cache_size = len(_cache)
    _cache = {}
    logger.info(f"Cache cleared: {cache_size} entries removed")
    return {"message": f"Cache cleared: {cache_size} entries removed"}


STALE_HOURS = 72  # 금 19시 발행분이 월 09시(62h)까지 주말 내내 유지되도록


@router.get("/briefing")
async def get_news_briefing() -> dict:
    """오늘의 중요 뉴스 (EC2 배치 발행분) — 실패·스테일은 {"active": False} 200 강등."""
    try:
        data = storage.read_json("news_briefing.json")
        as_of = datetime.fromisoformat(data["as_of"])
        now = datetime.now(as_of.tzinfo or timezone.utc)
        if now - as_of > timedelta(hours=STALE_HOURS):
            return {"active": False}
        return {"active": True, **data}
    except Exception as e:
        logger.warning(f"news briefing 강등: {e}")
        return {"active": False}

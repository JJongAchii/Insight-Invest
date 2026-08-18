"""News API router for fetching financial news from various sources."""

import logging
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
from app import schemas
from datastore import storage
from datastore import holdings as holdings_store
from datastore import meta as meta_store
from datastore import watchlist as watchlist_store
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

TOPIC_KEYWORDS = {
    "금리·통화정책": ("금리", "기준금리", "연준", "fed", "한국은행", "채권"),
    "환율": ("환율", "원·달러", "원달러", "달러", "엔화", "위안"),
    "반도체·AI": ("반도체", "메모리", "hbm", "ai", "인공지능", "칩"),
    "에너지·원자재": ("유가", "원유", "석유", "가스", "에너지", "금값", "원자재"),
    "무역·정책": ("관세", "수출", "수입", "무역", "규제", "정책"),
}


def _personal_relevance(data: dict) -> dict:
    """보유·관심 자산 및 거시 주제의 결정론적 문자열 매핑.

    감성·수익 예측이 아니며 제목/why에 명시적으로 등장한 경우만 붙인다.
    """
    payload = deepcopy(data)
    try:
        holdings = holdings_store.list_items()
        watchlist = watchlist_store.list_items()
        holding_ids = {int(value) for value in holdings.get("meta_id", [])}
        watch_ids = {int(value) for value in watchlist.get("meta_id", [])}
        ids = holding_ids | watch_ids
        md = meta_store.meta_df()
        assets = md[md["meta_id"].isin(ids)][["meta_id", "ticker", "name"]]
    except Exception:
        logger.debug("뉴스 개인 자산 매핑 준비 실패", exc_info=True)
        assets = []
        holding_ids, watch_ids = set(), set()

    for rows in payload.get("sections", {}).values():
        for item in rows:
            text = f"{item.get('title', '')} {item.get('why', '')}".lower()
            related = []
            for asset in getattr(assets, "itertuples", lambda: [])():
                name = str(asset.name or "").strip()
                ticker = str(asset.ticker or "").strip()
                name_hit = len(name) >= 2 and name.lower() in text
                ticker_hit = len(ticker) >= 2 and re.search(
                    rf"(?<![0-9a-z]){re.escape(ticker.lower())}(?![0-9a-z])", text
                )
                if name_hit or ticker_hit:
                    mid = int(asset.meta_id)
                    related.append({
                        "meta_id": mid,
                        "ticker": ticker,
                        "name": name,
                        "relation": "보유" if mid in holding_ids else "관심",
                    })
            item["related_assets"] = related
            item["related_topics"] = [
                topic for topic, words in TOPIC_KEYWORDS.items() if any(word in text for word in words)
            ]
    payload["relevance_method"] = "제목·요약의 종목명/티커 및 사전 정의 주제 키워드 일치"
    payload["relevance_warning"] = "관련성 표시는 인과관계나 가격 방향 예측이 아닙니다."
    return payload


@router.get("/briefing")
async def get_news_briefing() -> dict:
    """오늘의 중요 뉴스 (EC2 배치 발행분) — 실패·스테일은 {"active": False} 200 강등."""
    try:
        data = storage.read_json("news_briefing.json")
        as_of = datetime.fromisoformat(data["as_of"])
        now = datetime.now(as_of.tzinfo or timezone.utc)
        if now - as_of > timedelta(hours=STALE_HOURS):
            return {"active": False}
        return {"active": True, **_personal_relevance(data)}
    except Exception as e:
        logger.warning(f"news briefing 강등: {e}")
        return {"active": False}

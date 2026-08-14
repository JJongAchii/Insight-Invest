"""Configuration for news sources and categories."""

from enum import Enum


class NewsCategory(str, Enum):
    """News category filter options."""

    TOPNEWS = "topnews"  # Top news headlines (default)
    ECONOMY = "economy"  # World economy, macro
    POLICY = "policy"  # Central bank, Fed, interest rates
    TRADE = "trade"  # International trade, tariffs
    ENERGY = "energy"  # Oil, gas, energy markets
    TECH = "tech"  # Tech industry news


class NewsRegion(str, Enum):
    """News region filter options."""

    US = "us"
    ASIA = "asia"
    EUROPE = "europe"
    GLOBAL = "global"
    ALL = "all"
    KR = "kr"


# Allowed news sources (whitelist - source names from RSS)
ALLOWED_SOURCES = [
    "reuters",
    "bbc",
    "investing",
]

# Category to search query mapping for Google News
# Filtering to allowed sources is done in service.py
CATEGORY_QUERIES = {
    NewsCategory.TOPNEWS: None,  # Uses top stories feed
    NewsCategory.ECONOMY: "world economy market",
    NewsCategory.POLICY: "Federal Reserve interest rate central bank",
    NewsCategory.TRADE: "international trade tariffs",
    NewsCategory.ENERGY: "oil price energy OPEC",
    NewsCategory.TECH: "technology AI semiconductor",
}

# Default article limits by category
CATEGORY_LIMITS = {
    NewsCategory.TOPNEWS: 10,
    NewsCategory.ECONOMY: 10,
    NewsCategory.POLICY: 10,
    NewsCategory.TRADE: 10,
    NewsCategory.ENERGY: 10,
    NewsCategory.TECH: 10,
}

# Region-specific search terms
REGION_QUERIES = {
    NewsRegion.US: "US economy United States",
    NewsRegion.ASIA: "Asia economy China Japan Korea",
    NewsRegion.EUROPE: "Europe economy EU eurozone",
    NewsRegion.GLOBAL: "global economy world",
    NewsRegion.ALL: "",
    NewsRegion.KR: "한국 경제 시장",
}

# Domain to source name mapping
DOMAIN_TO_SOURCE = {
    "reuters.com": "Reuters",
    "cnbc.com": "CNBC",
    "yahoo.com": "Yahoo Finance",
    "finance.yahoo.com": "Yahoo Finance",
    "apnews.com": "AP News",
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "theguardian.com": "The Guardian",
    "aljazeera.com": "Al Jazeera",
    "investing.com": "Investing.com",
    "marketwatch.com": "MarketWatch",
    "koreaherald.com": "Korea Herald",
    "koreatimes.co.kr": "Korea Times",
    "en.yna.co.kr": "Yonhap News",
    "cnn.com": "CNN",
    "npr.org": "NPR",
    # 국내 언론사 (KR 라이브 헤드라인용)
    "yna.co.kr": "연합뉴스",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보",
    "donga.com": "동아일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "kbs.co.kr": "KBS",
    "imbc.com": "MBC",
    "sbs.co.kr": "SBS",
    "ytn.co.kr": "YTN",
    "mt.co.kr": "머니투데이",
    "sedaily.com": "서울경제",
    "einfomax.co.kr": "연합인포맥스",
}

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator

# ============================================
# News Schemas
# ============================================


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


class NewsArticle(BaseModel):
    """Individual news article."""

    id: str
    title: str
    summary: Optional[str] = None
    url: str
    source: str
    published_at: Optional[datetime] = None
    category: str
    region: str
    image_url: Optional[str] = None
    sentiment: Optional[str] = None

    class Config:
        from_attributes = True


class NewsResponse(BaseModel):
    """Response wrapper for news endpoint."""

    articles: List[NewsArticle]
    total_count: int
    cached: bool
    fetched_at: datetime


class NewsSource(BaseModel):
    """News source information."""

    id: str
    name: str
    region: str


class Meta(BaseModel):
    meta_id: int
    ticker: str
    name: Optional[str] = None
    isin: Optional[str] = None
    security_type: str
    asset_class: Optional[str] = None
    sector: Optional[str] = None
    iso_code: str
    marketcap: Optional[int] = None
    fee: Optional[float] = None
    remark: Optional[str] = None

    class Config:
        from_attributes = True


class Ticker(BaseModel):
    meta_id: int
    ticker: str
    name: Optional[str] = None
    iso_code: Optional[str] = None
    security_type: Optional[str] = None
    sector: Optional[str] = None

    class Config:
        from_attributes = True


class Strategy(BaseModel):
    strategy_id: int
    strategy: str
    strategy_name: str

    class Config:
        from_attributes = True


class Portfolio(BaseModel):
    port_id: int
    port_name: str
    strategy_name: str
    ann_ret: float
    ann_vol: float
    sharpe: float

    class Config:
        from_attributes = True


class PortNav(BaseModel):
    port_id: int
    trade_date: datetime
    value: float


class Price(BaseModel):
    meta_id: int
    trade_date: datetime
    close: Optional[float] = None
    adj_close: Optional[float] = None
    gross_return: Optional[float] = None

    @validator("trade_date", pre=True)
    def parse_trade_date(cls, value):
        if isinstance(value, date):  # Check if `value` is of type `date`
            return datetime(value.year, value.month, value.day)
        return value

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    strategy_name: str
    meta_id: List[int]
    algorithm: Optional[str]
    startDate: date
    endDate: date


class PortIdInfo(BaseModel):
    port_id: int
    port_name: str
    strategy_name: str
    ann_retr: float
    ann_vol: float
    sharpe: float
    mdd: float
    skew: float
    kurt: float
    var: float
    cvar: float

    class Config:
        from_attributes = True


# ============================================
# Portfolio Optimization Schemas
# ============================================


class OptimizationRequest(BaseModel):
    """Request for portfolio optimization."""

    meta_id: List[int] = Field(..., min_length=2, description="List of meta_ids to optimize")
    start_date: Optional[date] = Field(None, description="Start date for historical data")
    end_date: Optional[date] = Field(None, description="End date for historical data")
    lookback_period: int = Field(252, ge=60, le=1260, description="Days for return/cov estimation")
    risk_free_rate: float = Field(0.0, ge=0.0, le=0.2, description="Annual risk-free rate")
    min_weight: float = Field(0.0, ge=0.0, le=1.0, description="Minimum weight per asset")
    max_weight: float = Field(1.0, ge=0.0, le=1.0, description="Maximum weight per asset")
    n_points: int = Field(50, ge=10, le=200, description="Number of frontier points")


class OptimizedPortfolio(BaseModel):
    """Optimized portfolio result."""

    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_contributions: Dict[str, float]


class FrontierPoint(BaseModel):
    """Single point on the efficient frontier."""

    return_: float = Field(..., alias="return")
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]

    class Config:
        populate_by_name = True


class AssetStats(BaseModel):
    """Individual asset statistics."""

    expected_return: float
    volatility: float


class EfficientFrontierResponse(BaseModel):
    """Response for efficient frontier calculation."""

    frontier_points: List[FrontierPoint]
    max_sharpe: OptimizedPortfolio
    min_volatility: OptimizedPortfolio
    asset_stats: Dict[str, AssetStats]


class RiskParityResponse(BaseModel):
    """Response for risk parity calculation."""

    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_contributions: Dict[str, float]


# ============================================
# Stock Screener Schemas
# ============================================


class ScreenerSortField(str, Enum):
    """Fields available for sorting screener results."""

    RETURN_1M = "return_1m"
    RETURN_3M = "return_3m"
    RETURN_6M = "return_6m"
    RETURN_12M = "return_12m"
    RETURN_YTD = "return_ytd"
    VOLATILITY_1M = "volatility_1m"
    VOLATILITY_3M = "volatility_3m"
    MDD = "mdd"
    MDD_1Y = "mdd_1y"
    CURRENT_DRAWDOWN = "current_drawdown"
    PCT_FROM_HIGH = "pct_from_high"
    PCT_FROM_LOW = "pct_from_low"


class ScreenerRequest(BaseModel):
    """Request for stock screener."""

    iso_code: Optional[str] = Field(None, description="Filter by country (US, KR, or None for all)")

    # Momentum filters (percentage values, e.g., 10 means 10%)
    return_1m_min: Optional[float] = Field(None, description="Min 1-month return (%)")
    return_1m_max: Optional[float] = Field(None, description="Max 1-month return (%)")
    return_3m_min: Optional[float] = Field(None, description="Min 3-month return (%)")
    return_3m_max: Optional[float] = Field(None, description="Max 3-month return (%)")
    return_6m_min: Optional[float] = Field(None, description="Min 6-month return (%)")
    return_6m_max: Optional[float] = Field(None, description="Max 6-month return (%)")
    return_12m_min: Optional[float] = Field(None, description="Min 12-month return (%)")
    return_12m_max: Optional[float] = Field(None, description="Max 12-month return (%)")

    # Volatility filter
    volatility_min: Optional[float] = Field(None, description="Min volatility (%)")
    volatility_max: Optional[float] = Field(None, description="Max volatility (%)")

    # Drawdown filters (negative values, e.g., -20 means -20%)
    mdd_max: Optional[float] = Field(None, description="Max allowed MDD (%, negative)")
    current_drawdown_max: Optional[float] = Field(None, description="Max current drawdown (%)")

    # 52-week filters
    pct_from_high_min: Optional[float] = Field(None, description="Min % from 52-week high")
    pct_from_high_max: Optional[float] = Field(None, description="Max % from 52-week high")

    # Market cap filters (in USD, e.g., 1000000000 = $1B)
    marketcap_min: Optional[int] = Field(None, description="Min market cap (USD)")
    marketcap_max: Optional[int] = Field(None, description="Max market cap (USD)")

    # Sorting and pagination
    sort_by: ScreenerSortField = Field(ScreenerSortField.RETURN_3M, description="Sort field")
    ascending: bool = Field(False, description="Sort ascending (False = high to low)")
    limit: int = Field(100, ge=1, le=500, description="Max results")


class ScreenerStock(BaseModel):
    """Stock result from screener."""

    ticker: str
    meta_id: int
    name: Optional[str] = None
    sector: Optional[str] = None
    iso_code: Optional[str] = None
    marketcap: Optional[int] = None
    current_price: float
    return_1m: float
    return_3m: float
    return_6m: float
    return_12m: float
    return_ytd: float
    volatility_1m: float
    volatility_3m: float
    mdd: float
    mdd_1y: float
    current_drawdown: float
    high_52w: float
    low_52w: float
    pct_from_high: float
    pct_from_low: float


class ScreenerResponse(BaseModel):
    """Response for screener endpoint."""

    total_count: int
    filtered_count: int
    results: List[ScreenerStock]
    new_highs: List[ScreenerStock]
    new_lows: List[ScreenerStock]

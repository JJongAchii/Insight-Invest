"""
database models
"""

import logging

import sqlalchemy as sa

from .client import engine
from .mixins import Base, StaticBase

logger = logging.getLogger("sqlite")


def create_all() -> None:
    """drop all tables"""
    Base.metadata.create_all(bind=engine)


def drop_all() -> None:
    """drop all tables"""
    Base.metadata.drop_all(bind=engine)


class TbMeta(StaticBase):
    """meta data table"""

    __tablename__ = "tb_meta"

    meta_id = sa.Column(sa.Integer, sa.Identity(start=1), primary_key=True)
    ticker = sa.Column(sa.String(255), nullable=False)
    name = sa.Column(sa.String(1000), nullable=True)
    isin = sa.Column(sa.String(255), nullable=True)
    security_type = sa.Column(sa.String(255), nullable=False)
    asset_class = sa.Column(sa.String(255), nullable=True)
    sector = sa.Column(sa.String(255), nullable=True)
    iso_code = sa.Column(sa.String(255), nullable=False)
    marketcap = sa.Column(sa.BigInteger, nullable=True)
    fee = sa.Column(sa.Float, nullable=True)
    remark = sa.Column(sa.Text, nullable=True)
    min_date = sa.Column(sa.Date, nullable=True)
    max_date = sa.Column(sa.Date, nullable=True)
    # delisted_yn = sa.Column(sa.Boolean, nullable=False, server_default='false')


# NOTE: TbPrice가 Iceberg로 이관되어 삭제됨 (2025-12-14)
# - market.us_stocks_price (US 주식 가격)
# - market.kr_stocks_price (KR 주식 가격)
# 가격 데이터 조회는 module.data_lake.iceberg_client.read_price_data() 사용


class TbStrategy(StaticBase):
    """strategy table"""

    __tablename__ = "tb_strategy"

    strategy_id = sa.Column(sa.Integer, sa.Identity(start=1), primary_key=True)
    strategy = sa.Column(sa.String(255), nullable=False)
    strategy_name = sa.Column(sa.String(255), nullable=False)


class TbPortfolio(StaticBase):
    """custom portfolio table"""

    __tablename__ = "tb_portfolio"

    port_id = sa.Column(sa.Integer, sa.Identity(start=1), primary_key=True)
    port_name = sa.Column(sa.String(255), nullable=False, unique=True)
    strategy_id = sa.Column(sa.ForeignKey("tb_strategy.strategy_id"))


class TbUniverse(StaticBase):
    """portfolio universe table"""

    __tablename__ = "tb_universe"
    port_id = sa.Column(sa.ForeignKey("tb_portfolio.port_id"), primary_key=True)
    meta_id = sa.Column(sa.ForeignKey("tb_meta.meta_id"), primary_key=True)


# NOTE: TbRebalance, TbNav, TbMetrics가 Iceberg로 이관되어 삭제됨 (2025-12-14)
# - portfolio.portfolio_rebalance
# - portfolio.portfolio_nav
# - portfolio.portfolio_metrics


class TbScreenerIndicators(StaticBase):
    """Pre-calculated screener indicators for all stocks.

    Updated daily after market close via scheduled job.
    Enables instant screener queries without real-time calculation.
    """

    __tablename__ = "tb_screener_indicators"

    meta_id = sa.Column(sa.ForeignKey("tb_meta.meta_id"), primary_key=True)
    calculated_date = sa.Column(sa.Date, nullable=False)

    # Price info
    current_price = sa.Column(sa.Float, nullable=True)

    # Momentum (stored as decimal, e.g., 0.10 = 10%)
    return_1m = sa.Column(sa.Float, nullable=True)
    return_3m = sa.Column(sa.Float, nullable=True)
    return_6m = sa.Column(sa.Float, nullable=True)
    return_12m = sa.Column(sa.Float, nullable=True)
    return_ytd = sa.Column(sa.Float, nullable=True)

    # Volatility (annualized, stored as decimal)
    volatility_1m = sa.Column(sa.Float, nullable=True)
    volatility_3m = sa.Column(sa.Float, nullable=True)

    # Drawdown (stored as decimal, negative values)
    mdd = sa.Column(sa.Float, nullable=True)
    mdd_1y = sa.Column(sa.Float, nullable=True)
    current_drawdown = sa.Column(sa.Float, nullable=True)

    # 52-week analysis
    high_52w = sa.Column(sa.Float, nullable=True)
    low_52w = sa.Column(sa.Float, nullable=True)
    pct_from_high = sa.Column(sa.Float, nullable=True)  # negative
    pct_from_low = sa.Column(sa.Float, nullable=True)  # positive

    updated_at = sa.Column(sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())


class TbMacro(StaticBase):
    """macro economics definition"""

    __tablename__ = "tb_macro"
    macro_id = sa.Column(sa.Integer, sa.Identity(start=1), primary_key=True)
    fred = sa.Column(sa.String(255), nullable=True)
    description = sa.Column(sa.Text, nullable=True)


class TbMacroData(StaticBase):
    """macro economics data"""

    __tablename__ = "tb_macro_data"
    macro_id = sa.Column(sa.ForeignKey("tb_macro.macro_id"), primary_key=True)
    base_date = sa.Column(sa.Date, primary_key=True)
    value = sa.Column(sa.Float, nullable=True)

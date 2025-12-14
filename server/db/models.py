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


class TbPrice(StaticBase):
    """meta data price table"""

    __tablename__ = "tb_price"

    meta_id = sa.Column(sa.ForeignKey("tb_meta.meta_id"), primary_key=True)
    trade_date = sa.Column(sa.Date, primary_key=True)
    close = sa.Column(sa.Float, nullable=True)
    adj_close = sa.Column(sa.Float, nullable=True)
    gross_return = sa.Column(sa.Float, nullable=True)


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

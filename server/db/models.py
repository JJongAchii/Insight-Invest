"""
database models
"""
import logging
import sqlalchemy as sa
from .mixins import Base, StaticBase, TimeSeriesBase, Mixins
from .client import engine

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


class TbPrice(StaticBase):
    """meta data price table"""

    __tablename__ = "tb_price"
    
    meta_id = sa.Column(sa.ForeignKey("tb_meta.meta_id"), primary_key=True)
    trade_date = sa.Column(sa.Date, primary_key=True)
    close = sa.Column(sa.Float, nullable=True)
    adj_close = sa.Column(sa.Float, nullable=True)
    gross_return = sa.Column(sa.Float, nullable=True)

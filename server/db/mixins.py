import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import sqlalchemy as sa
from dateutil import parser
from sqlalchemy import Select, select
from sqlalchemy.orm import DeclarativeBase, Session

from .client import engine, session_local

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base class"""

    pass


def read_sql_select(stmt: Select, session: Session, **kwargs) -> pd.DataFrame:
    """Read SQL select statement into DataFrame (SQLAlchemy 2.0 style)

    Args:
        stmt: SQLAlchemy Select statement
        session: SQLAlchemy Session

    Returns:
        pd.DataFrame: Query result as DataFrame
    """
    return pd.read_sql_query(
        sql=stmt,
        con=session.connection(),
        index_col=kwargs.get("index_col", None),
        parse_dates=kwargs.get("parse_dates", None),
    )


class Mixins(Base):
    """mixins for models"""

    __abstract__ = True

    @classmethod
    def add(cls, **kwargs) -> None:
        """add an object"""
        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                session.add(cls(**kwargs))
                session.commit()
                return
        session.add(cls(**kwargs))

    @staticmethod
    def parse_datetime(table: sa.Table, records: List[Dict]) -> List[Dict]:
        mapped = {"datetime": [], "date": []}

        for column in table.__table__.columns:
            if isinstance(column.type, sa.Date):
                mapped["date"].append(column.name)
            elif isinstance(column.type, sa.DateTime):
                mapped["datetime"].append(column.name)
        for record in records:
            for dt in mapped["datetime"]:
                if dt in record:
                    record[dt] = parser.parse(str(record[dt]))
            for d in mapped["date"]:
                if d in record:
                    record[d] = parser.parse(str(record[d])).date()
        return records

    @classmethod
    def insert(cls, records: Union[List[Dict], pd.Series, pd.DataFrame], **kwargs) -> None:
        """insert bulk"""
        logger.debug(f"Starting insert into {cls.__tablename__}")
        if isinstance(records, pd.DataFrame):
            records = records.replace({np.nan: None}).to_dict("records")
        elif isinstance(records, pd.Series):
            records = [records.replace({np.nan: None}).to_dict()]
        elif isinstance(records, list):
            ...
        elif isinstance(records, dict):
            records = [records]
        else:
            raise TypeError(
                "insert only takes pd.Series or pd.DataFrame," + " but {type(records)} was given."
            )
        records = cls.parse_datetime(cls, records)
        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                session.bulk_insert_mappings(cls, records)
                session.commit()
                logger.info(f"Inserted {len(records)} records into {cls.__tablename__}")
                return
        session.bulk_insert_mappings(cls, records)
        session.flush()
        logger.info(f"Inserted {len(records)} records into {cls.__tablename__}")

    @classmethod
    def update(cls, records: Union[Dict, List[Dict], pd.Series, pd.DataFrame], **kwargs) -> None:
        """update bulk"""
        if isinstance(records, pd.DataFrame):
            records = records.replace({np.nan: None}).to_dict("records")
        elif isinstance(records, pd.Series):
            records = [records.replace({np.nan: None}).to_dict()]
        else:
            raise TypeError(
                "update only takes pd.Series or pd.DataFrame," + " but {type(records)} was given."
            )
        records = cls.parse_datetime(cls, records)

        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                session.bulk_update_mappings(cls, records)
                session.commit()
                logger.info(f"Updated {len(records)} records in {cls.__tablename__}")
                return
        session.bulk_update_mappings(cls, records)
        session.flush()
        logger.info(f"Updated {len(records)} records in {cls.__tablename__}")

    @classmethod
    def from_dict(cls, data: Dict):
        """instance construct from dict"""
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert database table row to dictionary."""
        mapper = sa.inspect(self.__class__)
        return {
            column.key: (
                getattr(self, column.key).isoformat()
                if isinstance(getattr(self, column.key), (date, datetime))
                else getattr(self, column.key)
            )
            for column in mapper.columns
        }

    @classmethod
    def query(cls, **kwargs) -> List[Any]:
        """Query records using SQLAlchemy 2.0 style

        Args:
            **kwargs: Filter conditions

        Returns:
            List of model instances
        """
        session = kwargs.pop("session", None)
        stmt = select(cls).filter_by(**kwargs)
        if session is None:
            with session_local() as session:
                return list(session.execute(stmt).scalars().all())
        return list(session.execute(stmt).scalars().all())

    @classmethod
    def query_df(cls, **kwargs) -> pd.DataFrame:
        """Query table and return as DataFrame (SQLAlchemy 2.0 style)"""
        read_kwargs = {
            "index_col": kwargs.pop("index_col", None),
            "parse_dates": kwargs.pop("parse_dates", None),
        }
        stmt = select(cls).filter_by(**kwargs)
        with session_local() as session:
            return read_sql_select(stmt, session, **read_kwargs)

    @classmethod
    def delete(cls, **kwargs) -> None:
        """Delete records using SQLAlchemy 2.0 style"""
        stmt = sa.delete(cls).filter_by(**kwargs)
        with session_local() as session:
            session.execute(stmt)
            session.commit()


class StaticBase(Mixins):
    """abstract static mixins"""

    __abstract__ = True
    created_date = sa.Column(
        sa.DateTime,
        default=sa.func.now(),
        server_default=sa.func.now(),
        nullable=False,
        comment="Last Modified Datetime.",
        doc="Last Modified Datetime.",
    )
    last_modified_date = sa.Column(
        sa.DateTime,
        default=sa.func.now(),
        onupdate=sa.func.now(),
        server_default=sa.func.now(),
        server_onupdate=sa.func.now(),
        nullable=False,
        comment="Last Modified Datetime.",
        doc="Last Modified Datetime.",
    )


class TimeSeriesBase(Mixins):
    """abstract timeseries mixins"""

    __abstract__ = True

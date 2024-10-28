import logging
from datetime import date, datetime
from dateutil import parser
from typing import Union, Dict, List
from sqlalchemy.orm import Query
import numpy as np
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from .client import session_local


Base = declarative_base()

logger = logging.getLogger("sqlite")


def read_sql_query(query: Query, **kwargs) -> pd.DataFrame:
    """Read sql query

    Args:
        query (Query): sqlalchemy.Query

    Returns:
        pd.DataFrame: read the query into dataframe.
    """
    return pd.read_sql_query(
        sql=query.statement,
        con=query.session.bind,
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
    def insert(
        cls, records: Union[List[Dict], pd.Series, pd.DataFrame], **kwargs
    ) -> None:
        """insert bulk"""
        print("start insert.")
        if isinstance(records, pd.DataFrame):
            records = records.replace({np.NaN: None}).to_dict("records")
        elif isinstance(records, pd.Series):
            records = [records.replace({np.NaN: None}).to_dict()]
        elif isinstance(records, list):
            ...
        elif isinstance(records, dict):
            records = [records]
        else:
            raise TypeError(
                "insert only takes pd.Series or pd.DataFrame,"
                + " but {type(records)} was given."
            )
        records = cls.parse_datetime(cls, records)
        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                session.bulk_insert_mappings(cls, records)
                session.commit()
                print(
                    f"insert into {cls.__tablename__}: {len(records)} records complete."
                )
                return
        session.bulk_insert_mappings(cls, records)
        session.flush()
        print(f"insert into {cls.__tablename__}: {len(records)} records complete.")

    @classmethod
    def update(
        cls, records: Union[Dict, List[Dict], pd.Series, pd.DataFrame], **kwargs
    ) -> None:
        """insert bulk"""

        if isinstance(records, pd.DataFrame):
            records = records.replace({np.NaN: None}).to_dict("records")
        elif isinstance(records, pd.Series):
            records = [records.replace({np.NaN: None}).to_dict()]
        else:
            raise TypeError(
                "insert only takes pd.Series or pd.DataFrame,"
                + " but {type(records)} was given."
            )
        records = cls.parse_datetime(cls, records)

        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                session.bulk_update_mappings(cls, records)
                session.commit()
                print(
                    f"update into {cls.__tablename__}: {len(records)} records complete."
                )
                return
        session.bulk_update_mappings(cls, records)
        session.flush()
        print(f"update into {cls.__tablename__}: {len(records)} records complete.")

    @classmethod
    def from_dict(cls, data: Dict):
        """instance construct from dict"""
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert database table row to dictionary."""
        mapper = sa.inspect(self.__class__)
        return {
            column.key: getattr(self, column.key).isoformat()
            if isinstance(getattr(self, column.key), (date, datetime))
            else getattr(self, column.key)
            for column in mapper.columns
        }

    @classmethod
    def query(cls, **kwargs) -> Query:
        """make a query"""
        session = kwargs.pop("session", None)
        if session is None:
            with session_local() as session:
                return session.query(cls).filter_by(**kwargs)
        return session.query(cls).filter_by(**kwargs)

    @classmethod
    def query_df(cls, **kwargs) -> pd.DataFrame:
        """query table with dataframe"""
        read_kwargs = {
            "index_col": kwargs.pop("index_col", None),
            "parse_dates": kwargs.pop("parse_dates", None),
        }
        return read_sql_query(cls.query(**kwargs), **read_kwargs)

    @classmethod
    def delete(cls, **kwargs) -> None:
        """delete recrods"""
        with session_local() as session:
            session.query(cls).filter_by(**kwargs).delete()
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

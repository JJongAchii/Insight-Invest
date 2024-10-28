from functools import lru_cache
from typing import Optional, Union, List
from dateutil import parser
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.orm import Query
from .client import engine, session_local
from .models import (
    TbMeta
)


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


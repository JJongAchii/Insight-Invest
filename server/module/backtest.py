import logging
import os
import sys
from datetime import date
from typing import List, Optional, Union

import pandas as pd
import polars as pl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
import db
from module.data_lake.iceberg_client import iceberg_client
from module.strategy import DualMomentum, EqualWeight
from module.util import backtest_result

logger = logging.getLogger(__name__)


class Backtest:
    def __init__(
        self,
        strategy_name: str = None,
    ) -> None:

        self.strategy_name = strategy_name

    def universe(self, tickers: Union[str, List] = None):

        return tickers

    def _get_iso_codes_and_meta_ids(
        self, meta_id: Optional[List[int]] = None, tickers: Optional[List[str]] = None
    ) -> dict:
        """
        meta_id 또는 tickers로 iso_code 조회 (SQLAlchemy 2.0 style)

        Returns:
            {"US": [meta_ids], "KR": [meta_ids], "tickers": {meta_id: ticker}}
        """
        from sqlalchemy import select

        with db.session_local() as session:
            stmt = select(
                db.TbMeta.meta_id,
                db.TbMeta.ticker,
                db.TbMeta.iso_code,
            )
            if meta_id:
                stmt = stmt.where(db.TbMeta.meta_id.in_(meta_id))
            if tickers:
                stmt = stmt.where(db.TbMeta.ticker.in_(tickers))

            results = session.execute(stmt).all()

        # iso_code별로 분류
        result = {"US": [], "KR": [], "tickers": {}}
        for row in results:
            if row.iso_code == "US":
                result["US"].append(row.meta_id)
            elif row.iso_code == "KR":
                result["KR"].append(row.meta_id)
            result["tickers"][row.meta_id] = row.ticker

        return result

    def data(
        self,
        meta_id: Union[int, List] = None,
        tickers: Union[str, List] = None,
        source: str = "iceberg",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        가격 데이터 조회

        Args:
            meta_id: 조회할 meta_id (단일 또는 리스트)
            tickers: 조회할 ticker (단일 또는 리스트)
            source: 데이터 소스 ("iceberg" 권장, "db"는 레거시)
            start_date: 조회 시작 날짜 (선택)
            end_date: 조회 종료 날짜 (선택)

        Returns:
            DataFrame with trade_date index and ticker columns, adj_close values
        """
        # 파라미터 정규화
        if meta_id and isinstance(meta_id, int):
            meta_id = [meta_id]
        if tickers and isinstance(tickers, str):
            tickers = [tickers]

        if source == "iceberg":
            # iso_code별 meta_id 조회
            iso_info = self._get_iso_codes_and_meta_ids(meta_id, tickers)

            all_data = []

            # US 데이터 조회
            if iso_info["US"]:
                us_df = iceberg_client.read_price_data(
                    iso_code="US",
                    meta_ids=iso_info["US"],
                    start_date=start_date,
                    end_date=end_date,
                )
                if not us_df.empty:
                    all_data.append(us_df)

            # KR 데이터 조회
            if iso_info["KR"]:
                kr_df = iceberg_client.read_price_data(
                    iso_code="KR",
                    meta_ids=iso_info["KR"],
                    start_date=start_date,
                    end_date=end_date,
                )
                if not kr_df.empty:
                    all_data.append(kr_df)

            if not all_data:
                logger.warning("Iceberg에서 가격 데이터를 찾을 수 없습니다")
                return pd.DataFrame()

            # 병합 - Polars 사용으로 성능 향상
            combined_df = pd.concat(all_data, ignore_index=True)

            # pivot using Polars for better performance
            pl_df = pl.from_pandas(combined_df[["trade_date", "ticker", "adj_close"]])
            pivot_df = pl_df.pivot(on="ticker", index="trade_date", values="adj_close")

            # Convert back to pandas with proper index
            data = pivot_df.to_pandas()
            data = data.set_index("trade_date")
            data.index = pd.to_datetime(data.index)
            data = data.sort_index()

            logger.info(f"Iceberg 가격 데이터 로드: {len(data)} rows, {len(data.columns)} tickers")
            return data

        else:
            raise ValueError(
                f"Unknown source: {source}. "
                "TbPrice MySQL 테이블은 Iceberg로 이관되어 제거되었습니다. "
                "source='iceberg'를 사용하세요."
            )

    def rebalance(
        self,
        price: pd.DataFrame,
        method: str = "eq",
        freq: str = "M",
        custom_weight: dict = None,
        offensive: List = None,
        defensive: List = None,
        start: ... = None,
        end: ... = None,
    ) -> pd.DataFrame:
        """_summary_

        Args:
            method (str, optional): _description_. Defaults to "eq".
            freq (str, optional): _description_. Defaults to "M".
            weight (dict, optional):
                using when method == "custom"
                ex) weight={"SPY": 0.6, "IEF":0.4}. Defaults to None.
        Returns:
            pd.DataFrame: _description_
        """

        price = price.loc[start:end].dropna()

        if method == "eq":
            """equal weights all assets"""
            weights = EqualWeight().simulate(price=price)

        if method == "dual_mmt":
            weights = DualMomentum().simulate(price=price)

        return weights

    def result(
        self,
        price: pd.DataFrame,
        weight: pd.DataFrame,
        start: ... = None,
        end: ... = None,
    ) -> pd.DataFrame:

        weight, nav, metrics = backtest_result(
            weight=weight,
            price=price,
            strategy_name=self.strategy_name,
            start_date=start,
            end_date=end,
        )

        merge = pd.concat(nav.values(), axis=1)
        merge.columns = nav.keys()
        nav = merge.ffill()

        mg_metrics = pd.concat(metrics.values(), axis=1)
        mg_metrics.columns = metrics.keys()
        mg_metrics = mg_metrics.T.reset_index().rename(columns={"index": "strategy"})

        return weight, nav, mg_metrics

    def delete_backtest_result(self, strategy_name: str):

        backtest_result.delete_strategy(strategy_name)

    def clear_backtest_result(self):

        backtest_result.clear_strategies()

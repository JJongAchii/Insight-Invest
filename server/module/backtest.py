import logging
import os
import sys
from datetime import date
from typing import List, Optional, Union

import pandas as pd
import polars as pl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../..")))
import datastore
from module.strategy import EqualWeight, FixedWeight, Momentum
from module.util import backtest_result

logger = logging.getLogger(__name__)

US_RETURN_BASIS = "split_adjusted_total_return_including_cash_distributions"


class BacktestDataContractError(ValueError):
    """가격 커버리지나 수익률 기준 계약을 충족하지 못한 백테스트 입력."""


class ReturnBasisMismatchError(BacktestDataContractError):
    """서로 다른 수익률 기준을 한 포트폴리오로 조용히 합치려 할 때 발생한다."""


class MissingPriceCoverageError(BacktestDataContractError):
    """요청한 자산 중 가격 패널에서 사라진 자산이 있을 때 발생한다."""


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
        meta_id 또는 tickers로 iso_code 조회 (통합 asset_master.parquet)

        Returns:
            {"US": [meta_ids], "KR": [meta_ids], "tickers": {meta_id: ticker}}
        """
        mapping = datastore.meta.resolve(meta_ids=meta_id, tickers=tickers)

        if meta_id is not None:
            requested_ids = {int(value) for value in meta_id}
            resolved_ids = set(mapping["meta_id"].astype(int))
            missing_ids = sorted(requested_ids - resolved_ids)
            if missing_ids:
                raise MissingPriceCoverageError(
                    "종목 마스터에 없는 meta_id가 있어 백테스트를 중단했습니다: "
                    + ", ".join(map(str, missing_ids))
                )
        if tickers is not None:
            requested_symbols = {str(value) for value in tickers}
            resolved_symbols = set(mapping["ticker"].astype(str))
            missing_symbols = sorted(requested_symbols - resolved_symbols)
            if missing_symbols:
                raise MissingPriceCoverageError(
                    "종목 마스터에 없는 ticker가 있어 백테스트를 중단했습니다: "
                    + ", ".join(missing_symbols)
                )

        result = {"US": [], "KR": [], "tickers": {}}
        for row in mapping.itertuples():
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
                us_df = datastore.read_price_data(
                    iso_code="US",
                    meta_ids=iso_info["US"],
                    start_date=start_date,
                    end_date=end_date,
                )
                if not us_df.empty:
                    us_df = us_df.copy()
                    us_df["return_basis"] = US_RETURN_BASIS
                    all_data.append(us_df)

            # KR 데이터 조회
            if iso_info["KR"]:
                kr_df = datastore.read_price_data(
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
            requested_tickers = set(iso_info["tickers"].values())
            found_tickers = set(combined_df["ticker"].astype(str))
            missing_tickers = sorted(requested_tickers - found_tickers)
            if missing_tickers:
                raise MissingPriceCoverageError(
                    "요청 자산의 가격 이력이 없어 백테스트를 중단했습니다: "
                    + ", ".join(missing_tickers)
                )
            if (
                "return_basis" not in combined_df.columns
                or combined_df["return_basis"].isna().any()
            ):
                raise ReturnBasisMismatchError(
                    "가격 수익률 기준이 명시되지 않은 자산이 있어 백테스트를 중단했습니다."
                )
            return_bases = sorted(set(combined_df["return_basis"].astype(str)))
            if len(return_bases) != 1:
                raise ReturnBasisMismatchError(
                    "서로 다른 수익률 기준을 한 백테스트에서 혼합할 수 없습니다: "
                    + ", ".join(return_bases)
                )

            # pivot using Polars for better performance
            pl_df = pl.from_pandas(combined_df[["trade_date", "ticker", "adj_close"]])
            pivot_df = pl_df.pivot(on="ticker", index="trade_date", values="adj_close")

            # Convert back to pandas with proper index
            data = pivot_df.to_pandas()
            data = data.set_index("trade_date")
            data.index = pd.to_datetime(data.index)
            data = data.sort_index()
            data.attrs["return_basis"] = return_bases[0]
            data.attrs["price_field"] = "adj_close"

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
        params: dict = None,
        offensive: List = None,
        defensive: List = None,
        start: ... = None,
        end: ... = None,
    ) -> pd.DataFrame:
        """리밸런싱 목표 비중 산출.

        Args:
            method: "eq" | "momentum" | "dual_mmt" | "custom"
            freq: 리밸런스 주기 "M" | "Q" | "Y"
            custom_weight: method == "custom"일 때 사용.
                ex) custom_weight={"SPY": 0.6, "IEF": 0.4}
            params: method == "momentum"일 때 {top_n, lookback_months}
        Returns:
            pd.DataFrame: index=rebal_date, columns=tickers
        """

        price = price.loc[start:end].dropna()

        if method == "eq":
            return EqualWeight().simulate(price=price, freq=freq)

        if method == "momentum":
            p = params or {}
            return Momentum(
                top_n=int(p.get("top_n", 4)),
                lookback_months=int(p.get("lookback_months", 12)),
            ).simulate(price=price, freq=freq)

        if method == "dual_mmt":
            return Momentum(top_n=4, lookback_months=12).simulate(price=price, freq=freq)

        if method == "custom":
            if not custom_weight:
                raise ValueError("custom method requires custom_weight, ex) {'SPY': 0.6}")
            return FixedWeight(custom_weight).simulate(price=price, freq=freq)

        raise ValueError(f"unknown method: {method}")

    def result(
        self,
        price: pd.DataFrame,
        weight: pd.DataFrame,
        start: ... = None,
        end: ... = None,
        cost_bps: float = 0.0,
    ):
        """엔진 실행 — 이 전략 하나의 결과만 반환 (누적 딕셔너리 없음).

        Returns:
            book: 보유 비중 long form (index Date)
            nav: 전략명 컬럼 하나짜리 NAV DataFrame
            metrics: strategy 컬럼 + 지표 컬럼의 1행 DataFrame
        """
        name = self.strategy_name or "strategy"

        book, nav_series, metric_series = backtest_result(
            weight=weight,
            price=price,
            start_date=start,
            end_date=end,
            cost_bps=cost_bps,
        )

        nav = nav_series.to_frame(name=name)

        metrics = metric_series.to_frame(name=name).T.reset_index()
        metrics = metrics.rename(columns={"index": "strategy"})

        return book, nav, metrics

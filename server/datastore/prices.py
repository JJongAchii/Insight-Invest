"""가격 조회 — iceberg_client.read_price_data의 drop-in 대체.

소스 우선순위:
- KR: qdata KRX 패널 (전 종목, 상폐 포함, 매일 갱신) — chg_pct가 곧 수정 수익률
- US: qdata 레이크(ETF 등 등록 종목, 매일 갱신) 우선,
      없으면 us_prices.parquet (1993~2025-12 개별주 아카이브, 정지 상태)

반환 스키마는 기존과 동일: [meta_id, trade_date, ticker, adj_close, gross_return]
"""

import logging
from datetime import date
from functools import lru_cache

import pandas as pd
from qdata import api as qdata_api

from datastore import meta, storage

logger = logging.getLogger(__name__)

US_ARCHIVE = "us_prices.parquet"


@lru_cache(maxsize=1)
def _qdata_us_tickers() -> frozenset:
    """qdata 레이크(prices.parquet)에 있는 US 티커 — 신선한 소스 우선 판단용."""
    try:
        cov = qdata_api.coverage()
        return frozenset(cov[cov["source"] == "yfinance"].index)
    except FileNotFoundError:
        return frozenset()


def _date_filters(start_date: date | None, end_date: date | None) -> list:
    filters = []
    if start_date:
        filters.append(("trade_date", ">=", pd.Timestamp(start_date)))
    if end_date:
        filters.append(("trade_date", "<=", pd.Timestamp(end_date)))
    return filters


def _kr_prices(mapping: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    df = qdata_api.load_krx_prices(
        start=str(start_date) if start_date else None,
        end=str(end_date) if end_date else None,
        tickers=mapping["ticker"].tolist(),
        columns=["adj_close", "chg_pct"],
    )
    if df.empty:
        return pd.DataFrame()
    out = df.rename(columns={"date": "trade_date"})
    out["gross_return"] = out["chg_pct"] / 100.0
    out = out.merge(mapping[["meta_id", "ticker"]], on="ticker", how="inner")
    return out[["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]]


def _us_fresh_prices(mapping: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """qdata 레이크의 US 종목 (수정종가 최신, gross_return은 파생)."""
    wide = qdata_api.load_prices(
        tickers=mapping["ticker"].tolist(),
        start=str(start_date) if start_date else None,
        end=str(end_date) if end_date else None,
        fields=("adj_close",),
    )["adj_close"]
    long = wide.stack().rename("adj_close").reset_index()
    long.columns = ["trade_date", "ticker", "adj_close"]
    long = long.sort_values(["ticker", "trade_date"])
    long["gross_return"] = long.groupby("ticker")["adj_close"].pct_change()
    return long.merge(mapping[["meta_id", "ticker"]], on="ticker", how="inner")[
        ["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]
    ]


def _us_archive_prices(mapping: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """1993~2025-12 US 개별주 아카이브 (meta_id 키, 컬럼 그대로 보존됨)."""
    filters = [("meta_id", "in", mapping["meta_id"].tolist()), *_date_filters(start_date, end_date)]
    df = storage.read_parquet(
        US_ARCHIVE,
        columns=["meta_id", "trade_date", "ticker", "adj_close", "gross_return"],
        filters=filters,
    )
    return df


def read_price_data(
    iso_code: str,
    meta_ids: list[int] | None = None,
    tickers: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """기존 iceberg_client.read_price_data와 동일 계약.

    Returns: DataFrame [meta_id, trade_date, ticker, adj_close, gross_return]
    """
    mapping = meta.resolve(meta_ids=meta_ids, tickers=tickers)
    mapping = mapping[mapping["iso_code"] == iso_code]
    if mapping.empty:
        return pd.DataFrame()

    try:
        if iso_code == "KR":
            out = _kr_prices(mapping, start_date, end_date)
        else:
            fresh_set = _qdata_us_tickers()
            fresh = mapping[mapping["ticker"].isin(fresh_set)]
            stale = mapping[~mapping["ticker"].isin(fresh_set)]
            frames = []
            if not fresh.empty:
                frames.append(_us_fresh_prices(fresh, start_date, end_date))
            if not stale.empty:
                frames.append(_us_archive_prices(stale, start_date, end_date))
            out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    except FileNotFoundError as e:
        logger.error(f"가격 소스 없음: {e}")
        return pd.DataFrame()

    if out.empty:
        return out
    out["trade_date"] = pd.to_datetime(out["trade_date"])
    return out.sort_values(["ticker", "trade_date"]).reset_index(drop=True)

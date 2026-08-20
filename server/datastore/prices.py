"""가격 조회 — iceberg_client.read_price_data의 drop-in 대체.

소스 우선순위:
- KR: qdata KRX 패널 (전 종목, 상폐 포함, 매일 갱신) — chg_pct가 곧 수정 수익률
- US: 배치가 massive 미러에서 재생성하는 앱 us_prices.parquet (총수익 계열, 매일 갱신)

기존 ``adj_close`` 소비자는 유지하되 신규 소비자는 ``series_value``를 사용한다.
KR ETF는 KRX 기준가격 수정 계열과 raw fallback을 ``return_basis``로 구분하며,
현금 이벤트를 직접 합성한 total return으로 오인하지 않게 한다.
"""

import logging
from datetime import date

import pandas as pd
from qdata import api as qdata_api

from datastore import meta, storage

logger = logging.getLogger(__name__)

US_ARCHIVE = "us_prices.parquet"


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
        columns=["close", "adj_close", "chg_pct"],
    )
    if df.empty:
        return pd.DataFrame()
    out = df.rename(columns={"date": "trade_date"})
    out["gross_return"] = out["chg_pct"] / 100.0
    out["series_value"] = out["adj_close"]
    out["return_basis"] = "split_adjusted_price_return_ex_cash_distributions"
    out = out.merge(mapping[["meta_id", "ticker"]], on="ticker", how="inner")
    return out[
        [
            "meta_id",
            "trade_date",
            "ticker",
            "close",
            "adj_close",
            "series_value",
            "gross_return",
            "return_basis",
        ]
    ]


def _kr_etf_prices(mapping: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """qdata KRX ETF 가격 패널.

    신규 qdata에서는 KRX ``FLUC_RT`` 기반 adj_close를 우선 사용한다. 이 계열은
    분배락 기준가격을 반영하지만 현금 이벤트를 직접 합성한 총수익은 아니다.
    구 clean 파일처럼 수정 열이 없거나 NaN이면 해당 행만 raw close로 fail-closed
    폴백하며 basis에 그대로 드러낸다.
    """
    df = qdata_api.load_krx_etf_prices(
        start=str(start_date) if start_date else None,
        end=str(end_date) if end_date else None,
        tickers=mapping["ticker"].tolist(),
    )
    if df.empty:
        return pd.DataFrame()
    out = df.rename(columns={"date": "trade_date"}).copy()
    out = out.sort_values(["ticker", "trade_date"])
    raw_return = out.groupby("ticker")["close"].pct_change(fill_method=None)
    has_adjusted = (
        out.get("adj_close", pd.Series(index=out.index, dtype="float64")).notna()
        & out.get("chg_pct", pd.Series(index=out.index, dtype="float64")).notna()
    )
    if "adj_close" not in out.columns:
        out["adj_close"] = out["close"]  # deprecated compatibility alias
    out["series_value"] = out["adj_close"].where(has_adjusted, out["close"]).astype("float64")
    source_return = out.get("chg_pct", pd.Series(index=out.index, dtype="float64")) / 100.0
    out["gross_return"] = source_return.where(has_adjusted, raw_return)
    out["return_basis"] = "raw_price_return_ex_cash_distributions"
    out.loc[has_adjusted, "return_basis"] = "krx_reference_price_adjusted_return"
    return out.merge(mapping[["meta_id", "ticker"]], on="ticker", how="inner")[
        [
            "meta_id",
            "trade_date",
            "ticker",
            "close",
            "adj_close",
            "series_value",
            "gross_return",
            "return_basis",
        ]
    ]


def _us_prices(mapping: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """앱 us_prices.parquet (meta_id 키, 컬럼 그대로 보존됨)."""
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

    Returns: 기존 5개 열. KR 경로는 전환 기간 동안 ``close``, ``series_value``,
    ``return_basis``를 추가로 제공하며 기존 열은 유지한다.
    """
    mapping = meta.resolve(meta_ids=meta_ids, tickers=tickers)
    mapping = mapping[mapping["iso_code"] == iso_code]
    if mapping.empty:
        return pd.DataFrame()

    try:
        if iso_code == "KR":
            is_etf = mapping["security_type"].astype(str).str.upper().eq("ETF")
            etf = mapping[is_etf]
            stock = mapping[~is_etf]
            frames = []
            if not stock.empty:
                frames.append(_kr_prices(stock, start_date, end_date))
            if not etf.empty:
                frames.append(_kr_etf_prices(etf, start_date, end_date))
            frames = [f for f in frames if not f.empty]
            out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        else:
            out = _us_prices(mapping, start_date, end_date)
    except FileNotFoundError as e:
        logger.error(f"가격 소스 없음: {e}")
        return pd.DataFrame()

    if out.empty:
        return out
    out["trade_date"] = pd.to_datetime(out["trade_date"])
    return out.sort_values(["ticker", "trade_date"]).reset_index(drop=True)


def us_adj_close_wide(
    tickers: list[str], start_date: date | None = None, end_date: date | None = None
) -> pd.DataFrame:
    """US adj_close(총수익 계열) wide — datetime 인덱스 × 티커 컬럼."""
    df = read_price_data("US", tickers=tickers, start_date=start_date, end_date=end_date)
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="trade_date", columns="ticker", values="adj_close").sort_index()

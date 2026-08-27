"""
Price data router for stock search features.

Provides endpoints for:
- Price history for individual stocks
- Summary statistics (YTD, 1Y return, volatility, etc.)
- Sparkline data for table view
- Comparison data for multiple stocks
"""

import logging
import math
from datetime import date, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

import datastore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price", tags=["Price"])

KRX_RATIO_TOLERANCE = 0.011


def _series_contract(meta_row: pd.Series, return_basis: Optional[str] = None) -> Dict:
    """차트·성과 숫자가 실제로 무엇을 포함하는지 명시하는 표시 계약."""
    iso_code = str(meta_row.get("iso_code", ""))
    security_type = str(meta_row.get("security_type", "")).upper()
    if iso_code == "US":
        return {
            "series_type": "total_return_index",
            "label": "Total Return",
            "return_basis": "split_adjusted_total_return_including_cash_distributions",
            "capital_actions": "included",
            "cash_distributions": "included",
            "calculation_version": "us_total_return_v1",
            "warning": None,
        }
    if security_type == "ETF":
        if return_basis == "krx_reference_price_adjusted_return":
            return {
                "series_type": "krx_reference_price_adjusted",
                "label": "KRX Adjusted Price",
                "return_basis": return_basis,
                "capital_actions": "included_from_krx_reference_price",
                "cash_distributions": "implicit_in_reference_price",
                "calculation_version": "kr_etf_reference_price_v1",
                "warning": "KRX 분배락 기준가격은 반영하지만 현금 분배 이벤트를 직접 합성한 Total Return은 아닙니다.",
            }
        return {
            "series_type": "raw_close",
            "label": "Raw Price",
            "return_basis": "raw_price_return_ex_cash_distributions",
            "capital_actions": "unverified",
            "cash_distributions": "excluded",
            "calculation_version": "kr_etf_raw_price_v1",
            "warning": "KR ETF는 현재 원종가 기준이며 분배금과 자본행동 조정은 포함하지 않습니다.",
        }
    return {
        "series_type": "split_adjusted_price",
        "label": "Adjusted Price",
        "return_basis": "split_adjusted_price_return_ex_cash_distributions",
        "capital_actions": "included_from_krx_reference_price",
        "cash_distributions": "excluded",
        "calculation_version": "kr_price_return_v1",
        "warning": "현금배당은 포함하지 않은 가격수익률입니다.",
    }


def _calculate_metrics(prices: pd.Series) -> Dict[str, Optional[float]]:
    """
    Calculate performance metrics from price series.

    Args:
        prices: Series of adjusted close prices indexed by date

    Returns:
        Dictionary with calculated metrics
    """
    if prices.empty or len(prices) < 2:
        return {
            "ytd_return": None,
            "return_1y": None,
            "return_3m": None,
            "volatility": None,
            "sharpe": None,
            "mdd": None,
        }

    # Ensure index is datetime for proper comparison
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    returns = prices.pct_change().dropna()

    # Calculate returns
    latest_price = prices.iloc[-1]
    today = prices.index[-1]

    # YTD return
    ytd_start = pd.Timestamp(date(today.year, 1, 1))
    ytd_prices = prices[prices.index >= ytd_start]
    ytd_return = (latest_price / ytd_prices.iloc[0] - 1) if len(ytd_prices) > 0 else None

    # 1Y return
    one_year_ago = today - pd.Timedelta(days=365)
    year_prices = prices[prices.index >= one_year_ago]
    return_1y = (latest_price / year_prices.iloc[0] - 1) if len(year_prices) > 0 else None

    # 3M return
    three_months_ago = today - pd.Timedelta(days=90)
    three_month_prices = prices[prices.index >= three_months_ago]
    return_3m = (
        (latest_price / three_month_prices.iloc[0] - 1) if len(three_month_prices) > 0 else None
    )

    # Annualized volatility (252 trading days)
    volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else None

    # Sharpe ratio (assuming risk-free rate of 4%)
    risk_free_rate = 0.04
    if return_1y is not None and volatility is not None and volatility > 0:
        sharpe = (return_1y - risk_free_rate) / volatility
    else:
        sharpe = None

    # Maximum drawdown
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    mdd = drawdown.min() if len(drawdown) > 0 else None

    return {
        "ytd_return": float(ytd_return) if ytd_return is not None else None,
        "return_1y": float(return_1y) if return_1y is not None else None,
        "return_3m": float(return_3m) if return_3m is not None else None,
        "volatility": float(volatility) if volatility is not None else None,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "mdd": float(mdd) if mdd is not None else None,
    }


def _kr_summary_extras(ticker: str, security_type: str = "STOCK") -> Dict:
    """KR 종목 부가 정보와 동일 기준일 밸류에이션 검증 결과.

    가격과 펀더멘털을 독립적인 최신 행으로 섞지 않고 ``date,ticker``가 같은 행만
    사용한다. KRX 공시 비율은 EPS/BPS/DPS·주식수·시총·종가로 재계산해 허용오차를
    벗어나면 해당 비율을 fail-closed 처리한다.
    """
    is_etf = str(security_type).upper() == "ETF"
    extras: Dict = {
        "value": None,
        "mktcap": None,
        "per": None,
        "pbr": None,
        "div": None,
        "flows_recent": None,
        "valuation": {
            "status": "not_applicable" if is_etf else "unavailable",
            "as_of": None,
            "price_as_of": None,
            "fundamental_as_of": None,
            "source": "KRX",
            "calculation_version": "kr_valuation_v2",
            "per_status": "not_applicable" if is_etf else "unavailable",
            "pbr_status": "not_applicable" if is_etf else "unavailable",
            "dividend_yield_status": "not_applicable" if is_etf else "unavailable",
            "missing_reasons": (["ETF에는 기업 밸류에이션을 적용하지 않습니다."] if is_etf else []),
            "inputs": None,
            "checks": None,
        },
    }
    start = (date.today() - timedelta(days=31)).isoformat()
    px = pd.DataFrame()
    fund = pd.DataFrame()

    try:
        from qdata import api as qdata_api

        px = qdata_api.load_krx_prices(
            start=start,
            tickers=[ticker],
            columns=["close", "value", "mktcap", "shares"],
        )
        if not px.empty:
            row = px.sort_values("date").iloc[-1]
            extras["value"] = float(row["value"]) if pd.notna(row["value"]) else None
            extras["mktcap"] = float(row["mktcap"]) if pd.notna(row["mktcap"]) else None
    except Exception:
        logger.warning(f"KR price extras 조회 실패: {ticker}", exc_info=True)

    try:
        fund = qdata_api.load_krx_fundamental(
            start=start,
            tickers=[ticker],
            columns=["per", "pbr", "div", "eps", "bps", "dps"],
        )
    except Exception:
        logger.debug(f"KR fundamental 조회 실패 (미수집 가능): {ticker}")

    if not is_etf and not px.empty and not fund.empty:
        try:
            price_cols = ["date", "ticker", "close", "mktcap", "shares"]
            fund_cols = ["date", "ticker", "per", "pbr", "div", "eps", "bps", "dps"]
            same_day = px[price_cols].merge(
                fund[fund_cols],
                on=["date", "ticker"],
                how="inner",
                validate="one_to_one",
            )
            if same_day.empty:
                extras["valuation"]["missing_reasons"] = [
                    "가격과 펀더멘털의 공통 기준일이 없습니다."
                ]
            else:
                row = same_day.sort_values("date").iloc[-1]

                def _number(name: str) -> Optional[float]:
                    return float(row[name]) if pd.notna(row[name]) else None

                close = _number("close")
                mktcap = _number("mktcap")
                shares = _number("shares")
                eps = _number("eps")
                bps = _number("bps")
                dps = _number("dps")
                source_per = _number("per")
                source_pbr = _number("pbr")
                source_div = _number("div")
                computed_per = (
                    mktcap / (eps * shares)
                    if mktcap and shares and shares > 0 and eps and eps > 0
                    else None
                )
                computed_pbr = (
                    mktcap / (bps * shares)
                    if mktcap and shares and shares > 0 and bps and bps > 0
                    else None
                )
                computed_div = (
                    dps / close * 100.0 if close and close > 0 and dps is not None else None
                )

                def _ratio_status(
                    source: Optional[float], computed: Optional[float], unavailable: str
                ) -> tuple[Optional[float], str, Optional[float]]:
                    if computed is None:
                        return None, unavailable, None
                    if source is None or source <= 0:
                        return None, "source_unavailable", None
                    error = abs(source - computed)
                    if error > KRX_RATIO_TOLERANCE:
                        return None, "quality_error", error
                    return source, "ok", error

                per, per_status, per_error = _ratio_status(
                    source_per,
                    computed_per,
                    (
                        "loss_or_zero_earnings"
                        if eps is not None and eps <= 0
                        else "input_unavailable"
                    ),
                )
                pbr, pbr_status, pbr_error = _ratio_status(
                    source_pbr,
                    computed_pbr,
                    (
                        "non_positive_or_missing_book_value"
                        if bps is not None and bps <= 0
                        else "input_unavailable"
                    ),
                )
                if computed_div is None or source_div is None:
                    div, div_status, div_error = None, "input_unavailable", None
                else:
                    div_error = abs(source_div - computed_div)
                    div_status = "ok" if div_error <= KRX_RATIO_TOLERANCE else "quality_error"
                    div = source_div if div_status == "ok" else None

                valuation_date = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
                statuses = (per_status, pbr_status, div_status)
                reasons = [
                    text
                    for status, text in (
                        (
                            per_status,
                            "PER: 이익이 0 이하이거나 입력·품질 검증을 통과하지 못했습니다.",
                        ),
                        (
                            pbr_status,
                            "PBR: 자본이 0 이하이거나 입력·품질 검증을 통과하지 못했습니다.",
                        ),
                        (div_status, "Dividend Yield: 입력·품질 검증을 통과하지 못했습니다."),
                    )
                    if status != "ok"
                ]
                extras.update({"per": per, "pbr": pbr, "div": div})
                extras["valuation"] = {
                    "status": "ok" if "ok" in statuses else "unavailable",
                    "as_of": valuation_date,
                    "price_as_of": valuation_date,
                    "fundamental_as_of": valuation_date,
                    "source": "KRX",
                    "calculation_version": "kr_valuation_v2",
                    "per_status": per_status,
                    "pbr_status": pbr_status,
                    "dividend_yield_status": div_status,
                    "missing_reasons": reasons,
                    "inputs": {
                        "close": close,
                        "market_cap": mktcap,
                        "shares": shares,
                        "eps": eps,
                        "bps": bps,
                        "dps": dps,
                    },
                    "checks": {
                        "per_recomputed": computed_per,
                        "pbr_recomputed": computed_pbr,
                        "dividend_yield_recomputed": computed_div,
                        "per_abs_error": per_error,
                        "pbr_abs_error": pbr_error,
                        "dividend_yield_abs_error": div_error,
                        "tolerance": KRX_RATIO_TOLERANCE,
                    },
                }
        except Exception:
            logger.warning("KR valuation 동일일 검증 실패: %s", ticker, exc_info=True)
            extras["valuation"]["missing_reasons"] = ["밸류에이션 검증에 실패했습니다."]

    try:
        from datastore import storage

        sig = storage.read_parquet(
            "insight",
            "flows_signals.parquet",
            columns=["ticker", "investor", "net_20d"],
            filters=[("ticker", "==", ticker)],
        )
        if not sig.empty:
            net = sig.set_index("investor")["net_20d"]
            extras["flows_recent"] = {
                "frgn_net_20d": float(net["frgn"]) if "frgn" in net.index else None,
                "inst_net_20d": float(net["inst"]) if "inst" in net.index else None,
            }
    except Exception:
        logger.debug(f"flows_signals 조회 실패: {ticker}")

    return extras


_EMPTY_EXTRAS: Dict = {
    "value": None,
    "mktcap": None,
    "per": None,
    "pbr": None,
    "div": None,
    "flows_recent": None,
    "valuation": None,
}


_US_FUNDAMENTAL_TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ),
    "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}
_US_DURATION_FACTS = {"revenue", "net_income", "operating_cash_flow"}


def _latest_annual_fact(df: pd.DataFrame, key: str) -> Optional[dict]:
    """현재 시점에 공개된 최신 연간 SEC 사실과 직전 연도 증감을 고른다.

    SEC는 같은 기간을 정정 제출할 수 있으므로 ddate별 최신 filed를 남긴다. 태그
    변천(Revenues ↔ RevenueFromContract...)은 최신 회계기간을 우선하고 같은 날이면
    위의 우선순위를 쓴다.
    """
    tags = _US_FUNDAMENTAL_TAGS[key]
    part = df[df["tag"].isin(tags)].copy()
    if key in _US_DURATION_FACTS:
        part = part[part["qtrs"] == 4]
    else:
        part = part[part["qtrs"] == 0]
    part = part[(part["uom"] == "USD") & part["ddate"].notna() & part["filed"].notna()]
    if part.empty:
        return None
    priority = {tag: idx for idx, tag in enumerate(tags)}
    part["_priority"] = part["tag"].map(priority).fillna(len(tags))
    part = part.sort_values(["ddate", "filed", "_priority"])
    # 정정 제출은 최신 filed, 같은 기간의 태그 중에는 정의한 우선순위가 앞선 것.
    by_period = (
        part.sort_values(["ddate", "filed", "_priority"], ascending=[True, True, False])
        .groupby("ddate", as_index=False)
        .tail(1)
        .sort_values("ddate")
    )
    current = by_period.iloc[-1]
    previous = by_period.iloc[-2] if len(by_period) >= 2 else None
    value = float(current["value"])
    yoy = None
    if previous is not None and float(previous["value"]) != 0:
        yoy = (value / float(previous["value"]) - 1.0) * 100.0
    return {
        "key": key,
        "value": value,
        "yoy_pct": yoy if yoy is None or math.isfinite(yoy) else None,
        "period": pd.Timestamp(current["ddate"]).strftime("%Y-%m-%d"),
        "filed": pd.Timestamp(current["filed"]).strftime("%Y-%m-%d"),
        "unit": str(current["uom"]),
        "tag": str(current["tag"]),
    }


def _us_fundamentals(ticker: str) -> dict:
    """Massive 티커→CIK 다리와 SEC as-filed 사실로 현재 핵심 재무를 구성한다."""
    from qdata import api as qdata_api

    today = date.today().isoformat()
    refs = qdata_api.load_us_tickers(asof=today)
    hit = refs[(refs["ticker"] == ticker) & refs["cik"].notna()]
    if hit.empty:
        return {"available": False, "note": "Massive 티커 참조에서 CIK를 찾지 못했습니다."}
    # 동일 티커가 한 빈티지에 중복이면 active 우선. 티커는 영구키가 아니므로 asof를
    # 명시하지 않은 현재 매핑을 임의로 과거에 적용하지 않는다.
    if "active" in hit.columns:
        hit = hit.sort_values("active")
    cik = int(hit.iloc[-1]["cik"])
    facts = qdata_api.load_sec_fundamental(
        start=(date.today() - timedelta(days=365 * 5)).isoformat(),
        end=today,
        ciks=[cik],
        tags=sorted({tag for tags in _US_FUNDAMENTAL_TAGS.values() for tag in tags}),
    )
    if facts.empty:
        return {"available": False, "cik": cik, "note": "공개된 SEC 연간 재무 사실이 없습니다."}
    annual = facts[facts["form"].astype(str).str.startswith("10-K")]
    if "fp" in annual.columns:
        annual = annual[annual["fp"].fillna("FY") == "FY"]
    rows = [fact for key in _US_FUNDAMENTAL_TAGS if (fact := _latest_annual_fact(annual, key))]
    if not rows:
        return {"available": False, "cik": cik, "note": "비교 가능한 연간 USD 사실이 없습니다."}
    return {
        "available": True,
        "ticker": ticker,
        "cik": cik,
        "as_of": max(row["filed"] for row in rows),
        "facts": rows,
        "note": "SEC 제출 원문 기준이며, filed 날짜 이후에만 알 수 있었던 값입니다.",
    }


@router.get("/sparklines")
def get_sparklines(
    meta_ids: str = Query(..., description="Comma-separated meta_ids"),
):
    """
    Get 30-day sparkline data for multiple stocks.

    Args:
        meta_ids: Comma-separated list of meta_ids

    Returns:
        Dictionary mapping meta_id to list of normalized prices (0-100 scale)
    """
    try:
        meta_id_list = [int(x.strip()) for x in meta_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meta_ids format")

    if not meta_id_list:
        return {"sparklines": {}}

    # Get meta info to determine iso_code
    meta_df = datastore.meta_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)][["meta_id", "iso_code"]]

    if meta_info.empty:
        return {"sparklines": {}}

    # Fetch price data (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=45)  # Extra days to ensure 30 trading days

    sparklines = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = datastore.read_price_data(
            iso_code=iso_code,
            meta_ids=iso_meta_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if price_df.empty:
            continue

        # Process each stock
        for meta_id in iso_meta_ids:
            stock_prices = price_df[price_df["meta_id"] == meta_id].sort_values("trade_date")

            if stock_prices.empty:
                sparklines[str(meta_id)] = []
                continue

            # Take last 30 data points
            stock_prices = stock_prices.tail(30)
            prices = stock_prices["adj_close"].values

            if len(prices) < 2:
                sparklines[str(meta_id)] = []
                continue

            # Normalize to 0-100 scale
            min_price = prices.min()
            max_price = prices.max()

            if max_price > min_price:
                normalized = ((prices - min_price) / (max_price - min_price) * 100).tolist()
            else:
                normalized = [50.0] * len(prices)

            sparklines[str(meta_id)] = [round(x, 1) for x in normalized]

    return {"sparklines": sparklines}


@router.get("/coverage")
def get_price_coverage(
    meta_ids: str = Query(..., description="Comma-separated meta_ids (max 50)"),
):
    """선택 자산의 실제 가격 가용 구간과 공통 교집합을 반환한다."""
    try:
        requested = list(
            dict.fromkeys(int(value.strip()) for value in meta_ids.split(",") if value.strip())
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid meta_ids format") from exc
    if not requested or len(requested) > 50:
        raise HTTPException(status_code=400, detail="meta_ids must contain 1-50 assets")

    mapping = datastore.meta_df()
    mapping = mapping[mapping["meta_id"].isin(requested)][["meta_id", "ticker", "iso_code"]]
    frames = []
    for iso in ("KR", "US"):
        ids = [int(value) for value in mapping[mapping["iso_code"] == iso]["meta_id"]]
        if ids:
            frame = datastore.read_price_data(iso, meta_ids=ids)
            if not frame.empty:
                frames.append(frame[["meta_id", "trade_date"]])
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    rows = []
    starts, ends = [], []
    for item in mapping.itertuples(index=False):
        series = prices[prices["meta_id"] == item.meta_id] if not prices.empty else prices
        if series.empty:
            start = end = None
            count = 0
        else:
            dates = pd.to_datetime(series["trade_date"])
            start, end, count = dates.min(), dates.max(), int(dates.nunique())
            starts.append(start)
            ends.append(end)
        rows.append(
            {
                "meta_id": int(item.meta_id),
                "ticker": item.ticker,
                "iso_code": item.iso_code,
                "start": start.strftime("%Y-%m-%d") if start is not None else None,
                "end": end.strftime("%Y-%m-%d") if end is not None else None,
                "rows": count,
            }
        )
    found = {row["meta_id"] for row in rows}
    for missing in sorted(set(requested) - found):
        rows.append(
            {
                "meta_id": missing,
                "ticker": None,
                "iso_code": None,
                "start": None,
                "end": None,
                "rows": 0,
            }
        )
    complete = len(starts) == len(requested)
    effective_start = max(starts) if complete else None
    effective_end = min(ends) if complete else None
    return {
        "assets": rows,
        "effective_start": (
            effective_start.strftime("%Y-%m-%d") if effective_start is not None else None
        ),
        "effective_end": effective_end.strftime("%Y-%m-%d") if effective_end is not None else None,
        "complete": complete and effective_start <= effective_end,
        "price_field": "adj_close",
        "note": "모든 선택 자산에 가격이 있는 공통 가능 구간. 실제 백테스트는 휴장일 교집합과 워밍업으로 더 짧아질 수 있습니다.",
    }


@router.get("/compare")
def get_compare_data(
    meta_ids: str = Query(..., description="Comma-separated meta_ids (max 5)"),
    period: str = Query("1y", description="Period: 1m, 3m, 6m, 1y, all"),
):
    """
    Get comparison data for multiple stocks.

    Args:
        meta_ids: Comma-separated list of meta_ids (max 5)
        period: Time period for comparison

    Returns:
        Normalized price series and metrics for each stock
    """
    try:
        meta_id_list = [int(x.strip()) for x in meta_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meta_ids format")

    if len(meta_id_list) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 stocks allowed for comparison")

    if not meta_id_list:
        return {"stocks": [], "normalized_prices": []}

    # Determine date range
    end_date = date.today()
    period_days = {
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "all": 365 * 5,
    }
    start_date = end_date - timedelta(days=period_days.get(period, 365))

    # Get meta info
    meta_df = datastore.meta_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)]

    if meta_info.empty:
        return {"stocks": [], "normalized_prices": []}

    # Collect price data
    all_prices = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = datastore.read_price_data(
            iso_code=iso_code,
            meta_ids=iso_meta_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if price_df.empty:
            continue

        for meta_id in iso_meta_ids:
            stock_prices = price_df[price_df["meta_id"] == meta_id].sort_values("trade_date")
            if not stock_prices.empty:
                all_prices[meta_id] = stock_prices

    # Build response
    stocks = []
    for meta_id in meta_id_list:
        meta_row = meta_info[meta_info["meta_id"] == meta_id]
        if meta_row.empty:
            continue

        stock_data = {
            "meta_id": int(meta_id),
            "ticker": meta_row.iloc[0]["ticker"],
            "name": meta_row.iloc[0]["name"],
            "sector": meta_row.iloc[0]["sector"],
            "iso_code": meta_row.iloc[0]["iso_code"],
        }

        if meta_id in all_prices:
            prices = all_prices[meta_id].set_index("trade_date")["adj_close"]
            metrics = _calculate_metrics(prices)
            stock_data["metrics"] = metrics
        else:
            stock_data["metrics"] = {
                "ytd_return": None,
                "return_1y": None,
                "return_3m": None,
                "volatility": None,
                "sharpe": None,
                "mdd": None,
            }

        stocks.append(stock_data)

    # Build normalized price series (base = 100)
    if all_prices:
        # Find common dates
        all_dates = set()
        for prices_df in all_prices.values():
            all_dates.update(prices_df["trade_date"].tolist())
        all_dates = sorted(all_dates)

        normalized_prices = []
        for trade_date in all_dates:
            point = {
                "date": (
                    trade_date.isoformat() if hasattr(trade_date, "isoformat") else str(trade_date)
                )
            }

            for meta_id, prices_df in all_prices.items():
                ticker = meta_info[meta_info["meta_id"] == meta_id].iloc[0]["ticker"]
                date_prices = prices_df[prices_df["trade_date"] == trade_date]

                if not date_prices.empty:
                    # Normalize to base 100
                    first_price = prices_df["adj_close"].iloc[0]
                    current_price = date_prices["adj_close"].iloc[0]
                    normalized = (current_price / first_price) * 100 if first_price > 0 else 100
                    point[ticker] = round(normalized, 2)

            normalized_prices.append(point)
    else:
        normalized_prices = []

    return {
        "stocks": stocks,
        "normalized_prices": normalized_prices,
    }


@router.get("/{meta_id}")
def get_price_history(
    meta_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get price history for a single stock.

    Args:
        meta_id: Stock meta_id
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of price records with trade_date, adj_close, gross_return
    """
    # Get meta info
    meta_df = datastore.meta_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    meta_item = meta_row.iloc[0]
    iso_code = str(meta_item["iso_code"])

    # Default to 1 year of data
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    price_df = datastore.read_price_data(
        iso_code=iso_code,
        meta_ids=[meta_id],
        start_date=start_date,
        end_date=end_date,
    )

    meta_payload = {
        "meta_id": int(meta_item["meta_id"]),
        "ticker": None if pd.isna(meta_item["ticker"]) else str(meta_item["ticker"]),
        "name": None if pd.isna(meta_item["name"]) else str(meta_item["name"]),
        "sector": None if pd.isna(meta_item["sector"]) else str(meta_item["sector"]),
        "iso_code": iso_code,
        "marketcap": (int(meta_item["marketcap"]) if pd.notna(meta_item["marketcap"]) else None),
    }

    if price_df.empty:
        return {
            "prices": [],
            "meta": meta_payload,
            "series_contract": _series_contract(meta_item),
        }

    price_df = price_df.sort_values("trade_date")

    # Convert to records
    prices = []
    for _, row in price_df.iterrows():
        prices.append(
            {
                "trade_date": (
                    row["trade_date"].isoformat()
                    if hasattr(row["trade_date"], "isoformat")
                    else str(row["trade_date"])
                ),
                "adj_close": float(row["adj_close"]) if pd.notna(row["adj_close"]) else None,
                "value": (
                    float(row.get("series_value"))
                    if pd.notna(row.get("series_value"))
                    else (float(row["adj_close"]) if pd.notna(row["adj_close"]) else None)
                ),
                "gross_return": (
                    float(row["gross_return"]) if pd.notna(row.get("gross_return")) else None
                ),
            }
        )

    return {
        "prices": prices,
        "meta": meta_payload,
        "series_contract": _series_contract(
            meta_item,
            (
                str(price_df["return_basis"].iloc[-1])
                if "return_basis" in price_df.columns
                and pd.notna(price_df["return_basis"].iloc[-1])
                else None
            ),
        ),
    }


def _build_summary(meta_id: int, meta_row: pd.Series) -> Dict:
    """Summary statistics payload for a single stock (shared by /price/{id}/summary and /stock/{id})."""
    iso_code = meta_row["iso_code"]

    # Get 1+ year of data for calculations
    end_date = date.today()
    start_date = end_date - timedelta(days=400)

    price_df = datastore.read_price_data(
        iso_code=iso_code,
        meta_ids=[meta_id],
        start_date=start_date,
        end_date=end_date,
    )

    extras = (
        _kr_summary_extras(meta_row["ticker"], str(meta_row.get("security_type", "STOCK")))
        if iso_code == "KR"
        else dict(_EMPTY_EXTRAS)
    )
    series_contract = _series_contract(
        meta_row,
        (
            str(price_df["return_basis"].iloc[-1])
            if not price_df.empty
            and "return_basis" in price_df.columns
            and pd.notna(price_df["return_basis"].iloc[-1])
            else None
        ),
    )

    if price_df.empty:
        return {
            "meta_id": meta_id,
            "ticker": meta_row["ticker"],
            "name": meta_row["name"],
            "metrics": {
                "ytd_return": None,
                "return_1y": None,
                "return_3m": None,
                "volatility": None,
                "sharpe": None,
                "mdd": None,
            },
            "latest_price": None,
            "latest_date": None,
            "series_contract": series_contract,
            **extras,
        }

    price_df = price_df.sort_values("trade_date")
    value_column = "series_value" if "series_value" in price_df.columns else "adj_close"
    latest_price_column = "close" if "close" in price_df.columns else value_column
    prices = price_df.set_index("trade_date")[value_column]

    metrics = _calculate_metrics(prices)

    return {
        "meta_id": meta_id,
        "ticker": meta_row["ticker"],
        "name": meta_row["name"],
        "metrics": metrics,
        "latest_price": float(price_df[latest_price_column].iloc[-1]),
        "latest_date": (
            price_df["trade_date"].iloc[-1].isoformat()
            if hasattr(price_df["trade_date"].iloc[-1], "isoformat")
            else str(price_df["trade_date"].iloc[-1])
        ),
        "series_contract": series_contract,
        **extras,
    }


@router.get("/{meta_id}/summary")
def get_price_summary(meta_id: int):
    """
    Get summary statistics for a single stock.

    Args:
        meta_id: Stock meta_id

    Returns:
        Summary statistics including YTD, 1Y return, volatility, Sharpe, MDD
    """
    meta_df = datastore.meta_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    return _build_summary(meta_id, meta_row.iloc[0])


# ---------- /stock — 종목 상세 페이지 복합 엔드포인트 ----------

stock_router = APIRouter(prefix="/stock", tags=["Stock"])


@stock_router.get("/{meta_id}/fundamentals")
def get_stock_fundamentals(meta_id: int):
    """US 보통주의 현재 시점 SEC 연간 핵심 재무. KR/ETF는 기존 요약을 사용한다."""
    meta_df = datastore.meta_df()
    hit = meta_df[meta_df["meta_id"] == meta_id]
    if hit.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")
    row = hit.iloc[0]
    if row["iso_code"] != "US":
        return {"available": False, "note": "KR 종목은 KRX PER·PBR·배당수익률을 제공합니다."}
    if str(row.get("security_type", "")).upper() == "ETF":
        return {"available": False, "note": "ETF에는 기업 재무제표를 적용하지 않습니다."}
    try:
        return _us_fundamentals(str(row["ticker"]))
    except (FileNotFoundError, KeyError):
        logger.debug("US fundamental 데이터 부재: %s", row["ticker"], exc_info=True)
        return {
            "available": False,
            "note": "SEC 또는 Massive 참조 데이터가 아직 발행되지 않았습니다.",
        }
    except Exception:
        logger.warning("US fundamental 조회 실패: %s", row["ticker"], exc_info=True)
        return {"available": False, "note": "재무 데이터를 불러오지 못했습니다."}


@stock_router.get("/{meta_id}")
def get_stock_detail(meta_id: int):
    """
    Composite payload for the stock detail page: meta + summary + watchlist flag.

    Price history and flows stay on their existing endpoints.
    """
    meta_df = datastore.meta_df()
    meta_rows = meta_df[meta_df["meta_id"] == meta_id]

    if meta_rows.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    row = meta_rows.iloc[0]

    in_watchlist = False
    try:
        from datastore import watchlist as watchlist_store

        wl = watchlist_store.list_items()
        in_watchlist = bool((wl["meta_id"] == meta_id).any()) if not wl.empty else False
    except Exception:
        logger.debug(f"watchlist 조회 실패: {meta_id}")

    holding = None
    try:
        from datastore import holdings as holdings_store

        hd = holdings_store.list_items()
        hrow = hd[hd["meta_id"] == meta_id] if not hd.empty else hd
        if not hrow.empty:
            h = hrow.iloc[0]
            opened_at = h["opened_at"]
            holding = {
                "shares": float(h["shares"]) if pd.notna(h["shares"]) else None,
                "avg_cost": float(h["avg_cost"]) if pd.notna(h["avg_cost"]) else None,
                "currency": h["currency"] if pd.notna(h["currency"]) else None,
                "opened_at": opened_at.isoformat() if pd.notna(opened_at) else None,
                "note": h["note"] if pd.notna(h["note"]) else None,
            }
    except Exception:
        logger.debug(f"holdings 조회 실패: {meta_id}")

    def _na(v):
        try:
            return None if pd.isna(v) else v
        except (TypeError, ValueError):
            return v

    return {
        "meta": {
            "meta_id": int(row["meta_id"]),
            "ticker": row["ticker"],
            "name": row["name"],
            "sector": _na(row["sector"]),
            "iso_code": row["iso_code"],
            "security_type": _na(row["security_type"]),
            "security_subtype": _na(row.get("security_subtype")),
            "marketcap": int(row["marketcap"]) if pd.notna(row["marketcap"]) else None,
            "marketcap_source": _na(row.get("marketcap_source")),
            "marketcap_as_of": _na(row.get("marketcap_as_of")),
            "shares_outstanding": (
                int(row["shares_outstanding"]) if pd.notna(row.get("shares_outstanding")) else None
            ),
            "weighted_shares_outstanding": (
                int(row["weighted_shares_outstanding"])
                if pd.notna(row.get("weighted_shares_outstanding"))
                else None
            ),
            "fund_size": int(row["fund_size"]) if pd.notna(row.get("fund_size")) else None,
            "fund_size_source": _na(row.get("fund_size_source")),
            "fund_size_as_of": _na(row.get("fund_size_as_of")),
            "reference_as_of": _na(row.get("reference_as_of")),
        },
        "summary": _build_summary(meta_id, row),
        "in_watchlist": in_watchlist,
        "holding": holding,
    }

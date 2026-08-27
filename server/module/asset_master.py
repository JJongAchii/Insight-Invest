"""qdata 종목 참조축 → Insight-Invest 단일 자산 마스터.

가격·이름·업종·상장 상태의 원천은 qdata뿐이다. ``asset_id_registry``는 앱의
숫자 참조키를 안정적으로 유지하는 append-only 레지스트리이며 종목 데이터 원천이
아니다. 신규 상장은 정렬된 키 순서로 새 ID를 받아 기존 ID를 바꾸지 않는다.
"""

from __future__ import annotations

import pandas as pd

MASTER_COLUMNS = [
    "meta_id",
    "ticker",
    "name",
    "isin",
    "security_type",
    "security_subtype",
    "asset_class",
    "sector",
    "iso_code",
    "marketcap",
    "marketcap_source",
    "marketcap_as_of",
    "shares_outstanding",
    "weighted_shares_outstanding",
    "fund_size",
    "fund_size_source",
    "fund_size_as_of",
    "reference_as_of",
    "fee",
    "remark",
    "min_date",
    "max_date",
    "as_of",
]
REGISTRY_COLUMNS = ["meta_id", "iso_code", "ticker", "created_at"]

US_STOCK_TYPES = {"CS", "ADRC"}
US_FUND_TYPES = {"ETF", "FUND", "ETN", "ETV", "ETS"}


def _text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _integer(series: pd.Series) -> pd.Series:
    """JSON/API 경계에서 실수로 직렬화되지 않도록 금액을 nullable 정수로 고정한다."""
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def _empty_integer(index) -> pd.Series:
    return pd.Series(pd.NA, index=index, dtype="Int64")


def kr_stock_rows(master: pd.DataFrame) -> pd.DataFrame:
    """qdata 최신 KRX 마스터를 앱 공통 스키마로 정규화한다."""
    if master.empty:
        raise ValueError("KRX 종목 마스터가 비어 있다")
    latest = pd.Timestamp(master["asof"].max())
    rows = master[master["asof"] == latest].copy()
    if "mktcap" not in rows:
        rows["mktcap"] = pd.NA
    return pd.DataFrame(
        {
            "ticker": _text(rows["ticker"]),
            "name": _text(rows["name"]),
            "isin": None,
            "security_type": "STOCK",
            "security_subtype": "STOCK",
            "asset_class": "EQUITY",
            "sector": _text(rows["sector"]),
            "iso_code": "KR",
            "marketcap": _integer(rows["mktcap"]),
            "marketcap_source": "krx_stock_master",
            "marketcap_as_of": latest.strftime("%Y-%m-%d"),
            "shares_outstanding": (
                _integer(rows["shares"]) if "shares" in rows else _empty_integer(rows.index)
            ),
            "weighted_shares_outstanding": _empty_integer(rows.index),
            "fund_size": _empty_integer(rows.index),
            "fund_size_source": None,
            "fund_size_as_of": None,
            "reference_as_of": latest.strftime("%Y-%m-%d"),
            "fee": None,
            "remark": None,
            "min_date": None,
            "max_date": latest.strftime("%Y-%m-%d"),
            "as_of": latest.strftime("%Y-%m-%d"),
        }
    )


def kr_etf_rows(meta: pd.DataFrame) -> pd.DataFrame:
    """qdata 최신 KRX ETF 일별 메타를 앱 공통 스키마로 정규화한다."""
    if meta.empty:
        raise ValueError("KRX ETF 메타가 비어 있다")
    latest = pd.Timestamp(meta["date"].max())
    rows = meta[meta["date"] == latest].drop_duplicates("ticker", keep="last").copy()
    return pd.DataFrame(
        {
            "ticker": _text(rows["ticker"]),
            "name": _text(rows["name"]),
            "isin": None,
            "security_type": "ETF",
            "security_subtype": "ETF",
            "asset_class": "FUND",
            "sector": _text(rows["index_name"]),
            "iso_code": "KR",
            "marketcap": _integer(rows["mktcap"]),
            "marketcap_source": "krx_etf_meta",
            "marketcap_as_of": latest.strftime("%Y-%m-%d"),
            "shares_outstanding": (
                _integer(rows["shares"]) if "shares" in rows else _empty_integer(rows.index)
            ),
            "weighted_shares_outstanding": _empty_integer(rows.index),
            "fund_size": _integer(rows["aum"]) if "aum" in rows else _empty_integer(rows.index),
            "fund_size_source": "krx_reported_aum",
            "fund_size_as_of": latest.strftime("%Y-%m-%d"),
            "reference_as_of": latest.strftime("%Y-%m-%d"),
            "fee": None,
            "remark": None,
            "min_date": None,
            "max_date": latest.strftime("%Y-%m-%d"),
            "as_of": latest.strftime("%Y-%m-%d"),
        }
    )


def us_rows(
    tickers: pd.DataFrame, details: pd.DataFrame, prices: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Massive 최신 활성 보통주·ADR·상장 펀드를 앱 공통 스키마로 정규화한다."""
    if tickers.empty:
        raise ValueError("US 티커 마스터가 비어 있다")
    allowed = US_STOCK_TYPES | US_FUND_TYPES
    rows = tickers[tickers["active"].eq(True) & tickers["type"].isin(allowed)].copy()  # noqa: E712
    rows = rows.drop_duplicates("ticker", keep="last")
    if not details.empty:
        keep = [
            c
            for c in (
                "ticker",
                "asof",
                "market_cap",
                "shares_outstanding",
                "weighted_shares_outstanding",
                "sic_description",
                "list_date",
            )
            if c in details.columns
        ]
        detail = (
            details[keep]
            .drop_duplicates("ticker", keep="last")
            .rename(columns={"asof": "detail_asof"})
        )
        rows = rows.merge(detail, on="ticker", how="left", validate="one_to_one")
    for column in (
        "market_cap",
        "shares_outstanding",
        "weighted_shares_outstanding",
        "sic_description",
        "list_date",
        "detail_asof",
    ):
        if column not in rows:
            rows[column] = pd.NA
    if prices is not None and not prices.empty:
        latest_price = prices[["ticker", "date", "close"]].copy()
        latest_price["date"] = pd.to_datetime(latest_price["date"], errors="coerce")
        latest_price["close"] = pd.to_numeric(latest_price["close"], errors="coerce")
        latest_price = (
            latest_price.dropna(subset=["ticker", "date"])
            .sort_values(["ticker", "date"])
            .drop_duplicates("ticker", keep="last")
            .rename(columns={"date": "price_asof", "close": "latest_close"})
        )
        rows = rows.merge(latest_price, on="ticker", how="left", validate="one_to_one")
    else:
        rows["price_asof"] = pd.NaT
        rows["latest_close"] = pd.NA

    as_of = pd.Timestamp(rows["asof"].max())
    security_type = rows["type"].map(lambda value: "STOCK" if value in US_STOCK_TYPES else "ETF")
    listing = pd.to_datetime(rows["list_date"], errors="coerce")
    detail_asof = pd.to_datetime(rows["detail_asof"], errors="coerce")
    price_asof = pd.to_datetime(rows["price_asof"], errors="coerce")
    vendor_cap = pd.to_numeric(rows["market_cap"], errors="coerce")
    shares = pd.to_numeric(rows["shares_outstanding"], errors="coerce")
    weighted = pd.to_numeric(rows["weighted_shares_outstanding"], errors="coerce")
    close = pd.to_numeric(rows["latest_close"], errors="coerce")

    computed_cap = close * weighted
    use_computed_cap = security_type.eq("STOCK") & computed_cap.gt(0)
    marketcap = vendor_cap.copy()
    marketcap.loc[use_computed_cap] = computed_cap.loc[use_computed_cap]
    marketcap_source = pd.Series(pd.NA, index=rows.index, dtype="string")
    marketcap_source.loc[vendor_cap.gt(0)] = "massive_ticker_details"
    marketcap_source.loc[use_computed_cap] = "massive_close_x_weighted_shares"
    marketcap_asof = detail_asof.dt.strftime("%Y-%m-%d").where(vendor_cap.gt(0)).copy()
    marketcap_asof.loc[use_computed_cap] = price_asof.loc[use_computed_cap].dt.strftime("%Y-%m-%d")

    fund_size = close * shares
    use_fund_size = security_type.eq("ETF") & fund_size.gt(0)
    fund_size = fund_size.where(use_fund_size)
    fund_size_source = pd.Series(pd.NA, index=rows.index, dtype="string")
    fund_size_source.loc[use_fund_size] = "estimate_close_x_share_class_shares"
    fund_size_asof = price_asof.dt.strftime("%Y-%m-%d").where(use_fund_size)
    return pd.DataFrame(
        {
            "ticker": _text(rows["ticker"]),
            "name": _text(rows["name"]),
            "isin": None,
            "security_type": security_type,
            "security_subtype": _text(rows["type"]),
            "asset_class": security_type.map({"STOCK": "EQUITY", "ETF": "FUND"}),
            "sector": _text(rows["sic_description"]),
            "iso_code": "US",
            "marketcap": _integer(marketcap),
            "marketcap_source": marketcap_source,
            "marketcap_as_of": marketcap_asof,
            "shares_outstanding": _integer(shares),
            "weighted_shares_outstanding": _integer(weighted),
            "fund_size": _integer(fund_size),
            "fund_size_source": fund_size_source,
            "fund_size_as_of": fund_size_asof,
            "reference_as_of": detail_asof.dt.strftime("%Y-%m-%d"),
            "fee": None,
            "remark": None,
            "min_date": listing.dt.strftime("%Y-%m-%d"),
            "max_date": None,
            "as_of": as_of.strftime("%Y-%m-%d"),
        }
    )


def compose_source_master(*parts: pd.DataFrame) -> pd.DataFrame:
    source = pd.concat(parts, ignore_index=True)
    source["ticker"] = _text(source["ticker"])
    source["iso_code"] = _text(source["iso_code"]).str.upper()
    source["name"] = _text(source["name"])
    for column in (
        "marketcap",
        "shares_outstanding",
        "weighted_shares_outstanding",
        "fund_size",
    ):
        source[column] = _integer(source[column])
    bad_name = source["name"].isna() | source["name"].eq("")
    if bad_name.any():
        sample = source.loc[bad_name, ["iso_code", "ticker"]].head(20)
        raise ValueError(f"자산 마스터 종목명 누락: {sample.to_dict(orient='records')}")
    dup = source.duplicated(["iso_code", "ticker"], keep=False)
    if dup.any():
        sample = source.loc[dup, ["iso_code", "ticker", "security_type"]].head(20)
        raise ValueError(f"자산 마스터 키 중복: {sample.to_dict(orient='records')}")
    return source.sort_values(["iso_code", "ticker"]).reset_index(drop=True)


def reconcile_registry(
    source: pd.DataFrame, registry: pd.DataFrame, now: str
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """append-only ID 레지스트리와 최신 소스를 결합한다.

    반환은 (서빙 마스터, 갱신 레지스트리, 신규 ID 수). 기존 키의 ID 변화,
    중복 ID, 소스의 무매칭은 모두 예외다.
    """
    reg = registry.reindex(columns=REGISTRY_COLUMNS).copy()
    if not reg.empty:
        reg["ticker"] = _text(reg["ticker"])
        reg["iso_code"] = _text(reg["iso_code"]).str.upper()
        reg["meta_id"] = pd.to_numeric(reg["meta_id"], errors="raise").astype("int64")
        if reg.duplicated(["iso_code", "ticker"]).any():
            raise ValueError("asset_id_registry에 중복 (iso_code,ticker)가 있다")
        if reg["meta_id"].duplicated().any():
            raise ValueError("asset_id_registry에 중복 meta_id가 있다")

    keys = source[["iso_code", "ticker"]].drop_duplicates()
    existing = set(zip(reg["iso_code"], reg["ticker"], strict=True))
    new_keys = [
        key for key in zip(keys["iso_code"], keys["ticker"], strict=True) if key not in existing
    ]
    next_id = int(reg["meta_id"].max()) + 1 if not reg.empty else 1
    additions = pd.DataFrame(
        [
            {"meta_id": next_id + i, "iso_code": iso, "ticker": ticker, "created_at": now}
            for i, (iso, ticker) in enumerate(sorted(new_keys))
        ],
        columns=REGISTRY_COLUMNS,
    )
    updated = reg.copy() if additions.empty else pd.concat([reg, additions], ignore_index=True)
    if updated.empty:
        raise ValueError("asset_id_registry가 비어 있다")
    updated["meta_id"] = pd.to_numeric(updated["meta_id"], errors="raise").astype("int64")
    updated["iso_code"] = _text(updated["iso_code"]).str.upper()
    updated["ticker"] = _text(updated["ticker"])
    updated = updated.sort_values("meta_id").reset_index(drop=True)

    master = source.merge(
        updated[["meta_id", "iso_code", "ticker"]],
        on=["iso_code", "ticker"],
        how="left",
        validate="one_to_one",
    )
    if master["meta_id"].isna().any() or len(master) != len(source):
        raise ValueError("자산 마스터와 ID 레지스트리 조인에서 행이 누락됐다")
    master["meta_id"] = master["meta_id"].astype("int64")
    master = master[MASTER_COLUMNS].sort_values("meta_id").reset_index(drop=True)
    return master, updated, len(additions)


def assert_ticker_coverage(master: pd.DataFrame, label: str, tickers) -> dict:
    requested = {str(value) for value in tickers if pd.notna(value) and str(value)}
    available = set(master["ticker"].astype(str))
    missing = sorted(requested - available)
    if missing:
        raise ValueError(
            f"{label} 티커가 자산 마스터에 없음: {len(missing)}/{len(requested)} {missing[:30]}"
        )
    return {"dataset": label, "requested": len(requested), "missing": 0}
